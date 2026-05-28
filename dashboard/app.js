/**
 * Main application — ties everything together.
 */

document.addEventListener('DOMContentLoaded', async () => {
    initMap();
    initCharts();
    initFilters();

    // Wire up events
    document.getElementById('apply-filters').addEventListener('click', applyFilters);
    document.getElementById('export-csv').addEventListener('click', exportTrendCSV);

    // Station click handler
    onStationClick = async (stationId, stationName) => {
        const filters = getFilterState();
        const category = filters.crimeCategory || 'Murder';

        try {
            const trendData = await Api.getTrends(stationId, {
                crimeCategory: category,
                startMonth: '2020-01',
                endMonth: '2025-12',
            });
            currentTrendData = trendData;
            updateTrendChart(trendData, stationName, category);
        } catch (err) {
            console.error('Failed to load trends:', err);
        }
    };

    // Initial load
    await applyFilters();
});

async function applyFilters() {
    const filters = getFilterState();
    const statsEl = {
        stations: document.getElementById('stat-stations'),
        hotspots: document.getElementById('stat-hotspots'),
        category: document.getElementById('stat-category'),
    };

    try {
        // Fetch hotspots
        const hotspotParams = { riskThreshold: filters.riskThreshold };
        if (filters.province) hotspotParams.province = filters.province;
        if (filters.crimeCategory) hotspotParams.crimeCategory = filters.crimeCategory;

        const hotspots = await Api.getHotspots(hotspotParams);
        plotHotspots(hotspots);

        statsEl.hotspots.textContent = `Hotspots: ${hotspots.length}`;
        statsEl.category.textContent = `Category: ${filters.crimeCategory || 'All'}`;

        // Fetch forecasts for bar chart
        const forecastParams = { pageSize: 100 };
        if (filters.province) forecastParams.province = filters.province;
        if (filters.crimeCategory) forecastParams.crimeCategory = filters.crimeCategory;

        const forecasts = await Api.getForecasts(forecastParams);
        updateBarChart(forecasts.items);

        statsEl.stations.textContent = `Stations: ${forecasts.total}`;

        // Load trend for the top station automatically
        if (forecasts.items && forecasts.items.length > 0) {
            const topStation = forecasts.items[0];
            const category = filters.crimeCategory || topStation.crimeCategory;
            try {
                const trendData = await Api.getTrends(topStation.stationId, {
                    crimeCategory: category,
                    startMonth: '2020-01',
                    endMonth: '2025-12',
                });
                currentTrendData = trendData;
                updateTrendChart(trendData, topStation.stationName, category);
            } catch (err) {
                console.warn('Could not load trend for top station:', err);
            }
        }

    } catch (err) {
        console.error('Failed to apply filters:', err);
        statsEl.hotspots.textContent = 'Hotspots: Error';
    }
}
