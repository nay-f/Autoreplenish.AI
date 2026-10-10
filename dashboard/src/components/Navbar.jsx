import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  Bot,
  User,
  LogOut,
  RefreshCw,
  Cpu,
  CloudSun,
  Send,
  Building2,
  Database,
  ChevronDown,
} from 'lucide-react';

function getStatusBadgeStyle(status) {
  const s = String(status || '').toUpperCase();
  if (s === 'CONNECTED' || s === 'ACTIVE') {
    return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
  }
  if (s === 'NOT CONFIGURED' || s.includes('WAITING') || s.includes('INACTIVE')) {
    return 'bg-amber-500/10 text-amber-300 border-amber-500/20';
  }
  return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
}

export function Navbar({ activeRole, setActiveRole }) {
  const { user, logout, switchRole } = useAuth();
  const [health, setHealth] = useState(null);
  const [loadingHealth, setLoadingHealth] = useState(false);

  const fetchHealth = async () => {
    setLoadingHealth(true);
    try {
      const res = await api.getIntegrationHealth();
      setHealth(res);
    } catch (err) {
      console.warn('[Navbar] Health check unreachable:', err);
    } finally {
      setLoadingHealth(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const integrations = health?.integrations || {};
  const bedrockStatus = integrations.bedrock?.status || 'NOT CONFIGURED';
  const weatherStatus = integrations.weather?.status || 'NOT CONFIGURED';
  const telegramStatus = integrations.telegram?.status || 'NOT CONFIGURED';
  const sapStatus = integrations.sap?.status || 'NOT CONFIGURED';
  const posStatus = integrations.pos?.status || 'INACTIVE / WAITING DATA';

  const handleRoleChange = (e) => {
    const newRole = e.target.value;
    if (setActiveRole) setActiveRole(newRole);
    if (switchRole) switchRole(newRole);
  };

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md flex items-center justify-between px-4 sm:px-6 sticky top-0 z-30">
      {/* Brand Identity */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20 shrink-0">
          <Bot className="w-6 h-6 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-bold text-base sm:text-lg text-white tracking-tight">AutoReplenish.ai</h1>
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 hidden sm:inline-block">
              Truth-in-State
            </span>
          </div>
          <p className="text-[11px] text-slate-400 hidden sm:block">
            Minimarket Multi-Store Supply Chain Orchestrator
          </p>
        </div>
      </div>

      {/* Dynamic Live Integration Badges (Strict Truth-in-State) */}
      <div className="hidden xl:flex items-center gap-2 text-[11px] bg-slate-950/60 p-1.5 rounded-xl border border-slate-800">
        {/* Bedrock */}
        <div
          className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border font-medium ${getStatusBadgeStyle(
            bedrockStatus
          )}`}
          title={`AWS Bedrock Claude: ${bedrockStatus}`}
        >
          <Cpu className="w-3 h-3" />
          <span>Bedrock: {bedrockStatus}</span>
        </div>

        {/* Weather */}
        <div
          className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border font-medium ${getStatusBadgeStyle(
            weatherStatus
          )}`}
          title={`OpenWeatherMap: ${weatherStatus}`}
        >
          <CloudSun className="w-3 h-3" />
          <span>Weather: {weatherStatus}</span>
        </div>

        {/* Telegram */}
        <div
          className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border font-medium ${getStatusBadgeStyle(
            telegramStatus
          )}`}
          title={`Telegram Bot: ${telegramStatus}`}
        >
          <Send className="w-3 h-3" />
          <span>Bot: {telegramStatus}</span>
        </div>

        {/* SAP S/4HANA */}
        <div
          className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border font-medium ${getStatusBadgeStyle(
            sapStatus
          )}`}
          title={`SAP S/4HANA: ${sapStatus}`}
        >
          <Building2 className="w-3 h-3" />
          <span>SAP: {sapStatus}</span>
        </div>

        {/* POS Local */}
        <div
          className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border font-medium ${getStatusBadgeStyle(
            posStatus
          )}`}
          title={`POS Kasir Lokal: ${posStatus}`}
        >
          <Database className="w-3 h-3" />
          <span>POS: {posStatus}</span>
        </div>

        <button
          onClick={fetchHealth}
          disabled={loadingHealth}
          title="Refresh Integration State"
          className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
        >
          <RefreshCw className={`w-3 h-3 ${loadingHealth ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* User Session & Role & Logout */}
      <div className="flex items-center gap-3">
        {/* Role Selector */}
        <div className="flex items-center gap-2 bg-slate-800/80 px-2.5 py-1 rounded-xl border border-slate-700 text-xs">
          <User className="w-3.5 h-3.5 text-blue-400" />
          <select
            value={user?.role || activeRole || 'Regional Manager'}
            onChange={handleRoleChange}
            className="bg-transparent text-slate-200 focus:outline-none pr-1 py-0.5 cursor-pointer font-medium text-xs"
          >
            <option value="Regional Manager" className="bg-slate-800">
              Regional Manager (Siti)
            </option>
            <option value="Store Manager" className="bg-slate-800">
              Store Manager (Budi)
            </option>
            <option value="IT Admin" className="bg-slate-800">
              IT Administrator (Andi)
            </option>
            <option value="Supply Chain Analyst" className="bg-slate-800">
              Supply Chain Analyst (Dewi)
            </option>
          </select>
        </div>

        {/* User Identity & Logout Button */}
        <div className="flex items-center gap-2">
          <div className="hidden md:flex flex-col text-right">
            <span className="text-xs font-semibold text-white leading-tight">
              {user?.full_name || user?.username || 'Administrator'}
            </span>
            <span className="text-[10px] text-slate-400 leading-tight">
              {user?.role || 'Regional Manager'}
            </span>
          </div>

          <button
            onClick={logout}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800/80 hover:bg-rose-500/20 hover:text-rose-300 hover:border-rose-500/40 border border-slate-700 text-xs text-slate-300 font-medium transition"
            title="Keluar dari sesi dashboard"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Keluar</span>
          </button>
        </div>
      </div>
    </header>
  );
}
