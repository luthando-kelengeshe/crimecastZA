/**
 * Chart.js chart module.
 */

let trendChart = null;
let barChart = null;

function initCharts() {
    const trendCtx = document.getElementById('trend-chart').getContext('2d');
    trendChart = new Chart(trendCtx, {
        type: 'line',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const ds = ctx.dataset;
                            return `${ds.label}: ${ctx.parsed.y} (${ctx.label})`;
                        }
                    }
                }
            },
            scales: {
                y: { beginAtZero: true, ticks: { color: '#aaa' }, grid: { color: '#333' } },
                x: { ticks: { color: '#aaa', maxRotation: 45 }, grid: { color: '#333' } },
            }
        }
    });

    const barCtx = document.getElementById('bar-chart').getContext('2d');
    barChart = new Chart(barCtx, {
        type: 'bar',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: { legend: { display: false } },
            scales: {
                x: { beginAtZero: true, ticks: { color: '#aaa' }, grid: { color: '#333' } },
                y: { ticks: { color: '#aaa' }, grid: { color: '#333' } },
            }
        }
    });
}

function updateTrendChart(data, stationName, crimeCategory) {
    const title = document.getElementById('trend-title');
    title.textContent = `${crimeCategory} — ${stationName}`;

    if (!data || !data.records || data.records.length === 0) {
        trendChart.data = { labels: [], datasets: [] };
        trendChart.update();
        return;
    }

    const historical = data.records.filter(r => r.dataType === 'historical');
    const forecast = data.records.filter(r => r.dataType === 'forecast');

    const allLabels = data.records.map(r => r.month);

    trendChart.data = {
        labels: allLabels,
        datasets: [
            {
                label: 'Historical',
                data: data.records.map(r => r.dataType === 'historical' ? r.crimeCount : null),
                borderColor: '#4fc3f7',
                backgroundColor: 'rgba(79, 195, 247, 0.1)',
                pointStyle: 'circle',
                pointRadius: 3,
                borderWidth: 2,
                spanGaps: false,
            },
            {
                label: 'Forecast',
                data: data.records.map(r => r.dataType === 'forecast' ? r.crimeCount : null),
                borderColor: '#e94560',
                backgroundColor: 'rgba(233, 69, 96, 0.1)',
                borderDash: [5, 5],
                pointStyle: 'rectRot',
                pointRadius: 5,
                borderWidth: 2,
                spanGaps: false,
            }
        ]
    };
    trendChart.update();

    // Show/hide export button
    document.getElementById('export-csv').style.display = data.records.length > 0 ? 'inline-block' : 'none';
}

function updateBarChart(forecasts) {
    if (!forecasts || forecasts.length === 0) {
        barChart.data = { labels: [], datasets: [] };
        barChart.update();
        return;
    }

    // Sort by predicted count descending, take top 10
    const sorted = [...forecasts].sort((a, b) => b.predictedCount - a.predictedCount);
    const top10 = sorted.slice(0, 10);

    barChart.data = {
        labels: top10.map(f => f.stationName),
        datasets: [{
            label: 'Predicted Count',
            data: top10.map(f => f.predictedCount),
            backgroundColor: top10.map(f => RISK_COLORS[f.riskScore] || '#999'),
            borderColor: '#333',
            borderWidth: 1,
        }]
    };
    barChart.update();
}

// Store current trend data for CSV export
let currentTrendData = null;
