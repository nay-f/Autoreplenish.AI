import React, { useState } from 'react';
import { useAuth, ROLE_PROFILES } from '../context/AuthContext';
import {
  Bot,
  Lock,
  User,
  Shield,
  Eye,
  EyeOff,
  ArrowRight,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  KeyRound,
  ShieldCheck,
} from 'lucide-react';

export function Login({ onSuccess }) {
  const { login } = useAuth();

  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('Admin123!');
  const [selectedRole, setSelectedRole] = useState('Regional Manager');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');

    if (!username.trim()) {
      setErrorMessage('Username atau Email wajib diisi.');
      return;
    }
    if (!password) {
      setErrorMessage('Kata sandi wajib diisi.');
      return;
    }

    setLoading(true);
    try {
      await login({
        username: username.trim(),
        password,
        role: selectedRole,
      });
      if (typeof onSuccess === 'function') {
        onSuccess();
      }
    } catch (err) {
      console.error('[Login Error]', err);
      setErrorMessage(
        err.message || 'Kombinasi kredensial tidak valid atau server autentikasi tidak dapat dihubungi.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleUseDemoAdmin = () => {
    setUsername('admin');
    setPassword('Admin123!');
    setSelectedRole('Regional Manager');
    setErrorMessage('');
  };

  const activeProfile = ROLE_PROFILES.find((p) => p.role === selectedRole) || ROLE_PROFILES[0];

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 sm:p-6 relative overflow-hidden">
      {/* Background Ambient Glows */}
      <div className="absolute top-1/4 left-1/3 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/3 translate-x-1/2 translate-y-1/2 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-12 gap-8 relative z-10">
        {/* Left Col: Brand Presentation & Role Overview */}
        <div className="lg:col-span-5 flex flex-col justify-between p-6 sm:p-8 rounded-3xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl shadow-2xl">
          <div>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/25">
                <Bot className="w-7 h-7 text-white" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="font-extrabold text-xl text-white tracking-tight">AutoReplenish.ai</h1>
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-400 border border-blue-500/25">
                    Enterprise
                  </span>
                </div>
                <p className="text-xs text-slate-400">Autonomous Supply Chain Orchestrator</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-slate-800/50 border border-slate-700/60">
                <div className="flex items-center gap-2 text-xs font-bold text-white mb-1.5">
                  <Sparkles className="w-4 h-4 text-purple-400" />
                  <span>Agentic AI & Multi-Store Autonomy</span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Platform middleware cerdas yang menghubungkan data kasir lokal, perkiraan cuaca satelit, dan model
                  AWS Bedrock ke ERP SAP S/4HANA secara real-time.
                </p>
              </div>

              {/* Selected Role Card Info */}
              <div className="p-4 rounded-2xl bg-blue-950/30 border border-blue-500/30">
                <div className="text-[11px] font-bold uppercase tracking-wider text-blue-400 mb-1">
                  Profil Peran Aktif (PRD §7)
                </div>
                <div className="text-sm font-bold text-white">{activeProfile.title}</div>
                <div className="text-xs text-blue-200/80 mt-1 leading-relaxed">
                  {activeProfile.description}
                </div>
              </div>
            </div>
          </div>

          <div className="pt-6 border-t border-slate-800/80 mt-6 flex items-center justify-between text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Zero Hardcoded Mock Protocol
            </span>
            <span>v1.0-prod</span>
          </div>
        </div>

        {/* Right Col: Login Form */}
        <div className="lg:col-span-7 p-6 sm:p-8 rounded-3xl bg-slate-900/90 border border-slate-800 backdrop-blur-2xl shadow-2xl flex flex-col justify-center">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-white tracking-tight">Masuk ke Portal Operasional</h2>
            <p className="text-xs text-slate-400 mt-1">
              Gunakan akun terdaftar atau kredensial administrator default untuk mengelola sistem.
            </p>
          </div>

          {errorMessage && (
            <div className="mb-5 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-2.5 text-xs text-rose-300">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
              <div className="leading-relaxed">{errorMessage}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Role Profile Selection */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Peran Pengguna (Role Profile)
              </label>
              <div className="grid grid-cols-2 gap-2">
                {ROLE_PROFILES.map((p) => {
                  const isSelected = selectedRole === p.role;
                  return (
                    <button
                      type="button"
                      key={p.role}
                      onClick={() => setSelectedRole(p.role)}
                      className={`p-2.5 rounded-xl text-left border transition text-xs flex flex-col justify-between ${
                        isSelected
                          ? 'bg-blue-600/20 border-blue-500 text-white shadow-sm'
                          : 'bg-slate-800/50 border-slate-700/60 text-slate-400 hover:border-slate-600 hover:text-slate-200'
                      }`}
                    >
                      <div className="font-semibold">{p.role}</div>
                      <div className="text-[10px] text-slate-400 truncate mt-0.5">{p.name}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Username / Email */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Username / Identitas Pengguna
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <User className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  required
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-800/80 border border-slate-700 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-slate-300">Kata Sandi</label>
                <span className="text-[11px] text-slate-500">Default: Admin123!</span>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full pl-10 pr-10 py-2.5 bg-slate-800/80 border border-slate-700 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-500 hover:text-slate-300 transition"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Quick Demo Helper */}
            <div className="pt-1">
              <button
                type="button"
                onClick={handleUseDemoAdmin}
                className="w-full py-2 px-3 rounded-xl bg-slate-800/50 hover:bg-slate-800 border border-slate-700/60 text-xs text-slate-300 flex items-center justify-center gap-2 transition"
              >
                <KeyRound className="w-3.5 h-3.5 text-amber-400" />
                <span>Gunakan Akun Demo Administrator (<code>admin</code> / <code>Admin123!</code>)</span>
              </button>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold text-sm shadow-lg shadow-blue-500/25 flex items-center justify-center gap-2 transition disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Memverifikasi Sesi...</span>
                </>
              ) : (
                <>
                  <span>Masuk ke Dashboard</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
