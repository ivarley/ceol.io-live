/**
 * AutoSave Management Module for Session Instance Detail Beta
 * Handles auto-save functionality, dirty state tracking, and save operations
 */

import { TunePillsData } from './stateManager.js';

export interface SaveData {
    success: boolean;
    message?: string;
}

export interface SaveTune {
    tune_id: number | null;
    name: string | null;
    tune_name: string | null;
    started_by_person_id: number | null;
}

export interface UserConfig {
    isUserLoggedIn?: boolean;
    userAutoSave?: boolean;
    userAutoSaveInterval?: number;
}

export class AutoSaveTimer {
    public timer: number | null = null;
    public seconds: number = 0;
    public intervalSeconds: number = 60;
    public isRunning: boolean = false;
    
    constructor() {}
    
    start(intervalSeconds: number): void {
        this.stop(); // Always stop any existing timer first
        this.intervalSeconds = intervalSeconds;
        this.seconds = intervalSeconds;
        this.isRunning = true;
        
        // Update UI immediately
        this.updateDisplay();
        this.showCountdown();
        
        // Start the countdown
        this.timer = window.setInterval(() => {
            this.seconds--;
            this.updateDisplay();
            
            if (this.seconds <= 0) {
                this.stop();
                this.hideCountdown();
                
                // Trigger auto-save
                if (AutoSaveManager.isDirty) {
                    AutoSaveManager.saveSession().then(() => {
                        // After saving, restart if still enabled and dirty again
                        const autoSaveCheckbox = document.getElementById('auto-save-checkbox') as HTMLInputElement | null;
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
    
    reset(intervalSeconds?: number): void {
        if (this.isRunning) {
            this.start(intervalSeconds || this.intervalSeconds);
        }
    }
    
    stop(): void {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
        this.isRunning = false;
    }
    
    updateDisplay(): void {
        const countdownSecondsElement = document.getElementById('countdown-seconds');
        const countdownSecondsMobileElement = document.getElementById('countdown-seconds-mobile');
        if (countdownSecondsElement) {
            countdownSecondsElement.textContent = this.seconds.toString();
        }
        if (countdownSecondsMobileElement) {
            countdownSecondsMobileElement.textContent = this.seconds.toString();
        }
    }
    
    showCountdown(): void {
        const countdownElement = document.getElementById('auto-save-countdown') as HTMLElement | null;
        if (countdownElement) {
            countdownElement.style.display = 'inline';
        }
    }
    
    hideCountdown(): void {
        const countdownElement = document.getElementById('auto-save-countdown') as HTMLElement | null;
        if (countdownElement) {
            countdownElement.style.display = 'none';
        }
    }
}

export class AutoSaveManager {
    static isDirty: boolean = false;
    static lastSavedData: TunePillsData | null = null;
    static lastCheckedData: TunePillsData | null = null;
    static autoSaveTimer: AutoSaveTimer = new AutoSaveTimer();
    static sessionPath: string | null = null;
    static sessionDate: string | null = null;
    static getTunePillsData: (() => TunePillsData) | null = null; // Function to get current data
    static isUserLoggedIn: boolean = false;
    static userAutoSave: boolean = false;
    static userAutoSaveInterval: number = 60;
    
    static initialize(
        sessionPath: string, 
        sessionDate: string, 
        getTunePillsDataFunc?: () => TunePillsData, 
        userConfig: UserConfig = {}
    ): void {
        this.sessionPath = sessionPath;
        this.sessionDate = sessionDate;
        this.getTunePillsData = getTunePillsDataFunc || (() => (window as any).tunePillsData);
        this.isUserLoggedIn = userConfig.isUserLoggedIn || false;
        this.userAutoSave = userConfig.userAutoSave || false;
        this.userAutoSaveInterval = userConfig.userAutoSaveInterval || 60;
    }
    
    static forceCheckChanges(): void {
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
            const saveBtn = document.getElementById('save-session-btn') as HTMLButtonElement | null;
            if (saveBtn) {
                saveBtn.disabled = !this.isDirty;
            }
            
            // Handle auto-save timer
            const autoSaveCheckbox = document.getElementById('auto-save-checkbox') as HTMLInputElement | null;
            if (autoSaveCheckbox && autoSaveCheckbox.checked) {
                const intervalSelect = document.getElementById('auto-save-interval') as HTMLSelectElement | null;
                const intervalSeconds = parseInt(intervalSelect?.value || '60');
                
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
    
    static checkDirtyState(): void {
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
            const autoSaveCheckbox = document.getElementById('auto-save-checkbox') as HTMLInputElement | null;
            if (autoSaveCheckbox && autoSaveCheckbox.checked && this.autoSaveTimer.isRunning) {
                const intervalSelect = document.getElementById('auto-save-interval') as HTMLSelectElement | null;
                this.autoSaveTimer.reset(parseInt(intervalSelect?.value || '60'));
            }
        }
        
        // Handle dirty state changes
        if (isCurrentlyDirty !== this.isDirty) {
            const wasDirty = this.isDirty;
            this.isDirty = isCurrentlyDirty;
            const saveBtn = document.getElementById('save-session-btn') as HTMLButtonElement | null;
            if (saveBtn) {
                saveBtn.disabled = !this.isDirty;
            }
            
            // If we just became dirty and auto-save is enabled, start countdown
            if (!wasDirty && this.isDirty) {
                const autoSaveCheckbox = document.getElementById('auto-save-checkbox') as HTMLInputElement | null;
                if (autoSaveCheckbox && autoSaveCheckbox.checked) {
                    const intervalSelect = document.getElementById('auto-save-interval') as HTMLSelectElement | null;
                    this.autoSaveTimer.start(parseInt(intervalSelect?.value || '60'));
                }
            }
            // If we just became clean, stop countdown
            else if (wasDirty && !this.isDirty) {
                this.autoSaveTimer.stop();
                this.autoSaveTimer.hideCountdown();
            }
        }
    }
    
    static markDirty(): void {
        // Call checkDirtyState instead of directly setting dirty
        this.checkDirtyState();
    }
    
    static markClean(): void {
        this.isDirty = false;
        const saveBtn = document.getElementById('save-session-btn') as HTMLButtonElement | null;
        if (saveBtn) {
            saveBtn.disabled = true;
        }
        if (this.getTunePillsData) {
            const tunePillsData = this.getTunePillsData();
            this.lastSavedData = JSON.parse(JSON.stringify(tunePillsData));
        }
    }
    
    static saveSession(): Promise<void> {
        if (!this.getTunePillsData) {
            console.error('AutoSaveManager not initialized');
            return Promise.reject(new Error('AutoSaveManager not initialized'));
        }
        
        // Disable save button and show status
        const saveBtn = document.getElementById('save-session-btn') as HTMLButtonElement | null;
        const saveStatus = document.getElementById('save-status') as HTMLElement | null;
        
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
                tune_name: pill.tuneName || null,
                started_by_person_id: pill.startedByPersonId || null
            } as SaveTune))
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
        .then((data: SaveData) => {
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
        .catch((error: Error) => {
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
    
    static initializeAutoSavePreference(): void {
        const autoSaveCheckbox = document.getElementById('auto-save-checkbox') as HTMLInputElement | null;
        const intervalSelect = document.getElementById('auto-save-interval') as HTMLSelectElement | null;
        
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
    
    static saveAutoSavePreference(isEnabled: boolean, interval?: number): void {
        const intervalSelect = document.getElementById('auto-save-interval') as HTMLSelectElement | null;
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
    
    static getCookie(name: string): string | null {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop()!.split(';').shift() || null;
        return null;
    }
    
    static setCookie(name: string, value: string, days: number): void {
        let expires = "";
        if (days) {
            const date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + (value || "") + expires + "; path=/; SameSite=Lax";
    }
    
    static setupAutoSave(): void {
        const autoSaveCheckbox = document.getElementById('auto-save-checkbox') as HTMLInputElement | null;
        const intervalSelect = document.getElementById('auto-save-interval') as HTMLSelectElement | null;
        
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
    
    static cancelAutoSave(): void {
        const autoSaveCheckbox = document.getElementById('auto-save-checkbox') as HTMLInputElement | null;
        
        if (!autoSaveCheckbox) return;
        
        // Uncheck the checkbox
        autoSaveCheckbox.checked = false;
        
        // Stop timer and hide countdown
        this.autoSaveTimer.stop();
        this.autoSaveTimer.hideCountdown();
    }
    
    static updateOptionText(): void {
        const select = document.getElementById('auto-save-interval') as HTMLSelectElement | null;
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
declare global {
    interface Window {
        AutoSaveManager: typeof AutoSaveManager;
    }
}

(window as any).AutoSaveManager = AutoSaveManager;