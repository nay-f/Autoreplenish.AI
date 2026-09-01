import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { StatCard } from '../components/StatCard';
import { RiskBadge } from '../components/RiskBadge';
import { Store, AlertTriangle, PackageX, CheckCircle2, Search, Filter } from 'lucide-react';

export function InventoryHealth() {
  const [stores, setStores] = useState([]);
  const [selectedStoreId, setSelectedStoreId] = useState('STR-001');
  const [healthData, setHealthData] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function init() {
      const storeList = await api.getStores();
      setStores(storeList);
      if (storeList.length > 0) {
        setSelectedStoreId(storeList[0].store_id);
      }
    }
    init();
  }, []);

  useEffect(() => {
    async function loadHealth() {
      if (!selectedStoreId) return;
      setLoading(true);
      const data = await api.getStoreInventoryHealth(selectedStoreId);
      setHealthData(data);
      setLoading(false);
    }
    loadHealth();
  }, [selectedStoreId]);

  const filteredInventory = healthData?.inventory?.filter((item) => {
    const matchesSearch = item.sku_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          item.sku_id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = categoryFilter === 'ALL' || item.category === categoryFilter;
    return matchesSearch && matchesCategory;
  }) || [];

  return (
    <div className="space-y-6">
      {/* Header & Store Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Multi-Store Inventory Health</h2>
          <p className="text-xs text-slate-400">Monitoring level stok fisik, ambang batas safety, dan risiko stockout/overstock per cabang</p>
        </div>

        {/* Store Tabs */}
        <div className="flex items-center gap-2 bg-slate-900/80 p-1.5 rounded-xl border border-slate-800">
          <Store className="w-4 h-4 text-slate-400 ml-2" />
          {stores.map((s) => (
            <button
              key={s.store_id}
              onClick={() => setSelectedStoreId(s.store_id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                selectedStoreId === s.store_id
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {s.store_name} ({s.area_type})
            </button>
          ))}
        </div>
      </div>

      {/* Summary KPI Cards */}
      {healthData && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total SKU Dipantau"
            value={healthData.summary.total_skus}
            subtitle={`${healthData.store_name} — Zone ${healthData.zone}`}
            icon={Store}
            color="blue"
          />
          <StatCard
            title="Risiko Stockout"
            value={healthData.summary.stockout_risk}
            subtitle="Di bawah safety threshold"
            icon={AlertTriangle}
            color="rose"
          />
          <StatCard
            title="Risiko Overstock"
            value={healthData.summary.overstock_risk}
            subtitle="> 2.5x safety threshold"
            icon={PackageX}
            color="amber"
          />
          <StatCard
            title="Kondisi Sehat"
            value={healthData.summary.healthy}
            subtitle="Level stok optimal"
            icon={CheckCircle2}
            color="emerald"
            trend={`${Math.round((healthData.summary.healthy / healthData.summary.total_skus) * 100)}%`}
          />
        </div>
      )}

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
                    Tidak ada SKU yang cocok dengan filter.
                  </td>
                </tr>
              ) : (
                filteredInventory.map((item) => {
                  const stockPct = Math.min(100, Math.round((item.physical_stock / item.threshold) * 100));
                  return (
                    <tr key={item.sku_id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-white">{item.sku_name}</div>
                        <div className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
                          <span>{item.sku_id}</span>
                          <span className="text-slate-600">•</span>
                          <span className={`px-1.5 py-0.2 rounded text-[10px] ${item.category === 'Perishable' ? 'bg-rose-500/10 text-rose-300 border border-rose-500/20' : 'bg-slate-800 text-slate-300'}`}>
                            {item.category}
                          </span>
                          {item.weather_sensitive && (
                            <span className="text-blue-400 text-[10px]">🌦️ Weather-Sensitive</span>
                          )}
                        </div>
                      </td>

                      <td className="py-3.5 px-4">
                        <div className="flex flex-col items-center gap-1">
                          <span className="font-bold text-white">
                            {item.physical_stock} <span className="text-slate-400 font-normal">/ {item.threshold} Pcs</span>
                          </span>
                          <div className="w-28 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                item.physical_stock < item.threshold
                                  ? 'bg-rose-500'
                                  : item.physical_stock > item.threshold * 2
                                  ? 'bg-amber-500'
                                  : 'bg-emerald-500'
                              }`}
                              style={{ width: `${stockPct}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 px-4 text-center font-medium text-slate-200">
                        {item.average_daily_burn_rate} Pcs / hari
                      </td>

                      <td className="py-3.5 px-4 text-center text-slate-300">
                        {item.lead_time_days} Hari
                      </td>

                      <td className="py-3.5 px-4 text-center font-bold">
                        <span className={item.days_of_supply <= 1.0 ? 'text-rose-400' : 'text-slate-200'}>
                          {item.days_of_supply} Hari
                        </span>
                      </td>

                      <td className="py-3.5 px-4 text-center">
                        <RiskBadge status={item.status} />
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
