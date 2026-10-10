import React, { useState, useEffect } from 'react';
import { api, apiConfig } from '../services/api';
import {
  Building2,
  MapPin,
  Database,
  Send,
  Package,
  Calendar,
  Sparkles,
  Check,
  Copy,
  ExternalLink,
  RefreshCw,
  Plus,
  Trash2,
  Edit3,
  CheckCircle2,
  AlertTriangle,
  Eye,
  EyeOff,
  Radio,
  Clock,
  ArrowRight,
  Save,
  Navigation,
  Lock,
  Layers,
  ShoppingBag,
  Truck,
  HelpCircle,
  X,
  Server,
  Zap,
  Activity,
} from 'lucide-react';

class IntegrationErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error('[StoreSettings] Integration form error boundary caught:', error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 bg-rose-950/40 border border-rose-500/30 rounded-2xl text-rose-200 space-y-3">
          <div className="flex items-center gap-2 text-rose-400 font-bold">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span>Terjadi Kendala Saat Menampilkan Formulir Integrasi</span>
          </div>
          <p className="text-xs text-rose-300 leading-relaxed">
            {this.state.error?.message || 'Gagal memuat konfigurasi form integrasi data.'}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-3.5 py-1.5 bg-rose-800/80 hover:bg-rose-700 text-xs font-semibold rounded-xl text-white transition"
          >
            Pulihkan Formulir
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const defaultSapConfig = {
  sap_odata_url: '',
  sap_token_url: '',
  sap_client_id: '',
  sap_client_secret: '',
  sap_plant: '1000',
  sap_storage_location: 'WH01',
  sap_purchasing_org: '1000',
};

const DEFAULT_SAP_CONFIG = defaultSapConfig;

const DEFAULT_POS_CONFIG = {
  pos_connector_type: 'REST Webhook',
  pos_sync_schedule: '21:00 / Saat Tutup Toko',
  pos_webhook_url: '',
  pos_secret_key: '',
};

const AREA_TYPE_OPTIONS = [
  {
    value: 'Komersial / Perkantoran',
    label: 'Komersial / Perkantoran',
    desc: 'Pola ramai saat weekday (hari kerja), relatif sepi saat weekend.',
    badge: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  },
  {
    value: 'Residensial / Pemukiman',
    label: 'Residensial / Pemukiman',
    desc: 'Pola konsumsi sembako dan kebutuhan rumah tangga melonjak saat weekend.',
    badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  },
  {
    value: 'Pasar / Sub-Urban',
    label: 'Pasar / Sub-Urban',
    desc: 'Sensitif terhadap kalender hari pasaran lokal (Pon/Wage/Kliwon) dan komoditas tani.',
    badge: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  },
];

const SKU_CATEGORIES = ['Daily Staples', 'FMCG', 'Perishable', 'Beverage'];

const DAYS_OF_WEEK = [
  'Senin',
  'Selasa',
  'Rabu',
  'Kamis',
  'Jumat',
  'Sabtu',
  'Minggu',
];

const PROMO_TYPES = ['Diskon Persen', 'JSM / Weekend', 'Buy 1 Get 1'];

const MULTIPLIER_OPTIONS = [
  { value: 1.1, label: '1.1x (+10% Lonjakan Ringan)' },
  { value: 1.2, label: '1.2x (+20% Lonjakan Sedang - Normal Event)' },
  { value: 1.5, label: '1.5x (+50% Lonjakan Signifikan - Pekan Gajian)' },
  { value: 2.0, label: '2.0x (+100% Lonjakan Puncak - Hari Pasaran/Festival)' },
];

export function StoreSettings() {
  // Navigation & Store selector
  const [stores, setStores] = useState([]);
  const [selectedStoreId, setSelectedStoreId] = useState('');
  const [activeTab, setActiveTab] = useState('profile');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [bannerMessage, setBannerMessage] = useState(null);

  // Settings form state
  const [profile, setProfile] = useState({
    store_id: '',
    store_name: '',
    area_type: 'Komersial / Perkantoran',
    latitude: -6.2088,
    longitude: 106.8456,
    delivery_zone: 'ZONE-SMG-01',
  });

  const [ingestion, setIngestion] = useState({
    mode: 'POS_WEBHOOK',
    ingestion_mode: 'POS_WEBHOOK',
    ...DEFAULT_POS_CONFIG,
    ...DEFAULT_SAP_CONFIG,
    pos_config: { ...DEFAULT_POS_CONFIG },
    sap_config: { ...DEFAULT_SAP_CONFIG },
    ingestion_config: {
      ...DEFAULT_POS_CONFIG,
      ...DEFAULT_SAP_CONFIG,
      mode: 'POS_WEBHOOK',
    },
  });

  const isSapMode =
    ingestion?.mode === 'SAP_ODATA' ||
    ingestion?.mode === 'SAP' ||
    ingestion?.mode === 'SAP_S4HANA' ||
    ingestion?.ingestion_mode === 'SAP' ||
    ingestion?.ingestion_mode === 'SAP_S4HANA';
  const isPosMode = !isSapMode;

  const [hitl, setHitl] = useState({
    telegram_chat_id: '',
    timeout_tolerance_hours: 4,
    enable_auto_reminder: true,
  });

  const [skus, setSkus] = useState([]);
  const [promos, setPromos] = useState([]);
  const [localEvents, setLocalEvents] = useState([]);

  // UI Interactive States
  const [showSapSecret, setShowSapSecret] = useState(false);
  const [copiedWebhook, setCopiedWebhook] = useState(false);
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [locating, setLocating] = useState(false);

  // Test Ping States
  const [telegramTesting, setTelegramTesting] = useState(false);
  const [telegramStatus, setTelegramStatus] = useState(null);
  const [sapTesting, setSapTesting] = useState(false);
  const [sapStatus, setSapStatus] = useState(null);

  // Modals
  const [editingSku, setEditingSku] = useState(null);
  const [skuModalOpen, setSkuModalOpen] = useState(false);

  const [promoModalOpen, setPromoModalOpen] = useState(false);
  const [newPromo, setNewPromo] = useState({
    promo_name: '',
    promo_type: 'Diskon Persen',
    start_date: new Date().toISOString().split('T')[0],
    end_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
    target_sku_ids: [],
  });

  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [newEvent, setNewEvent] = useState({
    event_name: '',
    event_date: new Date().toISOString().split('T')[0],
    impact_multiplier: 1.2,
  });

  const [createStoreModalOpen, setCreateStoreModalOpen] = useState(false);
  const [newStoreForm, setNewStoreForm] = useState({
    store_id: '',
    store_name: '',
    area_type: 'Komersial / Perkantoran',
    zone: 'ZONE-SMG-01',
    latitude: -6.2088,
    longitude: 106.8456,
  });

  // Load stores on mount
  useEffect(() => {
    loadStoresInitial();
  }, []);

  // Load store settings whenever selectedStoreId changes
  useEffect(() => {
    if (selectedStoreId) {
      loadStoreSettings(selectedStoreId);
    }
  }, [selectedStoreId]);

  async function loadStoresInitial() {
    setLoading(true);
    try {
      const storeList = await api.getStores(false);
      setStores(storeList);
      if (storeList.length > 0) {
        setSelectedStoreId(storeList[0].store_id);
      }
    } catch (err) {
      showBanner('error', `Gagal memuat daftar toko: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function loadStoreSettings(storeId) {
    setRefreshing(true);
    setTelegramStatus(null);
    setSapStatus(null);
    try {
      const data = await api.getStoreSettings(storeId);
      if (data) {
        setProfile({
          store_id: data.store_id || storeId,
          store_name: data.store_name || '',
          area_type: data.area_type || 'Komersial / Perkantoran',
          latitude: data.latitude !== undefined && data.latitude !== null ? data.latitude : -6.2088,
          longitude: data.longitude !== undefined && data.longitude !== null ? data.longitude : 106.8456,
          delivery_zone: data.delivery_zone || 'ZONE-SMG-01',
        });

        const ing = (data?.ingestion_config && typeof data.ingestion_config === 'object')
          ? data.ingestion_config
          : (data?.ingestion && typeof data.ingestion === 'object')
            ? data.ingestion
            : {};
        const sapCfg = (data?.sap_config && typeof data.sap_config === 'object') ? data.sap_config : {};
        const calculatedWebhookUrl = `${apiConfig.baseUrl}/api/v1/ingest/pos/${storeId}`;
        const activeMode =
          data?.ingestion_mode ||
          ing?.mode ||
          (ing?.sap_odata_url || sapCfg?.sap_odata_url ? 'SAP_ODATA' : 'POS_WEBHOOK');

        const mergedSapConfig = {
          sap_odata_url: ing.sap_odata_url ?? sapCfg.sap_odata_url ?? DEFAULT_SAP_CONFIG.sap_odata_url,
          sap_token_url: ing.sap_token_url ?? sapCfg.sap_token_url ?? DEFAULT_SAP_CONFIG.sap_token_url,
          sap_client_id: ing.sap_client_id ?? sapCfg.sap_client_id ?? DEFAULT_SAP_CONFIG.sap_client_id,
          sap_client_secret: ing.sap_client_secret ?? sapCfg.sap_client_secret ?? DEFAULT_SAP_CONFIG.sap_client_secret,
          sap_plant: ing.sap_plant ?? sapCfg.sap_plant ?? DEFAULT_SAP_CONFIG.sap_plant,
          sap_storage_location: ing.sap_storage_location ?? sapCfg.sap_storage_location ?? DEFAULT_SAP_CONFIG.sap_storage_location,
          sap_purchasing_org: ing.sap_purchasing_org ?? sapCfg.sap_purchasing_org ?? DEFAULT_SAP_CONFIG.sap_purchasing_org,
        };

        const mergedPosConfig = {
          pos_connector_type: ing.pos_connector_type || DEFAULT_POS_CONFIG.pos_connector_type,
          pos_sync_schedule: ing.pos_sync_schedule || DEFAULT_POS_CONFIG.pos_sync_schedule,
          pos_webhook_url: ing.pos_webhook_url || calculatedWebhookUrl,
          pos_secret_key: ing.pos_secret_key || `pos_sec_${storeId.toLowerCase().replace(/[^a-z0-9]/g, '')}_${Math.random().toString(36).substring(2, 10)}`,
        };

        setIngestion({
          mode: activeMode,
          ingestion_mode: activeMode,
          ...mergedPosConfig,
          ...mergedSapConfig,
          pos_config: mergedPosConfig,
          sap_config: mergedSapConfig,
          ingestion_config: {
            mode: activeMode,
            ...mergedPosConfig,
            ...mergedSapConfig,
          },
        });

        const h = data.hitl_config || {};
        setHitl({
          telegram_chat_id: h.telegram_chat_id || '',
          timeout_tolerance_hours: h.timeout_tolerance_hours !== undefined ? h.timeout_tolerance_hours : 4,
          enable_auto_reminder: h.enable_auto_reminder !== undefined ? h.enable_auto_reminder : true,
        });

        setPromos(Array.isArray(data.promos) ? data.promos : []);
        setLocalEvents(Array.isArray(data.local_events) ? data.local_events : []);
      }

      // Load SKU rules
      const skuList = await api.getStoreSkus(storeId);
      setSkus(Array.isArray(skuList) ? skuList : []);
    } catch (err) {
      showBanner('error', `Gagal memuat konfigurasi toko ${storeId}: ${err.message}`);
    } finally {
      setRefreshing(false);
    }
  }

  function showBanner(type, message) {
    setBannerMessage({ type, message });
    setTimeout(() => {
      setBannerMessage(null);
    }, 6000);
  }

  // Save Settings (Tabs 1, 2, 3)
  async function handleSaveSettings() {
    if (!selectedStoreId) return;
    setSaving(true);
    try {
      const payload = {
        store_name: profile.store_name,
        area_type: profile.area_type,
        latitude: parseFloat(profile.latitude),
        longitude: parseFloat(profile.longitude),
        delivery_zone: profile.delivery_zone,
        ingestion_config: ingestion,
        hitl_config: hitl,
      };

      await api.updateStoreSettings(selectedStoreId, payload);
      showBanner('success', `Pengaturan operasional untuk "${profile.store_name || selectedStoreId}" berhasil disimpan!`);
      // Update local store list label if store_name changed
      setStores(stores.map((s) => (s.store_id === selectedStoreId ? { ...s, store_name: profile.store_name } : s)));
    } catch (err) {
      showBanner('error', `Gagal menyimpan pengaturan: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  // Geolocation helper
  function handleUseCurrentLocation() {
    if (!navigator.geolocation) {
      showBanner('error', 'Browser Anda tidak mendukung Geolocation API.');
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setProfile((prev) => ({
          ...prev,
          latitude: parseFloat(pos.coords.latitude.toFixed(6)),
          longitude: parseFloat(pos.coords.longitude.toFixed(6)),
        }));
        setLocating(false);
        showBanner('success', `Koordinat diperbarui ke lokasi GPS Anda: ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
      },
      (err) => {
        setLocating(false);
        showBanner('error', `Gagal membaca GPS: ${err.message}`);
      },
      { timeout: 10000 }
    );
  }

  // Copy helper
  function copyToClipboard(text, type) {
    navigator.clipboard.writeText(text);
    if (type === 'webhook') {
      setCopiedWebhook(true);
      setTimeout(() => setCopiedWebhook(false), 2500);
    } else {
      setCopiedSecret(true);
      setTimeout(() => setCopiedSecret(false), 2500);
    }
  }

  // Test Telegram Ping
  async function handleTestTelegram() {
    if (!hitl.telegram_chat_id) {
      showBanner('error', 'Masukkan Telegram Chat ID terlebih dahulu untuk menguji koneksi.');
      return;
    }
    setTelegramTesting(true);
    setTelegramStatus(null);
    try {
      const res = await api.testTelegramIntegration({
        telegram_chat_id: hitl.telegram_chat_id,
        message: `🔔 [AutoReplenish.ai] Tes Koneksi Berhasil!\n\nBot Telegram terhubung dengan Chat ID: ${hitl.telegram_chat_id}.\nKanal Kepala Toko untuk ${profile.store_name || selectedStoreId} siap menerima rekomendasi restock.`,
      });
      setTelegramStatus({
        success: true,
        message: res.message || 'Pesan tes terkirim!',
        simulated: res.simulated,
      });
    } catch (err) {
      setTelegramStatus({
        success: false,
        message: err.message || 'Gagal mengirim pesan ke Telegram.',
      });
    } finally {
      setTelegramTesting(false);
    }
  }

  // Test SAP Handshake
  async function handleTestSap() {
    setSapTesting(true);
    setSapStatus(null);
    try {
      const res = await api.testSapIntegration({
        sap_odata_url:
          ingestion?.ingestion_config?.sap_odata_url ??
          ingestion?.sap_config?.sap_odata_url ??
          ingestion?.sap_odata_url ??
          DEFAULT_SAP_CONFIG.sap_odata_url,
        sap_token_url:
          ingestion?.ingestion_config?.sap_token_url ??
          ingestion?.sap_config?.sap_token_url ??
          ingestion?.sap_token_url ??
          DEFAULT_SAP_CONFIG.sap_token_url,
        sap_client_id:
          ingestion?.ingestion_config?.sap_client_id ??
          ingestion?.sap_config?.sap_client_id ??
          ingestion?.sap_client_id ??
          '',
        sap_client_secret:
          ingestion?.ingestion_config?.sap_client_secret ??
          ingestion?.sap_config?.sap_client_secret ??
          ingestion?.sap_client_secret ??
          '',
        sap_plant:
          ingestion?.ingestion_config?.sap_plant ??
          ingestion?.sap_config?.sap_plant ??
          ingestion?.sap_plant ??
          DEFAULT_SAP_CONFIG.sap_plant,
        sap_storage_location:
          ingestion?.ingestion_config?.sap_storage_location ??
          ingestion?.sap_config?.sap_storage_location ??
          ingestion?.sap_storage_location ??
          DEFAULT_SAP_CONFIG.sap_storage_location,
        sap_purchasing_org:
          ingestion?.ingestion_config?.sap_purchasing_org ??
          ingestion?.sap_config?.sap_purchasing_org ??
          ingestion?.sap_purchasing_org ??
          DEFAULT_SAP_CONFIG.sap_purchasing_org,
      });
      setSapStatus({
        success: res.success !== false,
        status: res.status || 'ONLINE',
        message: res.message || 'Koneksi SAP OData terverifikasi!',
        latency_ms: res.latency_ms || 40,
      });
    } catch (err) {
      setSapStatus({
        success: false,
        status: 'FAILED',
        message: err.message || 'Gagal menghubungi endpoint SAP.',
      });
    } finally {
      setSapTesting(false);
    }
  }

  // SKU Procurement Rule update
  async function handleSaveSkuRule(e) {
    e.preventDefault();
    if (!editingSku || !selectedStoreId) return;
    try {
      const updated = await api.updateStoreSku(selectedStoreId, editingSku.sku_id, editingSku);
      setSkus(skus.map((s) => (s.sku_id === editingSku.sku_id ? { ...s, ...updated } : s)));
      setSkuModalOpen(false);
      setEditingSku(null);
      showBanner('success', `Aturan pengadaan untuk SKU ${editingSku.sku_name || editingSku.sku_id} berhasil diperbarui!`);
    } catch (err) {
      showBanner('error', `Gagal memperbarui aturan SKU: ${err.message}`);
    }
  }

  // Promo CRUD
  async function handleAddPromo(e) {
    e.preventDefault();
    if (!selectedStoreId || !newPromo.promo_name) return;
    try {
      const created = await api.addStorePromo(selectedStoreId, newPromo);
      setPromos([...promos, created]);
      setPromoModalOpen(false);
      setNewPromo({
        promo_name: '',
        promo_type: 'Diskon Persen',
        start_date: new Date().toISOString().split('T')[0],
        end_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
        target_sku_ids: [],
      });
      showBanner('success', `Promo "${created.promo_name}" berhasil ditambahkan!`);
    } catch (err) {
      showBanner('error', `Gagal menambah promo: ${err.message}`);
    }
  }

  async function handleDeletePromo(promoId) {
    if (!window.confirm('Hapus promo ini dari kalender toko?')) return;
    try {
      await api.deleteStorePromo(selectedStoreId, promoId);
      setPromos(promos.filter((p) => p.promo_id !== promoId));
      showBanner('success', 'Promo berhasil dihapus.');
    } catch (err) {
      showBanner('error', `Gagal menghapus promo: ${err.message}`);
    }
  }

  // Local Event CRUD
  async function handleAddEvent(e) {
    e.preventDefault();
    if (!selectedStoreId || !newEvent.event_name) return;
    try {
      const created = await api.addStoreEvent(selectedStoreId, newEvent);
      setLocalEvents([...localEvents, created]);
      setEventModalOpen(false);
      setNewEvent({
        event_name: '',
        event_date: new Date().toISOString().split('T')[0],
        impact_multiplier: 1.2,
      });
      showBanner('success', `Event "${created.event_name}" berhasil ditambahkan ke agenda!`);
    } catch (err) {
      showBanner('error', `Gagal menambah agenda event: ${err.message}`);
    }
  }

  async function handleDeleteEvent(eventId) {
    if (!window.confirm('Hapus event ini dari agenda toko?')) return;
    try {
      await api.deleteStoreEvent(selectedStoreId, eventId);
      setLocalEvents(localEvents.filter((e) => e.event_id !== eventId));
      showBanner('success', 'Agenda event berhasil dihapus.');
    } catch (err) {
      showBanner('error', `Gagal menghapus agenda event: ${err.message}`);
    }
  }

  // Add New Store
  async function handleCreateStore(e) {
    e.preventDefault();
    if (!newStoreForm.store_id || !newStoreForm.store_name) return;
    try {
      const payload = {
        store_id: newStoreForm.store_id.toUpperCase().trim(),
        store_name: newStoreForm.store_name.trim(),
        area_type: newStoreForm.area_type,
        zone: newStoreForm.zone,
        latitude: parseFloat(newStoreForm.latitude),
        longitude: parseFloat(newStoreForm.longitude),
      };
      await api.addStore(payload);
      showBanner('success', `Cabang baru "${payload.store_name}" berhasil didaftarkan!`);
      setCreateStoreModalOpen(false);
      const updatedList = await api.getStores(false);
      setStores(updatedList);
      setSelectedStoreId(payload.store_id);
    } catch (err) {
      showBanner('error', `Gagal mendaftarkan cabang: ${err.message}`);
    }
  }

  const selectedAreaObj = AREA_TYPE_OPTIONS.find((a) => a.value === profile.area_type) || AREA_TYPE_OPTIONS[0];

  return (
    <div className="space-y-6 pb-20">
      {/* Top Banner Alert */}
      {bannerMessage && (
        <div
          className={`p-4 rounded-2xl border flex items-center justify-between text-sm transition-all duration-300 shadow-xl ${
            bannerMessage.type === 'success'
              ? 'bg-emerald-950/70 border-emerald-500/40 text-emerald-200'
              : 'bg-rose-950/70 border-rose-500/40 text-rose-200'
          }`}
        >
          <div className="flex items-center gap-3">
            {bannerMessage.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
            )}
            <p className="font-medium">{bannerMessage.message}</p>
          </div>
          <button
            onClick={() => setBannerMessage(null)}
            className="text-slate-400 hover:text-white p-1 rounded-lg"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Page Header & Store Selector Bar */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur-md">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Operational Control Center
              </span>
              <span className="text-xs text-slate-400">• Multi-Store Middleware</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight mt-1 flex items-center gap-2">
              <Building2 className="w-6 h-6 text-indigo-400" />
              Pengaturan Operasional & Toko
            </h1>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl">
              Kontrol seluruh parameter penalaran AI, protokol integrasi kasir/ERP, kanal HITL Telegram, serta aturan logistik SKU tanpa konfigurasi manual di cloud.
            </p>
          </div>

          {/* Store Switcher & Global Actions */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <div className="flex items-center bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 focus-within:border-indigo-500 transition">
              <label htmlFor="store-select" className="text-xs text-slate-400 mr-2 font-medium">
                Pilih Toko:
              </label>
              <select
                id="store-select"
                value={selectedStoreId}
                onChange={(e) => setSelectedStoreId(e.target.value)}
                disabled={loading || stores.length === 0}
                className="bg-transparent text-sm font-semibold text-white focus:outline-none cursor-pointer"
              >
                {stores.map((s) => (
                  <option key={s.store_id} value={s.store_id} className="bg-slate-900 text-white">
                    {s.store_name ? `${s.store_name} (${s.store_id})` : s.store_id}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => {
                setNewStoreForm({
                  store_id: `STR-${Math.random().toString(36).substring(2, 6).toUpperCase()}-01`,
                  store_name: '',
                  area_type: 'Komersial / Perkantoran',
                  zone: 'ZONE-SMG-01',
                  latitude: -6.2088,
                  longitude: 106.8456,
                });
                setCreateStoreModalOpen(true);
              }}
              className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 transition"
            >
              <Plus className="w-3.5 h-3.5 text-indigo-400" />
              Tambah Cabang
            </button>

            <button
              onClick={() => loadStoreSettings(selectedStoreId)}
              disabled={refreshing || !selectedStoreId}
              className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 transition disabled:opacity-50"
              title="Muat Ulang Konfigurasi"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-indigo-400' : ''}`} />
            </button>

            <button
              onClick={handleSaveSettings}
              disabled={saving || !selectedStoreId}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/30 transition disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Menyimpan...' : 'Simpan Pengaturan'}
            </button>
          </div>
        </div>

        {/* 5-Tab Navigation Header */}
        <div className="flex border-b border-slate-800 mt-6 gap-1 overflow-x-auto no-scrollbar">
          {[
            { id: 'profile', label: '1. Profil & Geolokasi', icon: MapPin },
            { id: 'ingestion', label: '2. Sumber Data Inventaris', icon: Database },
            { id: 'hitl', label: '3. Kanal HITL Telegram', icon: Send },
            { id: 'skus', label: `4. Aturan Pengadaan SKU (${skus.length})`, icon: Package },
            { id: 'calendar', label: `5. Kalender Promo & Event (${promos.length + localEvents.length})`, icon: Calendar },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold transition border-b-2 whitespace-nowrap ${
                  isActive
                    ? 'border-indigo-500 text-indigo-400 bg-indigo-500/5'
                    : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-400' : 'text-slate-500'}`} />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="space-y-6">
        {/* ============================================================== */}
        {/* TAB 1: PROFIL & GEOLOKASI TOKO */}
        {/* ============================================================== */}
        {activeTab === 'profile' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-5">
                <div className="border-b border-slate-800/80 pb-4">
                  <h3 className="text-base font-semibold text-white flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-indigo-400" />
                    Identitas & Karakter Wilayah Toko
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Konfigurasi metadata toko menentukan baseline perilaku pergerakan konsumen yang digunakan model AI.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                      <Lock className="w-3.5 h-3.5 text-slate-500" />
                      ID Toko (Read-Only)
                    </label>
                    <input
                      type="text"
                      readOnly
                      value={profile.store_id}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-400 font-mono cursor-not-allowed"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Nama Toko / Cabang <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={profile.store_name}
                      onChange={(e) => setProfile({ ...profile, store_name: e.target.value })}
                      placeholder="Contoh: Minimarket Cabang Sentra Bisnis"
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none transition"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Tipe Karakter Wilayah (Area Type) <span className="text-rose-400">*</span>
                  </label>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {AREA_TYPE_OPTIONS.map((opt) => (
                      <div
                        key={opt.value}
                        onClick={() => setProfile({ ...profile, area_type: opt.value })}
                        className={`p-3.5 rounded-xl border cursor-pointer transition flex flex-col justify-between ${
                          profile.area_type === opt.value
                            ? 'bg-indigo-950/40 border-indigo-500 ring-1 ring-indigo-500/50'
                            : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                        }`}
                      >
                        <div>
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-xs font-bold text-white">{opt.label}</span>
                            <Radio
                              className={`w-4 h-4 ${
                                profile.area_type === opt.value ? 'text-indigo-400 fill-indigo-400' : 'text-slate-600'
                              }`}
                            />
                          </div>
                          <p className="text-[11px] text-slate-400 leading-relaxed">{opt.desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800/80">
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                      <MapPin className="w-4 h-4 text-rose-400" />
                      Geolokasi GPS (Koordinat Presisi Cuaca Real-Time)
                    </label>
                    <button
                      type="button"
                      onClick={handleUseCurrentLocation}
                      disabled={locating}
                      className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium bg-slate-800 hover:bg-slate-700 text-indigo-400 rounded-lg border border-slate-700 transition"
                    >
                      <Navigation className={`w-3 h-3 ${locating ? 'animate-spin' : ''}`} />
                      {locating ? 'Mencari GPS...' : 'Gunakan Lokasi Saat Ini'}
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider block mb-1">
                        Latitude
                      </span>
                      <input
                        type="number"
                        step="0.000001"
                        value={profile.latitude}
                        onChange={(e) => setProfile({ ...profile, latitude: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono focus:outline-none transition"
                        placeholder="-6.208800"
                      />
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider block mb-1">
                        Longitude
                      </span>
                      <input
                        type="number"
                        step="0.000001"
                        value={profile.longitude}
                        onChange={(e) => setProfile({ ...profile, longitude: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono focus:outline-none transition"
                        placeholder="106.845600"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                    <Truck className="w-4 h-4 text-amber-400" />
                    Kode Zona Logistik DC (Delivery Zone) <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={profile.delivery_zone}
                    onChange={(e) => setProfile({ ...profile, delivery_zone: e.target.value.toUpperCase() })}
                    placeholder="Contoh: ZONE-SMG-01 atau ZONE-GROB-02"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono focus:outline-none transition"
                  />
                  <p className="text-[11px] text-slate-500 mt-1">
                    Digunakan oleh pusat distribusi (Distribution Center) untuk mengelompokkan armada pengiriman bersama cabang sekitar.
                  </p>
                </div>
              </div>
            </div>

            {/* Side Explainer Card */}
            <div className="space-y-6">
              <div className="bg-gradient-to-br from-indigo-950/40 via-slate-900/60 to-slate-900 border border-indigo-500/20 rounded-2xl p-5 shadow-xl">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-5 h-5 text-indigo-400" />
                  <h4 className="text-sm font-bold text-white">Dampak Penalaran AI</h4>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  AutoReplenish.ai menyesuaikan rekomendasi restock berdasarkan tipe wilayah yang Anda tentukan:
                </p>
                <div className="mt-4 space-y-3">
                  <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl">
                    <div className="text-[11px] font-bold text-blue-400">Pola Komersial</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      Meningkatkan kuota minuman siap saji, kopi, dan makanan ringan saat awal pekan (Senin - Rabu).
                    </div>
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl">
                    <div className="text-[11px] font-bold text-emerald-400">Pola Residensial</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      Meningkatkan stok beras, minyak goreng, dan telur 2 hari sebelum akhir pekan.
                    </div>
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl">
                    <div className="text-[11px] font-bold text-amber-400">Pola Pasar / Sub-Urban</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      Sinkron dengan hari pasaran adat lokal untuk mencegah kehabisan stok barang pokok saat pedagang luar datang.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 2: SUMBER DATA INVENTARIS (INGESTION MODE) */}
        {/* ============================================================== */}
        {activeTab === 'ingestion' && (
          <IntegrationErrorBoundary>
            <div className="space-y-6">
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-6">
                <div>
                  <h3 className="text-base font-semibold text-white flex items-center gap-2">
                    <Database className="w-5 h-5 text-indigo-400" />
                    Mode Ingestion & Integrasi Inventaris
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Tentukan bagaimana toko ini mengirimkan posisi stok dan penjualan ke AutoReplenish.ai.
                  </p>
                </div>

                {/* Ingestion Mode Toggle Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div
                    onClick={() =>
                      setIngestion((prev) => ({
                        ...prev,
                        mode: 'POS_WEBHOOK',
                        ingestion_mode: 'POS_WEBHOOK',
                        pos_config: {
                          ...DEFAULT_POS_CONFIG,
                          ...prev?.pos_config,
                        },
                        ingestion_config: {
                          ...DEFAULT_POS_CONFIG,
                          ...prev?.ingestion_config,
                          mode: 'POS_WEBHOOK',
                        },
                      }))
                    }
                    className={`p-5 rounded-2xl border cursor-pointer transition ${
                      isPosMode
                        ? 'bg-indigo-950/40 border-indigo-500 ring-1 ring-indigo-500'
                        : 'bg-slate-950/50 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <ShoppingBag className="w-5 h-5 text-indigo-400" />
                        <span className="text-sm font-bold text-white">Mode A: Ritel Kecil / Toserba</span>
                      </div>
                      <Radio className={`w-4 h-4 ${isPosMode ? 'text-indigo-400' : 'text-slate-600'}`} />
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Integrasi ringan menggunakan <b>POS Kasir Lokal</b> (Moka, Pawoon, Olsera, iReap, dsb.) via webhook real-time atau sinkronisasi harian.
                    </p>
                  </div>

                  <div
                    onClick={() =>
                      setIngestion((prev) => ({
                        ...prev,
                        mode: 'SAP_ODATA',
                        ingestion_mode: 'SAP_S4HANA',
                        sap_config: {
                          ...DEFAULT_SAP_CONFIG,
                          ...prev?.sap_config,
                        },
                        ingestion_config: {
                          ...DEFAULT_SAP_CONFIG,
                          ...prev?.ingestion_config,
                          mode: 'SAP_ODATA',
                        },
                      }))
                    }
                    className={`p-5 rounded-2xl border cursor-pointer transition ${
                      isSapMode
                        ? 'bg-indigo-950/40 border-indigo-500 ring-1 ring-indigo-500'
                        : 'bg-slate-950/50 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Server className="w-4 h-4 text-blue-400" />
                        <span className="text-sm font-bold text-white">Mode B: Ritel Korporat / Berjejaring</span>
                      </div>
                      <Radio className={`w-4 h-4 ${isSapMode ? 'text-blue-400' : 'text-slate-600'}`} />
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Integrasi tingkat enterprise langsung dengan <b>SAP S/4HANA OData v2/v4</b> dan generate Purchase Requisition otomatis.
                    </p>
                  </div>
                </div>

                {/* Mode A Details */}
                {isPosMode && (
                  <div className="bg-slate-950/80 border border-slate-800/80 rounded-2xl p-5 space-y-4">
                    <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                      <Zap className="w-4 h-4 text-amber-400" />
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                        Konfigurasi Webhook Kasir POS Lokal
                      </h4>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">
                          Tipe Konektor POS
                        </label>
                        <select
                          value={ingestion?.ingestion_config?.pos_connector_type ?? ingestion?.pos_connector_type ?? 'REST Webhook'}
                          onChange={(e) => {
                            const val = e.target.value;
                            setIngestion((prev) => ({
                              ...prev,
                              pos_connector_type: val,
                              ingestion_config: {
                                ...prev?.ingestion_config,
                                pos_connector_type: val,
                              },
                              pos_config: {
                                ...prev?.pos_config,
                                pos_connector_type: val,
                              },
                            }));
                          }}
                          className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                        >
                          <option value="REST Webhook">REST Webhook (Real-time Event)</option>
                          <option value="Direct DB Sync">Direct DB Sync (MySQL/PostgreSQL)</option>
                          <option value="CSV/JSON Auto-Import">CSV/JSON Auto-Import (Daily Export)</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 text-slate-400" />
                          Jadwal Sinkronisasi Penutupan Toko
                        </label>
                        <input
                          type="text"
                          value={ingestion?.ingestion_config?.pos_sync_schedule ?? ingestion?.pos_sync_schedule ?? ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            setIngestion((prev) => ({
                              ...prev,
                              pos_sync_schedule: val,
                              ingestion_config: {
                                ...prev?.ingestion_config,
                                pos_sync_schedule: val,
                              },
                              pos_config: {
                                ...prev?.pos_config,
                                pos_sync_schedule: val,
                              },
                            }));
                          }}
                          placeholder="Contoh: 21:00 / Saat Tutup Toko"
                          className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                        />
                      </div>
                    </div>

                    {/* Webhook Endpoint & Secret */}
                    <div className="space-y-3 pt-2">
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center justify-between">
                          <span>Webhook Ingestion URL (Pasang di POS Kasir)</span>
                          {copiedWebhook && <span className="text-[10px] text-emerald-400 font-bold">Disalin ke Clipboard!</span>}
                        </label>
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            readOnly
                            value={ingestion?.ingestion_config?.pos_webhook_url ?? ingestion?.pos_webhook_url ?? ''}
                            className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-300 font-mono"
                          />
                          <button
                            type="button"
                            onClick={() => copyToClipboard(ingestion?.ingestion_config?.pos_webhook_url ?? ingestion?.pos_webhook_url ?? '', 'webhook')}
                            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 flex items-center gap-1.5 transition"
                          >
                            <Copy className="w-3.5 h-3.5 text-indigo-400" />
                            Salin
                          </button>
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center justify-between">
                          <span>API Secret Key (Header: X-POS-Secret-Key)</span>
                          {copiedSecret && <span className="text-[10px] text-emerald-400 font-bold">Disalin ke Clipboard!</span>}
                        </label>
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            readOnly
                            value={ingestion?.ingestion_config?.pos_secret_key ?? ingestion?.pos_secret_key ?? ''}
                            className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-300 font-mono"
                          />
                          <button
                            type="button"
                            onClick={() => copyToClipboard(ingestion?.ingestion_config?.pos_secret_key ?? ingestion?.pos_secret_key ?? '', 'secret')}
                            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 flex items-center gap-1.5 transition"
                          >
                            <Copy className="w-3.5 h-3.5 text-indigo-400" />
                            Salin
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Mode B Details */}
                {isSapMode && (
                  <div className="bg-slate-950/80 border border-slate-800/80 rounded-2xl p-5 space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <div className="flex items-center gap-2">
                        <Server className="w-4 h-4 text-blue-400" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                          Parameter SAP S/4HANA (Enterprise Gateway)
                        </h4>
                      </div>

                      <button
                        type="button"
                        onClick={handleTestSap}
                        disabled={sapTesting}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 text-xs font-semibold rounded-xl border border-blue-500/30 transition disabled:opacity-50"
                      >
                        <Activity className={`w-3.5 h-3.5 ${sapTesting ? 'animate-spin' : ''}`} />
                        {sapTesting ? 'Melakukan Handshake...' : 'Uji Koneksi SAP (Ping OData)'}
                      </button>
                    </div>

                    {/* SAP Ping Status Result */}
                    {sapStatus && (
                      <div
                        className={`p-3 rounded-xl border text-xs flex items-center justify-between ${
                          sapStatus.success
                            ? 'bg-emerald-950/50 border-emerald-500/30 text-emerald-300'
                            : 'bg-rose-950/50 border-rose-500/30 text-rose-300'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          {sapStatus.success ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                          ) : (
                            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                          )}
                          <span>{sapStatus.message}</span>
                        </div>
                        {sapStatus.latency_ms && (
                          <span className="font-mono text-[10px] bg-slate-900/60 px-2 py-0.5 rounded border border-slate-700">
                            {sapStatus.latency_ms} ms
                          </span>
                        )}
                      </div>
                    )}

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        SAP OData Service URL (PRD Section 11.9)
                      </label>
                      <input
                        type="text"
                        value={ingestion?.ingestion_config?.sap_odata_url ?? ingestion?.sap_config?.sap_odata_url ?? ingestion?.sap_odata_url ?? ''}
                        onChange={(e) => {
                          const val = e.target.value;
                          setIngestion((prev) => ({
                            ...prev,
                            sap_odata_url: val,
                            ingestion_config: {
                              ...prev?.ingestion_config,
                              sap_odata_url: val,
                            },
                            sap_config: {
                              ...prev?.sap_config,
                              sap_odata_url: val,
                            },
                          }));
                        }}
                        placeholder="https://sap-server.corp:44300/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV"
                        className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none"
                      />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">OAuth Token URL</label>
                        <input
                          type="text"
                          value={ingestion?.ingestion_config?.sap_token_url ?? ingestion?.sap_config?.sap_token_url ?? ingestion?.sap_token_url ?? ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            setIngestion((prev) => ({
                              ...prev,
                              sap_token_url: val,
                              ingestion_config: {
                                ...prev?.ingestion_config,
                                sap_token_url: val,
                              },
                              sap_config: {
                                ...prev?.sap_config,
                                sap_token_url: val,
                              },
                            }));
                          }}
                          placeholder="https://oauth.corp/token"
                          className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">OAuth Client ID</label>
                        <input
                          type="text"
                          value={ingestion?.ingestion_config?.sap_client_id ?? ingestion?.sap_config?.sap_client_id ?? ingestion?.sap_client_id ?? ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            setIngestion((prev) => ({
                              ...prev,
                              sap_client_id: val,
                              ingestion_config: {
                                ...prev?.ingestion_config,
                                sap_client_id: val,
                              },
                              sap_config: {
                                ...prev?.sap_config,
                                sap_client_id: val,
                              },
                            }));
                          }}
                          placeholder="autoreplenish_sap_client"
                          className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center justify-between">
                          <span>Client Secret</span>
                          <button
                            type="button"
                            onClick={() => setShowSapSecret(!showSapSecret)}
                            className="text-[10px] text-slate-400 hover:text-white"
                          >
                            {showSapSecret ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                          </button>
                        </label>
                        <input
                          type={showSapSecret ? 'text' : 'password'}
                          value={ingestion?.ingestion_config?.sap_client_secret ?? ingestion?.sap_config?.sap_client_secret ?? ingestion?.sap_client_secret ?? ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            setIngestion((prev) => ({
                              ...prev,
                              sap_client_secret: val,
                              ingestion_config: {
                                ...prev?.ingestion_config,
                                sap_client_secret: val,
                              },
                              sap_config: {
                                ...prev?.sap_config,
                                sap_client_secret: val,
                              },
                            }));
                          }}
                          placeholder="••••••••••••••••"
                          className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">SAP Plant Code</label>
                        <input
                          type="text"
                          value={ingestion?.ingestion_config?.sap_plant ?? ingestion?.sap_config?.sap_plant ?? ingestion?.sap_plant ?? ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            setIngestion((prev) => ({
                              ...prev,
                              sap_plant: val,
                              ingestion_config: {
                                ...prev?.ingestion_config,
                                sap_plant: val,
                              },
                              sap_config: {
                                ...prev?.sap_config,
                                sap_plant: val,
                              },
                            }));
                          }}
                          placeholder="1000"
                          className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">Storage Location (SLoc)</label>
                        <input
                          type="text"
                          value={ingestion?.ingestion_config?.sap_storage_location ?? ingestion?.sap_config?.sap_storage_location ?? ingestion?.sap_storage_location ?? ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            setIngestion((prev) => ({
                              ...prev,
                              sap_storage_location: val,
                              ingestion_config: {
                                ...prev?.ingestion_config,
                                sap_storage_location: val,
                              },
                              sap_config: {
                                ...prev?.sap_config,
                                sap_storage_location: val,
                              },
                            }));
                          }}
                          placeholder="WH01"
                          className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">Purchasing Org</label>
                        <input
                          type="text"
                          value={ingestion?.ingestion_config?.sap_purchasing_org ?? ingestion?.sap_config?.sap_purchasing_org ?? ingestion?.sap_purchasing_org ?? ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            setIngestion((prev) => ({
                              ...prev,
                              sap_purchasing_org: val,
                              ingestion_config: {
                                ...prev?.ingestion_config,
                                sap_purchasing_org: val,
                              },
                              sap_config: {
                                ...prev?.sap_config,
                                sap_purchasing_org: val,
                              },
                            }));
                          }}
                          placeholder="1000"
                          className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none"
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </IntegrationErrorBoundary>
        )}

        {/* ============================================================== */}
        {/* TAB 3: KANAL VALIDASI KEPALA TOKO (HITL) */}
        {/* ============================================================== */}
        {activeTab === 'hitl' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-6">
                <div>
                  <h3 className="text-base font-semibold text-white flex items-center gap-2">
                    <Send className="w-5 h-5 text-indigo-400" />
                    Kanal Persetujuan Human-in-the-Loop (Telegram)
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Kartu interaktif berisi rekomendasi restock akan dikirimkan langsung ke Telegram Kepala Toko untuk diverifikasi sebelum terbit Purchase Requisition.
                  </p>
                </div>

                {/* Test Telegram Status */}
                {telegramStatus && (
                  <div
                    className={`p-3 rounded-xl border text-xs flex items-center justify-between ${
                      telegramStatus.success
                        ? 'bg-emerald-950/50 border-emerald-500/30 text-emerald-300'
                        : 'bg-rose-950/50 border-rose-500/30 text-rose-300'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {telegramStatus.success ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      ) : (
                        <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                      )}
                      <span>{telegramStatus.message}</span>
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center justify-between">
                    <span>Telegram Chat ID / Supergroup ID</span>
                    <span className="text-[10px] text-slate-500">Dapat berupa ID pengguna atau ID grup operasional (-100xxx)</span>
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={hitl.telegram_chat_id}
                      onChange={(e) => setHitl({ ...hitl, telegram_chat_id: e.target.value })}
                      placeholder="Contoh: 1181431005 atau -100123456789"
                      className="flex-1 bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono focus:outline-none transition"
                    />
                    <button
                      type="button"
                      onClick={handleTestTelegram}
                      disabled={telegramTesting || !hitl.telegram_chat_id}
                      className="flex items-center gap-1.5 px-3.5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-blue-600/20 transition disabled:opacity-50"
                    >
                      <Send className={`w-3.5 h-3.5 ${telegramTesting ? 'animate-spin' : ''}`} />
                      {telegramTesting ? 'Mengirim...' : 'Kirim Pesan Tes ke Telegram'}
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 pt-2 border-t border-slate-800/80">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-amber-400" />
                      Toleransi Waktu Persetujuan (Timeout Tolerance)
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min="1"
                        max="24"
                        value={hitl.timeout_tolerance_hours}
                        onChange={(e) => setHitl({ ...hitl, timeout_tolerance_hours: parseInt(e.target.value) || 4 })}
                        className="w-24 bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2 text-xs text-white font-mono text-center focus:outline-none transition"
                      />
                      <span className="text-xs text-slate-400">Jam sebelum order kedaluwarsa</span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1.5">
                      Batas toleransi memastikan pesanan tidak kedaluwarsa melewati jam cut-off penutupan pesanan distributor harian.
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-2">
                      Pengingat Otomatis (Auto-Reminder)
                    </label>
                    <div
                      onClick={() => setHitl({ ...hitl, enable_auto_reminder: !hitl.enable_auto_reminder })}
                      className="flex items-center gap-3 p-3 bg-slate-950 border border-slate-800 rounded-xl cursor-pointer hover:border-slate-700 transition"
                    >
                      <input
                        type="checkbox"
                        checked={hitl.enable_auto_reminder}
                        onChange={() => {}}
                        className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0 cursor-pointer"
                      />
                      <div className="text-xs text-slate-300">
                        <span className="font-semibold text-white block">Kirim Pengingat 1 Jam Sebelum Batas</span>
                        <span className="text-[11px] text-slate-500">Notifikasi lonceng ke Telegram jika kartu belum ditindaklanjuti.</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Side Explainer Card */}
            <div className="space-y-6">
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl">
                <h4 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
                  <HelpCircle className="w-4 h-4 text-indigo-400" />
                  Cara Mendapatkan Telegram Chat ID
                </h4>
                <ol className="text-xs text-slate-400 space-y-2 list-decimal list-inside leading-relaxed">
                  <li>
                    Kirim pesan ke bot pencari ID, misalnya <b className="text-slate-300">@userinfobot</b> di aplikasi Telegram Anda.
                  </li>
                  <li>
                    Salin angka <b className="text-indigo-400 font-mono">Id</b> Anda (misal: 1181431005).
                  </li>
                  <li>
                    Kirim pesan <b className="text-slate-300">/start</b> ke bot resmi AutoReplenish.ai agar bot memiliki izin mengirimkan pesan ke akun Anda.
                  </li>
                  <li>
                    Masukkan ID tersebut pada input di samping lalu tekan <b>[Kirim Pesan Tes ke Telegram]</b>.
                  </li>
                </ol>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 4: ATURAN PENGADAAN PER SKU */}
        {/* ============================================================== */}
        {activeTab === 'skus' && (
          <div className="space-y-4">
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
                <div>
                  <h3 className="text-base font-semibold text-white flex items-center gap-2">
                    <Package className="w-5 h-5 text-indigo-400" />
                    Aturan Pengadaan & Logistik per SKU (Procurement Rules)
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Atur batas threshold aman, lead time supplier, MOQ kemasan, dan toleransi kedaluwarsa produk segar untuk toko ini.
                  </p>
                </div>
              </div>

              {/* SKU Rules Table */}
              <div className="overflow-x-auto border border-slate-800 rounded-xl">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950/80 text-slate-400 font-bold uppercase tracking-wider text-[10px] border-b border-slate-800">
                    <tr>
                      <th className="px-4 py-3">SKU & Kategori</th>
                      <th className="px-4 py-3">Safety Stock</th>
                      <th className="px-4 py-3">Lead Time</th>
                      <th className="px-4 py-3">Delivery Window (Hari)</th>
                      <th className="px-4 py-3">MOQ & Kemasan</th>
                      <th className="px-4 py-3">Barang Segar / Expiry</th>
                      <th className="px-4 py-3 text-right">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {skus.length === 0 ? (
                      <tr>
                        <td colSpan="7" className="px-4 py-8 text-center text-slate-500">
                          Belum ada SKU terdaftar pada toko ini.
                        </td>
                      </tr>
                    ) : (
                      skus.map((sku) => (
                        <tr key={sku.sku_id} className="hover:bg-slate-800/30 transition">
                          <td className="px-4 py-3.5">
                            <div className="font-bold text-white">{sku.sku_name || sku.sku_id}</div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="font-mono text-[10px] text-slate-400">{sku.sku_id}</span>
                              <span className="px-1.5 py-0.5 text-[9px] rounded font-semibold bg-slate-800 text-indigo-300 border border-slate-700">
                                {sku.category || 'FMCG'}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3.5 font-mono">
                            <span className="text-amber-400 font-bold">{sku.safety_stock_threshold ?? 20}</span> unit
                          </td>
                          <td className="px-4 py-3.5 font-mono">
                            <span className="text-slate-200">{sku.supplier_lead_time_days ?? 2}</span> hari
                          </td>
                          <td className="px-4 py-3.5">
                            <div className="flex flex-wrap gap-1 max-w-[200px]">
                              {(sku.delivery_window || ['Senin', 'Rabu', 'Jumat']).map((day) => (
                                <span
                                  key={day}
                                  className="px-1.5 py-0.5 text-[10px] rounded bg-slate-800/80 text-slate-300 font-medium"
                                >
                                  {day.slice(0, 3)}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-4 py-3.5 font-mono">
                            <div>MOQ: <span className="text-white font-bold">{sku.moq ?? 1}</span></div>
                            <div className="text-[11px] text-slate-400">Kelipatan: {sku.packaging_multiple ?? 1} pcs/dus</div>
                          </td>
                          <td className="px-4 py-3.5">
                            {sku.is_perishable ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                                Segar ({sku.shelf_life_days ?? 3} hari)
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-800 text-slate-400">
                                Awet / Kering
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3.5 text-right">
                            <button
                              onClick={() => {
                                setEditingSku({
                                  ...sku,
                                  delivery_window: sku.delivery_window || ['Senin', 'Rabu', 'Jumat'],
                                });
                                setSkuModalOpen(true);
                              }}
                              className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-indigo-400 rounded-lg text-xs font-semibold transition inline-flex items-center gap-1"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                              Edit
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 5: KALENDER PROMO & EVENT LOKAL */}
        {/* ============================================================== */}
        {activeTab === 'calendar' && (
          <div className="space-y-6">
            {/* Sub-panel A: Katalog Promo Aktif */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
                <div>
                  <h3 className="text-base font-semibold text-white flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-indigo-400" />
                    Sub-panel A: Katalog Promo Aktif
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Kampanye diskon ritel yang meningkatkan laju penjualan SKU target selama periode promo berjalan.
                  </p>
                </div>
                <button
                  onClick={() => setPromoModalOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/20 transition self-start sm:self-auto"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Tambah Promo Baru
                </button>
              </div>

              <div className="overflow-x-auto border border-slate-800 rounded-xl">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950/80 text-slate-400 font-bold uppercase tracking-wider text-[10px] border-b border-slate-800">
                    <tr>
                      <th className="px-4 py-3">Nama Promo</th>
                      <th className="px-4 py-3">Tipe Promo</th>
                      <th className="px-4 py-3">Periode Tanggal</th>
                      <th className="px-4 py-3">SKU Target</th>
                      <th className="px-4 py-3 text-right">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {promos.length === 0 ? (
                      <tr>
                        <td colSpan="5" className="px-4 py-6 text-center text-slate-500">
                          Tidak ada promo aktif untuk toko ini saat ini.
                        </td>
                      </tr>
                    ) : (
                      promos.map((p) => (
                        <tr key={p.promo_id} className="hover:bg-slate-800/30 transition">
                          <td className="px-4 py-3.5 font-bold text-white">{p.promo_name}</td>
                          <td className="px-4 py-3.5">
                            <span className="px-2 py-0.5 rounded font-semibold text-[10px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                              {p.promo_type}
                            </span>
                          </td>
                          <td className="px-4 py-3.5 font-mono text-[11px] text-slate-300">
                            {p.start_date} s/d {p.end_date}
                          </td>
                          <td className="px-4 py-3.5">
                            <div className="flex flex-wrap gap-1">
                              {(p.target_sku_ids && p.target_sku_ids.length > 0) ? (
                                p.target_sku_ids.map((skuId) => (
                                  <span key={skuId} className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 font-mono">
                                    {skuId}
                                  </span>
                                ))
                              ) : (
                                <span className="text-[11px] text-slate-500 italic">Semua SKU</span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3.5 text-right">
                            <button
                              onClick={() => handleDeletePromo(p.promo_id)}
                              className="p-1.5 hover:bg-rose-950/40 text-slate-400 hover:text-rose-400 rounded-lg transition"
                              title="Hapus Promo"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Sub-panel B: Agenda Event & Dinamika Lokal */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
                <div>
                  <h3 className="text-base font-semibold text-white flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-amber-400" />
                    Sub-panel B: Agenda Event & Dinamika Lokal
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Hari pasaran adat lokal, pekan gajian, atau festival warga yang memicu faktor lonjakan belanja (impact multiplier).
                  </p>
                </div>
                <button
                  onClick={() => setEventModalOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-amber-600/20 transition self-start sm:self-auto"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Tambah Agenda Event
                </button>
              </div>

              <div className="overflow-x-auto border border-slate-800 rounded-xl">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950/80 text-slate-400 font-bold uppercase tracking-wider text-[10px] border-b border-slate-800">
                    <tr>
                      <th className="px-4 py-3">Nama Agenda / Event</th>
                      <th className="px-4 py-3">Tanggal Pelaksanaan</th>
                      <th className="px-4 py-3">Faktor Lonjakan (Impact Multiplier)</th>
                      <th className="px-4 py-3 text-right">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {localEvents.length === 0 ? (
                      <tr>
                        <td colSpan="4" className="px-4 py-6 text-center text-slate-500">
                          Tidak ada agenda event terdaftar untuk toko ini.
                        </td>
                      </tr>
                    ) : (
                      localEvents.map((ev) => (
                        <tr key={ev.event_id} className="hover:bg-slate-800/30 transition">
                          <td className="px-4 py-3.5 font-bold text-white">{ev.event_name}</td>
                          <td className="px-4 py-3.5 font-mono text-[11px] text-slate-300">{ev.event_date}</td>
                          <td className="px-4 py-3.5">
                            <span className="px-2 py-0.5 rounded font-bold text-[11px] bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">
                              {ev.impact_multiplier}x Lonjakan
                            </span>
                          </td>
                          <td className="px-4 py-3.5 text-right">
                            <button
                              onClick={() => handleDeleteEvent(ev.event_id)}
                              className="p-1.5 hover:bg-rose-950/40 text-slate-400 hover:text-rose-400 rounded-lg transition"
                              title="Hapus Event"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ============================================================== */}
      {/* MODAL: EDIT SKU PROCUREMENT RULES */}
      {/* ============================================================== */}
      {skuModalOpen && editingSku && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl p-6 shadow-2xl space-y-5 overflow-y-auto max-h-[90vh]">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">Edit Aturan Pengadaan SKU</h3>
                <p className="text-xs text-indigo-400 font-mono mt-0.5">
                  {editingSku.sku_name} ({editingSku.sku_id})
                </p>
              </div>
              <button onClick={() => setSkuModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveSkuRule} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Kategori Produk</label>
                  <select
                    value={editingSku.category}
                    onChange={(e) => setEditingSku({ ...editingSku, category: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                  >
                    {SKU_CATEGORIES.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Safety Stock Threshold (Unit)
                  </label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={editingSku.safety_stock_threshold}
                    onChange={(e) =>
                      setEditingSku({ ...editingSku, safety_stock_threshold: parseInt(e.target.value) || 0 })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Lead Time (Hari)</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={editingSku.supplier_lead_time_days}
                    onChange={(e) =>
                      setEditingSku({ ...editingSku, supplier_lead_time_days: parseInt(e.target.value) || 1 })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">MOQ Suplier</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={editingSku.moq}
                    onChange={(e) => setEditingSku({ ...editingSku, moq: parseInt(e.target.value) || 1 })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Kelipatan Kemasan</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={editingSku.packaging_multiple}
                    onChange={(e) =>
                      setEditingSku({ ...editingSku, packaging_multiple: parseInt(e.target.value) || 1 })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              {/* Delivery Window Checkboxes */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Delivery Window (Hari Kedatangan Truk Suplier)
                </label>
                <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
                  {DAYS_OF_WEEK.map((day) => {
                    const isSelected = (editingSku.delivery_window || []).includes(day);
                    return (
                      <button
                        type="button"
                        key={day}
                        onClick={() => {
                          const current = editingSku.delivery_window || [];
                          const updated = isSelected ? current.filter((d) => d !== day) : [...current, day];
                          setEditingSku({ ...editingSku, delivery_window: updated });
                        }}
                        className={`py-1.5 text-center text-xs font-bold rounded-lg border transition ${
                          isSelected
                            ? 'bg-indigo-600 border-indigo-500 text-white shadow'
                            : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                        }`}
                      >
                        {day.slice(0, 3)}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Fresh / Perishable Settings */}
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs font-bold text-white block">Parameter Produk Segar / Mudah Rusak</span>
                    <span className="text-[11px] text-slate-400">Aktifkan untuk membatasi order tidak melebihi masa simpan.</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={editingSku.is_perishable || false}
                    onChange={(e) => setEditingSku({ ...editingSku, is_perishable: e.target.checked })}
                    className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0 cursor-pointer"
                  />
                </div>

                {editingSku.is_perishable && (
                  <div className="pt-2 border-t border-slate-800/80">
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Masa Kedaluwarsa / Shelf Life (Hari)
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={editingSku.shelf_life_days || 3}
                      onChange={(e) =>
                        setEditingSku({ ...editingSku, shelf_life_days: parseInt(e.target.value) || 3 })
                      }
                      className="w-32 bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setSkuModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/20 transition"
                >
                  Simpan Aturan SKU
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: ADD PROMO */}
      {/* ============================================================== */}
      {promoModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                Tambah Promo Aktif
              </h3>
              <button onClick={() => setPromoModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddPromo} className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Nama Promo</label>
                <input
                  type="text"
                  required
                  placeholder="Contoh: Diskon Gajian Akhir Pekan (JSM)"
                  value={newPromo.promo_name}
                  onChange={(e) => setNewPromo({ ...newPromo, promo_name: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Tipe Promo</label>
                <select
                  value={newPromo.promo_type}
                  onChange={(e) => setNewPromo({ ...newPromo, promo_type: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                >
                  {PROMO_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Mulai</label>
                  <input
                    type="date"
                    required
                    value={newPromo.start_date}
                    onChange={(e) => setNewPromo({ ...newPromo, start_date: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Berakhir</label>
                  <input
                    type="date"
                    required
                    value={newPromo.end_date}
                    onChange={(e) => setNewPromo({ ...newPromo, end_date: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Target SKU (Pisahkan koma, kosongkan untuk semua)
                </label>
                <input
                  type="text"
                  placeholder="Contoh: SKU-BIMOLI-1L, SKU-INDOMIE-GORENG"
                  value={(newPromo.target_sku_ids || []).join(', ')}
                  onChange={(e) =>
                    setNewPromo({
                      ...newPromo,
                      target_sku_ids: e.target.value
                        .split(',')
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setPromoModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/20 transition"
                >
                  Tambahkan Promo
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: ADD LOCAL COMMUNITY EVENT */}
      {/* ============================================================== */}
      {eventModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Calendar className="w-4 h-4 text-amber-400" />
                Tambah Agenda Event Lokal
              </h3>
              <button onClick={() => setEventModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddEvent} className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Nama Event</label>
                <input
                  type="text"
                  required
                  placeholder="Contoh: Pasar Kliwon / Pesta Rakyat Desa"
                  value={newEvent.event_name}
                  onChange={(e) => setNewEvent({ ...newEvent, event_name: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Tanggal Event</label>
                <input
                  type="date"
                  required
                  value={newEvent.event_date}
                  onChange={(e) => setNewEvent({ ...newEvent, event_date: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Estimasi Faktor Lonjakan Permintaan
                </label>
                <select
                  value={newEvent.impact_multiplier}
                  onChange={(e) => setNewEvent({ ...newEvent, impact_multiplier: parseFloat(e.target.value) })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                >
                  {MULTIPLIER_OPTIONS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setEventModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-amber-600/20 transition"
                >
                  Tambahkan Event
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: DAFTARKAN CABANG BARU */}
      {/* ============================================================== */}
      {createStoreModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Building2 className="w-5 h-5 text-indigo-400" />
                Daftarkan Cabang Retail Baru
              </h3>
              <button onClick={() => setCreateStoreModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateStore} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Store ID <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="STR-JKT-02"
                    value={newStoreForm.store_id}
                    onChange={(e) => setNewStoreForm({ ...newStoreForm, store_id: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500 uppercase"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Nama Cabang <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Minimarket Cabang Barat"
                    value={newStoreForm.store_name}
                    onChange={(e) => setNewStoreForm({ ...newStoreForm, store_name: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Karakter Wilayah</label>
                <select
                  value={newStoreForm.area_type}
                  onChange={(e) => setNewStoreForm({ ...newStoreForm, area_type: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                >
                  {AREA_TYPE_OPTIONS.map((a) => (
                    <option key={a.value} value={a.value}>
                      {a.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Zona DC</label>
                  <input
                    type="text"
                    required
                    value={newStoreForm.zone}
                    onChange={(e) => setNewStoreForm({ ...newStoreForm, zone: e.target.value.toUpperCase() })}
                    placeholder="ZONE-SMG-01"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Latitude</label>
                  <input
                    type="number"
                    step="0.000001"
                    value={newStoreForm.latitude}
                    onChange={(e) => setNewStoreForm({ ...newStoreForm, latitude: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Longitude</label>
                  <input
                    type="number"
                    step="0.000001"
                    value={newStoreForm.longitude}
                    onChange={(e) => setNewStoreForm({ ...newStoreForm, longitude: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setCreateStoreModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/20 transition"
                >
                  Daftarkan Toko
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
