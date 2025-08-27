/**
 * AutoSave Management Module for Session Instance Detail Beta
 * Handles auto-save functionality, dirty state tracking, and save operations
 */

class AutoSaveTimer {
    constructor() {
        this.timer = null;
        this.seconds = 0;
        this.intervalSeconds = 60;
        this.isRunning = false;
    }
    
    start(intervalSeconds) {
        this.stop(); // Always stop any existing timer first
        this.intervalSeconds = intervalSeconds;
        this.seconds = intervalSeconds;
        this.isRunning = true;
        
        // Update UI immediately
        this.updateDisplay();
        this.showCountdown();
        
        // Start the countdown
        this.timer = setInterval(() => {
            this.seconds--;
            this.updateDisplay();
            
            if (this.seconds <= 0) {
                this.stop();
                this.hideCountdown();
                
                // Trigger auto-save
                if (AutoSaveManager.isDirty) {
                    AutoSaveManager.saveSession().then(() => {
                        // After saving, restart if still enabled and dirty again
                        const autoSaveCheckbox = document.getElementById('auto-save-checkbox');
                        if (autoSaveCheckbox && autoSaveCheckbox.checked && AutoSaveManager.isDirty) {
                            this.start(this.intervalSeconds);
                        }
                    }).catch(() => {
                        // On save error, don't restart timer
                    });
                }
            }
        }, 1000);
    }
    
    reset(intervalSeconds) {
        if (this.isRunning) {
            this.start(intervalSeconds || this.intervalSeconds);
        }
    }
    
    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
        this.isRunning = false;
    }
    
    updateDisplay() {
        const countdownSecondsElement = document.getElementById('countdown-seconds');
        const countdownSecondsMobileElement = document.getElementById('countdown-seconds-mobile');
        if (countdownSecondsElement) {
            countdownSecondsElement.textContent = this.seconds;
        }
        if (countdownSecondsMobileElement) {
            countdownSecondsMobileElement.textContent = this.seconds;
        }
    }
    
    showCountdown() {
        const countdownElement = document.getElementById('auto-save-countdown');
        if (countdownElement) {
            countdownElement.style.display = 'inline';
        }
    }
    
    hideCountdown() {
        const countdownElement = document.getElementById('auto-save-countdown');
        if (countdownElement) {
            countdownElement.style.display = 'none';
        }
    }
}

class AutoSaveManager {
    static isDirty = false;
    static lastSavedData = null;
    static lastCheckedData = null;
    static autoSaveTimer = new AutoSaveTimer();
    static sessionPath = null;
    static sessionDate = null;
    static getTunePillsData = null; // Function to get current data
    static isUserLoggedIn = false;
    static userAutoSave = false;
    static userAutoSaveInterval = 60;
    
    static initialize(sessionPath, sessionDate, getTunePillsDataFunc, userConfig = {}) {
        this.sessionPath = sessionPath;
        this.sessionDate = sessionDate;
        this.getTunePillsData = getTunePillsDataFunc || (() => window.tunePillsData);
        this.isUserLoggedIn = userConfig.isUserLoggedIn || false;
        this.userAutoSave = userConfig.userAutoSave || false;
        this.userAutoSaveInterval = userConfig.userAutoSaveInterval || 60;
    }
    
    static forceCheckChanges() {
        if (!this.getTunePillsData) return; // Not initialized yet
        const tunePillsData = this.getTunePillsData();
        if (!tunePillsData) return;
        
        const currentDataStr = JSON.stringify(tunePillsData);
        const lastCheckedDataStr = JSON.stringify(this.lastCheckedData);
        
        if (currentDataStr !== lastCheckedDataStr) {
            // Update lastCheckedData
            this.lastCheckedData = JSON.parse(JSON.stringify(tunePillsData));
            
            // Check dirty state
            const savedDataStr = JSON.stringify(this.lastSavedData);
            const wasDirty = this.isDirty;
            this.isDirty = currentDataStr !== savedDataStr;
            
            // Update save button
            const saveBtn = document.getElementById('save-session-btn');
            if (saveBtn) {
                saveBtn.disabled = !this.isDirty;
            }
            
            // Handle auto-save timer
            const autoSaveCheckbox = document.getElementById('auto-save-checkbox');
            if (autoSaveCheckbox && autoSaveCheckbox.checked) {
                const intervalSelect = document.getElementById('auto-save-interval');
                const intervalSeconds = parseInt(intervalSelect.value);
                
                if (this.isDirty) {
                    // Data changed and we're dirty - start/restart timer
                    this.autoSaveTimer.start(intervalSeconds);
                } else {
                    // Data changed but we're not dirty - stop timer
                    this.autoSaveTimer.stop();
                    this.autoSaveTimer.hideCountdown();
                }
            }
        }
    }
    
