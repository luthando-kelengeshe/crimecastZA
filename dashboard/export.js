/**
 * CSV export module.
 */

function exportTrendCSV() {
    if (!currentTrendData || !currentTrendData.records || currentTrendData.records.length === 0) {
        return;
    }

    const stationName = document.getElementById('trend-title').textContent.split(' — ')[1] || 'station';
    const rows = [['station_name', 'month', 'crime_count', 'data_type']];

    currentTrendData.records.forEach(r => {
        rows.push([stationName, r.month, r.crimeCount, r.dataType]);
    });

    const csv = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `crimecast_trend_${stationName.replace(/\s+/g, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
