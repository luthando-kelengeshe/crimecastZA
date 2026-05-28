/**
 * API client for CrimecastZA backend.
 */
const API_BASE = 'http://localhost:8080/api/v1';

const Api = {
    async getForecasts(params = {}) {
        const query = new URLSearchParams(params).toString();
        const resp = await fetch(`${API_BASE}/forecasts?${query}`);
        if (!resp.ok) throw new Error(`Forecasts: ${resp.status}`);
        return resp.json();
    },

    async getStationForecasts(stationId) {
        const resp = await fetch(`${API_BASE}/forecasts/${stationId}`);
        if (!resp.ok) throw new Error(`Station forecasts: ${resp.status}`);
        return resp.json();
    },

    async getHotspots(params = {}) {
        const query = new URLSearchParams(params).toString();
        const resp = await fetch(`${API_BASE}/hotspots?${query}`);
        if (!resp.ok) throw new Error(`Hotspots: ${resp.status}`);
        return resp.json();
    },

    async getTrends(stationId, params = {}) {
        const query = new URLSearchParams(params).toString();
        const resp = await fetch(`${API_BASE}/trends/${stationId}?${query}`);
        if (!resp.ok) throw new Error(`Trends: ${resp.status}`);
        return resp.json();
    },

    async getProvinceTrends(provinceId, params = {}) {
        const query = new URLSearchParams(params).toString();
        const resp = await fetch(`${API_BASE}/trends/province/${provinceId}?${query}`);
        if (!resp.ok) throw new Error(`Province trends: ${resp.status}`);
        return resp.json();
    },

    async getStations() {
        const resp = await fetch(`${API_BASE}/stations`);
        if (!resp.ok) throw new Error(`Stations: ${resp.status}`);
        return resp.json();
    },
};
