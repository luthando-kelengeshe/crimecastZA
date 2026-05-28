/**
 * Leaflet map module.
 */

const RISK_COLORS = {
    1: '#1a9641',
    2: '#a6d96a',
    3: '#ffffbf',
    4: '#fdae61',
    5: '#d7191c',
};

let map;
let markersLayer;

function initMap() {
    map = L.map('map').setView([-29.0, 25.0], 5); // Center on South Africa

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18,
    }).addTo(map);

    markersLayer = L.layerGroup().addTo(map);
}

function clearMarkers() {
    markersLayer.clearLayers();
}

function plotHotspots(hotspots) {
    clearMarkers();

    if (!hotspots || hotspots.length === 0) {
        return;
    }

    hotspots.forEach(station => {
        // Skip stations without real coordinates
        if (station.latitude === 0 && station.longitude === 0) return;

        const color = RISK_COLORS[station.riskScore] || '#999';

        const marker = L.circleMarker([station.latitude, station.longitude], {
            radius: 8 + station.riskScore * 2,
            fillColor: color,
            color: '#333',
            weight: 1,
            opacity: 0.9,
            fillOpacity: 0.8,
        });

        marker.bindPopup(`
            <div style="min-width:200px">
                <strong>${station.stationName}</strong><br>
                <small>${station.province}</small><br>
                <hr style="margin:4px 0">
                <b>Risk Score:</b> ${station.riskScore}/5<br>
                <b>Crime:</b> ${station.crimeCategory}<br>
                <b>Predicted Count:</b> ${station.predictedCount.toFixed(1)}<br>
            </div>
        `);

        marker.on('click', () => {
            onStationClick(station.stationId, station.stationName);
        });

        marker.addTo(markersLayer);
    });

    // Fit bounds if we have markers
    if (markersLayer.getLayers().length > 0) {
        const group = L.featureGroup(markersLayer.getLayers());
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

function plotAllStations(stations, forecasts) {
    clearMarkers();

    // Build a lookup of forecasts by stationId
    const forecastMap = {};
    if (forecasts && forecasts.items) {
        forecasts.items.forEach(f => {
            if (!forecastMap[f.stationId] || f.riskScore > forecastMap[f.stationId].riskScore) {
                forecastMap[f.stationId] = f;
            }
        });
    }

    stations.forEach(station => {
        if (station.latitude === 0 && station.longitude === 0) return;

        const forecast = forecastMap[station.stationId];
        const riskScore = forecast ? forecast.riskScore : 1;
        const color = RISK_COLORS[riskScore] || '#999';

        const marker = L.circleMarker([station.latitude, station.longitude], {
            radius: 6 + riskScore,
            fillColor: color,
            color: '#333',
            weight: 1,
            opacity: 0.8,
            fillOpacity: 0.7,
        });

        let popupContent = `
            <strong>${station.stationName}</strong><br>
            <small>${station.province}</small>
        `;
        if (forecast) {
            popupContent += `
                <hr style="margin:4px 0">
                <b>Risk:</b> ${forecast.riskScore}/5<br>
                <b>${forecast.crimeCategory}:</b> ${forecast.predictedCount.toFixed(1)}
            `;
        }
        marker.bindPopup(popupContent);

        marker.on('click', () => {
            onStationClick(station.stationId, station.stationName);
        });

        marker.addTo(markersLayer);
    });
}

// This will be set by app.js
let onStationClick = (stationId, stationName) => {};
