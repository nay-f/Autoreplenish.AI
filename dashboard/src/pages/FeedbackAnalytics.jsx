import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { StatCard } from '../components/StatCard';
import { MessageSquareHeart, ThumbsUp, ThumbsDown, Edit3, MessageCircle } from 'lucide-react';

export function FeedbackAnalytics() {
  const [feedbackData, setFeedbackData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadFeedback() {
      setLoading(true);
      try {
        const data = await api.getFeedbackAnalytics();
        setFeedbackData(data);
      } catch (err) {
        console.error('Failed to load feedback analytics:', err);
      } finally {
        setLoading(false);
      }
    }
    loadFeedback();
  }, []);

  const metrics = feedbackData?.metrics || {
    approval_rate_pct: 0.0,
    rejection_rate_pct: 0.0,
    edit_rate_pct: 0.0,
    total_recommendations: 0,
  };
  const topRejections = Array.isArray(feedbackData?.top_rejection_reasons) ? feedbackData.top_rejection_reasons : [];
  const recentRecords = Array.isArray(feedbackData?.recent_feedback_records) ? feedbackData.recent_feedback_records : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
          <MessageSquareHeart className="w-5 h-5 text-amber-400" />
          Feedback & Human-in-the-Loop Analytics
        </h2>
        <p className="text-xs text-slate-400">
          Analisis persetujuan Kepala Toko, pola penolakan (rejection loop), dan revisi kuantitas untuk penyempurnaan agen AI
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Tingkat Persetujuan (Approval Rate)"
          value={`${metrics.approval_rate_pct ?? 0}%`}
          subtitle="Target: > 70%"
          icon={ThumbsUp}
          color="emerald"
          trend="+7.8% di atas target"
        />
        <StatCard
          title="Tingkat Penolakan (Rejection Rate)"
          value={`${metrics.rejection_rate_pct ?? 0}%`}
          subtitle="Kepala Toko menolak draft"
          icon={ThumbsDown}
          color="rose"
        />
        <StatCard
          title="Tingkat Revisi Manual (Edit Rate)"
          value={`${metrics.edit_rate_pct ?? 0}%`}
          subtitle="Penyesuaian kuantitas"
          icon={Edit3}
          color="blue"
        />
        <StatCard
          title="Total Evaluasi Diproses"
          value={metrics.total_recommendations ?? 0}
          subtitle="Telegram recommendation cards"
          icon={MessageCircle}
          color="purple"
        />
      </div>

      {/* Rejection Reasons Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <h3 className="font-bold text-white text-sm">Alasan Penolakan Paling Sering</h3>
          <p className="text-xs text-slate-400">
            Penyebab utama Kepala Toko menolak kuota AI untuk dimasukkan ke konteks reasoning berikutnya:
          </p>

          <div className="space-y-3">
            {topRejections.length === 0 ? (
              <div className="p-4 text-center text-slate-400 text-xs bg-slate-800/40 rounded-lg border border-slate-800">
                Belum ada data penolakan yang tercatat.
              </div>
            ) : (
              topRejections.map((item, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/60">
                  <div className="flex items-center justify-between text-xs font-semibold text-white">
                    <span className="text-amber-300">#{idx + 1}</span>
                    <span className="bg-rose-500/10 text-rose-400 px-2 py-0.5 rounded text-[11px] font-bold">
                      {item.count} Kejadian
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                    "{item.reason}"
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Feedback Feed */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <h3 className="font-bold text-white text-sm">Log Umpan Balik Terbaru (Store Manager Field Notes)</h3>
          <div className="divide-y divide-slate-800/80">
            {recentRecords.length === 0 ? (
              <div className="py-8 text-center text-slate-400 text-xs">
                Belum ada catatan interaksi dari Kepala Toko.
              </div>
            ) : (
              recentRecords.map((fb, idx) => (
                <div key={idx} className="py-3 flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                        fb.action === 'REJECTED' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                      }`}>
                        {fb.action}
                      </span>
                      <span className="font-bold text-white text-xs">{fb.sku_id}</span>
                      <span className="text-[11px] text-slate-400">({fb.store_id})</span>
                    </div>
                    <p className="text-xs text-slate-300 mt-1.5 italic">
                      "{fb.reason || '-'}"
                    </p>
                  </div>
                  <div className="text-right text-[11px] text-slate-400 whitespace-nowrap">
                    <div>Rekomendasi Awal: <strong className="text-white">{fb.original_recommended_qty ?? '-'} Pcs</strong></div>
                    {fb.final_qty ? <div>Revisi Final: <strong className="text-emerald-400">{fb.final_qty} Pcs</strong></div> : null}
                    <div className="text-slate-400 text-[10px] mt-0.5">{fb.created_at ? fb.created_at.slice(11, 19) + ' WIB' : '-'}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
