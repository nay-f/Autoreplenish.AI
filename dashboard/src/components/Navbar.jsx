import React from 'react';
import { Bot, ShieldCheck, Activity, User } from 'lucide-react';

export function Navbar({ activeRole, setActiveRole }) {
  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md flex items-center justify-between px-6 sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <Bot className="w-6 h-6 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-bold text-lg text-white tracking-tight">AutoReplenish.ai</h1>
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
              Agentic AI v1.0
            </span>
          </div>
          <p className="text-xs text-slate-400">Minimarket Multi-Store Supply Chain Orchestrator</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden md:flex items-center gap-2 text-xs text-slate-400 bg-slate-800/60 px-3 py-1.5 rounded-lg border border-slate-700/50">
          <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
          <span>Bedrock Claude 3.5: <strong className="text-emerald-300">Online</strong></span>
          <span className="text-slate-600">|</span>
          <span>SAP S/4HANA: <strong className="text-blue-300">Connected</strong></span>
        </div>

        {/* Role Selector */}
        <div className="flex items-center gap-2 bg-slate-800 p-1 rounded-lg border border-slate-700 text-xs">
          <User className="w-3.5 h-3.5 text-slate-400 ml-1.5" />
          <select
            value={activeRole}
            onChange={(e) => setActiveRole(e.target.value)}
            className="bg-transparent text-slate-200 focus:outline-none pr-2 py-0.5 cursor-pointer font-medium"
          >
            <option value="Regional Manager" className="bg-slate-800">Regional Manager (Siti)</option>
            <option value="Store Manager" className="bg-slate-800">Store Manager (Budi)</option>
            <option value="IT Admin" className="bg-slate-800">IT Administrator (Andi)</option>
            <option value="Supply Chain Analyst" className="bg-slate-800">Supply Chain Analyst</option>
          </select>
        </div>
      </div>
    </header>
  );
}
