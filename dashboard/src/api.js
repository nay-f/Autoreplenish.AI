import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: { "Content-Type": "application/json" },
});

// Request Interceptor: Sisipkan JWT Bearer Token otomatis
apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem("ar_token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Response Interceptor: Auto-logout jika token expired atau tidak valid (401)
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            localStorage.removeItem("ar_token");
            localStorage.removeItem("ar_user");
        }
        return Promise.reject(error);
    }
);

export const api = {
    login: async (username, password, role) => {
        const res = await apiClient.post("/api/v1/auth/login", { username, password, role });
        if (res.data?.token) {
            localStorage.setItem("ar_token", res.data.token);
        }
        return res.data;
    },

    getIntegrationsHealth: async () => {
        const res = await apiClient.get("/api/v1/health/integrations");
        return res.data;
    },

    getStores: async () => {
        const res = await apiClient.get("/api/v1/stores");
        return res.data;
    },

    saveStore: async (storeData) => {
        const res = await apiClient.post("/api/v1/stores", storeData);
        return res.data;
    },

    getStoreSkus: async (storeId) => {
        const res = await apiClient.get(`/api/v1/stores/${storeId}/skus`);
        return res.data;
    },

    saveStoreSku: async (storeId, skuData) => {
        const res = await apiClient.post(`/api/v1/stores/${storeId}/skus`, skuData);
        return res.data;
    },

    deleteStoreSku: async (storeId, skuId) => {
        const res = await apiClient.delete(`/api/v1/stores/${storeId}/skus/${skuId}`);
        return res.data;
    },

    evaluateStore: async (storeId) => {
        const res = await apiClient.post(`/api/v1/evaluate/${storeId}?force_all=true`);
        return res.data;
    },

    getAuditLogs: async (storeId = "") => {
        const query = storeId ? `?store_id=${storeId}` : "";
        const res = await apiClient.get(`/api/v1/audit-logs${query}`);
        return res.data;
    },
    // Metrik Observability & AI Governance Aktual (Fase 3 & 4)
    getGovernanceMetrics: async (storeId = "") => {
        const query = storeId ? `?store_id=${storeId}` : "";
        const res = await apiClient.get(`/api/v1/metrics/governance${query}`);
        return res.data;
    },
};