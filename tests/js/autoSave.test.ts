import { AutoSaveTimer, AutoSaveManager, UserConfig } from '../../src/ts/components/autoSave';
import { TunePillsData } from '../../src/ts/components/stateManager';

// Mock the global fetch function
global.fetch = jest.fn();

describe('AutoSaveTimer', () => {
    let autoSaveTimer: AutoSaveTimer;

    beforeEach(() => {
        autoSaveTimer = new AutoSaveTimer();
        
        // Mock DOM elements
        document.body.innerHTML = `
            <span id="countdown-seconds">60</span>
            <span id="countdown-seconds-mobile">60</span>
            <div id="auto-save-countdown" style="display: none;"></div>
        `;
        
        // Clear all timers
        jest.clearAllTimers();
        jest.useFakeTimers();
        
        // Mock AutoSaveManager for timer callback
        AutoSaveManager.isDirty = false;
        AutoSaveManager.saveSession = jest.fn().mockResolvedValue({ success: true });
    });

    afterEach(() => {
        autoSaveTimer.stop();
        jest.useRealTimers();
        document.body.innerHTML = '';
    });

    describe('initialization', () => {
        test('should initialize with default values', () => {
            expect(autoSaveTimer.timer).toBeNull();
            expect(autoSaveTimer.seconds).toBe(0);
            expect(autoSaveTimer.intervalSeconds).toBe(60);
            expect(autoSaveTimer.isRunning).toBe(false);
        });
    });

    describe('timer control', () => {
        test('should start timer with specified interval', () => {
            autoSaveTimer.start(30);

            expect(autoSaveTimer.intervalSeconds).toBe(30);
            expect(autoSaveTimer.seconds).toBe(30);
            expect(autoSaveTimer.isRunning).toBe(true);
            expect(autoSaveTimer.timer).not.toBeNull();
        });

        test('should stop existing timer before starting new one', () => {
            autoSaveTimer.start(60);
            const firstTimer = autoSaveTimer.timer;

            autoSaveTimer.start(30);

            expect(autoSaveTimer.timer).not.toBe(firstTimer);
            expect(autoSaveTimer.intervalSeconds).toBe(30);
        });

        test('should stop timer', () => {
            autoSaveTimer.start(60);
            expect(autoSaveTimer.isRunning).toBe(true);

            autoSaveTimer.stop();

            expect(autoSaveTimer.isRunning).toBe(false);
            expect(autoSaveTimer.timer).toBeNull();
        });

        test('should reset timer if running', () => {
            autoSaveTimer.start(60);
            autoSaveTimer.seconds = 30; // Simulate timer countdown

            autoSaveTimer.reset(45);

            expect(autoSaveTimer.seconds).toBe(45);
            expect(autoSaveTimer.intervalSeconds).toBe(45);
        });

        test('should not restart timer when reset if not running', () => {
            autoSaveTimer.intervalSeconds = 60;

            autoSaveTimer.reset(30);

            expect(autoSaveTimer.isRunning).toBe(false);
            expect(autoSaveTimer.intervalSeconds).toBe(60); // Should not change
        });
    });

    describe('countdown behavior', () => {
        beforeEach(() => {
            // Mock DOM elements for auto-save checkbox
            const checkboxHtml = '<input type="checkbox" id="auto-save-checkbox" checked>';
            document.body.insertAdjacentHTML('beforeend', checkboxHtml);
        });

        test('should countdown and update display', () => {
            autoSaveTimer.start(3);

            expect(document.getElementById('countdown-seconds')?.textContent).toBe('3');

            // Advance timer by 1 second
            jest.advanceTimersByTime(1000);
            expect(autoSaveTimer.seconds).toBe(2);
            expect(document.getElementById('countdown-seconds')?.textContent).toBe('2');

            // Advance timer by 1 more second
            jest.advanceTimersByTime(1000);
            expect(autoSaveTimer.seconds).toBe(1);
            expect(document.getElementById('countdown-seconds')?.textContent).toBe('1');
        });

        test('should trigger auto-save when countdown reaches zero and isDirty', () => {
            AutoSaveManager.isDirty = true;
            autoSaveTimer.start(1);

            jest.advanceTimersByTime(1000);

            expect(AutoSaveManager.saveSession).toHaveBeenCalled();
            expect(autoSaveTimer.isRunning).toBe(false);
        });

        test('should not trigger auto-save when countdown reaches zero and not dirty', () => {
            AutoSaveManager.isDirty = false;
            autoSaveTimer.start(1);

            jest.advanceTimersByTime(1000);

            expect(AutoSaveManager.saveSession).not.toHaveBeenCalled();
            expect(autoSaveTimer.isRunning).toBe(false);
        });

        test('should restart timer after successful save if still dirty', async () => {
            AutoSaveManager.isDirty = true;
            AutoSaveManager.saveSession = jest.fn().mockResolvedValue({ success: true });
            
            autoSaveTimer.start(1);
            jest.advanceTimersByTime(1000);

            // Wait for the promise to resolve
            await Promise.resolve();

            expect(AutoSaveManager.saveSession).toHaveBeenCalled();
        });

        test('should not restart timer after failed save', async () => {
            AutoSaveManager.isDirty = true;
            AutoSaveManager.saveSession = jest.fn().mockRejectedValue(new Error('Save failed'));
            
            autoSaveTimer.start(1);
            jest.advanceTimersByTime(1000);

            // Wait for the promise to reject
            await Promise.resolve();

            expect(AutoSaveManager.saveSession).toHaveBeenCalled();
            expect(autoSaveTimer.isRunning).toBe(false);
        });
    });

    describe('display management', () => {
        test('should update countdown display in both elements', () => {
            autoSaveTimer.seconds = 45;
            autoSaveTimer.updateDisplay();

            expect(document.getElementById('countdown-seconds')?.textContent).toBe('45');
            expect(document.getElementById('countdown-seconds-mobile')?.textContent).toBe('45');
        });

        test('should handle missing display elements gracefully', () => {
            document.getElementById('countdown-seconds')?.remove();
            document.getElementById('countdown-seconds-mobile')?.remove();

            expect(() => {
                autoSaveTimer.updateDisplay();
            }).not.toThrow();
        });

        test('should show countdown', () => {
            const countdownElement = document.getElementById('auto-save-countdown') as HTMLElement;
            countdownElement.style.display = 'none';

            autoSaveTimer.showCountdown();

            expect(countdownElement.style.display).toBe('inline');
        });

        test('should hide countdown', () => {
            const countdownElement = document.getElementById('auto-save-countdown') as HTMLElement;
            countdownElement.style.display = 'inline';

            autoSaveTimer.hideCountdown();

            expect(countdownElement.style.display).toBe('none');
        });
    });
});

