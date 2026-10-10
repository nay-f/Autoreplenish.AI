import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Login } from '../pages/Login';
import { ShieldCheck, Loader2 } from 'lucide-react';

export function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-950 text-slate-100">
        <div className="flex flex-col items-center gap-4 p-8 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-2xl backdrop-blur-xl">
          <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
          <div className="text-center">
            <h3 className="font-bold text-white text-base">Memvalidasi Sesi AutoReplenish.ai</h3>
            <p className="text-xs text-slate-400 mt-1">Mengamankan kredensial enterprise & handshake token...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login />;
  }

  return children;
}
