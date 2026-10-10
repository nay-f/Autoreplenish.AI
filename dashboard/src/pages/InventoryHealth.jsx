import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { StatCard } from '../components/StatCard';
import { RiskBadge } from '../components/RiskBadge';
import {
  Store,
  AlertTriangle,
  PackageX,
  CheckCircle2,
  Search,
  Filter,
  PlusCircle,
  Send,
  Database,
  ArrowRight,
} from 'lucide-react';

export function InventoryHealth() {
  const [stores, setStores] = useState([]);
  const [selectedStoreId, setSelectedStoreId] = useState('');
  const [healthData, setHealthData] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [loadingStores, setLoadingStores] = useState(true);

  useEffect(() => {
    async function init() {
      setLoadingStores(true);
      try {
        const storeList = await api.getStores();
        if (Array.isArray(storeList)) {
          setStores(storeList);
          if (storeList.length > 0) {
            setSelectedStoreId(storeList[0].store_id);
          }
        }
      } catch (err) {
        console.error('Failed to initialize stores:', err);
      } finally {
        setLoadingStores(false);
      }
    }
    init();
  }, []);

  useEffect(() => {
    async function loadHealth() {
      if (!selectedStoreId) {
        setHealthData(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const data = await api.getStoreInventoryHealth(selectedStoreId);
        setHealthData(data);
      } catch (err) {
        console.error('Failed to load inventory health:', err);
        setHealthData(null);
      } finally {
        setLoading(false);
      }
    }
    loadHealth();
  }, [selectedStoreId]);

  // Informative Empty State when no stores are registered
  if (!loadingStores && stores.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Multi-Store Inventory Health</h2>
          <p className="text-xs text-slate-400">
            Monitoring level stok fisik, ambang batas safety, dan risiko stockout/overstock per cabang
          </p>
        </div>

        <div className="p-8 sm:p-12 rounded-3xl bg-slate-900/80 border border-slate-800 text-center flex flex-col items-center justify-center max-w-2xl mx-auto shadow-2xl">
          <div className="w-16 h-16 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mb-4">
            <Store className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-bold text-white">Belum Ada Data Inventaris</h3>
          <p className="text-xs text-slate-400 mt-2 max-w-md leading-relaxed">
            Belum ada toko yang terdaftar di database sistem. Daftarkan toko pertama Anda atau sinkronkan data kasir
            terlebih dahulu untuk mulai memantau kesehatan inventaris.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg mt-6">
            <a
              href="#store-settings"
              onClick={() => {
                window.location.hash = 'store-settings';
              }}
              className="p-3.5 rounded-xl bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/40 text-left transition group"
            >
              <div className="flex items-center justify-between text-blue-300 font-bold text-xs">
                <span>Daftarkan via Web</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Buka menu Store Settings untuk konfigurasi toko baru & aturan SKU.
              </p>
            </a>

            <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60 text-left">
              <div className="flex items-center gap-1.5 text-emerald-300 font-bold text-xs">
                <Send className="w-3.5 h-3.5" />
                <span>Onboarding via Telegram</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Kirim perintah <code>/register_store</code> pada bot Telegram pengelola.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const inventoryItems = healthData?.inventory || healthData?.items || [];
  const summary = healthData?.summary || {
    total_skus: inventoryItems.length,
    stockout_risk: inventoryItems.filter(
      (i) => i.status === 'STOCKOUT_RISK' || i.health_status === 'stockout_risk'
    ).length,
    overstock_risk: inventoryItems.filter(
      (i) => i.status === 'OVERSTOCK_RISK' || i.health_status === 'overstock_risk'
    ).length,
    healthy: inventoryItems.filter(
      (i) => i.status === 'HEALTHY' || i.health_status === 'healthy'
    ).length,
  };

  const filteredInventory = inventoryItems.filter((item) => {
    const skuName = item?.sku_name || '';
    const skuId = item?.sku_id || '';
    const matchesSearch =
      skuName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      skuId.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = categoryFilter === 'ALL' || item?.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  const totalSkus = summary?.total_skus || 0;
  const healthyPct = totalSkus > 0 ? Math.round(((summary?.healthy || 0) / totalSkus) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Header & Store Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Multi-Store Inventory Health</h2>
          <p className="text-xs text-slate-400">
            Monitoring level stok fisik, ambang batas safety, dan risiko stockout/overstock per cabang
          </p>
        </div>

        {/* Store Tabs */}
        <div className="flex items-center gap-2 bg-slate-900/80 p-1.5 rounded-xl border border-slate-800 overflow-x-auto">
          <Store className="w-4 h-4 text-slate-400 ml-2 shrink-0" />
          {stores.map((s) => (
            <button
              key={s.store_id}
              onClick={() => setSelectedStoreId(s.store_id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition ${
                selectedStoreId === s.store_id
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {s.store_name} ({s.area_type || 'Umum'})
            </button>
          ))}
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total SKU Dipantau"
          value={summary?.total_skus ?? 0}
          subtitle={`${healthData?.store_name || selectedStoreId} — Zone ${
            healthData?.zone || 'JABODETABEK'
          }`}
          icon={Store}
          color="blue"
        />
        <StatCard
          title="Risiko Stockout"
          value={summary?.stockout_risk ?? 0}
          subtitle="Di bawah safety threshold"
          icon={AlertTriangle}
          color="rose"
        />
        <StatCard
          title="Risiko Overstock"
          value={summary?.overstock_risk ?? 0}
          subtitle="> 2.5x safety threshold"
          icon={PackageX}
          color="amber"
        />
        <StatCard
          title="Kondisi Sehat"
          value={summary?.healthy ?? 0}
          subtitle="Level stok optimal"
          icon={CheckCircle2}
          color="emerald"
          trend={totalSkus > 0 ? `${healthyPct}%` : undefined}
        />
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Cari SKU ID atau nama produk..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-800/80 border border-slate-700/60 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 transition"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Filter className="w-3.5 h-3.5" />
            <span>Kategori:</span>
          </div>
          <div className="flex gap-1.5">
            {['ALL', 'Perishable', 'Non-Perishable'].map((cat) => (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  categoryFilter === cat
                    ? 'bg-blue-600/20 text-blue-300 border border-blue-500/40'
                    : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-slate-700/50'
                }`}
              >
                {cat === 'ALL' ? 'Semua' : cat}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Inventory Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/80 text-slate-400 font-semibold uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3.5 px-4">SKU & Kategori</th>
                <th className="py-3.5 px-4 text-center">Stok Fisik / Threshold</th>
                <th className="py-3.5 px-4 text-center">Laju Konsumsi (Burn Rate)</th>
                <th className="py-3.5 px-4 text-center">Lead Time</th>
                <th className="py-3.5 px-4 text-center">Days of Supply</th>
                <th className="py-3.5 px-4 text-center">Status AI</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-slate-400">
                    Memuat data inventaris...
                  </td>
                </tr>
              ) : filteredInventory.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-slate-400">
                    Tidak ada SKU yang cocok dengan filter atau belum ada data inventaris untuk toko ini.
                  </td>
                </tr>
              ) : (
                filteredInventory.map((item) => {
                  const physicalStock = item?.physical_stock ?? 0;
                  const threshold = item?.threshold || 1;
                  const stockPct = Math.min(100, Math.round((physicalStock / threshold) * 100));
                  const burnRate = item?.average_daily_burn_rate ?? 0;
                  const leadTime = item?.lead_time_days ?? item?.default_lead_time_days ?? 1;
                  const daysOfSupply =
                    item?.days_of_supply ?? (burnRate > 0 ? (physicalStock / burnRate).toFixed(1) : '-');
                  const status =
                    item?.status || (physicalStock < threshold ? 'STOCKOUT_RISK' : 'HEALTHY');

                  return (
                    <tr key={item.sku_id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-white">{item.sku_name || item.sku_id}</div>
                        <div className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
                          <span>{item.sku_id}</span>
                          <span className="text-slate-600">•</span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] ${
                              item.category === 'Perishable'
                                ? 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
                                : 'bg-slate-800 text-slate-300'
                            }`}
                          >
                            {item.category || 'Non-Perishable'}
                          </span>
                          {item.weather_sensitive && (
                            <span className="text-blue-400 text-[10px]">🌦️ Weather-Sensitive</span>
                          )}
                        </div>
                      </td>

                      <td className="py-3.5 px-4">
                        <div className="flex flex-col items-center gap-1">
                          <span className="font-bold text-white">
                            {physicalStock} <span className="text-slate-400 font-normal">/ {threshold} Pcs</span>
                          </span>
                          <div className="w-28 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                physicalStock < threshold
                                  ? 'bg-rose-500'
                                  : physicalStock > threshold * 2
                                  ? 'bg-amber-500'
                                  : 'bg-emerald-500'
                              }`}
                              style={{ width: `${stockPct}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 px-4 text-center font-medium text-slate-200">
                        {burnRate} Pcs / hari
                      </td>

                      <td className="py-3.5 px-4 text-center text-slate-300">{leadTime} Hari</td>

                      <td className="py-3.5 px-4 text-center font-bold">
                        <span className={Number(daysOfSupply) <= 1.0 ? 'text-rose-400' : 'text-slate-200'}>
                          {daysOfSupply} Hari
                        </span>
                      </td>

                      <td className="py-3.5 px-4 text-center">
                        <RiskBadge status={status} />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
