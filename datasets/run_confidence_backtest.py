from dotenv import load_dotenv
load_dotenv('.env.development', override=True)

import json
import os
import sys
import time
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if os.getenv('ENVIRONMENT') != 'development':
    raise RuntimeError('Safety stop: ENVIRONMENT must be development')
if any(x in os.getenv('DYNAMODB_TABLE', '').lower() for x in ('prod', 'coretable')):
    raise RuntimeError('Safety stop: production-like DynamoDB table')
if os.getenv('SAP_WRITE_ENABLED', '').lower() == 'true':
    raise RuntimeError('Safety stop: SAP write is enabled')

from backend.src.models.schema import StoreProfile, SKUItem
from backend.src.services.bedrock_service import BedrockReasoningService
from backend.src.services.moq_packaging_service import MOQPackagingService

ROOT = Path('datasets/raw')
REPORT = Path('datasets/reports')
REPORT.mkdir(parents=True, exist_ok=True)
MAX_SCHEMA_QTY = 100000
NORMALIZATION_TARGET_QTY = 80000


def read_zip(name, member, **kwargs):
    with ZipFile(ROOT / name) as archive:
        with archive.open(member) as stream:
            return pd.read_csv(stream, low_memory=False, **kwargs)


def make_cases(dataset, frame, keys, date_col, value_col, horizons, min_history=28, min_future=14):
    frame = frame.copy()
    frame[date_col] = pd.to_datetime(frame[date_col])
    frame[value_col] = pd.to_numeric(frame[value_col], errors='coerce').fillna(0).clip(lower=0)
    grouped = frame.groupby(keys)
    spans = grouped[date_col].agg(['min', 'max', 'count']).reset_index()
    spans = spans[(spans['count'] >= min_history + min_future)]
    totals = grouped[value_col].sum().reset_index(name='total').merge(spans, on=keys)
    totals = totals.sort_values('total')
    if totals.empty:
        return []
    indices = np.linspace(0, len(totals) - 1, min(5, len(totals))).astype(int)
    entities = totals.iloc[indices][keys].to_dict('records')
    cases = []
    for entity in entities:
        mask = np.ones(len(frame), dtype=bool)
        for key, value in entity.items():
            mask &= frame[key].values == value
        series = frame.loc[mask, [date_col, value_col]].groupby(date_col)[value_col].sum().sort_index()
        if len(series) < min_history + max(horizons):
            continue
        cutoffs = np.linspace(min_history, len(series) - max(horizons) - 1, 3).astype(int)
        for index in cutoffs:
            cutoff = series.index[index]
            for horizon in horizons:
                history = series.loc[:cutoff].tail(min_history)
                future = series[(series.index > cutoff) & (series.index <= cutoff + pd.Timedelta(days=horizon))]
                if len(future) >= horizon * 0.7:
                    cases.append({
                        'dataset': dataset,
                        'entity': entity,
                        'cutoff': cutoff,
                        'horizon': horizon,
                        'history': history,
                        'actual': float(future.sum()),
                    })
    return cases