    static checkDirtyState() {
        if (!this.getTunePillsData) return; // Not initialized yet
        const tunePillsData = this.getTunePillsData();
        if (!tunePillsData) return;
        
        // Compare current data with last saved data for dirty state
        const currentDataStr = JSON.stringify(tunePillsData);
        const savedDataStr = JSON.stringify(this.lastSavedData);
        const isCurrentlyDirty = currentDataStr !== savedDataStr;
        
        // Check if data has changed since last check (for activity detection)
        const lastCheckedDataStr = JSON.stringify(this.lastCheckedData);
        const dataHasChanged = currentDataStr !== lastCheckedDataStr;
        
        // Update last checked data
        this.lastCheckedData = JSON.parse(JSON.stringify(tunePillsData));
        
        // Reset timer on ANY data change (regardless of dirty state)
        if (dataHasChanged) {
            const autoSaveCheckbox = document.getElementById('auto-save-checkbox');
            if (autoSaveCheckbox && autoSaveCheckbox.checked && this.autoSaveTimer.isRunning) {
                const intervalSelect = document.getElementById('auto-save-interval');
                this.autoSaveTimer.reset(parseInt(intervalSelect.value));
            }
        }
        
        // Handle dirty state changes
        if (isCurrentlyDirty !== this.isDirty) {
            const wasDirty = this.isDirty;
            this.isDirty = isCurrentlyDirty;
            const saveBtn = document.getElementById('save-session-btn');
            if (saveBtn) {
                saveBtn.disabled = !this.isDirty;
            }
            
            // If we just became dirty and auto-save is enabled, start countdown
            if (!wasDirty && this.isDirty) {
                const autoSaveCheckbox = document.getElementById('auto-save-checkbox');
                if (autoSaveCheckbox && autoSaveCheckbox.checked) {
                    const intervalSelect = document.getElementById('auto-save-interval');
                    this.autoSaveTimer.start(parseInt(intervalSelect.value));
                }
            }
            // If we just became clean, stop countdown
            else if (wasDirty && !this.isDirty) {
                this.autoSaveTimer.stop();
                this.autoSaveTimer.hideCountdown();
            }
        }
    }
    
    static markDirty() {
        // Call checkDirtyState instead of directly setting dirty
        this.checkDirtyState();
    }
    
    static markClean() {
        this.isDirty = false;
        const saveBtn = document.getElementById('save-session-btn');
        if (saveBtn) {
            saveBtn.disabled = true;
        }
        if (this.getTunePillsData) {
            const tunePillsData = this.getTunePillsData();
            this.lastSavedData = JSON.parse(JSON.stringify(tunePillsData));
        }
    }
    
    static saveSession() {
        if (!this.getTunePillsData) {
            console.error('AutoSaveManager not initialized');
            return Promise.reject(new Error('AutoSaveManager not initialized'));
        }
        
        // Disable save button and show status
        const saveBtn = document.getElementById('save-session-btn');
        const saveStatus = document.getElementById('save-status');
        
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
        }
        if (saveStatus) {
            saveStatus.style.display = 'inline';
            saveStatus.textContent = 'Saving...';
            saveStatus.style.color = 'var(--text-color)';
        }
        
        // Convert tunePillsData to the format expected by the API
        const tunePillsData = this.getTunePillsData();
        const tuneSets = tunePillsData.map(set => 
            set.map(pill => ({
                tune_id: pill.tuneId || null,
                name: pill.tuneName || null,
                tune_name: pill.tuneName || null
            }))
        );
        
