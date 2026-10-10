/**
 * Dashboard API Connector for AutoReplenish.ai.
 *
 * Connects to live production/demo backend:
 *   - Local server    -> http://localhost:8000  (demo/scripts/05_dashboard_api.py)
 *   - AWS deployment  -> https://<api-id>.execute-api.<region>.amazonaws.com
 *                        (API Gateway -> dashboard_api Lambda)
 *
 * CRITICAL RULE: Zero silent mocks. If the backend is unreachable or returns an error,
 * this connector throws explicit errors so the UI displays transparent degraded-state
 * banners and error diagnostics instead of fabricating fake data.
 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

// API Gateway base URLs include `/api/v1`; local FastAPI servers accept both direct and prefixed routes.
const isApiGateway = API_BASE_URL.includes('execute-api');
const API_PREFIX = (isApiGateway ? '/api/v1' : (import.meta.env.VITE_API_PREFIX || '')).replace(/\/$/, '');

export const apiConfig = {
  baseUrl: API_BASE_URL,
  prefix: API_PREFIX,
  isApiGateway,
};

/**
 * Last connection failure snapshot for reactive banners and status components.
 */
let lastApiError = null;

export function getLastApiError() {
  return lastApiError;
}

function url(path) {
  // Prevent double slashes when joining
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  if (API_PREFIX && cleanPath.startsWith(API_PREFIX)) {
    return `${API_BASE_URL}${cleanPath}`;
  }
  return `${API_BASE_URL}${API_PREFIX}${cleanPath}`;
}

function fail(endpoint, status, message, method = 'GET') {
  lastApiError = { endpoint, status, message, method, timestamp: new Date().toISOString() };
  console.error(`[API Error] ${method} ${endpoint} -> ${message}`);
  return new Error(message);
}

async function request(path, options = {}) {
  lastApiError = null;
  const method = options.method || 'GET';
  const startedAt = performance.now();

  try {
    const token = typeof window !== 'undefined' ? localStorage.getItem('ar_token') : null;
    const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

    const fetchOptions = {
      method,
      headers: {
        Accept: 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...authHeaders,
        ...options.headers,
      },
    };

    if (options.body) {
      fetchOptions.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }

    const res = await fetch(url(path), fetchOptions);

    if (!res.ok) {
      const detail = await res.text().catch(() => '');
      throw fail(
        path,
        res.status,
        `HTTP ${res.status} ${res.statusText}${detail ? ` - ${detail.slice(0, 200)}` : ''}`,
        method
      );
    }

    const payload = await res.json();
    return { data: payload, latencyMs: Math.round(performance.now() - startedAt) };
  } catch (e) {
    if (!lastApiError) {
      throw fail(path, 0, `Tidak dapat menghubungi ${API_BASE_URL} - ${e.message}`, method);
    }
    throw e;
  }
}

