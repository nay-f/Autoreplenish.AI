import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const AuthContext = createContext(null);

export const ROLE_PROFILES = [
  {
    role: 'Regional Manager',
    name: 'Siti Rahmawati',
    title: 'Regional Supply Chain Manager (JABODETABEK)',
    description: 'Akses penuh seluruh cabang regional, monitor multi-store inventory, dan audit jejak penalaran Bedrock.',
  },
  {
    role: 'Store Manager',
    name: 'Budi Santoso',
    title: 'Kepala Toko Cabang Sentra Bisnis (STR-COMMERCIAL-01)',
    description: 'Human-in-the-Loop review, feedback rekomendasi kuota restock, dan integrasi kasir toko.',
  },
  {
    role: 'IT Admin',
    name: 'Andi Wijaya',
    title: 'Lead Cloud Integration & SAP Systems Administrator',
    description: 'Konfigurasi integrasi OData S/4HANA, sinkronisasi webhook kasir, dan pengujian API produksi.',
  },
  {
    role: 'Supply Chain Analyst',
    name: 'Dewi Lestari',
    title: 'Senior Demand & Replenishment Analyst',
    description: 'Analisis akurasi reasoning Bedrock, laju konsumsi SKU perishable, dan metrik penolakan restock.',
  },
];

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Probe auth state on initial mount
  useEffect(() => {
    let mounted = true;

    async function checkAuth() {
      const token = typeof window !== 'undefined' ? localStorage.getItem('ar_token') : null;
      if (!token) {
        if (mounted) {
          setUser(null);
          setLoading(false);
        }
        return;
      }

      try {
        const me = await api.getMe();
        if (mounted) {
          setUser(me);
        }
      } catch (err) {
        console.warn('[Auth] Token validation failed:', err);
        localStorage.removeItem('ar_token');
        if (mounted) {
          setUser(null);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    checkAuth();

    return () => {
      mounted = false;
    };
  }, []);

  const login = async (credentials) => {
    const res = await api.login(credentials);
    if (res?.token) {
      localStorage.setItem('ar_token', res.token);
      const userPayload = {
        username: res.username || credentials.username,
        role: res.role || credentials.role || 'Regional Manager',
        full_name: res.full_name || (res.role === 'Store Manager' ? 'Budi Santoso' : 'Administrator'),
        role_title: res.role_title || res.role,
        store_id: res.store_id || null,
      };
      setUser(userPayload);
      return userPayload;
    }
    throw new Error('Respons login tidak menyertakan token autentikasi.');
  };

  const logout = () => {
    localStorage.removeItem('ar_token');
    setUser(null);
    if (typeof window !== 'undefined') {
      window.history.pushState({}, '', '/login');
      // Trigger a popstate event so App can respond if watching URL
      window.dispatchEvent(new PopStateEvent('popstate'));
    }
  };

  const switchRole = (newRole) => {
    if (!user) return;
    const profile = ROLE_PROFILES.find((p) => p.role === newRole);
    setUser((prev) => ({
      ...prev,
      role: newRole,
      role_title: profile ? profile.title : newRole,
    }));
  };

  const value = {
    user,
    token: typeof window !== 'undefined' ? localStorage.getItem('ar_token') : null,
    isAuthenticated: !!user,
    loading,
    login,
    logout,
    switchRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
