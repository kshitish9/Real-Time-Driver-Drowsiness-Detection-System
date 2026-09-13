// Analytics Charts Manager
class ChartManager {
    constructor() {
        this.charts = {};
        this.data = {
            ear: [],
            perclos: [],
            alerts: [],
            timestamps: []
        };
    }

    initializeCharts() {
        this.createEARChart();
        this.createPERCLOSChart();
        this.createAlertChart();
        this.loadHistoricalData();
    }

    createEARChart() {
        const ctx = document.getElementById('earChart')?.getContext('2d');
        if (!ctx) return;

        this.charts.ear = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Eye Aspect Ratio',
                    data: [],
                    borderColor: '#4e73df',
                    backgroundColor: 'rgba(78, 115, 223, 0.1)',
                    borderWidth: 2,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 0
                },
                plugins: {
                    legend: {
                        labels: { color: 'white' }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        titleColor: 'white',
                        bodyColor: 'white'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 0.4,
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { 
                            color: 'white',
                            callback: function(value) {
                                return value.toFixed(2);
                            }
                        }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { 
                            color: 'white',
                            maxRotation: 45,
                            maxTicksLimit: 10
                        }
                    }
                }
            }
        });
    }

    createPERCLOSChart() {
        const ctx = document.getElementById('perclosChart')?.getContext('2d');
        if (!ctx) return;

        this.charts.perclos = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'PERCLOS (%)',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: 'white' }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { 
                            color: 'white',
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: 'white' }
                    }
                }
            }
        });
    }

    createAlertChart() {
        const ctx = document.getElementById('alertChart')?.getContext('2d');
        if (!ctx) return;

        this.charts.alerts = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Alerts',
                    data: [0, 0, 0, 0, 0, 0, 0],
                    backgroundColor: '#ef4444',
                    borderRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: 'white' }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { color: 'white' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: 'white' }
                    }
                }
            }
        });
    }

    updateCharts(data) {
        const now = new Date().toLocaleTimeString();
        
        // Update EAR chart
        if (this.charts.ear) {
            this.data.timestamps.push(now);
            this.data.ear.push(data.current_ear || 0);
            
            if (this.data.timestamps.length > 30) {
                this.data.timestamps.shift();
                this.data.ear.shift();
            }
            
            this.charts.ear.data.labels = this.data.timestamps;
            this.charts.ear.data.datasets[0].data = this.data.ear;
            this.charts.ear.update();
        }
        
        // Update PERCLOS chart
        if (this.charts.perclos && data.perclos !== undefined) {
            this.data.perclos.push(data.perclos);
            
            if (this.data.perclos.length > 30) {
                this.data.perclos.shift();
            }
            
            this.charts.perclos.data.labels = this.data.timestamps;
            this.charts.perclos.data.datasets[0].data = this.data.perclos;
            this.charts.perclos.update();
        }
    }

    async loadHistoricalData() {
        try {
            const response = await fetch('/api/history');
            const data = await response.json();
            
            if (data.history && data.history.length > 0) {
                const history = data.history;
                
                this.data.timestamps = history.map(h => 
                    new Date(h.timestamp).toLocaleTimeString()
                );
                this.data.ear = history.map(h => h.ear);
                this.data.perclos = history.map(h => h.perclos || 0);
                
                if (this.charts.ear) {
                    this.charts.ear.data.labels = this.data.timestamps;
                    this.charts.ear.data.datasets[0].data = this.data.ear;
                    this.charts.ear.update();
                }
                
                if (this.charts.perclos) {
                    this.charts.perclos.data.labels = this.data.timestamps;
                    this.charts.perclos.data.datasets[0].data = this.data.perclos;
                    this.charts.perclos.update();
                }
            }
        } catch (error) {
            console.error('Failed to load historical data:', error);
        }
    }

    updateAlertStats(alerts) {
        if (!this.charts.alerts) return;
        
        // Group alerts by day of week
        const dayCounts = [0, 0, 0, 0, 0, 0, 0];
        
        alerts.forEach(alert => {
            const date = new Date(alert.timestamp);
            const day = date.getDay(); // 0 = Sunday, 1 = Monday, ...
            dayCounts[day === 0 ? 6 : day - 1]++; // Convert to Mon-Sun format
        });
        
        this.charts.alerts.data.datasets[0].data = dayCounts;
        this.charts.alerts.update();
    }

    resizeCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.resize();
        });
    }
}

// Initialize on window resize
window.addEventListener('resize', () => {
    if (window.chartManager) {
        window.chartManager.resizeCharts();
    }
});