        // Send save request and return the promise
        return fetch(`/api/sessions/${this.sessionPath}/${this.sessionDate}/save_tunes`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ tune_sets: tuneSets })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.markClean();
                if (saveStatus) {
                    saveStatus.textContent = data.message || 'Saved successfully!';
                    saveStatus.style.color = 'var(--success, #28a745)';
                }
                if (saveBtn) {
                    saveBtn.textContent = 'Save Session';
                    saveBtn.disabled = true;  // Ensure button is disabled after successful save
                }
                
                // Hide status message after 3 seconds
                if (saveStatus) {
                    setTimeout(() => {
                        saveStatus.style.display = 'none';
                    }, 3000);
                }
            } else {
                throw new Error(data.message || 'Save failed');
            }
        })
        .catch(error => {
            console.error('Save error:', error);
            if (saveStatus) {
                saveStatus.textContent = 'Save failed: ' + error.message;
                saveStatus.style.color = 'var(--danger, #dc3545)';
            }
            if (saveBtn) {
                saveBtn.textContent = 'Save Session';
                // Re-enable button on error if still dirty
                if (this.isDirty) {
                    saveBtn.disabled = false;
                }
            }
            // Re-throw the error so promise chain can handle it
            throw error;
        });
    }
    
    static initializeAutoSavePreference() {
        const autoSaveCheckbox = document.getElementById('auto-save-checkbox');
        const intervalSelect = document.getElementById('auto-save-interval');
        
        if (!autoSaveCheckbox) return;
        
        if (this.isUserLoggedIn) {
            // For logged-in users, use their stored preferences
            autoSaveCheckbox.checked = this.userAutoSave;
            if (intervalSelect) {
                intervalSelect.value = this.userAutoSaveInterval.toString();
            }
        } else {
            // For anonymous users, check for cookies
            const cookieValue = this.getCookie('auto_save_tunes');
            autoSaveCheckbox.checked = cookieValue === 'true';
            
            const intervalCookie = this.getCookie('auto_save_interval');
            if (intervalSelect && intervalCookie && [10, 30, 60].includes(parseInt(intervalCookie))) {
                intervalSelect.value = intervalCookie;
            }
        }
    }
    
    static saveAutoSavePreference(isEnabled, interval = null) {
        const intervalSelect = document.getElementById('auto-save-interval');
        const saveInterval = interval || (intervalSelect ? parseInt(intervalSelect.value) : 60);
        
        if (this.isUserLoggedIn) {
            // Save to user account via API
            fetch('/api/user/auto-save-preference', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    auto_save: isEnabled,
                    auto_save_interval: saveInterval
                })
            })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    console.error('Failed to save auto-save preference:', data.error);
                }
            })
            .catch(error => {
                console.error('Error saving auto-save preference:', error);
            });
        } else {
            // Save to cookies for anonymous users
            this.setCookie('auto_save_tunes', isEnabled.toString(), 365);
            this.setCookie('auto_save_interval', saveInterval.toString(), 365);
        }
    }
    
    static getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }
    
    static setCookie(name, value, days) {
        let expires = "";
        if (days) {
            const date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + (value || "") + expires + "; path=/; SameSite=Lax";
    }
    
    static setupAutoSave() {
        const autoSaveCheckbox = document.getElementById('auto-save-checkbox');
        const intervalSelect = document.getElementById('auto-save-interval');
        
        if (!autoSaveCheckbox) return;
        
        // Stop any existing timer
        this.autoSaveTimer.stop();
        this.autoSaveTimer.hideCountdown();
        
        // Save preference when checkbox state changes
        const intervalSeconds = intervalSelect ? parseInt(intervalSelect.value) : 60;
        this.saveAutoSavePreference(autoSaveCheckbox.checked, intervalSeconds);
        
        // Start timer if checkbox is checked and we're dirty
        if (autoSaveCheckbox.checked && this.isDirty) {
            this.autoSaveTimer.start(intervalSeconds);
        }
    }
    
    static cancelAutoSave() {
        const autoSaveCheckbox = document.getElementById('auto-save-checkbox');
        
        if (!autoSaveCheckbox) return;
        
        // Uncheck the checkbox
        autoSaveCheckbox.checked = false;
        
        // Stop timer and hide countdown
        this.autoSaveTimer.stop();
        this.autoSaveTimer.hideCountdown();
    }
    
    static updateOptionText() {
        const select = document.getElementById('auto-save-interval');
        const isMobile = window.innerWidth <= 768;
        
        if (select) {
            const options = select.querySelectorAll('option');
            options.forEach(option => {
                const value = option.value;
                if (isMobile) {
                    option.textContent = `${value} sec`;
                } else {
                    option.textContent = `${value} seconds`;
                }
            });
        }
    }
}

// Export for use in other modules or global scope
window.AutoSaveManager = AutoSaveManager;