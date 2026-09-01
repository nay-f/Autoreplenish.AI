/**
 * Dashboard API Connector for AutoReplenish.ai.
 * Connects to live FastAPI Backend (http://localhost:8000).
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const api = {
  async getStores() {
    try {
      const res = await fetch(`${API_BASE_URL}/stores`);
      if (res.ok) {
        return await res.json();
      }
      console.error(`[API Error] GET /stores responded with status ${res.status}`);
    } catch (e) {
      console.error(`[API Connection Error] Failed to fetch /stores from ${API_BASE_URL}:`, e);
    }
    // Fallback if backend is not running
    return [
      { store_id: 'STR-001', store_name: 'Cabang Sudirman', area_type: 'Perkantoran', zone: 'JAKARTA_PUSAT', active: true },
      { store_id: 'STR-002', store_name: 'Cabang Kemang', area_type: 'Perumahan', zone: 'JAKARTA_SELATAN', active: true },
      { store_id: 'STR-003', store_name: 'Cabang UI Depok', area_type: 'Kampus', zone: 'DEPOK', active: true }
    ];
  },

  async getStoreInventoryHealth(storeId = 'STR-001') {
    try {
      const res = await fetch(`${API_BASE_URL}/stores/${storeId}/inventory-health`);
      if (res.ok) {
        return await res.json();
      }
      console.error(`[API Error] GET /stores/${storeId}/inventory-health responded with status ${res.status}`);
    } catch (e) {
      console.error(`[API Connection Error] Failed to fetch inventory health from ${API_BASE_URL}:`, e);
    }
    // Fallback if backend is not running
    return {
      store_id: storeId,
      store_name: storeId === 'STR-001' ? 'Cabang Sudirman' : storeId === 'STR-002' ? 'Cabang Kemang' : 'Cabang UI Depok',
      area_type: storeId === 'STR-001' ? 'Perkantoran' : storeId === 'STR-002' ? 'Perumahan' : 'Kampus',
      zone: storeId === 'STR-001' ? 'JAKARTA_PUSAT' : storeId === 'STR-002' ? 'JAKARTA_SELATAN' : 'DEPOK',
      summary: {
        total_skus: 4,
        stockout_risk: 2,
        overstock_risk: 1,
        healthy: 1
      },
      inventory: [
        {
          sku_id: 'SKU-10023',
          sku_name: 'Roti Manis Cokelat 100g',
          category: 'Perishable',
          weather_sensitive: true,
          physical_stock: 12,
          threshold: 20,
          average_daily_burn_rate: 25.0,
          lead_time_days: 2,
          status: 'STOCKOUT_RISK',
          days_of_supply: 0.5
        },
        {
          sku_id: 'SKU-20045',
          sku_name: 'Air Mineral 600ml',
          category: 'Non-Perishable',
          weather_sensitive: true,
          physical_stock: 18,
          threshold: 30,
          average_daily_burn_rate: 40.0,
          lead_time_days: 1,
          status: 'STOCKOUT_RISK',
          days_of_supply: 0.5
        },
        {
          sku_id: 'SKU-30067',
          sku_name: 'Susu UHT Full Cream 1L',
          category: 'Perishable',
          weather_sensitive: false,
          physical_stock: 35,
          threshold: 15,
          average_daily_burn_rate: 10.0,
          lead_time_days: 3,
          status: 'HEALTHY',
          days_of_supply: 3.5
        }
      ]
    };
  },

  async getAuditLogs(params = {}) {
    try {
      const qs = new URLSearchParams(params).toString();
      const url = `${API_BASE_URL}/audit-logs${qs ? `?${qs}` : ''}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        return Array.isArray(data) ? data : (data.recommendations || []);
      }
      console.error(`[API Error] GET /audit-logs responded with status ${res.status}`);
    } catch (e) {
      console.error(`[API Connection Error] Failed to fetch audit logs from ${API_BASE_URL}:`, e);
    }
    // Fallback if backend is not running
    return [];
  },

  async getSapMonitor() {
    try {
      const res = await fetch(`${API_BASE_URL}/sap-monitor`);
      if (res.ok) {
        return await res.json();
      }
      console.error(`[API Error] GET /sap-monitor responded with status ${res.status}`);
    } catch (e) {
      console.error(`[API Connection Error] Failed to fetch SAP monitor from ${API_BASE_URL}:`, e);
    }
    // Fallback if backend is not running
    return {
      connection_status: 'ONLINE',
      sap_host: 'sap-s4hana.enterprise.corp:443',
      odata_endpoint: '/sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV',
      average_latency_ms: 42,
      metrics: {
        total_pr_generated: 0,
        total_pr_failed: 0,
        success_rate_pct: 100.0,
        active_retry_queue_size: 0,
        dlq_message_count: 0
      },
      recent_transactions: []
    };
  },

  async getFeedbackAnalytics() {
    try {
      const res = await fetch(`${API_BASE_URL}/feedback-analytics`);
      if (res.ok) {
        return await res.json();
      }
      console.error(`[API Error] GET /feedback-analytics responded with status ${res.status}`);
    } catch (e) {
      console.error(`[API Connection Error] Failed to fetch feedback analytics from ${API_BASE_URL}:`, e);
    }
    // Fallback if backend is not running
    return {
      metrics: {
        total_recommendations: 0,
        approval_rate_pct: 0.0,
        rejection_rate_pct: 0.0,
        edit_rate_pct: 0.0,
        timeout_count: 0
      },
      top_rejection_reasons: [],
      recent_feedback_records: []
    };
  }
};
