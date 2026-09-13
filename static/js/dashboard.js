/**
 * Advanced Drowsiness Detection System
 * Dashboard Manager Class - ENHANCED with Fire Alarm Sound
 */

class DashboardManager {
    constructor() {
        // Socket connection with retry options
        this.socket = io({
            reconnectionAttempts: 5,
            reconnectionDelay: 1000,
            timeout: 10000
        });
        
        // Data storage
        this.alertHistory = [];
        this.charts = {};
        this.stats = {
            ear: [],
            tilt: [],
            perclos: [],
            timestamps: []
        };
        this.maxHistoryPoints = 100;
        this.audioEnabled = true;
        this.audioContext = null;
        this.updateInterval = null;
        this.detectionActive = false;
        
        // Initialize
        this.initializeEventListeners();
        this.initializeCharts();
        this.loadInitialData();
        this.setupKeyboardShortcuts();
        this.initAudio();
    }

    /**
     * Initialize Audio Context (required by browsers for Web Audio API)
     */
    initAudio() {
        // Initialize audio context on first user interaction
        document.addEventListener('click', () => {
            if (!this.audioContext) {
                try {
                    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    console.log('✅ Audio context initialized');
                } catch (e) {
                    console.log('❌ Web Audio API not supported:', e);
                }
            }
        }, { once: true });

        // Pre-warm audio by loading a silent file
        const silentAudio = new Audio('data:audio/mp3;base64,SUQzBAAAAAABEVRYWFgAAAAtAAADY29tbWVudABCaWdTb3VuZEJhbmsuY29tIC8gTGFTb25vdGhlcXVlLm9yZwBURU5DAAAAHQAAA1N3aXRjaCBQbHVzIMKpIE5DSCBTb2Z0d2FyZQBUSVQyAAAABgAAAzIyMzUAVFNTRQAAAA8AAANMYXZmNTcuODMuMTAwAAAAAAAAAAAAAAD/80DEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVUxBTUUzLjEwMEVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsRbAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV');
        silentAudio.load();
    }

    initializeEventListeners() {
        // Socket events
        this.socket.on('connect', () => this.handleConnect());
        this.socket.on('disconnect', () => this.handleDisconnect());
        this.socket.on('connect_error', (error) => {
            console.error('Socket connection error:', error);
            this.showNotification('Connection error. Retrying...', 'error');
        });
        this.socket.on('detection_update', (data) => this.updateDashboard(data));
        this.socket.on('drowsy_alert', (alert) => this.handleAlert(alert));

        // DOM elements
        this.startBtn = document.getElementById('startBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.refreshBtn = document.getElementById('refreshBtn');
        this.exportBtn = document.getElementById('exportBtn');
        this.statusDot = document.getElementById('statusDot');
        this.statusText = document.getElementById('statusText');
        this.videoBadge = document.getElementById('videoBadge');
        this.drowsyAlert = document.getElementById('drowsyAlert');
        this.timeRange = document.getElementById('timeRange');
        
        // Stats elements
        this.earValue = document.getElementById('earValue');
        this.faceCount = document.getElementById('faceCount');
        this.tiltValue = document.getElementById('tiltValue');
        this.fpsValue = document.getElementById('fpsValue');
        this.earProgress = document.getElementById('earProgress');
        this.tiltProgress = document.getElementById('tiltProgress');
        this.alertList = document.getElementById('alertList');
        this.eventCount = document.getElementById('eventCount');
        
        // Button events
        if (this.startBtn) {
            this.startBtn.addEventListener('click', () => this.startDetection());
        }
        if (this.stopBtn) {
            this.stopBtn.addEventListener('click', () => this.stopDetection());
        }
        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => this.refreshDashboard());
        }
        if (this.exportBtn) {
            this.exportBtn.addEventListener('click', () => this.exportData());
        }
        if (this.timeRange) {
            this.timeRange.addEventListener('change', () => this.loadDashboardData());
        }

        // Video feed error handling
        const videoFeed = document.getElementById('videoFeed');
        if (videoFeed) {
            videoFeed.onerror = () => {
                this.showNotification('Video feed error - check camera', 'error');
                this.updateConnectionStatus('disconnected');
            };
            videoFeed.onload = () => {
                console.log('Video feed loaded successfully');
            };
        }

