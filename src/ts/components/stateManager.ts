/**
 * StateManager Module for Session Instance Detail Beta
 * Handles undo/redo functionality, data state management, and data conversion
 */

// Type definitions
export interface TunePill {
    id: string;
    orderNumber: number;
    tuneId: number | null;
    tuneName: string;
    setting: string;
    tuneType: string;
    state: 'linked' | 'unlinked';
}

export interface TuneSet extends Array<TunePill> {}

export interface TunePillsData extends Array<TuneSet> {}

export interface TunePosition {
    setIndex: number;
    tuneIndex: number;
    tune: TunePill;
}

// Raw tune data from backend (array format)
export type RawTune = [number, boolean, number | null, string, string, string];
export type RawTuneSet = RawTune[];
export type RawTuneSets = RawTuneSet[];

export type ChangeCallback = () => void;

export class StateManager {
    private static tunePillsData: TunePillsData = [];
    private static undoStack: TunePillsData[] = [];
    private static redoStack: TunePillsData[] = [];
    private static maxUndoSize: number = 50;
    private static changeCallback: ChangeCallback | null = null;
    
    public static initialize(changeCallback: ChangeCallback): void {
        this.tunePillsData = [];
        this.undoStack = [];
        this.redoStack = [];
        this.changeCallback = changeCallback;
    }
    
    public static getTunePillsData(): TunePillsData {
        return this.tunePillsData;
    }
    
    public static setTunePillsData(data: TunePillsData): void {
        this.tunePillsData = data;
        if (this.changeCallback) {
            this.changeCallback();
        }
    }
    
    public static saveToUndo(): void {
        this.undoStack.push(JSON.parse(JSON.stringify(this.tunePillsData)));
        this.redoStack.length = 0; // Clear redo stack when new action is performed
        
        // Limit undo stack size
        if (this.undoStack.length > this.maxUndoSize) {
            this.undoStack.shift();
        }
    }
    
    public static undo(): boolean {
        if (this.undoStack.length === 0) return false;
        
        this.redoStack.push(JSON.parse(JSON.stringify(this.tunePillsData)));
        const undoData = this.undoStack.pop();
        if (undoData) {
            this.tunePillsData = undoData;
        }
        
        if (this.changeCallback) {
            this.changeCallback();
        }
        return true;
    }
    
    public static redo(): boolean {
        if (this.redoStack.length === 0) return false;
        
        this.undoStack.push(JSON.parse(JSON.stringify(this.tunePillsData)));
        const redoData = this.redoStack.pop();
        if (redoData) {
            this.tunePillsData = redoData;
        }
        
        if (this.changeCallback) {
            this.changeCallback();
        }
        return true;
    }
    
    public static canUndo(): boolean {
        return this.undoStack.length > 0;
    }
    
    public static canRedo(): boolean {
        return this.redoStack.length > 0;
    }
    
    public static getUndoStackSize(): number {
        return this.undoStack.length;
    }
    
    public static getRedoStackSize(): number {
        return this.redoStack.length;
    }
    
    public static clearHistory(): void {
        this.undoStack.length = 0;
        this.redoStack.length = 0;
    }
    
    public static generateId(): string {
        return 'pill_' + Math.random().toString(36).substr(2, 9);
    }
    
    public static convertTuneSetsToPills(tuneSets: RawTuneSets, skipCallback: boolean = false): void {
        this.tunePillsData = [];
        
        if (!tuneSets || tuneSets.length === 0) {
            return;
        }
        
        tuneSets.forEach(tuneSet => {
            const setData: TuneSet = [];
            tuneSet.forEach(tune => {
                const [orderNumber, continuesSet, tuneId, tuneName, setting, tuneType] = tune;
                setData.push({
                    id: this.generateId(),
                    orderNumber: orderNumber,
                    tuneId: tuneId,
                    tuneName: tuneName,
                    setting: setting,
                    tuneType: tuneType,
                    state: tuneId ? 'linked' : 'unlinked'
                });
            });
            if (setData.length > 0) {
                this.tunePillsData.push(setData);
            }
        });
        
        if (!skipCallback && this.changeCallback) {
            this.changeCallback();
        }
    }
    
    public static addTuneSet(tuneSet: TuneSet): void {
        this.saveToUndo();
        this.tunePillsData.push(tuneSet);
        if (this.changeCallback) {
            this.changeCallback();
        }
    }
    
    public static removeTuneSet(setIndex: number): void {
        if (setIndex >= 0 && setIndex < this.tunePillsData.length) {
            this.saveToUndo();
            this.tunePillsData.splice(setIndex, 1);
            if (this.changeCallback) {
                this.changeCallback();
            }
        }
    }
    
    public static addTune(setIndex: number, tune: TunePill, tuneIndex: number = -1): void {
        if (setIndex >= 0 && setIndex < this.tunePillsData.length) {
            this.saveToUndo();
            if (tuneIndex === -1) {
                this.tunePillsData[setIndex]!.push(tune);
            } else {
                this.tunePillsData[setIndex]!.splice(tuneIndex, 0, tune);
            }
            if (this.changeCallback) {
                this.changeCallback();
            }
        }
    }
    
    public static removeTune(setIndex: number, tuneIndex: number): void {
        if (setIndex >= 0 && setIndex < this.tunePillsData.length &&
            tuneIndex >= 0 && tuneIndex < this.tunePillsData[setIndex]!.length) {
            this.saveToUndo();
            this.tunePillsData[setIndex]!.splice(tuneIndex, 1);
            
            // Remove empty sets
            if (this.tunePillsData[setIndex]!.length === 0) {
                this.tunePillsData.splice(setIndex, 1);
            }
            
            if (this.changeCallback) {
                this.changeCallback();
            }
        }
    }
    
    public static updateTune(setIndex: number, tuneIndex: number, updates: Partial<TunePill>): void {
        if (setIndex >= 0 && setIndex < this.tunePillsData.length &&
            tuneIndex >= 0 && tuneIndex < this.tunePillsData[setIndex]!.length) {
            this.saveToUndo();
            Object.assign(this.tunePillsData[setIndex]![tuneIndex]!, updates);
            if (this.changeCallback) {
                this.changeCallback();
            }
        }
    }
    
    public static findTuneById(tuneId: string): TunePosition | null {
        for (let setIndex = 0; setIndex < this.tunePillsData.length; setIndex++) {
            const tuneSet = this.tunePillsData[setIndex]!;
            for (let tuneIndex = 0; tuneIndex < tuneSet.length; tuneIndex++) {
                if (tuneSet[tuneIndex]!.id === tuneId) {
                    return { setIndex, tuneIndex, tune: tuneSet[tuneIndex]! };
                }
            }
        }
        return null;
    }
    
    public static getTuneCount(): number {
        return this.tunePillsData.reduce((count, set) => count + set.length, 0);
    }
    
    public static getSetCount(): number {
        return this.tunePillsData.length;
    }
    
    public static exportData(): TunePillsData {
        return JSON.parse(JSON.stringify(this.tunePillsData));
    }
    
    public static importData(data: TunePillsData): void {
        this.saveToUndo();
        this.tunePillsData = JSON.parse(JSON.stringify(data));
        if (this.changeCallback) {
            this.changeCallback();
        }
    }
}

// Export for use in other modules or global scope
declare global {
    interface Window {
        StateManager: typeof StateManager;
    }
}

(window as any).StateManager = StateManager;