export const api = {
  /** Authentication login */
  async login(credentials) {
    const { data } = await request('/api/v1/auth/login', {
      method: 'POST',
      body: credentials,
    });
    return data;
  },

  /** Get current authenticated user profile */
  async getMe() {
    const { data } = await request('/api/v1/auth/me');
    return data;
  },

  /** Health probe used by the UI banner */
  async health() {
    return api.getRaw('/health');
  },

  /** Integration diagnostic ping (AWS Bedrock, OpenWeatherMap, Telegram, SAP, POS) */
  async getIntegrationHealth() {
    const { data } = await request('/api/v1/health/integrations');
    return data;
  },

  /** Raw GET for endpoints that return non-JSON or raw error bodies */
  async getRaw(path) {
    lastApiError = null;
    const res = await fetch(url(path));
    if (!res.ok) {
      throw fail(path, res.status, `HTTP ${res.status} ${res.statusText}`, 'GET');
    }
    return res.json();
  },

  /** Retrieve list of retail stores from master DB */
  async getStores(activeOnly = false) {
    const qs = activeOnly ? '?active_only=true' : '?active_only=false';
    const { data } = await request(`/stores${qs}`);
    return Array.isArray(data) ? data : (data?.data ?? []);
  },

  /** Register new store */
  async addStore(storeData) {
    const { data } = await request('/stores', {
      method: 'POST',
      body: storeData,
    });
    return data;
  },

  /** Update existing store profile */
  async updateStore(storeId, storeData) {
    const { data } = await request(`/stores/${encodeURIComponent(storeId)}`, {
      method: 'PUT',
      body: storeData,
    });
    return data;
  },

  /** Trigger live end-to-end evaluation pipeline on-demand */
  async triggerEvaluation(storeId) {
    const { data } = await request(`/api/v1/evaluate/${encodeURIComponent(storeId)}`, {
      method: 'POST',
    });
    return data;
  },

  /** Inventory health summary and item details for a specific store */
  async getStoreInventoryHealth(storeId = 'STR-COMMERCIAL-01') {
    const { data } = await request(`/stores/${encodeURIComponent(storeId)}/inventory-health`);
    return data;
  },

  /** Audit log history */
  async getAuditLogs(params = {}) {
    const qs = new URLSearchParams(params).toString();
    const { data } = await request(`/audit-logs${qs ? `?${qs}` : ''}`);
    return Array.isArray(data) ? data : (data?.recommendations ?? data?.data ?? []);
  },

  /** Detailed AI reasoning trace for a specific replenishment request */
  async getAuditLogDetail(requestId) {
    if (!requestId) throw new Error('requestId is required');
    const { data } = await request(`/audit-logs/${encodeURIComponent(requestId)}`);
    return data;
  },

  /** Live SAP connection status & Purchase Requisitions created */
  async getSapMonitor() {
    const { data } = await request('/sap-monitor');
    return data;
  },

  /** Human feedback and managerial override loop analytics */
  async getFeedbackAnalytics() {
    const { data } = await request('/feedback-analytics');
    return data;
  },

  /** Get full store operational settings (5 modules) */
  async getStoreSettings(storeId) {
    if (!storeId) throw new Error('storeId is required');
    const { data } = await request(`/stores/${encodeURIComponent(storeId)}/settings`);
    return data;
  },

  /** Update store operational settings (metadata, ingestion, hitl) */
  async updateStoreSettings(storeId, settings) {
    if (!storeId) throw new Error('storeId is required');
    const { data } = await request(`/stores/${encodeURIComponent(storeId)}/settings`, {
      method: 'PUT',
      body: settings,
    });
    return data;
  },

  /** Get SKU procurement rules for a store */
  async getStoreSkus(storeId) {
    if (!storeId) throw new Error('storeId is required');
    const { data } = await request(`/stores/${encodeURIComponent(storeId)}/skus`);
    return Array.isArray(data) ? data : (data?.data ?? []);
  },

  /** Update procurement rule for a specific SKU */
  async updateStoreSku(storeId, skuId, ruleData) {
    if (!storeId || !skuId) throw new Error('storeId and skuId are required');
    const { data } = await request(`/stores/${encodeURIComponent(storeId)}/skus/${encodeURIComponent(skuId)}`, {
      method: 'PUT',
      body: ruleData,
    });
    return data;
  },

  /** Add active promotional event for a store */
  async addStorePromo(storeId, promoData) {
    if (!storeId) throw new Error('storeId is required');
    const { data } = await request(`/stores/${encodeURIComponent(storeId)}/promos`, {
      method: 'POST',
      body: promoData,
    });
    return data;
  },

  /** Delete promotional event from a store */
  async deleteStorePromo(storeId, promoId) {
    if (!storeId || !promoId) throw new Error('storeId and promoId are required');
    const { data } = await request(`/stores/${encodeURIComponent(storeId)}/promos/${encodeURIComponent(promoId)}`, {
      method: 'DELETE',
    });
    return data;
  },

  /** Add local community event for a store */
  async addStoreEvent(storeId, eventData) {
    if (!storeId) throw new Error('storeId is required');
    const { data } = await request(`/stores/${encodeURIComponent(storeId)}/events`, {
      method: 'POST',
      body: eventData,
    });
    return data;
  },

  /** Delete local community event from a store */
  async deleteStoreEvent(storeId, eventId) {
    if (!storeId || !eventId) throw new Error('storeId and eventId are required');
    const { data } = await request(`/stores/${encodeURIComponent(storeId)}/events/${encodeURIComponent(eventId)}`, {
      method: 'DELETE',
    });
    return data;
  },

  /** Test ping to store manager Telegram chat */
  async testTelegramIntegration(payload) {
    const { data } = await request('/integrations/test-telegram', {
      method: 'POST',
      body: payload,
    });
    return data;
  },

  /** Test handshake and OData metadata ping to SAP S/4HANA */
  async testSapIntegration(payload) {
    const { data } = await request('/integrations/test-sap', {
      method: 'POST',
      body: payload,
    });
    return data;
  },
};

