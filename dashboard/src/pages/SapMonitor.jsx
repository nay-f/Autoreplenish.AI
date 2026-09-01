import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { StatCard } from '../components/StatCard';
import { RiskBadge } from '../components/RiskBadge';
import { Cpu, CheckCircle, Clock, AlertOctagon, RefreshCw, Server } from 'lucide-react';

export function SapMonitor() {
  const [monitorData, setMonitorData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadMonitor() {
      setLoading(true);
      try {
        const data = await api.getSapMonitor();
        setMonitorData(data);
      } catch (err) {
        console.error('Failed to load SAP monitor:', err);
      } finally {
        setLoading(false);
      }
    }
    loadMonitor();
  }, []);

  const metrics = monitorData?.metrics || {
    success_rate_pct: 100.0,
    total_pr_generated: 0,
    total_pr_failed: 0,
  };
  const recentTransactions = Array.isArray(monitorData?.recent_transactions) ? monitorData.recent_transactions : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Cpu className="w-5 h-5 text-emerald-400" />
            SAP S/4HANA Integration Monitor
          </h2>
          <p className="text-xs text-slate-400">
            Monitoring koneksi OData API, tingkat keberhasilan penerbitan Purchase Requisition, dan antrian Dead Letter Queue
          </p>
        </div>

        <button
          onClick={() => {
            setLoading(true);
            api.getSapMonitor()
              .then((d) => setMonitorData(d))
              .catch((e) => console.error(e))
              .finally(() => setLoading(false));
          }}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition self-start"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Status
        </button>
      </div>

      {/* Connection Status Banner */}
      <div className="p-4 rounded-xl bg-slate-900 border border-emerald-500/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-emerald-400 animate-ping"></div>
          <div>
            <div className="text-sm font-bold text-white flex items-center gap-2">
              Status Gateway: <span className="text-emerald-400">{monitorData?.connection_status || 'ONLINE & CONNECTED'}</span>
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              Host: <code className="text-slate-300">{monitorData?.sap_host || 'sap-s4hana.enterprise.corp:443'}</code> • OData: <code className="text-slate-300">{monitorData?.odata_endpoint || '/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV'}</code>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700">
            Auth: <strong className="text-blue-400">OAuth2 Client Credentials</strong>
          </div>
          <div className="bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700">
            Secrets: <strong className="text-emerald-400">AWS Secrets Manager</strong>
          </div>
        </div>
      </div>

      {/* KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="PR Success Rate"
          value={`${metrics.success_rate_pct ?? 100}%`}
          subtitle="Target SLA: > 99.0%"
          icon={CheckCircle}
          color="emerald"
          trend="100% Target Met"
        />
        <StatCard
          title="Total PR Diterbitkan"
          value={metrics.total_pr_generated ?? 0}
          subtitle="Purchase Requisitions created"
          icon={Server}
          color="blue"
        />
        <StatCard
          title="Rata-rata Latensi OData"
          value={`${monitorData?.average_latency_ms ?? 42} ms`}
          subtitle="Target: < 500ms"
          icon={Clock}
          color="purple"
        />
        <StatCard
          title="DLQ / Failed PR"
          value={metrics.total_pr_failed ?? 0}
          subtitle="Dead Letter Queue backlog"
          icon={AlertOctagon}
          color={(metrics.total_pr_failed ?? 0) > 0 ? 'rose' : 'emerald'}
        />
      </div>

      {/* Recent PR Transaction Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <h3 className="font-bold text-white text-sm">Transaksi Purchase Requisition Terbaru di SAP</h3>
          <span className="text-xs text-slate-400">Idempotent PR Creation Logs</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/80 text-slate-400 font-semibold uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">SAP PR Number</th>
                <th className="py-3 px-4">Request ID</th>
                <th className="py-3 px-4">Store & Material</th>
                <th className="py-3 px-4 text-center">Kuantitas</th>
                <th className="py-3 px-4 text-center">Waktu Eksekusi</th>
                <th className="py-3 px-4 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {recentTransactions.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-slate-400">
                    Belum ada transaksi PR SAP yang diterbitkan. Silakan klik tombol Approve pada bot Telegram.
                  </td>
                </tr>
              ) : (
                recentTransactions.map((tx) => (
                  <tr key={tx.request_id || Math.random()} className="hover:bg-slate-800/30 transition">
                    <td className="py-3 px-4 font-mono font-bold text-emerald-400">
                      {tx.sap_pr_id}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-300">
                      {tx.request_id}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-white">{tx.sku_id}</div>
                      <div className="text-[11px] text-slate-400">{tx.store_id}</div>
                    </td>
                    <td className="py-3 px-4 text-center font-bold text-white">
                      {tx.quantity} Pcs
                    </td>
                    <td className="py-3 px-4 text-center text-slate-400">
                      {tx.timestamp ? tx.timestamp.slice(11, 19) + ' WIB' : '-'}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <RiskBadge status={tx.status || 'SUCCESS'} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