describe('AutoSaveManager', () => {
    let mockTunePillsData: TunePillsData;
    let getTunePillsDataMock: jest.Mock;

    beforeEach(() => {
        mockTunePillsData = [
            [
                { id: 'tune1', orderNumber: 1, tuneId: 123, tuneName: 'Test Tune', setting: 'A', tuneType: 'jig', state: 'linked' }
            ]
        ];

        getTunePillsDataMock = jest.fn().mockReturnValue(mockTunePillsData);

        // Reset static state
        AutoSaveManager.isDirty = false;
        AutoSaveManager.lastSavedData = null;
        AutoSaveManager.lastCheckedData = null;
        AutoSaveManager.sessionPath = null;
        AutoSaveManager.sessionDate = null;
        AutoSaveManager.getTunePillsData = null;

        // Mock DOM elements
        document.body.innerHTML = `
            <button id="save-session-btn">Save Session</button>
            <input type="checkbox" id="auto-save-checkbox">
            <select id="auto-save-interval">
                <option value="60">60</option>
                <option value="120">120</option>
            </select>
        `;

        // Mock the timer
        AutoSaveManager.autoSaveTimer = {
            start: jest.fn(),
            stop: jest.fn(),
            reset: jest.fn(),
            hideCountdown: jest.fn(),
            isRunning: false
        } as any;
    });

    afterEach(() => {
        document.body.innerHTML = '';
        jest.clearAllMocks();
    });

    describe('initialization', () => {
        test('should initialize with basic parameters', () => {
            AutoSaveManager.initialize('/session/123', '2024-01-01', getTunePillsDataMock);

            expect(AutoSaveManager.sessionPath).toBe('/session/123');
            expect(AutoSaveManager.sessionDate).toBe('2024-01-01');
            expect(AutoSaveManager.getTunePillsData).toBe(getTunePillsDataMock);
            expect(AutoSaveManager.isUserLoggedIn).toBe(false);
            expect(AutoSaveManager.userAutoSave).toBe(false);
            expect(AutoSaveManager.userAutoSaveInterval).toBe(60);
        });

        test('should initialize with user configuration', () => {
            const userConfig: UserConfig = {
                isUserLoggedIn: true,
                userAutoSave: true,
                userAutoSaveInterval: 120
            };

            AutoSaveManager.initialize('/session/123', '2024-01-01', getTunePillsDataMock, userConfig);

            expect(AutoSaveManager.isUserLoggedIn).toBe(true);
            expect(AutoSaveManager.userAutoSave).toBe(true);
            expect(AutoSaveManager.userAutoSaveInterval).toBe(120);
        });

        test('should use window.tunePillsData when getTunePillsDataFunc not provided', () => {
            (window as any).tunePillsData = mockTunePillsData;

            AutoSaveManager.initialize('/session/123', '2024-01-01');

            const result = AutoSaveManager.getTunePillsData!();
            expect(result).toBe(mockTunePillsData);
        });
    });

    describe('change detection', () => {
        beforeEach(() => {
            AutoSaveManager.initialize('/session/123', '2024-01-01', getTunePillsDataMock);
        });

        test('should detect changes and mark as dirty', () => {
            AutoSaveManager.lastSavedData = [];
            
            AutoSaveManager.forceCheckChanges();

            expect(AutoSaveManager.isDirty).toBe(true);
            expect(AutoSaveManager.lastCheckedData).toEqual(mockTunePillsData);
        });

        test('should not mark as dirty when data matches saved data', () => {
            AutoSaveManager.lastSavedData = JSON.parse(JSON.stringify(mockTunePillsData));
            
            AutoSaveManager.forceCheckChanges();

            expect(AutoSaveManager.isDirty).toBe(false);
        });

        test('should handle missing getTunePillsData gracefully', () => {
            AutoSaveManager.getTunePillsData = null;

            expect(() => {
                AutoSaveManager.forceCheckChanges();
            }).not.toThrow();

            expect(AutoSaveManager.isDirty).toBe(false);
        });

        test('should handle null data from getTunePillsData', () => {
            AutoSaveManager.getTunePillsData = jest.fn().mockReturnValue(null);

            expect(() => {
                AutoSaveManager.forceCheckChanges();
            }).not.toThrow();
        });

        test('should update save button disabled state', () => {
            const saveBtn = document.getElementById('save-session-btn') as HTMLButtonElement;
            AutoSaveManager.lastSavedData = [];

            AutoSaveManager.forceCheckChanges();

            expect(AutoSaveManager.isDirty).toBe(true);
            expect(saveBtn.disabled).toBe(false);
        });
    });

    describe('auto-save timer integration', () => {
        beforeEach(() => {
            AutoSaveManager.initialize('/session/123', '2024-01-01', getTunePillsDataMock);
            const checkbox = document.getElementById('auto-save-checkbox') as HTMLInputElement;
            checkbox.checked = true;
        });

        test('should start timer when data becomes dirty', () => {
            AutoSaveManager.lastSavedData = [];

            AutoSaveManager.forceCheckChanges();

            expect(AutoSaveManager.isDirty).toBe(true);
            expect(AutoSaveManager.autoSaveTimer.start).toHaveBeenCalledWith(60);
        });

        test('should stop timer when data is no longer dirty', () => {
            AutoSaveManager.lastSavedData = JSON.parse(JSON.stringify(mockTunePillsData));
            AutoSaveManager.isDirty = true; // Set up initial dirty state

            AutoSaveManager.forceCheckChanges();

            expect(AutoSaveManager.isDirty).toBe(false);
            expect(AutoSaveManager.autoSaveTimer.stop).toHaveBeenCalled();
            expect(AutoSaveManager.autoSaveTimer.hideCountdown).toHaveBeenCalled();
        });

        test('should use custom interval from select element', () => {
            const intervalSelect = document.getElementById('auto-save-interval') as HTMLSelectElement;
            intervalSelect.value = '120';
            AutoSaveManager.lastSavedData = [];

            AutoSaveManager.forceCheckChanges();

            expect(AutoSaveManager.autoSaveTimer.start).toHaveBeenCalledWith(120);
        });

        test('should not start timer when auto-save is disabled', () => {
            const checkbox = document.getElementById('auto-save-checkbox') as HTMLInputElement;
            checkbox.checked = false;
            AutoSaveManager.lastSavedData = [];

            AutoSaveManager.forceCheckChanges();

            expect(AutoSaveManager.autoSaveTimer.start).not.toHaveBeenCalled();
        });
    });

    describe('checkDirtyState', () => {
        beforeEach(() => {
            AutoSaveManager.initialize('/session/123', '2024-01-01', getTunePillsDataMock);
        });

        test('should reset timer on data change when auto-save is enabled', () => {
            const checkbox = document.getElementById('auto-save-checkbox') as HTMLInputElement;
            checkbox.checked = true;
            (AutoSaveManager.autoSaveTimer as any).isRunning = true;
            
            AutoSaveManager.lastCheckedData = []; // Different from current data

            AutoSaveManager.checkDirtyState();

            expect(AutoSaveManager.autoSaveTimer.reset).toHaveBeenCalledWith(60);
        });

        test('should not reset timer when data has not changed', () => {
            AutoSaveManager.lastCheckedData = JSON.parse(JSON.stringify(mockTunePillsData));

            AutoSaveManager.checkDirtyState();

            expect(AutoSaveManager.autoSaveTimer.reset).not.toHaveBeenCalled();
        });

        test('should handle missing getTunePillsData gracefully', () => {
            AutoSaveManager.getTunePillsData = null;

            expect(() => {
                AutoSaveManager.checkDirtyState();
            }).not.toThrow();
        });
    });
});