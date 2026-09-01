import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { RiskBadge } from '../components/RiskBadge';
import { JsonModal } from '../components/JsonModal';
import { Sparkles, Code, CheckCircle, XCircle, Edit3, ShieldAlert, Cpu } from 'lucide-react';

export function ReasoningTrace() {
  const [logs, setLogs] = useState([]);
  const [selectedLogForJson, setSelectedLogForJson] = useState(null);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadAuditLogs() {
      setLoading(true);
      const data = await api.getAuditLogs();
      setLogs(data);
      setLoading(false);
    }
    loadAuditLogs();
  }, []);

  const filteredLogs = logs.filter((log) => {
    if (statusFilter === 'ALL') return true;
    if (statusFilter === 'APPROVED') return log.human_action === 'APPROVED';
    if (statusFilter === 'REJECTED') return log.human_action === 'REJECTED';
    if (statusFilter === 'EDITED') return log.human_action === 'EDITED';
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-400" />
            Agent Reasoning Trace & Audit Log
          </h2>
          <p className="text-xs text-slate-400">
            Jejak transparansi penuh dari input multi-variabel, model Bedrock, narasi penalaran, hingga aksi Kepala Toko & SAP PR
          </p>
        </div>

        {/* Filter */}
        <div className="flex items-center gap-2 bg-slate-900/80 p-1.5 rounded-xl border border-slate-800">
          {['ALL', 'APPROVED', 'EDITED', 'REJECTED'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                statusFilter === st
                  ? 'bg-purple-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {st === 'ALL' ? 'Semua Status' : st}
            </button>
          ))}
        </div>
      </div>

      {/* Trace Log Cards */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-8 text-center text-slate-400 bg-slate-900 border border-slate-800 rounded-xl">
            Memuat audit log dan trace penalaran AI...
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="p-8 text-center text-slate-400 bg-slate-900 border border-slate-800 rounded-xl">
            Tidak ada audit log yang sesuai dengan filter.
          </div>
        ) : (
          filteredLogs.map((log) => {
            return (
              <div
                key={log.request_id}
                className="bg-slate-900 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 shadow-lg space-y-4 transition"
              >
                {/* Top Row: SKU, Store, Confidence, Status */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 font-bold text-xs">
                      AI
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-sm">{log.sku_name}</span>
                        <span className="text-[11px] text-slate-400">({log.sku_id})</span>
                      </div>
                      <div className="text-xs text-slate-400 flex items-center gap-2 mt-0.5">
                        <span>{log.store_name} ({log.area_type})</span>
                        <span className="text-slate-600">•</span>
                        <span>Ref: <code className="text-blue-400">{log.request_id}</code></span>
                        <span className="text-slate-600">•</span>
                        <span>Prompt: <code className="text-purple-300">{log.prompt_version}</code></span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-xs font-semibold text-slate-200">
                        Confidence: <span className="text-emerald-400 font-bold">{Math.round(log.confidence_score * 100)}%</span>
                      </div>
                      <div className="text-[10px] text-slate-400 uppercase tracking-wider">
                        Risk: <span className={log.risk_level === 'high' ? 'text-rose-400' : 'text-amber-400'}>{log.risk_level}</span>
                      </div>
                    </div>
                    <RiskBadge status={log.human_action || 'PENDING'} />
                  </div>
                </div>

                {/* Indonesian Reasoning Narrative */}
                <div className="p-4 rounded-xl bg-purple-950/20 border border-purple-800/30">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-purple-300 flex items-center gap-1.5 mb-1.5">
                    <Sparkles className="w-3.5 h-3.5" />
                    Penalaran Kontekstual Bedrock (Claude 3.5 Sonnet)
                  </div>
                  <p className="text-xs text-purple-100 leading-relaxed italic">
                    "{log.reasoning_narrative}"
                  </p>
                </div>

                {/* Key Factors & Warnings */}
                <div className="flex flex-wrap gap-2 items-center">
                  <span className="text-xs text-slate-400 font-semibold mr-1">Faktor Utama:</span>
                  {log.key_factors?.map((factor) => (
                    <span
                      key={factor}
                      className="px-2.5 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-[11px] font-medium text-slate-300"
                    >
                      🏷️ {factor}
                    </span>
                  ))}
                  {log.warnings?.map((warn) => (
                    <span
                      key={warn}
                      className="px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-[11px] font-medium text-amber-300 flex items-center gap-1"
                    >
                      <ShieldAlert className="w-3 h-3" />
                      {warn}
                    </span>
                  ))}
                </div>

                {/* Quantity Breakdown & SAP Result */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-800/40 p-3 rounded-xl border border-slate-800 text-xs">
                  <div>
                    <div className="text-slate-400 text-[11px]">Rekomendasi AI</div>
                    <div className="font-bold text-white text-sm mt-0.5">
                      {log.ai_recommended_qty} Pcs
                    </div>
                    <div className="text-[10px] text-slate-400">Normal: {log.normal_qty} Pcs</div>
                  </div>

                  <div>
                    <div className="text-slate-400 text-[11px]">Penyesuaian Kemasan / MOQ</div>
                    <div className="font-bold text-blue-400 text-sm mt-0.5">
                      {log.final_recommended_qty} Pcs
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {log.packaging_multiple_applied ? `Kelipatan ${log.packaging_multiple} Pcs` : 'Sesuai pesanan'}
                    </div>
                  </div>

                  <div>
                    <div className="text-slate-400 text-[11px]">Keputusan Kepala Toko</div>
                    <div className="font-bold text-emerald-400 text-sm mt-0.5 flex items-center gap-1">
                      {log.human_action === 'APPROVED' ? (
                        <>
                          <CheckCircle className="w-3.5 h-3.5" /> Disetujui ({log.human_final_qty || log.final_recommended_qty} Pcs)
                        </>
                      ) : log.human_action === 'REJECTED' ? (
                        <>
                          <XCircle className="w-3.5 h-3.5 text-rose-400" /> Ditolak
                        </>
                      ) : log.human_action === 'EDITED' ? (
                        <>
                          <Edit3 className="w-3.5 h-3.5 text-blue-400" /> Diedit ({log.human_final_qty} Pcs)
                        </>
                      ) : (
                        'Menunggu Approval'
                      )}
                    </div>
                    {log.rejection_reason && (
                      <div className="text-[10px] text-rose-300 italic truncate max-w-[160px]" title={log.rejection_reason}>
                        Alasan: {log.rejection_reason}
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="text-slate-400 text-[11px]">Status SAP S/4HANA</div>
                    <div className="font-bold text-slate-200 text-sm mt-0.5 flex items-center gap-1">
                      <Cpu className="w-3.5 h-3.5 text-blue-400" />
                      {log.sap_pr_id ? (
                        <span className="text-emerald-400">{log.sap_pr_id}</span>
                      ) : (
                        <span className="text-slate-400">Tidak ada PR</span>
                      )}
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {log.completed_at ? log.completed_at.slice(11, 19) + ' WIB' : '-'}
                    </div>
                  </div>
                </div>

                {/* Bottom Bar: Action Trigger to view JSON */}
                <div className="flex justify-end pt-1">
                  <button
                    onClick={() => setSelectedLogForJson(log)}
                    className="flex items-center gap-1 text-[11px] font-semibold text-purple-400 hover:text-purple-300 hover:underline"
                  >
                    <Code className="w-3.5 h-3.5" />
                    Lihat Raw JSON Payload (DynamoDB Trace)
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* JSON Modal */}
      <JsonModal
        title={`Audit Record: ${selectedLogForJson?.request_id}`}
        data={selectedLogForJson}
        isOpen={!!selectedLogForJson}
        onClose={() => setSelectedLogForJson(null)}
      />
    </div>
  );
}