def prepare_cases():
    cases = []
    rossmann = read_zip('rossmann-store-sales.zip', 'train.csv')
    cases += make_cases('rossmann', rossmann[rossmann.Open == 1], ['Store'], 'Date', 'Sales', [7, 14])

    walmart = read_zip('walmart-sales-forecast.zip', 'train.csv')
    cases += make_cases('walmart', walmart, ['Store', 'Dept'], 'Date', 'Weekly_Sales', [1, 2], 8, 2)

    m5 = read_zip('m5-forecasting-accuracy.zip', 'sales_train_validation.csv', nrows=5000)
    days = [column for column in m5 if column.startswith('d_')]
    calendar = read_zip('m5-forecasting-accuracy.zip', 'calendar.csv', usecols=['d', 'date'])
    dates = pd.to_datetime(calendar.date).iloc[:len(days)].to_numpy()
    m5_totals = m5[days].sum(axis=1)
    selected = m5.assign(total=m5_totals).sort_values('total').iloc[np.linspace(0, len(m5) - 1, 5).astype(int)]
    for _, row in selected.iterrows():
        series = pd.Series(row[days].to_numpy(float), index=dates)
        for index in np.linspace(28, len(series) - 15, 3).astype(int):
            cutoff = series.index[index]
            for horizon in (7, 14):
                history = series.loc[:cutoff].tail(28)
                future = series[(series.index > cutoff) & (series.index <= cutoff + pd.Timedelta(days=horizon))]
                if len(future) >= horizon * 0.7:
                    cases.append({'dataset': 'm5', 'entity': {'id': row['id']}, 'cutoff': cutoff, 'horizon': horizon, 'history': history, 'actual': float(future.sum())})

    favorita = ROOT / 'favorita-grocery-sales-forecasting'
    chunks = []
    for chunk in pd.read_csv(favorita / 'train.csv', usecols=['date', 'store_nbr', 'item_nbr', 'unit_sales'], parse_dates=['date'], chunksize=500000, low_memory=False):
        chunk['unit_sales'] = pd.to_numeric(chunk['unit_sales'], errors='coerce').fillna(0).clip(lower=0)
        chunks.append(chunk)
        if sum(len(item) for item in chunks) >= 8_000_000:
            break
    favorita_frame = pd.concat(chunks).groupby(['date', 'store_nbr', 'item_nbr'], as_index=False).unit_sales.sum()
    cases += make_cases('favorita', favorita_frame, ['store_nbr', 'item_nbr'], 'date', 'unit_sales', [7, 14])

    grouped = {}
    for case in cases:
        grouped.setdefault(case['dataset'], []).append(case)
    for dataset in grouped:
        grouped[dataset] = grouped[dataset][:30]
    return [case for dataset in ('rossmann', 'walmart', 'm5', 'favorita') for case in grouped.get(dataset, [])], {key: len(value) for key, value in grouped.items()}


