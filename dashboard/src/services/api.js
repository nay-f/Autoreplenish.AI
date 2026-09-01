/**
 * Dashboard API Connector.
 * Integrates with API Gateway or provides rich demo fallback matching the PRD.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const api = {
  async getStores() {
    try {
      const res = await fetch(`${API_BASE_URL}/stores`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn('Using local fallback for stores');
    }
    return [
      { store_id: 'STR-001', store_name: 'Cabang Sudirman', area_type: 'Perkantoran', zone: 'JAKARTA_PUSAT', active: true },
      { store_id: 'STR-002', store_name: 'Cabang Kemang', area_type: 'Perumahan', zone: 'JAKARTA_SELATAN', active: true },
      { store_id: 'STR-003', store_name: 'Cabang Dago', area_type: 'Kampus', zone: 'BANDUNG_KOTA', active: true }
    ];
  },

  async getStoreInventoryHealth(storeId = 'STR-001') {
    try {
      const res = await fetch(`${API_BASE_URL}/stores/${storeId}/inventory-health`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn('Using local fallback for inventory health');
    }
    return {
      store_id: storeId,
      store_name: storeId === 'STR-001' ? 'Cabang Sudirman' : storeId === 'STR-002' ? 'Cabang Kemang' : 'Cabang Dago',
      area_type: storeId === 'STR-001' ? 'Perkantoran' : storeId === 'STR-002' ? 'Perumahan' : 'Kampus',
      zone: storeId === 'STR-001' ? 'JAKARTA_PUSAT' : storeId === 'STR-002' ? 'JAKARTA_SELATAN' : 'BANDUNG_KOTA',
      summary: {
        total_skus: 4,
        stockout_risk: 2,
        overstock_risk: 1,
        healthy: 1
      },
      inventory: [
        {
          sku_id: 'SKU-10023',
          sku_name: 'Roti Manis Cokelat 100g',
          category: 'Perishable',
          weather_sensitive: true,
          physical_stock: 12,
          threshold: 20,
          average_daily_burn_rate: 25.0,
          lead_time_days: 2,
          status: 'STOCKOUT_RISK',
          days_of_supply: 0.5
        },
        {
          sku_id: 'SKU-10045',
          sku_name: 'Minuman Isotonik 500ml',
          category: 'Non-Perishable',
          weather_sensitive: true,
          physical_stock: 18,
          threshold: 30,
          average_daily_burn_rate: 20.0,
          lead_time_days: 2,
          status: 'STOCKOUT_RISK',
          days_of_supply: 0.9
        },
        {
          sku_id: 'SKU-10088',
          sku_name: 'Sabun Cuci Piring 750ml',
          category: 'Non-Perishable',
          weather_sensitive: false,
          physical_stock: 35,
          threshold: 15,
          average_daily_burn_rate: 5.0,
          lead_time_days: 3,
          status: 'OVERSTOCK_RISK',
          days_of_supply: 7.0
        },
        {
          sku_id: 'SKU-10099',
          sku_name: 'Susu Pasteurisasi Cokelat 200ml',
          category: 'Perishable',
          weather_sensitive: true,
          physical_stock: 6,
          threshold: 15,
          average_daily_burn_rate: 12.0,
          lead_time_days: 1,
          status: 'STOCKOUT_RISK',
          days_of_supply: 0.5
        }
      ]
    };
  },

  async getAuditLogs(params = {}) {
    try {
      const qs = new URLSearchParams(params).toString();
      const res = await fetch(`${API_BASE_URL}/audit-logs?${qs}`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn('Using local fallback for audit logs');
    }
    return [
      {
        request_id: 'REQ-20260901-77020B',
        run_id: 'RUN-20260901-0500',
        store_id: 'STR-001',
        store_name: 'Cabang Sudirman',
        area_type: 'Perkantoran',
        sku_id: 'SKU-10023',
        sku_name: 'Roti Manis Cokelat 100g',
        category: 'Perishable',
        physical_stock: 12,
        threshold: 20,
        average_daily_burn_rate: 25.0,
        lead_time_days: 2,
        moq: 12,
        packaging_multiple: 12,
        weather_condition: 'Hujan deras',
        calendar_day: 'Weekend',
        is_public_holiday: false,
        is_payday: false,
        promo_active: false,
        prompt_version: 'v1.0',
        model: 'anthropic.claude-3-5-sonnet',
        ai_recommended_qty: 15,
        normal_qty: 50,
        adjusted_qty_before_moq: 15,
        final_recommended_qty: 15,
        moq_applied: false,
        packaging_multiple_applied: true,
        confidence_score: 0.88,
        risk_level: 'medium',
        reasoning_narrative: 'Stok di bawah threshold (12/20 pcs), namun area perkantoran sepi saat weekend dan cuaca hujan deras menurunkan kunjungan. Kuota disesuaikan ke 15 pcs untuk mencegah overstock dan kedaluwarsa.',
        key_factors: ['below_threshold', 'weekend_office_area_quiet', 'heavy_rain', 'perishable_sku', 'lead_time_2_days'],
        warnings: ['SKU perishable dengan lead time 2 hari', 'Permintaan weekend berisiko lebih rendah dari estimasi normal'],
        human_action: 'APPROVED',
        human_final_qty: 15,
        sap_pr_status: 'SUCCESS',
        sap_pr_id: 'PR-4500012345',
        created_at: '2026-09-01T05:12:00+07:00',
        approved_at: '2026-09-01T05:14:10+07:00',
        completed_at: '2026-09-01T05:14:35+07:00'
      },
      {
        request_id: 'REQ-20260901-CEBF6D',
        run_id: 'RUN-20260901-0500',
        store_id: 'STR-001',
        store_name: 'Cabang Sudirman',
        area_type: 'Perkantoran',
        sku_id: 'SKU-10045',
        sku_name: 'Minuman Isotonik 500ml',
        category: 'Non-Perishable',
        physical_stock: 18,
        threshold: 30,
        average_daily_burn_rate: 20.0,
        lead_time_days: 2,
        moq: 24,
        packaging_multiple: 24,
        weather_condition: 'Hujan deras',
        calendar_day: 'Weekend',
        is_public_holiday: false,
        is_payday: false,
        promo_active: true,
        promo_type: 'Buy 1 Get 1',
        prompt_version: 'v1.0',
        model: 'anthropic.claude-3-5-sonnet',
        ai_recommended_qty: 48,
        normal_qty: 60,
        adjusted_qty_before_moq: 48,
        final_recommended_qty: 48,
        moq_applied: false,
        packaging_multiple_applied: true,
        confidence_score: 0.92,
        risk_level: 'low',
        reasoning_narrative: 'Stok mendekati threshold dengan promo aktif Beli 1 Gratis 1 Segar. Kuota dinaikkan untuk mengantisipasi lonjakan permintaan promo.',
        key_factors: ['below_threshold', 'promo_active_Buy 1 Get 1'],
        warnings: [],
        human_action: 'APPROVED',
        human_final_qty: 48,
        sap_pr_status: 'SUCCESS',
        sap_pr_id: 'PR-4500012346',
        created_at: '2026-09-01T05:12:00+07:00',
        approved_at: '2026-09-01T05:15:02+07:00',
        completed_at: '2026-09-01T05:15:20+07:00'
      },
      {
        request_id: 'REQ-20260901-E6DB45',
        run_id: 'RUN-20260901-0500',
        store_id: 'STR-001',
        store_name: 'Cabang Sudirman',
        area_type: 'Perkantoran',
        sku_id: 'SKU-10099',
        sku_name: 'Susu Pasteurisasi Cokelat 200ml',
        category: 'Perishable',
        physical_stock: 6,
        threshold: 15,
        average_daily_burn_rate: 12.0,
        lead_time_days: 1,
        moq: 10,
        packaging_multiple: 10,
        weather_condition: 'Hujan deras',
        calendar_day: 'Weekend',
        is_public_holiday: false,
        is_payday: false,
        promo_active: false,
        prompt_version: 'v1.0',
        model: 'anthropic.claude-3-5-sonnet',
        ai_recommended_qty: 10,
        normal_qty: 30,
        adjusted_qty_before_moq: 10,
        final_recommended_qty: 10,
        moq_applied: true,
        packaging_multiple_applied: true,
        confidence_score: 0.85,
        risk_level: 'medium',
        reasoning_narrative: 'Stok kritis (6 pcs), kuota dibatasi ke 10 pcs (1 Pack) mengingat daya simpan pendek dan akhir pekan perkantoran yang relatif tenang.',
        key_factors: ['below_threshold', 'perishable_sku', 'weekend_office_area_quiet'],
        warnings: ['SKU perishable dengan lead time 1 hari'],
        human_action: 'REJECTED',
        human_final_qty: null,
        rejection_reason: 'Stok di chiller display masih ada 8 pcs yang belum tercatat di sistem',
        sap_pr_status: 'PENDING',
        sap_pr_id: null,
        created_at: '2026-09-01T05:12:00+07:00',
        completed_at: '2026-09-01T05:20:11+07:00'
      }
    ];
  },

  async getSapMonitor() {
    try {
      const res = await fetch(`${API_BASE_URL}/sap-monitor`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn('Using local fallback for SAP monitor');
    }
    return {
      connection_status: 'ONLINE',
      sap_host: 'sap-s4hana.enterprise.corp:443',
      odata_endpoint: '/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV',
      average_latency_ms: 242,
      metrics: {
        total_pr_generated: 48,
        total_pr_failed: 0,
        success_rate_pct: 100.0,
        active_retry_queue_size: 0,
        dlq_message_count: 0
      },
      recent_transactions: [
        { request_id: 'REQ-20260901-77020B', store_id: 'STR-001', sku_id: 'SKU-10023', quantity: 15, sap_pr_id: 'PR-4500012345', status: 'SUCCESS', timestamp: '2026-09-01T05:14:35+07:00' },
        { request_id: 'REQ-20260901-CEBF6D', store_id: 'STR-001', sku_id: 'SKU-10045', quantity: 48, sap_pr_id: 'PR-4500012346', status: 'SUCCESS', timestamp: '2026-09-01T05:15:20+07:00' },
        { request_id: 'REQ-20260901-FB9433', store_id: 'STR-002', sku_id: 'SKU-10045', quantity: 48, sap_pr_id: 'PR-4500012347', status: 'SUCCESS', timestamp: '2026-09-01T05:18:40+07:00' }
      ]
    };
  },

  async getFeedbackAnalytics() {
    try {
      const res = await fetch(`${API_BASE_URL}/feedback-analytics`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn('Using local fallback for feedback analytics');
    }
    return {
      metrics: {
        total_recommendations: 54,
        approval_rate_pct: 77.8,
        rejection_rate_pct: 13.0,
        edit_rate_pct: 9.2,
        timeout_count: 0
      },
      top_rejection_reasons: [
        { reason: 'Stok di gudang belakang masih ada dan belum terinput di sistem', count: 4 },
        { reason: 'Event lokal dibatalkan sehingga traffic toko diprediksi sepi', count: 2 },
        { reason: 'Produk sedang dalam proses retur/penukaran batch dari vendor', count: 1 }
      ],
      recent_feedback_records: [
        { store_id: 'STR-001', sku_id: 'SKU-10099', action: 'REJECTED', reason: 'Stok di chiller display masih ada 8 pcs yang belum tercatat di sistem', original_recommended_qty: 10, created_at: '2026-09-01T05:20:11+07:00' },
        { store_id: 'STR-002', sku_id: 'SKU-10088', action: 'EDITED', reason: 'Store manager manually changed qty from 12 to 24 due to upcoming residential weekend sale', original_recommended_qty: 12, final_qty: 24, created_at: '2026-09-01T05:25:30+07:00' }
      ]
    };
  }
};