        // Page visibility
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.pauseUpdates();
            } else {
                this.resumeUpdates();
            }
        });

        // Enable audio on first user interaction
        document.addEventListener('click', () => {
            this.audioEnabled = true;
        }, { once: true });

        // Range input live updates
        document.querySelectorAll('input[type="range"]').forEach(input => {
            input.addEventListener('input', (e) => {
                const valueSpan = document.getElementById(e.target.id + 'Value');
                if (valueSpan) {
                    valueSpan.textContent = e.target.value;
                }
            });
        });
    }

    initializeCharts() {
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js not loaded');
            return;
        }

        // EAR Chart
        const earCtx = document.getElementById('earChart')?.getContext('2d');
        if (earCtx) {
            try {
                this.charts.ear = new Chart(earCtx, {
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
                        animation: { duration: 0 },
                        plugins: {
                            legend: {
                                labels: { color: 'white', font: { size: 12 } }
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                backgroundColor: 'rgba(0,0,0,0.8)'
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 0.4,
                                grid: { color: 'rgba(255,255,255,0.1)' },
                                ticks: { 
                                    color: 'white',
                                    callback: v => v.toFixed(2)
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
            } catch (error) {
                console.error('Failed to initialize EAR chart:', error);
            }
        }

        // PERCLOS Chart
        const perclosCtx = document.getElementById('perclosChart')?.getContext('2d');
        if (perclosCtx) {
            try {
                this.charts.perclos = new Chart(perclosCtx, {
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
                            legend: { labels: { color: 'white' } }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                grid: { color: 'rgba(255,255,255,0.1)' },
                                ticks: { 
                                    color: 'white',
                                    callback: v => v + '%'
                                }
                            },
                            x: {
                                grid: { display: false },
                                ticks: { color: 'white' }
                            }
                        }
                    }
                });
            } catch (error) {
                console.error('Failed to initialize PERCLOS chart:', error);
            }
        }

        // Head Tilt Chart
        const tiltCtx = document.getElementById('tiltChart')?.getContext('2d');
        if (tiltCtx) {
            try {
                this.charts.tilt = new Chart(tiltCtx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Head Tilt (°)',
                            data: [],
                            borderColor: '#f59e0b',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            borderWidth: 2,
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { labels: { color: 'white' } }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 30,
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
            } catch (error) {
                console.error('Failed to initialize tilt chart:', error);
            }
        }

        // Daily Alert Chart
        const dailyCtx = document.getElementById('dailyChart')?.getContext('2d');
        if (dailyCtx) {
            try {
                this.charts.daily = new Chart(dailyCtx, {
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
                            legend: { labels: { color: 'white' } }
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
            } catch (error) {
                console.error('Failed to initialize daily chart:', error);
            }
        }
    }

    // Connection handlers
    handleConnect() {
        console.log('✅ Connected to server');
        this.updateConnectionStatus('connected');
        this.showNotification('Connected to server', 'success');
        this.fetchStatus();
        this.resumeUpdates();
    }

    handleDisconnect() {
        console.log('❌ Disconnected from server');
        this.updateConnectionStatus('disconnected');
        this.showNotification('Disconnected from server', 'error');
        this.pauseUpdates();
    }

    updateConnectionStatus(status) {
        if (this.statusDot) {
            this.statusDot.className = `status-dot ${status}`;
        }
        if (this.statusText) {
            this.statusText.textContent = status === 'connected' ? 'Connected' : 'Disconnected';
        }
        if (this.videoBadge) {
            this.videoBadge.className = `video-badge ${status === 'connected' ? 'live' : 'offline'}`;
            this.videoBadge.innerHTML = `<i class="fas fa-circle"></i> ${status === 'connected' ? 'Live' : 'Offline'}`;
        }
    }

    // Dashboard updates
    updateDashboard(data) {
        if (!data) return;

        // Update numeric displays
        if (this.earValue) {
            const ear = data.current_ear || 0;
            this.earValue.textContent = ear.toFixed(3);
            this.earValue.style.color = ear < 0.2 ? '#ef4444' : ear < 0.25 ? '#f59e0b' : '#10b981';
        }
        
        if (this.faceCount) {
            this.faceCount.textContent = data.faces_detected || 0;
        }
        
        if (this.fpsValue) {
            this.fpsValue.textContent = data.fps || 0;
        }

        if (this.tiltValue && data.current_tilt !== undefined) {
            this.tiltValue.textContent = Math.abs(data.current_tilt).toFixed(1) + '°';
        }

        // Update progress bars
        if (this.earProgress) {
            const earPercent = Math.min(((data.current_ear || 0) / 0.3) * 100, 100);
            this.earProgress.style.width = earPercent + '%';
            this.earProgress.style.background = earPercent < 50 ? '#ef4444' : earPercent < 70 ? '#f59e0b' : '#10b981';
        }

        if (this.tiltProgress && data.current_tilt !== undefined) {
            const tiltPercent = Math.min(Math.abs(data.current_tilt) * 3.33, 100);
            this.tiltProgress.style.width = tiltPercent + '%';
        }

        // Update status text
        const statusText = document.getElementById('statusText');
        if (statusText) {
            if (data.is_drowsy) {
                statusText.textContent = 'DROWSY!';
                statusText.className = 'text-danger';
                this.showDrowsyIndicator();
            } else {
                statusText.textContent = 'AWAKE';
                statusText.className = 'text-success';
            }
        }

        // Update charts
        this.updateCharts(data);
    }

    updateCharts(data) {
        const now = new Date().toLocaleTimeString();
        
        // Update data history
        this.stats.timestamps.push(now);
        this.stats.ear.push(data.current_ear || 0);
        if (data.current_tilt !== undefined) {
            this.stats.tilt.push(Math.abs(data.current_tilt));
        }
        if (data.perclos !== undefined) {
            this.stats.perclos.push(data.perclos);
        }

        // Keep only last 30 points
        if (this.stats.timestamps.length > 30) {
            this.stats.timestamps.shift();
            this.stats.ear.shift();
            if (this.stats.tilt.length > 30) this.stats.tilt.shift();
            if (this.stats.perclos.length > 30) this.stats.perclos.shift();
        }

        // Update EAR chart
        if (this.charts.ear) {
            this.charts.ear.data.labels = this.stats.timestamps;
            this.charts.ear.data.datasets[0].data = this.stats.ear;
            this.charts.ear.update('none');
        }

        // Update PERCLOS chart
        if (this.charts.perclos && this.stats.perclos.length > 0) {
            this.charts.perclos.data.labels = this.stats.timestamps;
            this.charts.perclos.data.datasets[0].data = this.stats.perclos;
            this.charts.perclos.update('none');
        }

        // Update tilt chart
        if (this.charts.tilt && this.stats.tilt.length > 0) {
            this.charts.tilt.data.labels = this.stats.timestamps;
            this.charts.tilt.data.datasets[0].data = this.stats.tilt;
            this.charts.tilt.update('none');
        }
    }

    // Alert handling
    handleAlert(alert) {
        this.alertHistory.unshift({
            ...alert,
            timestamp: new Date().toISOString()
        });
        
        if (this.alertHistory.length > 20) this.alertHistory.pop();

        // Show visual alerts
        this.showDrowsyAlert();
        this.addAlertToList(alert);
        this.showNotification('⚠️ Drowsiness Detected!', 'warning');
        
        // Play sound if enabled - ENHANCED VERSION
        if (this.audioEnabled) {
            this.playEnhancedAlertSound();
        }

        // Update total alerts counter
        if (this.eventCount) {
            this.eventCount.textContent = parseInt(this.eventCount.textContent || 0) + 1;
        }

        // Vibrate on mobile
        if (window.navigator?.vibrate) {
            window.navigator.vibrate([500, 200, 500]);
        }
    }

    /**
     * 🔥 ENHANCED FIRE ALARM SOUND - MAXIMUM ATTENTION! 🔥
     * Rapid beeping like a real fire alarm: BEEP! BEEP! BEEP! BEEP!
     */
    playEnhancedAlertSound() {
        if (!this.audioEnabled) return;

        console.log('🔊 🔥 FIRE ALARM! WAKE UP! 🔥 🔊');

        // Try multiple alarm formats (prioritize the wake_off alarm)
        const alarmFormats = [
            '/alerts/wake_off.mp3',
            '/alerts/wake_off.wav',
            '/alerts/fire_alarm_intense.mp3',
            '/alerts/fire_alarm_intense.wav',
            '/alerts/alert.mp3',
            '/alerts/alert.wav',
            '/static/sounds/alert.mp3',
            '/static/sounds/alert.wav'
        ];

        let attempted = 0;
        
        const tryPlay = (src) => {
            if (!src || attempted >= alarmFormats.length) {
                // Fallback to Web Audio API if all files fail
                console.log('⚠️ All audio files failed, using Web Audio fallback');
                this.playWebAudioAlarm();
                return;
            }
            
            console.log(`🔊 Trying alarm: ${src}`);
            const audio = new Audio(src);
            audio.volume = 1.0; // MAX VOLUME!
            audio.preload = 'auto';
            
            // Set up timeout for loading
            const loadTimeout = setTimeout(() => {
                console.log(`⏱️ Timeout loading ${src}`);
                audio.oncanplaythrough = null;
                audio.onerror = null;
                attempted++;
                tryPlay(alarmFormats[attempted]);
            }, 2000);
            
            audio.oncanplaythrough = () => {
                clearTimeout(loadTimeout);
                console.log(`✅ Loaded alarm: ${src}`);
                audio.play()
                    .then(() => {
                        console.log('✅🔥 FIRE ALARM PLAYING! Wake up!');
                        
                        // Play multiple times for full effect (like a real fire alarm)
                        setTimeout(() => {
                            const audio2 = new Audio(src);
                            audio2.volume = 1.0;
                            audio2.play().catch(e => console.log('Second play failed:', e));
                        }, 800);
                        
                        setTimeout(() => {
                            const audio3 = new Audio(src);
                            audio3.volume = 1.0;
                            audio3.play().catch(e => console.log('Third play failed:', e));
                        }, 1600);
                        
                        setTimeout(() => {
                            const audio4 = new Audio(src);
                            audio4.volume = 1.0;
                            audio4.play().catch(e => console.log('Fourth play failed:', e));
                        }, 2400);
                    })
                    .catch(e => {
                        console.log(`❌ Failed to play ${src}:`, e.message);
                        attempted++;
                        tryPlay(alarmFormats[attempted]);
                    });
            };
            
            audio.onerror = (e) => {
                clearTimeout(loadTimeout);
                console.log(`❌ Failed to load ${src}:`, e);
                attempted++;
                tryPlay(alarmFormats[attempted]);
            };
            
            audio.load();
        };

        // Start with first format
        tryPlay(alarmFormats[0]);
    }

    /**
     * Web Audio API fallback - Creates a REAL FIRE ALARM sound
     * Guaranteed to work even without audio files
     */
    playWebAudioAlarm() {
        console.log('🔊 Using Web Audio API to create FIRE ALARM');
        
        try {
            // Create audio context if not exists
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            
            // Resume if suspended
            if (this.audioContext.state === 'suspended') {
                this.audioContext.resume();
            }
            
            const now = this.audioContext.currentTime;
            
            /**
             * Create a fire alarm style beep
             * Rapid alternating high-low frequencies
             */
            const createFireBeep = (startTime, duration, highPitch = true) => {
                // Main oscillator (harsh sawtooth for attention)
                const osc = this.audioContext.createOscillator();
                const gain = this.audioContext.createGain();
                
                // Use sawtooth for harsh, attention-grabbing sound
                osc.type = 'sawtooth';
                
                // Alternating frequencies: 880Hz (A5) and 1046.5Hz (C6)
                const freq = highPitch ? 1046.5 : 880;
                osc.frequency.value = freq;
                
                // Add a second oscillator for harmonic richness
                const osc2 = this.audioContext.createOscillator();
                osc2.type = 'square';
                osc2.frequency.value = freq * 2; // Octave higher for piercing effect
                
                // Gain envelope - sharp attack, quick decay (like a real alarm)
                gain.gain.setValueAtTime(0.8, startTime);
                gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
                
                // Connect both oscillators
                osc.connect(gain);
                osc2.connect(gain);
                gain.connect(this.audioContext.destination);
                
                // Start and stop
                osc.start(startTime);
                osc2.start(startTime);
                osc.stop(startTime + duration);
                osc2.stop(startTime + duration);
            };
            
            /**
             * Create rapid beeping pattern (like real fire alarm)
             * Pattern: BEEP BEEP BEEP BEEP (12 beeps per second)
             */
            const createRapidBeeps = () => {
                const beepCount = 40; // 3-4 seconds of beeping
                const beepDuration = 0.06; // Short beep
                const gapDuration = 0.02; // Tiny gap
                
                for (let i = 0; i < beepCount; i++) {
                    const time = now + (i * (beepDuration + gapDuration));
                    // Alternate frequencies for more annoying effect
                    createFireBeep(time, beepDuration, i % 2 === 0);
                }
            };
            
            /**
             * Create alternating pattern like: BEEP-boop-BEEP-boop
             */
            const createAlternatingPattern = () => {
                for (let i = 0; i < 20; i++) {
                    const time = now + (i * 0.2);
                    // Two beeps close together then pause
                    createFireBeep(time, 0.08, true);
                    createFireBeep(time + 0.1, 0.08, false);
                }
            };
            
            /**
             * Create siren-like rising/falling tone
             */
            const createSweepingSiren = () => {
                const sweepOsc = this.audioContext.createOscillator();
                const sweepGain = this.audioContext.createGain();
                
                sweepOsc.type = 'sawtooth';
                sweepGain.gain.setValueAtTime(0.6, now);
                sweepGain.gain.exponentialRampToValueAtTime(0.01, now + 2);
                
                // Sweep frequency up and down
                sweepOsc.frequency.setValueAtTime(660, now);
                sweepOsc.frequency.linearRampToValueAtTime(1320, now + 0.5);
                sweepOsc.frequency.linearRampToValueAtTime(660, now + 1.0);
                sweepOsc.frequency.linearRampToValueAtTime(1320, now + 1.5);
                sweepOsc.frequency.linearRampToValueAtTime(660, now + 2.0);
                
                sweepOsc.connect(sweepGain);
                sweepGain.connect(this.audioContext.destination);
                
                sweepOsc.start(now);
                sweepOsc.stop(now + 2);
            };
            
            // Play multiple alarm patterns for maximum attention
            console.log('🔥 PLAYING FIRE ALARM PATTERNS!');
            
            // Pattern 1: Rapid beeping (most annoying)
            createRapidBeeps();
            
            // Pattern 2: Alternating pattern after a short pause
            setTimeout(() => {
                createAlternatingPattern();
            }, 4000);
            
            // Pattern 3: Sweeping siren after another pause
            setTimeout(() => {
                createSweepingSiren();
            }, 8000);
            
            console.log('✅🔥 FIRE ALARM ACTIVATED! Wake up!');
            
        } catch (e) {
            console.log('❌ Web Audio failed:', e);
            this.fallbackBeep();
        }
    }

    /**
     * Ultimate fallback - simple beep using AudioContext
     */
    fallbackBeep() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            
            osc.type = 'sine';
            osc.frequency.value = 880;
            
            gain.gain.setValueAtTime(0.5, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
            
            osc.connect(gain);
            gain.connect(ctx.destination);
            
            osc.start();
            osc.stop(ctx.currentTime + 0.5);
            
            // Do it again
            setTimeout(() => {
                const osc2 = ctx.createOscillator();
                const gain2 = ctx.createGain();
                osc2.type = 'sine';
                osc2.frequency.value = 1046.5;
                gain2.gain.setValueAtTime(0.5, ctx.currentTime);
                gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
                osc2.connect(gain2);
                gain2.connect(ctx.destination);
                osc2.start();
                osc2.stop(ctx.currentTime + 0.5);
            }, 600);
            
            console.log('✅ Fallback beep played');
        } catch (e) {
            console.log('❌ All audio methods failed');
        }
    }

    showDrowsyAlert() {
        if (this.drowsyAlert) {
            this.drowsyAlert.style.display = 'flex';
            setTimeout(() => {
                this.drowsyAlert.style.display = 'none';
            }, 3000);
        }
    }

    showDrowsyIndicator() {
        const videoContainer = document.querySelector('.video-container');
        if (videoContainer) {
            videoContainer.style.boxShadow = '0 0 20px #ef4444';
            setTimeout(() => {
                videoContainer.style.boxShadow = 'none';
            }, 500);
        }
    }

    addAlertToList(alert) {
        if (!this.alertList) return;

        const time = new Date().toLocaleTimeString();
        
        // Remove "no alerts" message if present
        if (this.alertList.children.length === 1 && 
            this.alertList.children[0]?.classList.contains('no-alerts')) {
            this.alertList.innerHTML = '';
        }
        
        const alertItem = document.createElement('div');
        alertItem.className = 'alert-item';
        alertItem.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <span>
                    <i class="fas fa-exclamation-triangle text-danger me-2"></i>
                    Alert #${alert.alert_id || this.alertHistory.length}
                </span>
                <small class="text-muted">${time}</small>
            </div>
            <div class="small mt-1">
                <span class="badge bg-danger">EAR: ${alert.ear?.toFixed(3) || '0.00'}</span>
                ${alert.head_tilt ? `<span class="badge bg-warning ms-2">Tilt: ${alert.head_tilt.toFixed(1)}°</span>` : ''}
                ${alert.duration ? `<span class="badge bg-secondary ms-2">${alert.duration}</span>` : ''}
            </div>
        `;
        
        // Add with fade-in animation
        alertItem.style.opacity = '0';
        this.alertList.insertBefore(alertItem, this.alertList.firstChild);
        
        setTimeout(() => {
            alertItem.style.opacity = '1';
        }, 10);

        // Keep only last 20 items
        while (this.alertList.children.length > 20) {
            this.alertList.removeChild(this.alertList.lastChild);
        }
    }

    // API Calls
    async startDetection() {
        console.log('▶️ Starting detection...');
        
        if (this.startBtn) {
            this.startBtn.disabled = true;
            this.startBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
        }

        try {
            const response = await fetch('/api/start', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache'
                }
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                this.detectionActive = true;
                if (this.stopBtn) {
                    this.stopBtn.disabled = false;
                    this.stopBtn.innerHTML = '<i class="fas fa-stop"></i> Stop';
                }
                if (this.startBtn) {
                    this.startBtn.innerHTML = '<i class="fas fa-play"></i> Start';
                }
                this.showNotification('Detection started', 'success');
            } else {
                throw new Error(result.message || 'Failed to start');
            }
        } catch (error) {
            console.error('Error starting detection:', error);
            if (this.startBtn) {
                this.startBtn.disabled = false;
                this.startBtn.innerHTML = '<i class="fas fa-play"></i> Start';
            }
            this.showNotification('Failed to start: ' + error.message, 'error');
        }
    }

    async stopDetection() {
        console.log('⏹️ Stopping detection...');
        
        if (this.stopBtn) {
            this.stopBtn.disabled = true;
            this.stopBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Stopping...';
        }

        try {
            const response = await fetch('/api/stop', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache'
                }
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                this.detectionActive = false;
                if (this.startBtn) {
                    this.startBtn.disabled = false;
                    this.startBtn.innerHTML = '<i class="fas fa-play"></i> Start';
                }
                if (this.stopBtn) {
                    this.stopBtn.disabled = true;
                    this.stopBtn.innerHTML = '<i class="fas fa-stop"></i> Stop';
                }
                this.showNotification('Detection stopped', 'info');
            }
        } catch (error) {
            console.error('Error stopping detection:', error);
            if (this.stopBtn) {
                this.stopBtn.disabled = false;
                this.stopBtn.innerHTML = '<i class="fas fa-stop"></i> Stop';
            }
        }
    }

    async fetchStatus() {
        try {
            const response = await fetch('/api/status?' + Date.now(), {
                headers: { 'Cache-Control': 'no-cache' }
            });
            
            if (!response.ok) throw new Error('Status fetch failed');
            
            const data = await response.json();
            
            // Update button states
            if (this.startBtn && this.stopBtn) {
                this.startBtn.disabled = data.active;
                this.stopBtn.disabled = !data.active;
            }
            
            if (data.stats) {
                this.updateDashboard(data.stats);
            }

            // Update camera status
            const cameraStatus = document.getElementById('cameraStatus');
            if (cameraStatus) {
                cameraStatus.innerHTML = data.camera_ready ? 
                    '<span class="text-success"><i class="fas fa-check-circle"></i> Ready</span>' : 
                    '<span class="text-danger"><i class="fas fa-exclamation-circle"></i> Not Available</span>';
            }
        } catch (error) {
            console.error('Status fetch error:', error);
        }
    }

    async loadInitialData() {
        // Show loading state
        if (this.alertList) {
            this.alertList.innerHTML = '<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i> Loading alerts...</div>';
        }

        // Load alerts
        try {
            const response = await fetch('/api/alerts');
            if (!response.ok) throw new Error('Failed to fetch alerts');
            
            const data = await response.json();
            
            if (this.alertList) {
                this.alertList.innerHTML = '';
            }
            
            if (data.alerts?.length > 0) {
                data.alerts.slice(0, 20).forEach(alert => this.addAlertToList(alert));
            } else if (this.alertList) {
                this.alertList.innerHTML = '<div class="no-alerts"><i class="fas fa-check-circle"></i> No alerts yet</div>';
            }
        } catch (error) {
            console.error('Failed to load alerts:', error);
            if (this.alertList) {
                this.alertList.innerHTML = '<div class="no-alerts text-danger"><i class="fas fa-exclamation-triangle"></i> Failed to load alerts</div>';
            }
        }

        // Load stats summary
        try {
            const response = await fetch('/api/stats/summary');
            const data = await response.json();
            
            if (this.eventCount) {
                this.eventCount.textContent = data.total_alerts || 0;
            }
            
            const avgEAR = document.getElementById('avgEAR');
            if (avgEAR) {
                avgEAR.textContent = (data.avg_ear || 0).toFixed(3);
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
        }

        // Load dashboard data if timeRange exists
        if (this.timeRange) {
            await this.loadDashboardData();
        }

        // Start periodic updates
        this.resumeUpdates();
    }

    async loadDashboardData() {
        try {
            const period = this.timeRange?.value || 'day';
            const response = await fetch(`/api/stats?period=${period}`);
            const data = await response.json();
            
            this.updateSummaryCards(data);
            this.updateDailyChart(data);
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        }
    }

    updateSummaryCards(data) {
        const cards = {
            'avgEar': data.summary?.avg_ear?.toFixed(3) || '0.000',
            'avgTilt': data.summary?.avg_tilt?.toFixed(1) + '°' || '0°',
            'totalTime': this.formatDuration(data.summary?.total_time || 0),
            'peakHour': data.summary?.peak_hour || 'N/A'
        };

        Object.entries(cards).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        });
    }

    updateDailyChart(data) {
        if (!this.charts.daily || !data.daily) return;

        const dates = data.daily.map(d => d.date);
        const events = data.daily.map(d => d.events);

        this.charts.daily.data.labels = dates;
        this.charts.daily.data.datasets[0].data = events;
        this.charts.daily.update();
    }

    // Utility functions
    refreshDashboard() {
        this.loadDashboardData();
        this.stats = {
            ear: [],
            tilt: [],
            perclos: [],
            timestamps: []
        };
        
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.data.labels = [];
                chart.data.datasets.forEach(ds => ds.data = []);
                chart.update();
            }
        });
        
        this.showNotification('Dashboard refreshed', 'info');
    }

    async exportData() {
        try {
            const format = document.getElementById('exportFormat')?.value || 'csv';
            const response = await fetch(`/api/export?format=${format}`);
            const blob = await response.blob();
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `drowsiness_data_${new Date().toISOString().split('T')[0]}.${format}`;
            a.click();
            
            window.URL.revokeObjectURL(url);
            this.showNotification('Data exported successfully', 'success');
        } catch (error) {
            console.error('Export error:', error);
            this.showNotification('Export failed', 'error');
        }
    }

    showNotification(message, type) {
        // Remove existing toasts
        document.querySelectorAll('.toast-notification').forEach(t => t.remove());

        const toast = document.createElement('div');
        toast.className = `toast-notification ${type}`;
        
        const icon = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        }[type] || 'info-circle';
        
        toast.innerHTML = `<i class="fas fa-${icon} me-2"></i><span>${message}</span>`;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl+S - Start/Stop
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                if (this.detectionActive) {
                    this.stopDetection();
                } else {
                    this.startDetection();
                }
            }
            
            // Ctrl+E - Export
            if (e.ctrlKey && e.key === 'e') {
                e.preventDefault();
                this.exportData();
            }
            
            // Esc - Clear alerts
            if (e.key === 'Escape') {
                this.alertHistory = [];
                if (this.alertList) {
                    this.alertList.innerHTML = '<div class="no-alerts"><i class="fas fa-check-circle"></i> No alerts</div>';
                }
            }
        });
    }

    // Update management
    pauseUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    resumeUpdates() {
        this.pauseUpdates();
        this.updateInterval = setInterval(() => this.fetchStatus(), 1000);
    }

    // Cleanup
    destroy() {
        this.pauseUpdates();
        if (this.socket) {
            this.socket.disconnect();
        }
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    // Add slideOut animation if not exists
    if (!document.querySelector('#dashboard-animations')) {
        const style = document.createElement('style');
        style.id = 'dashboard-animations';
        style.textContent = `
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    try {
        window.dashboard = new DashboardManager();
        console.log('✅ Dashboard initialized');
    } catch (error) {
        console.error('Failed to initialize dashboard:', error);
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.dashboard) {
        window.dashboard.destroy();
    }
});