def run():
    cases, counts = prepare_cases()
    print(f'Prepared cases: {counts}; total={len(cases)}')
    service = BedrockReasoningService()
    results = []
    for number, case in enumerate(cases, 1):
        history = case['history']
        horizon = int(case['horizon'])
        raw_average = float(history.mean())
        raw_estimated_qty = raw_average * horizon
        normalization_factor = min(1.0, NORMALIZATION_TARGET_QTY / raw_estimated_qty) if raw_estimated_qty > NORMALIZATION_TARGET_QTY else 1.0
        history = history * normalization_factor
        actual_demand = case['actual'] * normalization_factor
        average = float(history.mean())
        identity = '-'.join(str(value) for value in case['entity'].values())
        identifier = ('DEV-' + case['dataset'].upper() + '-' + identity)[:64]
        store = StoreProfile(store_id=identifier, store_name=case['dataset'] + ' development store', zone='DEV-DATASET', latitude=-6.9666, longitude=110.4166)
        sku = SKUItem(sku_id=identifier, sku_name=case['dataset'] + ' test item ' + identity, category='Dataset Backtest', physical_stock=max(0, int(round(average * max(1, horizon - 2) * 0.25))), threshold=max(1, int(round(average * horizon))), average_daily_burn_rate=average, lead_time_days=horizon, moq=1, packaging_multiple=1, shelf_life_days=3, is_perishable=False)
        estimated_deficit = max(sku.threshold - sku.physical_stock, 0)
        estimated_horizon_demand = average * horizon
        estimated_final_qty = estimated_deficit + estimated_horizon_demand
        if estimated_final_qty > MAX_SCHEMA_QTY:
            results.append({'status': 'SKIPPED_GUARDRAIL', 'dataset': case['dataset'], 'entity': case['entity'], 'cutoff_date': str(case['cutoff'].date()), 'horizon_days': horizon, 'normalization_factor': normalization_factor, 'estimated_final_qty': estimated_final_qty, 'reason': 'estimated final quantity exceeds schema limit'})
            print(f'[{number}/{len(cases)}] SKIP {case["dataset"]} h={horizon}: estimated final quantity={estimated_final_qty:.0f} exceeds {MAX_SCHEMA_QTY}')
            continue
        context = {'date': str(case['cutoff'].date()), 'day_name': case['cutoff'].day_name(), 'is_weekend': case['cutoff'].day_of_week >= 5, 'is_payday': case['cutoff'].day >= 25, 'forecast_horizon_days': horizon, 'historical_demand_last_28_days': [float(value) for value in history]}
        try:
            started = time.perf_counter()
            recommendation = service.generate_recommendation(store=store, sku=sku, weather={'condition': 'Cerah', 'temperature_c': 30, 'rain_probability': 0.1, 'is_cached': False, 'source': 'synthetic'}, calendar_context=context, active_promos=[])
            final = MOQPackagingService.adjust_quantity(sku, recommendation.recommended_qty, recommendation.risk_level)['final_qty']
            actual = actual_demand
            relative_error = abs(final - actual) / max(actual, 1)
            results.append({'status': 'SUCCESS', 'dataset': case['dataset'], 'entity': case['entity'], 'cutoff_date': str(case['cutoff'].date()), 'horizon_days': horizon, 'normalization_factor': normalization_factor, 'raw_actual_demand': case['actual'], 'actual_demand': actual, 'recommended_qty': recommendation.recommended_qty, 'final_qty': final, 'confidence_score': recommendation.confidence_score, 'confidence_percentage': recommendation.confidence_score * 100, 'confidence_tier': recommendation.confidence_tier, 'is_fallback': recommendation.is_fallback, 'relative_error': relative_error, 'within_10_percent': relative_error <= 0.10, 'within_20_percent': relative_error <= 0.20, 'latency_ms': round((time.perf_counter() - started) * 1000)})
            print(f'[{number}/{len(cases)}] {case["dataset"]} h={horizon} confidence={recommendation.confidence_score * 100:.1f}% error={relative_error * 100:.1f}%')
        except Exception as error:
            results.append({'status': 'ERROR', 'dataset': case['dataset'], 'entity': case['entity'], 'cutoff_date': str(case['cutoff'].date()), 'horizon_days': horizon, 'error': type(error).__name__ + ': ' + str(error)})
            print(f'[{number}/{len(cases)}] ERROR {case["dataset"]}: {error}')

    successful = [row for row in results if row.get('status') == 'SUCCESS']

    def summarize(rows):
        actual = sum(row['actual_demand'] for row in rows)
        error = sum(abs(row['final_qty'] - row['actual_demand']) for row in rows)
        return {'rows': len(rows), 'avg_confidence_percentage': sum(row['confidence_score'] for row in rows) / len(rows) * 100 if rows else None, 'wape_percentage': error / actual * 100 if actual else None, 'accuracy_percentage': 100 - error / actual * 100 if actual else None, 'within_10_rate': sum(row['within_10_percent'] for row in rows) / len(rows) * 100 if rows else None, 'within_20_rate': sum(row['within_20_percent'] for row in rows) / len(rows) * 100 if rows else None, 'fallback_rate': sum(row['is_fallback'] for row in rows) / len(rows) * 100 if rows else None}

    summary = {'environment': os.getenv('ENVIRONMENT'), 'table': os.getenv('DYNAMODB_TABLE'), 'total_cases': len(results), 'successful_cases': len(successful), 'error_cases': sum(row.get('status') == 'ERROR' for row in results), 'skipped_guardrail_cases': sum(row.get('status') == 'SKIPPED_GUARDRAIL' for row in results), 'by_dataset': {dataset: summarize([row for row in successful if row['dataset'] == dataset]) for dataset in ('rossmann', 'walmart', 'm5', 'favorita')}, 'by_confidence_bucket': {}}
    for low, high in ((0, .6), (.6, .7), (.7, .8), (.8, .9), (.9, 1.01)):
        bucket = [row for row in successful if low <= row['confidence_score'] < high]
        summary['by_confidence_bucket'][f'{int(low * 100)}-{min(100, int(high * 100) - 1)}'] = summarize(bucket)
    (REPORT / 'horizon_confidence_results.json').write_text(json.dumps(results, indent=2, default=str), encoding='utf-8')
    (REPORT / 'horizon_confidence_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    run()
