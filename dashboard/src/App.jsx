import React, { useState, useEffect } from "react";
import { api } from "./api";
import {
  MapPin,
  Database,
  Send,
  Package,
  Calendar,
  Zap,
  RefreshCw,
  LogOut,
  Plus,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ShieldCheck,
  Store,
  Activity,
  BarChart3,
  Search,
} from "lucide-react";

const DEFAULT_STORE = {
  store_id: "STR-BARU-01",
  store_name: "",
  area_type: "Komersial / Perkantoran",
  zone: "ZONE-SMG-01",
  latitude: -6.9666,
  longitude: 110.4166,
  telegram_chat_id: "",
  ingestion_mode: "POS_LOCAL",
  pos_connector_type: "REST Webhook (Real-time Event)",
  pos_sync_schedule: "21:00 / Saat Tutup Toko",
  sap_odata_url: "",
  sap_plant: "1000",
  sap_storage_location: "WH01",
  sap_purchasing_org: "1000",
  timeout_tolerance_hours: 4,
  enable_auto_reminder: true,
  promos: [],
  local_events: [],
  active: true,
};

export default function App() {
  // --- Auth State ---
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem("ar_user");
    const token = localStorage.getItem("ar_token");
    return saved && token ? JSON.parse(saved) : null;
  });
  const [loginForm, setLoginForm] = useState({
    username: "admin",
    password: "",
    role: "Store Manager",
  });
  const [authError, setAuthError] = useState("");

  // --- Data & Navigation State ---
  const [mainView, setMainView] = useState("overview"); // 'overview' | 'settings' | 'audit'
  const [activeSettingsTab, setActiveSettingsTab] = useState(1);
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [stores, setStores] = useState([]);
  const [selectedStoreId, setSelectedStoreId] = useState("");
  const [storeForm, setStoreForm] = useState(DEFAULT_STORE);
  const [skus, setSkus] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);

  // --- Filter & Pagination Audit Log (P2 #24) ---
  const [auditFilterType, setAuditFilterType] = useState("ALL"); // 'ALL' | 'EVAL' | 'SAP_PR'
  const [auditSearch, setAuditSearch] = useState("");
  const [auditPage, setAuditPage] = useState(1);
  const AUDIT_PAGE_SIZE = 8;

  // --- Form Tambah SKU (Dengan Unit Price IDR) ---
  const [newSku, setNewSku] = useState({
    sku_id: "SKU-001",
    sku_name: "",
    category: "Daily Staples",
    physical_stock: 10,
    threshold: 25,
    average_daily_burn_rate: 15,
    lead_time_days: 2,
    moq: 12,
    packaging_multiple: 12,
    unit_price: 18500,
    currency: "IDR",
    shelf_life_days: 3,
    is_perishable: false,
  });
  const [newPromo, setNewPromo] = useState({
    promo_name: "",
    promo_type: "JSM / Weekend",
    start_date: "2026-10-27",
    end_date: "2026-10-30",
  });
  const [newEvent, setNewEvent] = useState({
    event_name: "",
    event_date: "2026-10-29",
    impact_multiplier: 1.5,
  });

  // --- UI Feedback & Double-Submit Protection ---
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [bannerMsg, setBannerMsg] = useState(null);

  const notify = (text, type = "success") => {
    setBannerMsg({ text, type });
    setTimeout(() => setBannerMsg(null), 5000);
  };

  // --- Fetch Initial Data ---
  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [healthData, storesData, logsData, metricsData] = await Promise.all([
        api.getIntegrationsHealth(),
        api.getStores(),
        api.getAuditLogs(),
        api.getGovernanceMetrics(),
      ]);
      setHealth(healthData);
      setStores(storesData);
      setAuditLogs(logsData);
      setMetrics(metricsData);

      if (storesData.length > 0) {
        const current =
          storesData.find((s) => s.store_id === selectedStoreId) || storesData[0];
        setSelectedStoreId(current.store_id);
        setStoreForm({ ...DEFAULT_STORE, ...current });
        const skuList = await api.getStoreSkus(current.store_id);
        setSkus(skuList);
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setUser(null);
        return;
      }
      notify(
        `Gagal memuat data dari backend (${err.message}). Pastikan uvicorn aktif di port 8000.`,
        "error"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      loadDashboardData();
    }
  }, [user]);

  const handleSelectStore = async (storeId) => {
    setSelectedStoreId(storeId);
    const found = stores.find((s) => s.store_id === storeId);
    if (found) {
      setStoreForm({ ...DEFAULT_STORE, ...found });
      try {
        const skuList = await api.getStoreSkus(storeId);
        setSkus(skuList);
      } catch (e) {
        notify("Gagal memuat daftar SKU toko.", "error");
      }
    }
  };

  // --- Handlers ---
  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError("");
    setSaving(true);
    try {
      const res = await api.login(
        loginForm.username,
        loginForm.password,
        loginForm.role
      );
      localStorage.setItem("ar_user", JSON.stringify(res.user));
      setUser(res.user);
    } catch (err) {
      setAuthError(
        err.response?.data?.detail || "Login gagal. Periksa kredensial Anda."
      );
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("ar_token");
    localStorage.removeItem("ar_user");
    setUser(null);
  };

  const handleSaveStoreSettings = async (e) => {
    if (e) e.preventDefault();
    setSaving(true);
    try {
      const saved = await api.saveStore(storeForm);
      notify(`Pengaturan toko ${saved.store_name} berhasil disimpan ke DynamoDB!`);
      await loadDashboardData();
    } catch (err) {
      notify(
        `Gagal menyimpan pengaturan: ${err.response?.data?.detail || err.message}`,
        "error"
      );
    } finally {
      setSaving(false);
    }
  };

  const handleAddSku = async (e) => {
    e.preventDefault();
    if (!storeForm.store_id) return;
    setSaving(true);
    try {
      await api.saveStoreSku(storeForm.store_id, newSku);
      const updatedSkus = await api.getStoreSkus(storeForm.store_id);
      setSkus(updatedSkus);
      notify(`SKU ${newSku.sku_name} berhasil disimpan!`);
      setNewSku({
        ...newSku,
        sku_id: `SKU-00${updatedSkus.length + 1}`,
        sku_name: "",
      });
    } catch (err) {
      notify(
        `Gagal menyimpan SKU: ${err.response?.data?.detail || err.message}`,
        "error"
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteSku = async (skuId, skuName) => {
    if (!window.confirm(`Hapus SKU "${skuName}" (${skuId}) dari toko ini?`)) {
      return;
    }
    try {
      await api.deleteStoreSku(storeForm.store_id, skuId);
      setSkus(skus.filter((s) => s.sku_id !== skuId));
      notify(`SKU ${skuId} berhasil dihapus.`);
    } catch (err) {
      notify(`Gagal menghapus SKU: ${err.message}`, "error");
    }
  };

  const handleTriggerEvaluation = async (storeId) => {
    setEvaluating(true);
    try {
      const res = await api.evaluateStore(storeId);
      if (res.skipped_locked) {
        notify(res.message, "error");
      } else {
        notify(
          `Evaluasi selesai untuk ${res.store_name}! ${res.evaluated_count} SKU dievaluasi & dikirim ke Telegram.`
        );
      }
      const [logsData, metricsData] = await Promise.all([
        api.getAuditLogs(),
        api.getGovernanceMetrics(),
      ]);
      setAuditLogs(logsData);
      setMetrics(metricsData);
    } catch (err) {
      notify(`Evaluasi gagal: ${err.response?.data?.detail || err.message}`, "error");
    } finally {
      setEvaluating(false);
    }
  };

  // --- Helper Render Badge Status Jujur ---
  const renderStatusBadge = (serviceObj) => {
    const st = serviceObj?.status || "NOT_CONFIGURED";
    if (st === "CONNECTED") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <CheckCircle2 className="w-3.5 h-3.5" /> CONNECTED
        </span>
      );
    }
    if (st === "NOT_CONFIGURED") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <AlertTriangle className="w-3.5 h-3.5" /> NOT CONFIGURED
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
        <XCircle className="w-3.5 h-3.5" /> {st}
      </span>
    );
  };

  // Filter & Pagination Audit Log
  const filteredAuditLogs = auditLogs.filter((log) => {
    if (auditFilterType === "SAP_PR" && !log.sap_pr) return false;
    if (auditFilterType === "EVAL" && log.sap_pr) return false;
    if (auditSearch.trim()) {
      const q = auditSearch.toLowerCase();
      const textMatch =
        (log.store_id || "").toLowerCase().includes(q) ||
        (log.store_name || "").toLowerCase().includes(q) ||
        (log.sku_id || "").toLowerCase().includes(q) ||
        (log.sku_name || "").toLowerCase().includes(q) ||
        (log.sap_pr?.pr_number || "").toLowerCase().includes(q);
      return textMatch;
    }
    return true;
  });

  const totalAuditPages = Math.max(
    1,
    Math.ceil(filteredAuditLogs.length / AUDIT_PAGE_SIZE)
  );
  const paginatedAuditLogs = filteredAuditLogs.slice(
    (auditPage - 1) * AUDIT_PAGE_SIZE,
    auditPage * AUDIT_PAGE_SIZE
  );

  // ===================================================================
  // TAMPILAN 1: HALAMAN LOGIN (JWT + RBAC)
  // ===================================================================
  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
        <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-3 rounded-xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-400">
              <ShieldCheck className="w-7 h-7" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">AutoReplenish.ai</h1>
              <p className="text-xs text-slate-400">
                Enterprise Retail Replenishment Middleware
              </p>
            </div>
          </div>

          {authError && (
            <div className="mb-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
              {authError}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Username</label>
              <input
                type="text"
                required
                value={loginForm.username}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, username: e.target.value })
                }
                className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Password</label>
              <input
                type="password"
                required
                placeholder="Masukkan password admin"
                value={loginForm.password}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, password: e.target.value })
                }
                className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">
                Peran Operasional (RBAC Role)
              </label>
              <select
                value={loginForm.role}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, role: e.target.value })
                }
                className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm focus:border-indigo-500 focus:outline-none"
              >
                <option value="Store Manager">Store Manager (Kepala Toko)</option>
                <option value="Regional Manager">Regional Manager</option>
                <option value="IT Administrator">IT Administrator</option>
                <option value="Auditor">Auditor (Read-Only Audit)</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={saving}
              className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-sm transition"
            >
              {saving ? "Memverifikasi JWT..." : "Masuk ke Dashboard"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // ===================================================================
  // TAMPILAN 2: DASHBOARD UTAMA
  // ===================================================================
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-600 text-white">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <h1 className="font-bold text-lg tracking-tight">AutoReplenish.ai</h1>
              <p className="text-xs text-slate-400">
                Production Middleware ({metrics?.version_info?.prompt_version || "v2.0"})
              </p>
            </div>
          </div>

          {/* Menu Navigasi Utama */}
          <div className="flex items-center gap-2 bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setMainView("overview")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition ${mainView === "overview"
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:text-white"
                }`}
            >
              Monitor &amp; Governance
            </button>
            <button
              onClick={() => setMainView("settings")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition ${mainView === "settings"
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:text-white"
                }`}
            >
              Pengaturan Toko (5 Tab)
            </button>
            <button
              onClick={() => setMainView("audit")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition ${mainView === "audit"
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:text-white"
                }`}
            >
              Audit AI &amp; PR SAP ({auditLogs.length})
            </button>
          </div>

          {/* User Info & Refresh */}
          <div className="flex items-center gap-3">
            <button
              onClick={loadDashboardData}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
              title="Muat Ulang Data Live"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <div className="text-right hidden sm:block">
              <div className="text-xs font-semibold text-white">{user.username}</div>
              <div className="text-[11px] text-indigo-400">{user.role}</div>
            </div>
            <button
              onClick={handleLogout}
              className="p-2 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20"
              title="Keluar"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Notifikasi Banner */}
        {bannerMsg && (
          <div
            className={`p-4 rounded-xl border text-sm flex items-center justify-between ${bannerMsg.type === "error"
                ? "bg-rose-500/10 border-rose-500/30 text-rose-300"
                : "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
              }`}
          >
            <span>{bannerMsg.text}</span>
            <button onClick={() => setBannerMsg(null)} className="text-xs underline">
              Tutup
            </button>
          </div>
        )}

        {/* Bar Indikator Koneksi API Riil */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
            <div>
              <div className="text-xs text-slate-400">AWS Bedrock AI</div>
              <div className="text-sm font-semibold mt-0.5 truncate max-w-[160px]">
                {health?.bedrock?.model || "Claude Sonnet"}
              </div>
            </div>
            {renderStatusBadge(health?.bedrock)}
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
            <div>
              <div className="text-xs text-slate-400">OpenWeatherMap</div>
              <div className="text-sm font-semibold mt-0.5">Satelit Cuaca GPS</div>
            </div>
            {renderStatusBadge(health?.weather)}
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
            <div>
              <div className="text-xs text-slate-400">Telegram Bot HITL</div>
              <div className="text-sm font-semibold mt-0.5">
                {health?.telegram?.username || "Bot Kanal Toko"}
              </div>
            </div>
            {renderStatusBadge(health?.telegram)}
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
            <div>
              <div className="text-xs text-slate-400">SAP BTP / S/4HANA</div>
              <div className="text-sm font-semibold mt-0.5">OAuth2 &amp; PR OData</div>
            </div>
            {renderStatusBadge(health?.sap)}
          </div>
        </div>

        {/* Kartu Metrik Observability & AI Governance Aktual (Fase 3 & 4) */}
        {metrics && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="text-[11px] text-slate-400 flex items-center gap-1">
                <BarChart3 className="w-3.5 h-3.5 text-indigo-400" />
                HITL Acceptance / Edit Rate
              </div>
              <div className="text-lg font-bold text-white mt-1">
                {metrics.hitl_decision_metrics?.acceptance_rate_pct ?? 0}%{" "}
                <span className="text-xs font-normal text-slate-400">
                  (Edit: {metrics.hitl_decision_metrics?.edit_rate_pct ?? 0}%)
                </span>
              </div>
              <div className="text-[11px] text-slate-500">
                Total Keputusan: {metrics.hitl_decision_metrics?.decided_total ?? 0}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="text-[11px] text-slate-400">
                Akurasi Keselarasan Manajer (100 - WAPE)
              </div>
              <div className="text-lg font-bold text-emerald-400 mt-1">
                {metrics.hitl_decision_metrics?.manager_alignment_accuracy_pct !== null
                  ? `${metrics.hitl_decision_metrics?.manager_alignment_accuracy_pct}%`
                  : "Menunggu Approval"}
              </div>
              <div className="text-[11px] text-slate-500">
                Deviasi WAPE: {metrics.hitl_decision_metrics?.manager_alignment_wape_pct ?? 0}%
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="text-[11px] text-slate-400">
                Rata-Rata Latensi &amp; Fallback Bedrock
              </div>
              <div className="text-lg font-bold text-white mt-1">
                {metrics.evaluation_metrics?.average_bedrock_latency_ms ?? 0} ms
              </div>
              <div className="text-[11px] text-slate-500">
                Fallback Rate: {metrics.evaluation_metrics?.bedrock_fallback_rate_pct ?? 0}% | Guardrail:{" "}
                {metrics.evaluation_metrics?.guardrail_interventions_total ?? 0}x
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="text-[11px] text-slate-400">
                Keberhasilan Dokumen PR SAP
              </div>
              <div className="text-lg font-bold text-indigo-400 mt-1">
                {metrics.sap_transaction_metrics?.sap_pr_success_total ?? 0} /{" "}
                {metrics.sap_transaction_metrics?.sap_pr_total ?? 0} PR
              </div>
              <div className="text-[11px] text-slate-500">
                Success Rate: {metrics.sap_transaction_metrics?.sap_success_rate_pct ?? 0}%
              </div>
            </div>
          </div>
        )}

        {/* Pemilih Toko Aktif */}
        <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Store className="w-5 h-5 text-indigo-400" />
            <div>
              <label className="block text-xs text-slate-400">
                Pilih Gerai Toko Aktif (Sinkron dengan Bot Telegram <code>/tambah_toko</code>):
              </label>
              <select
                value={selectedStoreId}
                onChange={(e) => handleSelectStore(e.target.value)}
                className="mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
              >
                {stores.length === 0 && (
                  <option value="">-- Belum ada toko terdaftar --</option>
                )}
                {stores.map((s) => (
                  <option key={s.store_id} value={s.store_id}>
                    {s.store_name} ({s.store_id}) — {s.area_type}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setStoreForm({
                  ...DEFAULT_STORE,
                  store_id: `STR-TOKO-${Math.floor(100 + Math.random() * 900)}`,
                });
                setMainView("settings");
                setActiveSettingsTab(1);
              }}
              className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" /> Buat Toko Baru
            </button>

            {selectedStoreId && user.role !== "Auditor" && (
              <button
                onClick={() => handleTriggerEvaluation(selectedStoreId)}
                disabled={evaluating}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold text-white flex items-center gap-2 shadow-lg shadow-indigo-600/20"
              >
                <Zap className="w-4 h-4" />
                {evaluating
                  ? "Mengevaluasi Baseline + Bedrock..."
                  : "Analisa Stok Sekarang (On-Demand)"}
              </button>
            )}
          </div>
        </div>

        {/* ===============================================================
            VIEW 1: MONITOR & INVENTARIS TOKO
        =============================================================== */}
        {mainView === "overview" && (
          <div className="space-y-6">
            {stores.length === 0 ? (
              <div className="p-12 text-center rounded-2xl bg-slate-900 border border-slate-800">
                <p className="text-slate-300 font-medium">
                  Belum ada data toko di DynamoDB.
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Klik tombol &ldquo;Buat Toko Baru&rdquo; di atas atau ketik{" "}
                  <code>/tambah_toko</code> di Bot Telegram Anda.
                </p>
              </div>
            ) : (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-base font-bold text-white">
                      Status Posisi Stok &amp; Aturan SKU — {storeForm.store_name}
                    </h2>
                    <p className="text-xs text-slate-400">
                      Koordinat GPS: {storeForm.latitude}, {storeForm.longitude} | Zona:{" "}
                      {storeForm.zone} | Mode: {storeForm.ingestion_mode}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setMainView("settings");
                      setActiveSettingsTab(4);
                    }}
                    className="text-xs text-indigo-400 hover:underline"
                  >
                    + Kelola Aturan SKU
                  </button>
                </div>

                {skus.length === 0 ? (
                  <p className="text-xs text-slate-400 py-6 text-center">
                    Belum ada SKU untuk toko ini. Tambahkan SKU di tab Pengaturan Toko.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-sm">
                      <thead>
                        <tr className="border-b border-slate-800 text-xs text-slate-400">
                          <th className="py-3 px-3">ID &amp; Nama Barang</th>
                          <th className="py-3 px-3">Kategori</th>
                          <th className="py-3 px-3">Harga Satuan</th>
                          <th className="py-3 px-3">Stok Fisik</th>
                          <th className="py-3 px-3">Safety Threshold</th>
                          <th className="py-3 px-3">Burn Rate</th>
                          <th className="py-3 px-3">MOQ &amp; Kemasan</th>
                          <th className="py-3 px-3">Status Rak</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {skus.map((item) => {
                          const isLow = item.physical_stock <= item.threshold;
                          return (
                            <tr key={item.sku_id} className="hover:bg-slate-800/30">
                              <td className="py-3 px-3 font-medium">
                                <div>{item.sku_name}</div>
                                <div className="text-xs text-slate-500">{item.sku_id}</div>
                              </td>
                              <td className="py-3 px-3 text-xs">
                                {item.category}{" "}
                                {item.is_perishable && (
                                  <span className="ml-1 px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400">
                                    Segar ({item.shelf_life_days}h)
                                  </span>
                                )}
                              </td>
                              <td className="py-3 px-3 text-xs font-mono">
                                Rp {(item.unit_price || 15000).toLocaleString("id-ID")}
                              </td>
                              <td className="py-3 px-3 font-bold">
                                {item.physical_stock} Pcs
                              </td>
                              <td className="py-3 px-3">{item.threshold} Pcs</td>
                              <td className="py-3 px-3">
                                {item.average_daily_burn_rate} Pcs/h
                              </td>
                              <td className="py-3 px-3 text-xs text-slate-300">
                                MOQ {item.moq} | Kelipatan {item.packaging_multiple}
                              </td>
                              <td className="py-3 px-3">
                                {isLow ? (
                                  <span className="px-2.5 py-1 rounded-full text-xs bg-rose-500/10 text-rose-400 border border-rose-500/20">
                                    Perlu Reorder
                                  </span>
                                ) : (
                                  <span className="px-2.5 py-1 rounded-full text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                    Stok Aman
                                  </span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ===============================================================
            VIEW 2: 5 TAB PENGATURAN OPERASIONAL TOKO
        =============================================================== */}
        {mainView === "settings" && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            <div className="flex overflow-x-auto border-b border-slate-800 bg-slate-950/60">
              {[
                { id: 1, label: "1. Profil & Geolokasi", icon: MapPin },
                { id: 2, label: "2. Sumber Data Inventaris", icon: Database },
                { id: 3, label: "3. Kanal HITL Telegram", icon: Send },
                { id: 4, label: `4. Aturan Pengadaan SKU (${skus.length})`, icon: Package },
                {
                  id: 5,
                  label: `5. Kalender Promo & Event (${(storeForm.promos?.length || 0) +
                    (storeForm.local_events?.length || 0)
                    })`,
                  icon: Calendar,
                },
              ].map((tab) => {
                const Icon = tab.icon;
                const active = activeSettingsTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveSettingsTab(tab.id)}
                    className={`flex items-center gap-2 px-5 py-4 text-xs font-semibold whitespace-nowrap border-b-2 transition ${active
                        ? "border-indigo-500 text-indigo-400 bg-indigo-500/5"
                        : "border-transparent text-slate-400 hover:text-slate-200"
                      }`}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            <div className="p-6">
              {/* TAB 1: PROFIL & GEOLOKASI TOKO */}
              {activeSettingsTab === 1 && (
                <form onSubmit={handleSaveStoreSettings} className="space-y-4 max-w-3xl">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">
                        ID Toko (Hanya Huruf, Angka, Strip)
                      </label>
                      <input
                        type="text"
                        required
                        value={storeForm.store_id ?? ""}
                        onChange={(e) =>
                          setStoreForm({ ...storeForm, store_id: e.target.value })
                        }
                        className="w-full px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">
                        Nama Gerai / Toko
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="Contoh: Toko Almadina Wirosari"
                        value={storeForm.store_name ?? ""}
                        onChange={(e) =>
                          setStoreForm({ ...storeForm, store_name: e.target.value })
                        }
                        className="w-full px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">
                        Tipe Wilayah (Area Type)
                      </label>
                      <select
                        value={storeForm.area_type ?? "Komersial / Perkantoran"}
                        onChange={(e) =>
                          setStoreForm({ ...storeForm, area_type: e.target.value })
                        }
                        className="w-full px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm"
                      >
                        <option value="Komersial / Perkantoran">
                          Komersial / Perkantoran
                        </option>
                        <option value="Residensial / Pemukiman">
                          Residensial / Pemukiman
                        </option>
                        <option value="Pasar / Sub-Urban">Pasar / Sub-Urban</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">
                        Zona Logistik DC (Delivery Zone)
                      </label>
                      <input
                        type="text"
                        required
                        value={storeForm.zone ?? ""}
                        onChange={(e) =>
                          setStoreForm({ ...storeForm, zone: e.target.value })
                        }
                        className="w-full px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">
                        Latitude GPS (-90 s/d 90)
                      </label>
                      <input
                        type="number"
                        step="any"
                        min="-90"
                        max="90"
                        required
                        value={storeForm.latitude ?? -6.9666}
                        onChange={(e) =>
                          setStoreForm({
                            ...storeForm,
                            latitude: parseFloat(e.target.value || 0),
                          })
                        }
                        className="w-full px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">
                        Longitude GPS (-180 s/d 180)
                      </label>
                      <input
                        type="number"
                        step="any"
                        min="-180"
                        max="180"
                        required
                        value={storeForm.longitude ?? 110.4166}
                        onChange={(e) =>
                          setStoreForm({
                            ...storeForm,
                            longitude: parseFloat(e.target.value || 0),
                          })
                        }
                        className="w-full px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm"
                      />
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={saving}
                    className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold text-white"
                  >
                    {saving ? "Menyimpan..." : "Simpan Profil & Geolokasi"}
                  </button>
                </form>
              )}

              {/* TAB 2: SUMBER DATA INVENTARIS */}
              {activeSettingsTab === 2 && (
                <form onSubmit={handleSaveStoreSettings} className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div
                      onClick={() =>
                        setStoreForm((prev) => ({
                          ...DEFAULT_STORE,
                          ...prev,
                          ingestion_mode: "POS_LOCAL",
                        }))
                      }
                      className={`cursor-pointer p-5 rounded-xl border transition ${storeForm?.ingestion_mode !== "SAP_BTP"
                          ? "border-indigo-500 bg-indigo-500/10"
                          : "border-slate-800 bg-slate-950 hover:border-slate-700"
                        }`}
                    >
                      <div className="font-bold text-sm text-white">
                        Mode A: Ritel Kecil / Toserba
                      </div>
                      <p className="text-xs text-slate-400 mt-1">
                        Integrasi menggunakan POS Kasir Lokal via webhook atau sinkronisasi harian.
                      </p>
                    </div>

                    <div
                      onClick={() =>
                        setStoreForm((prev) => ({
                          ...DEFAULT_STORE,
                          ...prev,
                          ingestion_mode: "SAP_BTP",
                        }))
                      }
                      className={`cursor-pointer p-5 rounded-xl border transition ${storeForm?.ingestion_mode === "SAP_BTP"
                          ? "border-indigo-500 bg-indigo-500/10"
                          : "border-slate-800 bg-slate-950 hover:border-slate-700"
                        }`}
                    >
                      <div className="font-bold text-sm text-white">
                        Mode B: Ritel Korporat / Berjejaring
                      </div>
                      <p className="text-xs text-slate-400 mt-1">
                        Integrasi enterprise dengan SAP S/4HANA OData &amp; SAP BTP untuk penerbitan Purchase Requisition.
                      </p>
                    </div>
                  </div>

                  {storeForm?.ingestion_mode !== "SAP_BTP" ? (
                    <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
                      <div className="text-xs font-bold text-amber-400 uppercase tracking-wider">
                        ⚡ Konfigurasi Webhook Kasir POS Lokal
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs text-slate-400 mb-1">
                            Tipe Konektor POS
                          </label>
                          <select
                            value={
                              storeForm?.pos_connector_type ??
                              "REST Webhook (Real-time Event)"
                            }
                            onChange={(e) =>
                              setStoreForm({
                                ...storeForm,
                                pos_connector_type: e.target.value,
                              })
                            }
                            className="w-full px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm"
                          >
                            <option value="REST Webhook (Real-time Event)">
                              REST Webhook (Real-time Event)
                            </option>
                            <option value="Direct DB Sync">Direct DB Sync</option>
                            <option value="CSV / JSON Daily Auto-Import">
                              CSV / JSON Daily Auto-Import
                            </option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-slate-400 mb-1">
                            Jadwal Sinkronisasi Penutupan Toko
                          </label>
                          <input
                            type="text"
                            value={
                              storeForm?.pos_sync_schedule ?? "21:00 / Saat Tutup Toko"
                            }
                            onChange={(e) =>
                              setStoreForm({
                                ...storeForm,
                                pos_sync_schedule: e.target.value,
                              })
                            }
                            className="w-full px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm"
                          />
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-bold text-indigo-400 uppercase tracking-wider">
                          🏢 Konfigurasi Enterprise SAP S/4HANA &amp; SAP BTP
                        </div>
                        {renderStatusBadge(health?.sap)}
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <div className="sm:col-span-3">
                          <label className="block text-xs text-slate-400 mb-1">
                            SAP OData Purchase Requisition Endpoint URL (Kosongkan jika menggunakan mode BTP Sandbox)
                          </label>
                          <input
                            type="text"
                            value={storeForm?.sap_odata_url ?? ""}
                            onChange={(e) =>
                              setStoreForm({
                                ...storeForm,
                                sap_odata_url: e.target.value,
                              })
                            }
                            placeholder="https://<s4hana-host>/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV"
                            className="w-full px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-slate-400 mb-1">
                            Kode Plant SAP
                          </label>
                          <input
                            type="text"
                            value={storeForm?.sap_plant ?? "1000"}
                            onChange={(e) =>
                              setStoreForm({ ...storeForm, sap_plant: e.target.value })
                            }
                            className="w-full px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-slate-400 mb-1">
                            Storage Location
                          </label>
                          <input
                            type="text"
                            value={storeForm?.sap_storage_location ?? "WH01"}
                            onChange={(e) =>
                              setStoreForm({
                                ...storeForm,
                                sap_storage_location: e.target.value,
                              })
                            }
                            className="w-full px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-slate-400 mb-1">
                            Purchasing Organization
                          </label>
                          <input
                            type="text"
                            value={storeForm?.sap_purchasing_org ?? "1000"}
                            onChange={(e) =>
                              setStoreForm({
                                ...storeForm,
                                sap_purchasing_org: e.target.value,
                              })
                            }
                            className="w-full px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm"
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={saving}
                    className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold text-white"
                  >
                    {saving ? "Menyimpan..." : "Simpan Konfigurasi Sumber Data"}
                  </button>
                </form>
              )}

              {/* TAB 3: KANAL VALIDASI KEPALA TOKO (HITL TELEGRAM) */}
              {activeSettingsTab === 3 && (
                <form onSubmit={handleSaveStoreSettings} className="space-y-4 max-w-xl">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">
                      Telegram Chat ID Kepala Toko / Grup Cabang
                    </label>
                    <input
                      type="text"
                      placeholder="Contoh: 123456789"
                      value={storeForm?.telegram_chat_id ?? ""}
                      onChange={(e) =>
                        setStoreForm({
                          ...storeForm,
                          telegram_chat_id: e.target.value,
                        })
                      }
                      className="w-full px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">
                      Batas Waktu Persetujuan / Timeout Tolerance (Jam)
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="48"
                      value={storeForm?.timeout_tolerance_hours ?? 4}
                      onChange={(e) =>
                        setStoreForm({
                          ...storeForm,
                          timeout_tolerance_hours: parseInt(e.target.value || 4, 10),
                        })
                      }
                      className="w-full px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={saving}
                    className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold text-white"
                  >
                    {saving ? "Menyimpan..." : "Simpan Pengaturan HITL Telegram"}
                  </button>
                </form>
              )}

              {/* TAB 4: ATURAN PENGADAAN SKU (DENGAN HARGA SATUAN RESMI) */}
              {activeSettingsTab === 4 && (
                <div className="space-y-6">
                  <form
                    onSubmit={handleAddSku}
                    className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-4"
                  >
                    <div className="text-xs font-bold text-indigo-400 uppercase">
                      + Tambah / Perbarui Aturan Pengadaan SKU
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                      <input
                        type="text"
                        required
                        placeholder="ID SKU (SKU-001)"
                        value={newSku.sku_id}
                        onChange={(e) =>
                          setNewSku({ ...newSku, sku_id: e.target.value })
                        }
                        className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                      />
                      <input
                        type="text"
                        required
                        placeholder="Nama Barang (Roti Tawar / Minyak)"
                        value={newSku.sku_name}
                        onChange={(e) =>
                          setNewSku({ ...newSku, sku_name: e.target.value })
                        }
                        className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs sm:col-span-2"
                      />
                      <select
                        value={newSku.category}
                        onChange={(e) =>
                          setNewSku({
                            ...newSku,
                            category: e.target.value,
                            is_perishable: e.target.value === "Perishable",
                          })
                        }
                        className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                      >
                        <option value="Daily Staples">Daily Staples (Sembako)</option>
                        <option value="Perishable">Perishable (Barang Segar)</option>
                        <option value="Beverage">Beverage (Minuman)</option>
                      </select>
                      <div>
                        <label className="text-[11px] text-slate-400">
                          Harga Satuan (IDR)
                        </label>
                        <input
                          type="number"
                          min="1"
                          required
                          value={newSku.unit_price}
                          onChange={(e) =>
                            setNewSku({
                              ...newSku,
                              unit_price: parseFloat(e.target.value || 15000),
                            })
                          }
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400">Stok Fisik</label>
                        <input
                          type="number"
                          min="0"
                          required
                          value={newSku.physical_stock}
                          onChange={(e) =>
                            setNewSku({
                              ...newSku,
                              physical_stock: parseInt(e.target.value || 0, 10),
                            })
                          }
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400">
                          Safety Stock Threshold
                        </label>
                        <input
                          type="number"
                          min="0"
                          required
                          value={newSku.threshold}
                          onChange={(e) =>
                            setNewSku({
                              ...newSku,
                              threshold: parseInt(e.target.value || 0, 10),
                            })
                          }
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400">
                          Laju Jual / Hari
                        </label>
                        <input
                          type="number"
                          step="0.1"
                          min="0"
                          required
                          value={newSku.average_daily_burn_rate}
                          onChange={(e) =>
                            setNewSku({
                              ...newSku,
                              average_daily_burn_rate: parseFloat(e.target.value || 0),
                            })
                          }
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400">
                          Lead Time (Hari)
                        </label>
                        <input
                          type="number"
                          min="0"
                          required
                          value={newSku.lead_time_days}
                          onChange={(e) =>
                            setNewSku({
                              ...newSku,
                              lead_time_days: parseInt(e.target.value || 1, 10),
                            })
                          }
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400">MOQ</label>
                        <input
                          type="number"
                          min="1"
                          required
                          value={newSku.moq}
                          onChange={(e) =>
                            setNewSku({
                              ...newSku,
                              moq: parseInt(e.target.value || 1, 10),
                            })
                          }
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400">
                          Kelipatan Dus (Multiple)
                        </label>
                        <input
                          type="number"
                          min="1"
                          required
                          value={newSku.packaging_multiple}
                          onChange={(e) =>
                            setNewSku({
                              ...newSku,
                              packaging_multiple: parseInt(e.target.value || 1, 10),
                            })
                          }
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400">
                          Masa Simpan (Hari)
                        </label>
                        <input
                          type="number"
                          min="0"
                          value={newSku.shelf_life_days || 0}
                          onChange={(e) =>
                            setNewSku({
                              ...newSku,
                              shelf_life_days: parseInt(e.target.value || 0, 10),
                            })
                          }
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                        />
                      </div>
                    </div>
                    <button
                      type="submit"
                      disabled={saving}
                      className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold text-white"
                    >
                      {saving ? "Menyimpan..." : "Simpan SKU ke Toko"}
                    </button>
                  </form>

                  {/* Daftar SKU */}
                  <div className="space-y-2">
                    {skus.map((s) => (
                      <div
                        key={s.sku_id}
                        className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between text-xs"
                      >
                        <div>
                          <span className="font-bold text-white">{s.sku_name}</span> (
                          {s.sku_id}) — Harga: Rp{" "}
                          {(s.unit_price || 15000).toLocaleString("id-ID")} | Stok:{" "}
                          {s.physical_stock} | Threshold: {s.threshold} | MOQ: {s.moq} |
                          Kelipatan: {s.packaging_multiple}
                        </div>
                        <button
                          onClick={() => handleDeleteSku(s.sku_id, s.sku_name)}
                          className="text-rose-400 hover:text-rose-300 p-1"
                          title="Hapus SKU"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 5: KALENDER PROMO & EVENT LOKAL */}
              {activeSettingsTab === 5 && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                      <div className="text-xs font-bold text-indigo-400 uppercase">
                        Katalog Promo Aktif (JSM / Diskon)
                      </div>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder="Nama Promo (misal: Promo JSM Minyak)"
                          value={newPromo.promo_name}
                          onChange={(e) =>
                            setNewPromo({ ...newPromo, promo_name: e.target.value })
                          }
                          className="flex-1 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                        />
                        <button
                          type="button"
                          onClick={() => {
                            if (!newPromo.promo_name) return;
                            const updated = [
                              ...(storeForm.promos || []),
                              {
                                ...newPromo,
                                promo_id: `PRM-${Date.now()}`,
                                target_sku_ids: [],
                              },
                            ];
                            setStoreForm({ ...storeForm, promos: updated });
                            setNewPromo({ ...newPromo, promo_name: "" });
                          }}
                          className="px-3 py-1.5 rounded-lg bg-indigo-600 text-xs font-semibold"
                        >
                          + Tambah
                        </button>
                      </div>
                      <div className="space-y-1.5">
                        {(storeForm.promos || []).map((p, idx) => (
                          <div
                            key={idx}
                            className="p-2 rounded bg-slate-900 text-xs flex justify-between"
                          >
                            <span>
                              {p.promo_name} ({p.promo_type})
                            </span>
                            <button
                              type="button"
                              onClick={() =>
                                setStoreForm({
                                  ...storeForm,
                                  promos: storeForm.promos.filter((_, i) => i !== idx),
                                })
                              }
                              className="text-rose-400"
                            >
                              Hapus
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                      <div className="text-xs font-bold text-emerald-400 uppercase">
                        Agenda Event Lokal (Pasaran Desa / Libur)
                      </div>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder="Nama Event (misal: Pasar Pon / Pengajian)"
                          value={newEvent.event_name}
                          onChange={(e) =>
                            setNewEvent({ ...newEvent, event_name: e.target.value })
                          }
                          className="flex-1 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                        />
                        <button
                          type="button"
                          onClick={() => {
                            if (!newEvent.event_name) return;
                            const updated = [
                              ...(storeForm.local_events || []),
                              { ...newEvent, event_id: `EVT-${Date.now()}` },
                            ];
                            setStoreForm({ ...storeForm, local_events: updated });
                            setNewEvent({ ...newEvent, event_name: "" });
                          }}
                          className="px-3 py-1.5 rounded-lg bg-emerald-600 text-xs font-semibold"
                        >
                          + Tambah
                        </button>
                      </div>
                      <div className="space-y-1.5">
                        {(storeForm.local_events || []).map((ev, idx) => (
                          <div
                            key={idx}
                            className="p-2 rounded bg-slate-900 text-xs flex justify-between"
                          >
                            <span>
                              {ev.event_name} (Dampak: {ev.impact_multiplier}x)
                            </span>
                            <button
                              type="button"
                              onClick={() =>
                                setStoreForm({
                                  ...storeForm,
                                  local_events: storeForm.local_events.filter(
                                    (_, i) => i !== idx
                                  ),
                                })
                              }
                              className="text-rose-400"
                            >
                              Hapus
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    disabled={saving}
                    onClick={handleSaveStoreSettings}
                    className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold text-white"
                  >
                    {saving ? "Menyimpan..." : "Simpan Kalender Promo & Event ke DynamoDB"}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ===============================================================
            VIEW 3: JEJAK AUDIT PENALARAN AI & PR SAP (DENGAN FILTER & PAGINATION)
        =============================================================== */}
        {mainView === "audit" && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Activity className="w-5 h-5 text-indigo-400" />
                  Jejak Penalaran Kognitif Bedrock &amp; Dokumen PR SAP BTP
                </h2>
                <p className="text-xs text-slate-400">
                  Mencakup Baseline Deterministik, Guardrail AI, Versi Prompt, &amp; Status Transaksi SAP.
                </p>
              </div>

              {/* Filter & Pencarian */}
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="Cari toko, SKU, atau No. PR..."
                    value={auditSearch}
                    onChange={(e) => {
                      setAuditSearch(e.target.value);
                      setAuditPage(1);
                    }}
                    className="pl-8 pr-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs"
                  />
                </div>
                <select
                  value={auditFilterType}
                  onChange={(e) => {
                    setAuditFilterType(e.target.value);
                    setAuditPage(1);
                  }}
                  className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs"
                >
                  <option value="ALL">Semua Log ({auditLogs.length})</option>
                  <option value="EVAL">Hanya Evaluasi AI</option>
                  <option value="SAP_PR">Hanya Dokumen PR SAP</option>
                </select>
              </div>
            </div>

            {paginatedAuditLogs.length === 0 ? (
              <p className="text-xs text-slate-400 py-8 text-center">
                Tidak ada riwayat audit yang cocok dengan filter pencarian.
              </p>
            ) : (
              <div className="space-y-3">
                {paginatedAuditLogs.map((log, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2"
                  >
                    {log.sap_pr ? (
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-xs font-bold border border-emerald-500/20">
                            {log.sap_pr.status}
                          </span>
                          <span className="ml-2 font-mono text-sm font-bold text-white">
                            {log.sap_pr.pr_number}
                          </span>
                        </div>
                        <span className="text-xs text-slate-400">
                          Toko: {log.store_id} | SKU: {log.sap_pr.sku_name || log.sku_id} | Qty:{" "}
                          <b>{log.sap_pr.quantity} Pcs</b> | Nilai:{" "}
                          <b>Rp {(log.sap_pr.total_amount || 0).toLocaleString("id-ID")}</b> | Plant:{" "}
                          {log.sap_pr.plant || "1000"} | {log.sap_pr.created_at}
                        </span>
                      </div>
                    ) : (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="font-semibold text-sm text-white">
                            {log.store_name || log.store_id} —{" "}
                            <span className="text-indigo-400">
                              {log.sku_name || log.sku_id}
                            </span>
                          </div>
                          <div className="flex flex-wrap items-center gap-2 text-xs">
                            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                              Cuaca: {log.weather_snapshot?.condition} (
                              {log.weather_snapshot?.temperature_c}°C)
                            </span>
                            {log.confidence_tier && (
                              <span
                                className={`px-2 py-0.5 rounded text-[11px] font-medium ${log.confidence_tier === "HIGH_CONFIDENCE"
                                    ? "bg-emerald-500/10 text-emerald-400"
                                    : "bg-amber-500/10 text-amber-400"
                                  }`}
                              >
                                {log.confidence_tier}
                              </span>
                            )}
                            <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-bold">
                              Order Final: {log.final_recommended_qty} Pcs
                            </span>
                          </div>
                        </div>
                        <p className="text-xs text-slate-300 italic leading-relaxed">
                          &ldquo;{log.reasoning_narrative}&rdquo;
                        </p>
                        <div className="text-[11px] text-slate-500 flex flex-wrap gap-4">
                          <span>Stok Rak: {log.physical_stock} Pcs</span>
                          <span>
                            Baseline Python: {log.deterministic_baseline_qty ?? "-"} Pcs
                          </span>
                          <span>AI Constrained: {log.ai_raw_qty} Pcs</span>
                          <span>MOQ: {log.moq_note}</span>
                          <span>
                            Confidence: {((log.confidence_score || 0) * 100).toFixed(0)}%
                          </span>
                          {log.latency_ms > 0 && <span>Latensi: {log.latency_ms} ms</span>}
                          {log.prompt_version && <span>Prompt: {log.prompt_version}</span>}
                        </div>
                      </>
                    )}
                  </div>
                ))}

                {/* Navigasi Pagination */}
                {totalAuditPages > 1 && (
                  <div className="flex items-center justify-between pt-3 border-t border-slate-800 text-xs text-slate-400">
                    <span>
                      Halaman {auditPage} dari {totalAuditPages} ({filteredAuditLogs.length} item)
                    </span>
                    <div className="flex gap-2">
                      <button
                        disabled={auditPage <= 1}
                        onClick={() => setAuditPage((p) => p - 1)}
                        className="px-3 py-1 rounded bg-slate-800 disabled:opacity-40 text-white"
                      >
                        Sebelumnya
                      </button>
                      <button
                        disabled={auditPage >= totalAuditPages}
                        onClick={() => setAuditPage((p) => p + 1)}
                        className="px-3 py-1 rounded bg-slate-800 disabled:opacity-40 text-white"
                      >
                        Berikutnya
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}