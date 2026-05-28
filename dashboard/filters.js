/**
 * Filter state management.
 */

const PROVINCES = [
    'Eastern Cape', 'Free State', 'Gauteng', 'KwaZulu-Natal',
    'Limpopo', 'Mpumalanga', 'North West', 'Northern Cape', 'Western Cape'
];

const CRIME_CATEGORIES = [
    'Murder', 'Attempted murder', 'Rape', 'Assault with the intent to inflict grievous bodily harm',
    'Common assault', 'Common robbery', 'Robbery with aggravating circumstances',
    'Burglary at residential premises', 'Burglary at non-residential premises',
    'Theft of motor vehicle and motorcycle', 'Theft out of or from motor vehicle',
    'Stock-Theft', 'Shoplifting', 'Carjacking', 'Truck hijacking',
    'Robbery at residential premises', 'Robbery at non-residential premises',
    'Arson', 'Malicious damage to property', 'Drug-Related Crime',
    'Driving under the influence of alcohol or drugs', 'Sexual Assault',
    'Kidnapping', 'Abduction', 'Public violence', 'Crimen Injuria',
    'Culpable homicide',
];

function initFilters() {
    const provinceSelect = document.getElementById('province-filter');
    const categorySelect = document.getElementById('category-filter');

    PROVINCES.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p;
        opt.textContent = p;
        provinceSelect.appendChild(opt);
    });

    CRIME_CATEGORIES.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        categorySelect.appendChild(opt);
    });
}

function getFilterState() {
    return {
        province: document.getElementById('province-filter').value,
        crimeCategory: document.getElementById('category-filter').value,
        riskThreshold: document.getElementById('risk-filter').value,
    };
}
