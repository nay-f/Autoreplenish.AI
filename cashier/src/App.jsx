import React, { useState, useEffect } from 'react';
import {
  ShoppingCart,
  Trash2,
  Plus,
  Minus,
  CreditCard,
  Banknote,
  QrCode,
  Store,
  Send,
  Settings,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  X,
  Receipt,
  Search,
  ArrowRight,
  TrendingUp,
  Package,
  Layers,
  Sparkles,
  ExternalLink,
} from 'lucide-react';
import { INITIAL_CATALOG } from './data/initialCatalog';

export default function App() {
  // -------------------------------------------------------------
  // State Initialization with LocalStorage Persistence
  // -------------------------------------------------------------
  const [catalog, setCatalog] = useState(() => {
    try {
      const saved = localStorage.getItem('autoreplenish_pos_catalog');
      if (saved) return JSON.parse(saved);
    } catch (e) {
      console.warn('Failed to parse catalog from localStorage', e);
    }
    return INITIAL_CATALOG;
  });

  const [cart, setCart] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('Semua');

  const [settings, setSettings] = useState(() => {
    try {
      const saved = localStorage.getItem('autoreplenish_pos_settings');
      if (saved) return JSON.parse(saved);
    } catch (e) {
      console.warn('Failed to parse settings from localStorage', e);
    }
    return {
      store_id: 'STR-COMMERCIAL-01',
      webhook_url: 'http://localhost:8000/api/v1/ingest/pos/STR-COMMERCIAL-01',
      secret_key: 'sec_str_commercial_01_live',
    };
  });

  const [transactions, setTransactions] = useState(() => {
    try {
      const saved = localStorage.getItem('autoreplenish_pos_transactions');
      if (saved) return JSON.parse(saved);
    } catch (e) {
      console.warn('Failed to parse transactions', e);
    }
    return [];
  });

  // Modals & UI States
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState('CASH'); // CASH, QRIS, DEBIT
  const [cashAmountGiven, setCashAmountGiven] = useState('');
  const [lastReceipt, setLastReceipt] = useState(null);

  // Sync Status Feedback
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncStatus, setSyncStatus] = useState(null); // { type: 'SUCCESS' | 'ERROR', message: '', details: null }

  // Save changes to localStorage
  useEffect(() => {
    localStorage.setItem('autoreplenish_pos_catalog', JSON.stringify(catalog));
  }, [catalog]);

  useEffect(() => {
    localStorage.setItem('autoreplenish_pos_settings', JSON.stringify(settings));
  }, [settings]);

  useEffect(() => {
    localStorage.setItem('autoreplenish_pos_transactions', JSON.stringify(transactions));
  }, [transactions]);

  // Handle changing store_id in settings automatically updates webhook_url default
  const handleStoreIdChange = (newStoreId) => {
    const updatedUrl = settings.webhook_url.replace(
      /\/ingest\/pos\/[^/]+$/,
      `/ingest/pos/${newStoreId}`
    );
    const updatedSecret = `sec_${newStoreId.toLowerCase().replace(/-/g, '_')}_live`;
    setSettings((prev) => ({
      ...prev,
      store_id: newStoreId,
      webhook_url: updatedUrl.includes('/ingest/pos/') ? updatedUrl : `http://localhost:8000/api/v1/ingest/pos/${newStoreId}`,
      secret_key: prev.secret_key.startsWith('sec_') ? updatedSecret : prev.secret_key,
    }));
  };

  // -------------------------------------------------------------
  // Cart Actions
  // -------------------------------------------------------------
  const addToCart = (product) => {
    if (product.current_physical_stock <= 0) return;

    setCart((prev) => {
      const existing = prev.find((item) => item.sku_id === product.sku_id);
      if (existing) {
        if (existing.qty >= product.current_physical_stock) {
          return prev; // Cannot exceed physical stock
        }
        return prev.map((item) =>
          item.sku_id === product.sku_id ? { ...item, qty: item.qty + 1 } : item
        );
      }
      return [
        ...prev,
        {
          sku_id: product.sku_id,
          sku_name: product.sku_name,
          price: product.price,
          unit: product.unit,
          emoji: product.emoji,
          qty: 1,
          maxStock: product.current_physical_stock,
        },
      ];
    });
  };

  const updateCartQty = (skuId, delta) => {
    setCart((prev) =>
      prev
        .map((item) => {
          if (item.sku_id !== skuId) return item;
          const product = catalog.find((p) => p.sku_id === skuId);
          const max = product ? product.current_physical_stock : item.maxStock;
          const newQty = item.qty + delta;
          if (newQty > max) return item;
          return { ...item, qty: newQty };
        })
        .filter((item) => item.qty > 0)
    );
  };

  const removeFromCart = (skuId) => {
    setCart((prev) => prev.filter((item) => item.sku_id !== skuId));
  };

  const clearCart = () => setCart([]);

  const cartTotal = cart.reduce((sum, item) => sum + item.price * item.qty, 0);
  const cartItemCount = cart.reduce((sum, item) => sum + item.qty, 0);

  // -------------------------------------------------------------
  // Transaction Payment ("Bayar Transaksi")
  // -------------------------------------------------------------
  const handleOpenPayment = () => {
    if (cart.length === 0) return;
    setCashAmountGiven(cartTotal.toString());
    setIsPaymentModalOpen(true);
  };

  const handleConfirmPayment = () => {
    if (cart.length === 0) return;

    // 1. Deduct local physical stock and increment daily_sales_qty
    const updatedCatalog = catalog.map((item) => {
      const cartItem = cart.find((c) => c.sku_id === item.sku_id);
      if (cartItem) {
        const remaining = Math.max(0, item.current_physical_stock - cartItem.qty);
        const newDailySales = (item.daily_sales_qty || 0) + cartItem.qty;
        return {
          ...item,
          current_physical_stock: remaining,
          daily_sales_qty: newDailySales,
        };
      }
      return item;
    });

    setCatalog(updatedCatalog);

    // 2. Record Transaction
    const receiptData = {
      trx_id: `TRX-${Date.now().toString().slice(-6)}`,
      timestamp: new Date().toISOString(),
      store_id: settings.store_id,
      items: [...cart],
      total: cartTotal,
      payment_method: selectedPaymentMethod,
      amount_paid: Number(cashAmountGiven) || cartTotal,
      change: Math.max(0, (Number(cashAmountGiven) || cartTotal) - cartTotal),
    };

    setTransactions((prev) => [receiptData, ...prev]);
    setLastReceipt(receiptData);
    setCart([]);
    setIsPaymentModalOpen(false);
  };

  // -------------------------------------------------------------
  // Closing Shift & Sync ("Tutup Toko & Sinkronkan")
  // -------------------------------------------------------------
  const handleTriggerSync = async () => {
    setSyncLoading(true);
    setSyncStatus(null);

    const payload = {
      store_id: settings.store_id,
      timestamp: new Date().toISOString(),
      sync_type: 'CLOSING_SHIFT',
      inventory: catalog.map((item) => ({
        sku_id: item.sku_id,
        current_physical_stock: item.current_physical_stock,
        daily_sales_qty: item.daily_sales_qty,
      })),
    };

    try {
      const response = await fetch(settings.webhook_url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-POS-Secret-Key': settings.secret_key,
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => ({}));

      if (response.ok && (data.status === 'SUCCESS' || data.status === 'success')) {
        setSyncStatus({
          type: 'SUCCESS',
          message: data.message || 'Inventory synced successfully',
          items_updated: data.items_updated || catalog.length,
          timestamp: new Date().toLocaleTimeString('id-ID'),
        });
      } else {
        setSyncStatus({
          type: 'ERROR',
          message: data.detail || data.error || `HTTP ${response.status}: Sinkronisasi ditolak server`,
          code: response.status,
        });
      }
    } catch (err) {
      console.error('POS Sync fetch error:', err);
      setSyncStatus({
        type: 'ERROR',
        message: `Koneksi Terputus: Tidak dapat menghubungi ${settings.webhook_url}. Pastikan server backend aktif.`,
      });
    } finally {
      setSyncLoading(false);
    }
  };

  // Reset to initial catalogue (for testing)
  const handleResetCatalog = () => {
    if (window.confirm('Reset seluruh stok barang ke katalog awal percontohan?')) {
      setCatalog(INITIAL_CATALOG);
      setCart([]);
      setTransactions([]);
      localStorage.removeItem('autoreplenish_pos_catalog');
      localStorage.removeItem('autoreplenish_pos_transactions');
    }
  };

  // Categories list
  const categories = ['Semua', 'Bakery / Perishable', 'Sembako / Bahan Pokok', 'Minyak & Bumbu Dapur', 'Minuman Segar'];

  // Filtered catalog
  const filteredProducts = catalog.filter((product) => {
    const matchesSearch =
      product.sku_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      product.sku_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory =
      selectedCategory === 'Semua' || product.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  // Daily revenue summary
  const totalRevenueToday = transactions.reduce((sum, t) => sum + t.total, 0);
  const totalItemsSoldToday = catalog.reduce((sum, item) => sum + (item.daily_sales_qty || 0), 0);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* --------------------------------------------------------- */}
      {/* 1. TOP HEADER / NAVBAR */}
      {/* --------------------------------------------------------- */}
      <header className="bg-slate-900/90 backdrop-blur-md border-b border-slate-800 sticky top-0 z-30 px-4 lg:px-6 py-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Brand & Store Badge */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Store className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-lg tracking-tight text-white">AutoReplenish</span>
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-semibold">
                  POS CASHIER
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span>Toko:</span>
                <span className="font-mono text-slate-200 font-semibold">{settings.store_id}</span>
                <span className="text-slate-600">•</span>
                <span className="text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  Terminal Siap
                </span>
              </div>
            </div>
          </div>

          {/* Metrics summary */}
          <div className="hidden md:flex items-center gap-4 bg-slate-950/60 px-4 py-1.5 rounded-xl border border-slate-800/80 text-xs">
            <div>
              <span className="text-slate-400 block text-[10px] uppercase tracking-wider font-semibold">Omzet Hari Ini</span>
              <span className="font-mono font-bold text-emerald-400 text-sm">
                Rp {totalRevenueToday.toLocaleString('id-ID')}
              </span>
            </div>
            <div className="h-6 w-px bg-slate-800"></div>
            <div>
              <span className="text-slate-400 block text-[10px] uppercase tracking-wider font-semibold">Barang Terjual</span>
              <span className="font-mono font-bold text-slate-200 text-sm">
                {totalItemsSoldToday} <span className="text-xs font-normal text-slate-400">pcs</span>
              </span>
            </div>
            <div className="h-6 w-px bg-slate-800"></div>
            <div>
              <span className="text-slate-400 block text-[10px] uppercase tracking-wider font-semibold">Transaksi</span>
              <span className="font-mono font-bold text-indigo-400 text-sm">{transactions.length}</span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="px-3.5 py-2 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/80 text-xs font-medium text-slate-200 flex items-center gap-2 transition shadow-sm hover:text-white"
              title="Pengaturan Koneksi Webhook AutoReplenish"
            >
              <Settings className="w-4 h-4 text-slate-400" />
              <span className="hidden sm:inline">Pengaturan Toko</span>
            </button>

            <button
              onClick={() => {
                setSyncStatus(null);
                setIsSyncModalOpen(true);
              }}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-semibold flex items-center gap-2 transition shadow-lg shadow-emerald-600/25 active:scale-95"
            >
              <Send className="w-4 h-4" />
              <span>Tutup Toko & Sinkronkan</span>
            </button>
          </div>
        </div>
      </header>

      {/* --------------------------------------------------------- */}
      {/* 2. MAIN LAYOUT: CATALOG (LEFT) & CART (RIGHT) */}
      {/* --------------------------------------------------------- */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Left Column: Product Catalog Grid */}
        <main className="flex-1 p-4 lg:p-6 overflow-y-auto flex flex-col gap-4">
          {/* Search & Category Filter Bar */}
          <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
            {/* Search Input */}
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Cari SKU atau nama produk sembako..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Category tabs */}
            <div className="flex gap-1.5 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition ${
                    selectedCategory === cat
                      ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20'
                      : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-slate-800/80'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* Product Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-4 gap-4">
            {filteredProducts.map((product) => {
              const inCartItem = cart.find((c) => c.sku_id === product.sku_id);
              const inCartQty = inCartItem ? inCartItem.qty : 0;
              const remainingAvailable = product.current_physical_stock - inCartQty;
              const isOutOfStock = product.current_physical_stock <= 0;

              return (
                <div
                  key={product.sku_id}
                  className={`group bg-slate-900 rounded-2xl border transition-all flex flex-col overflow-hidden ${
                    isOutOfStock
                      ? 'border-red-950/40 opacity-70 bg-slate-900/50'
                      : remainingAvailable <= 5
                      ? 'border-amber-500/30 hover:border-amber-500/60 shadow-lg shadow-amber-950/20'
                      : 'border-slate-800/80 hover:border-slate-700 hover:shadow-xl hover:shadow-black/40'
                  }`}
                >
                  {/* Card Header & Badges */}
                  <div className="p-4 flex items-start justify-between gap-3 border-b border-slate-800/60 bg-slate-900/40">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-slate-800 flex items-center justify-center text-2xl shadow-inner border border-slate-700/50 group-hover:scale-105 transition">
                        {product.emoji}
                      </div>
                      <div>
                        <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                          {product.sku_id}
                        </span>
                        <h3 className="font-bold text-sm text-slate-100 mt-1 line-clamp-1 group-hover:text-emerald-400 transition">
                          {product.sku_name}
                        </h3>
                      </div>
                    </div>
                  </div>

                  {/* Card Body */}
                  <div className="p-4 flex-1 flex flex-col justify-between gap-3">
                    <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                      {product.description}
                    </p>

                    {/* Stock Indicators */}
                    <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/60 flex items-center justify-between text-xs">
                      <div>
                        <span className="text-[10px] uppercase font-semibold text-slate-500 block">Sisa Stok Fisik</span>
                        <span
                          className={`font-mono font-bold text-sm ${
                            product.current_physical_stock === 0
                              ? 'text-red-400'
                              : product.current_physical_stock < 15
                              ? 'text-amber-400'
                              : 'text-emerald-400'
                          }`}
                        >
                          {product.current_physical_stock}{' '}
                          <span className="text-xs font-normal text-slate-400">{product.unit}</span>
                        </span>
                      </div>

                      <div className="text-right">
                        <span className="text-[10px] uppercase font-semibold text-slate-500 block">Terjual Hari Ini</span>
                        <span className="font-mono font-bold text-slate-300 text-sm">
                          {product.daily_sales_qty || 0}{' '}
                          <span className="text-xs font-normal text-slate-500">{product.unit}</span>
                        </span>
                      </div>
                    </div>

                    {/* Price and Add Button */}
                    <div className="flex items-center justify-between pt-1">
                      <div>
                        <span className="text-[10px] uppercase font-semibold text-slate-500 block">Harga Satuan</span>
                        <span className="text-base font-extrabold text-white font-mono">
                          Rp {product.price.toLocaleString('id-ID')}
                        </span>
                      </div>

                      <button
                        onClick={() => addToCart(product)}
                        disabled={remainingAvailable <= 0}
                        className={`px-3.5 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition ${
                          remainingAvailable <= 0
                            ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                            : inCartQty > 0
                            ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/30 active:scale-95'
                            : 'bg-slate-800 hover:bg-emerald-600 hover:text-white text-emerald-400 border border-slate-700 hover:border-emerald-500 transition active:scale-95'
                        }`}
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>{inCartQty > 0 ? `+ Tambah (${inCartQty})` : 'Pilih'}</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {filteredProducts.length === 0 && (
            <div className="p-12 text-center bg-slate-900/40 rounded-2xl border border-slate-800/80">
              <Package className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <h4 className="text-base font-semibold text-slate-300">Produk Tidak Ditemukan</h4>
              <p className="text-xs text-slate-500 mt-1">Coba sesuaikan kata kunci pencarian atau kategori filter.</p>
            </div>
          )}
        </main>

        {/* --------------------------------------------------------- */}
        {/* Right Column: POS CART & CHECKOUT PANEL */}
        {/* --------------------------------------------------------- */}
        <aside className="w-full lg:w-96 xl:w-[420px] bg-slate-900 border-t lg:border-t-0 lg:border-l border-slate-800 flex flex-col h-auto lg:h-[calc(100vh-65px)]">
          {/* Cart Header */}
          <div className="p-4 border-b border-slate-800/80 flex items-center justify-between bg-slate-900/80">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <ShoppingCart className="w-4 h-4" />
              </div>
              <div>
                <h2 className="font-bold text-sm text-white">Keranjang Kasir</h2>
                <span className="text-[11px] text-slate-400">
                  {cartItemCount} item ({cart.length} SKU)
                </span>
              </div>
            </div>

            {cart.length > 0 && (
              <button
                onClick={clearCart}
                className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1 transition px-2 py-1 rounded-lg hover:bg-red-500/10"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Kosongkan</span>
              </button>
            )}
          </div>

          {/* Cart Items List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {cart.length === 0 ? (
              <div className="h-full min-h-[220px] flex flex-col items-center justify-center text-center text-slate-500">
                <ShoppingCart className="w-12 h-12 stroke-[1.2] text-slate-700 mb-2" />
                <p className="text-sm font-medium text-slate-400">Keranjang Masih Kosong</p>
                <p className="text-xs text-slate-600 mt-0.5 max-w-xs">
                  Klik barang di katalog sebelah kiri untuk memulai transaksi baru.
                </p>
              </div>
            ) : (
              cart.map((item) => (
                <div
                  key={item.sku_id}
                  className="bg-slate-950/80 p-3 rounded-xl border border-slate-800/80 flex items-center justify-between gap-3 shadow-sm hover:border-slate-700 transition"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="text-xl">{item.emoji}</span>
                    <div className="min-w-0">
                      <h4 className="text-xs font-bold text-slate-200 truncate">{item.sku_name}</h4>
                      <div className="text-[11px] font-mono text-emerald-400 font-semibold">
                        Rp {item.price.toLocaleString('id-ID')}
                      </div>
                    </div>
                  </div>

                  {/* Quantity adjustment buttons */}
                  <div className="flex items-center gap-2">
                    <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5">
                      <button
                        onClick={() => updateCartQty(item.sku_id, -1)}
                        className="w-6 h-6 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800 rounded transition"
                      >
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="w-7 text-center font-mono font-bold text-xs text-white">
                        {item.qty}
                      </span>
                      <button
                        onClick={() => updateCartQty(item.sku_id, 1)}
                        disabled={item.qty >= item.maxStock}
                        className={`w-6 h-6 flex items-center justify-center rounded transition ${
                          item.qty >= item.maxStock
                            ? 'text-slate-600 cursor-not-allowed'
                            : 'text-slate-400 hover:text-white hover:bg-slate-800'
                        }`}
                      >
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>

                    <div className="w-20 text-right font-mono font-bold text-xs text-white">
                      Rp {(item.price * item.qty).toLocaleString('id-ID')}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Cart Bill Summary & Pay Button */}
          <div className="p-4 border-t border-slate-800 bg-slate-950/90 space-y-3">
            <div className="space-y-1.5 text-xs text-slate-400">
              <div className="flex justify-between">
                <span>Subtotal Barang:</span>
                <span className="font-mono text-slate-200 font-semibold">
                  Rp {cartTotal.toLocaleString('id-ID')}
                </span>
              </div>
              <div className="flex justify-between">
                <span>PPN 0% (Sembako Bebas Pajak):</span>
                <span className="font-mono text-slate-400">Rp 0</span>
              </div>
              <div className="h-px bg-slate-800 my-1"></div>
              <div className="flex justify-between items-baseline text-sm font-bold text-white">
                <span>Total Pembayaran:</span>
                <span className="font-mono text-lg text-emerald-400 font-extrabold">
                  Rp {cartTotal.toLocaleString('id-ID')}
                </span>
              </div>
            </div>

            <button
              onClick={handleOpenPayment}
              disabled={cart.length === 0}
              className={`w-full py-3.5 px-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition shadow-lg ${
                cart.length === 0
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/30 active:scale-[0.98]'
              }`}
            >
              <CreditCard className="w-4 h-4" />
              <span>Bayar Transaksi (Checkout)</span>
            </button>
          </div>
        </aside>
      </div>

      {/* --------------------------------------------------------- */}
      {/* 3. MODAL: PAYMENT CHECKOUT */}
      {/* --------------------------------------------------------- */}
      {isPaymentModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-5 animate-in fade-in duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <Receipt className="w-5 h-5 text-emerald-400" />
                <h3 className="font-bold text-base text-white">Pembayaran Kasir</h3>
              </div>
              <button
                onClick={() => setIsPaymentModalOpen(false)}
                className="text-slate-400 hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80 text-center">
              <span className="text-xs uppercase font-semibold text-slate-400 tracking-wider">Total Tagihan</span>
              <div className="text-2xl font-black font-mono text-emerald-400 mt-1">
                Rp {cartTotal.toLocaleString('id-ID')}
              </div>
              <span className="text-xs text-slate-500 mt-0.5 block">{cartItemCount} item sembako</span>
            </div>

            {/* Payment Method Selector */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300">Pilih Metode Pembayaran:</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'CASH', label: 'Tunai', icon: Banknote },
                  { id: 'QRIS', label: 'QRIS', icon: QrCode },
                  { id: 'DEBIT', label: 'Debit', icon: CreditCard },
                ].map((m) => {
                  const Icon = m.icon;
                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => setSelectedPaymentMethod(m.id)}
                      className={`p-3 rounded-xl border flex flex-col items-center gap-1.5 transition text-xs font-semibold ${
                        selectedPaymentMethod === m.id
                          ? 'bg-emerald-500/10 border-emerald-500 text-emerald-400 shadow-sm'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      <span>{m.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {selectedPaymentMethod === 'CASH' && (
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300">Uang Diterima (Rp):</label>
                <input
                  type="number"
                  value={cashAmountGiven}
                  onChange={(e) => setCashAmountGiven(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-base font-mono text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
                {Number(cashAmountGiven) >= cartTotal && (
                  <div className="flex justify-between text-xs text-emerald-400 font-mono bg-emerald-500/10 p-2.5 rounded-lg border border-emerald-500/20">
                    <span>Kembalian:</span>
                    <span className="font-bold">
                      Rp {(Number(cashAmountGiven) - cartTotal).toLocaleString('id-ID')}
                    </span>
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setIsPaymentModalOpen(false)}
                className="flex-1 py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleConfirmPayment}
                className="flex-1 py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white transition shadow-lg shadow-emerald-600/30"
              >
                Konfirmasi Pembayaran
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------- */}
      {/* 4. MODAL: RECEIPT POPUP */}
      {/* --------------------------------------------------------- */}
      {lastReceipt && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-4 animate-in fade-in">
            <div className="text-center space-y-1">
              <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center mx-auto mb-2">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-lg text-white">Transaksi Berhasil!</h3>
              <p className="text-xs text-slate-400 font-mono">No: {lastReceipt.trx_id}</p>
            </div>

            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>Toko:</span>
                <span className="text-slate-200 font-mono font-semibold">{lastReceipt.store_id}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Metode:</span>
                <span className="text-emerald-400 font-semibold">{lastReceipt.payment_method}</span>
              </div>
              <div className="h-px bg-slate-800 my-1"></div>
              {lastReceipt.items.map((it) => (
                <div key={it.sku_id} className="flex justify-between text-slate-300">
                  <span>
                    {it.sku_name} x{it.qty}
                  </span>
                  <span className="font-mono">Rp {(it.price * it.qty).toLocaleString('id-ID')}</span>
                </div>
              ))}
              <div className="h-px bg-slate-800 my-1"></div>
              <div className="flex justify-between font-bold text-sm text-white pt-1">
                <span>Total:</span>
                <span className="text-emerald-400 font-mono">Rp {lastReceipt.total.toLocaleString('id-ID')}</span>
              </div>
              {lastReceipt.payment_method === 'CASH' && (
                <div className="flex justify-between text-slate-400 text-[11px]">
                  <span>Kembalian:</span>
                  <span className="font-mono">Rp {lastReceipt.change.toLocaleString('id-ID')}</span>
                </div>
              )}
            </div>

            <button
              onClick={() => setLastReceipt(null)}
              className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-200 transition"
            >
              Tutup Struk
            </button>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------- */}
      {/* 5. MODAL: SETTINGS (WEBHOOK & SECRET KEY) */}
      {/* --------------------------------------------------------- */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5 animate-in fade-in">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <Settings className="w-5 h-5 text-emerald-400" />
                <h3 className="font-bold text-base text-white">Pengaturan Koneksi Toko POS</h3>
              </div>
              <button onClick={() => setIsSettingsOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="font-semibold text-slate-300 block mb-1.5">Store ID Toko Aktif:</label>
                <select
                  value={settings.store_id}
                  onChange={(e) => handleStoreIdChange(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 font-mono"
                >
                  <option value="STR-COMMERCIAL-01">STR-COMMERCIAL-01 (Minimarket Sentra Bisnis)</option>
                  <option value="STR-RESIDENTIAL-01">STR-RESIDENTIAL-01 (Minimarket Cabang Residensial)</option>
                  <option value="STR-SUBURBAN-02">STR-SUBURBAN-02 (Minimarket Perumahan Mandiri)</option>
                </select>
              </div>

              <div>
                <label className="font-semibold text-slate-300 block mb-1.5">Webhook Ingestion URL (AutoReplenish.ai):</label>
                <input
                  type="text"
                  value={settings.webhook_url}
                  onChange={(e) => setSettings({ ...settings, webhook_url: e.target.value })}
                  placeholder="http://localhost:8000/api/v1/ingest/pos/STR-COMMERCIAL-01"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-slate-200 font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
                <span className="text-[11px] text-slate-500 mt-1 block">
                  Endpoint ingestion POS di cloud atau runner lokal FastAPI.
                </span>
              </div>

              <div>
                <label className="font-semibold text-slate-300 block mb-1.5">API Secret Key (X-POS-Secret-Key):</label>
                <input
                  type="text"
                  value={settings.secret_key}
                  onChange={(e) => setSettings({ ...settings, secret_key: e.target.value })}
                  placeholder="sec_str_commercial_01_live"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-slate-200 font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
                <span className="text-[11px] text-slate-500 mt-1 block">
                  Kunci otorisasi toko untuk validasi header <code>X-POS-Secret-Key</code>.
                </span>
              </div>

              <div className="pt-2 border-t border-slate-800 flex justify-between items-center">
                <button
                  type="button"
                  onClick={handleResetCatalog}
                  className="text-xs text-amber-400 hover:text-amber-300 underline"
                >
                  Reset Stok ke Katalog Awal
                </button>

                <button
                  type="button"
                  onClick={() => setIsSettingsOpen(false)}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition"
                >
                  Simpan & Tutup
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------- */}
      {/* 6. MODAL: CLOSING SHIFT & SYNC TO AUTOREPLENISH.AI */}
      {/* --------------------------------------------------------- */}
      {isSyncModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 animate-in fade-in">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <Send className="w-5 h-5 text-emerald-400" />
                <h3 className="font-bold text-base text-white">Penutupan Toko & Sinkronisasi POS</h3>
              </div>
              <button
                onClick={() => setIsSyncModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Tindakan ini akan mengirimkan sisa stok fisik riil dan total penjualan harian (
              <span className="text-slate-200 font-mono">daily_sales_qty</span>) untuk seluruh katalog ke Webhook Ingestion AutoReplenish.ai.
            </p>

            {/* Inventory payload preview */}
            <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800/80 space-y-2 max-h-48 overflow-y-auto">
              <span className="text-[10px] uppercase font-semibold text-slate-500 block">Ringkasan Data Sinkronisasi:</span>
              <div className="divide-y divide-slate-800/60 text-xs">
                {catalog.map((item) => (
                  <div key={item.sku_id} className="py-1.5 flex justify-between items-center text-slate-300">
                    <div>
                      <span className="font-mono text-slate-400">{item.sku_id}</span> - {item.sku_name}
                    </div>
                    <div className="font-mono text-right">
                      <span className="text-emerald-400 font-semibold">{item.current_physical_stock} {item.unit}</span>
                      <span className="text-slate-500 text-[11px] ml-2">(jual: {item.daily_sales_qty || 0})</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Sync Feedback Alert */}
            {syncStatus && (
              <div
                className={`p-3.5 rounded-xl border flex items-start gap-3 text-xs ${
                  syncStatus.type === 'SUCCESS'
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                    : 'bg-red-500/10 border-red-500/30 text-red-300'
                }`}
              >
                {syncStatus.type === 'SUCCESS' ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                )}
                <div>
                  <h4 className="font-bold">
                    {syncStatus.type === 'SUCCESS' ? 'Sinkronisasi Berhasil!' : 'Sinkronisasi Gagal!'}
                  </h4>
                  <p className="mt-0.5 text-slate-300">{syncStatus.message}</p>
                  {syncStatus.type === 'SUCCESS' && (
                    <span className="text-[11px] text-emerald-400/80 block mt-1">
                      Waktu kirim: {syncStatus.timestamp} • {syncStatus.items_updated} SKU diperbarui di database
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setIsSyncModalOpen(false)}
                className="flex-1 py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition"
              >
                Tutup
              </button>
              <button
                type="button"
                onClick={handleTriggerSync}
                disabled={syncLoading}
                className="flex-1 py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-xs font-bold text-white transition flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/25 disabled:opacity-50"
              >
                {syncLoading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Mengirim ke Webhook...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    <span>Kirim Sinkronisasi Sekarang</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
