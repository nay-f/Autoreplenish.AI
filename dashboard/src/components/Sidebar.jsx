import React from 'react';
import { Layers, FileText, Cpu, MessageSquareHeart, Sparkles, Store } from 'lucide-react';

export function Sidebar({ activeTab, setActiveTab }) {
  const navItems = [
    {
      id: 'inventory-health',
      label: 'Inventory Health',
      subtitle: 'Multi-Store Stock & Risk',
      icon: Layers,
      color: 'text-blue-400'
    },
    {
      id: 'reasoning-trace',
      label: 'Agent Reasoning Trace',
      subtitle: 'Bedrock Prompts & Audits',
      icon: Sparkles,
      color: 'text-purple-400'
    },
    {
      id: 'store-settings',
      label: 'Store & Region Settings',
      subtitle: 'Master Data & Field Test',
      icon: Store,
      color: 'text-cyan-400'
    },
    {
      id: 'sap-monitor',
      label: 'SAP Integration Monitor',
      subtitle: 'OData PR & Connection',
      icon: Cpu,
      color: 'text-emerald-400'
    },
    {
      id: 'feedback-analytics',
      label: 'Feedback Analytics',
      subtitle: 'Approval & Override Loop',
      icon: MessageSquareHeart,
      color: 'text-amber-400'
    }
  ];

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-900/60 flex flex-col p-4 gap-2 min-h-[calc(100vh-4rem)]">
      <div className="text-[11px] uppercase font-bold text-slate-400 tracking-wider px-3 mb-1">
        Control Modules
      </div>
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = activeTab === item.id;
        return (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            className={`w-full flex items-start gap-3 p-3 rounded-xl transition-all text-left ${
              isActive
                ? 'bg-blue-600/15 border border-blue-500/30 text-white shadow-sm'
                : 'hover:bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-transparent'
            }`}
          >
            <div className={`p-2 rounded-lg ${isActive ? 'bg-blue-500/20 ' + item.color : 'bg-slate-800 text-slate-400'}`}>
              <Icon className="w-4 h-4" />
            </div>
            <div>
              <div className={`font-semibold text-sm leading-tight ${isActive ? 'text-white' : 'text-slate-300'}`}>
                {item.label}
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">{item.subtitle}</div>
            </div>
          </button>
        );
      })}

      <div className="mt-auto p-3.5 rounded-xl bg-gradient-to-br from-slate-800/80 to-slate-800/30 border border-slate-700/60 text-xs">
        <div className="font-semibold text-slate-200 flex items-center gap-1.5 mb-1">
          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
          Autonomous Scheduler
        </div>
        <p className="text-slate-400 text-[11px] leading-relaxed">
          Evaluasi otomatis berkala aktif setiap <strong>3 jam</strong> (05:00, 08:00, 11:00, dst). Analisa instan dapat dipicu via Telegram atau Store Settings.
        </p>
      </div>
    </aside>
  );
}
