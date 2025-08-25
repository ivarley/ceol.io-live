/**
 * StateManager Module for Session Instance Detail Beta
 * Handles undo/redo functionality, data state management, and data conversion
 */

class StateManager {
    static tunePillsData = [];
    static undoStack = [];
    static redoStack = [];
    static maxUndoSize = 50;
    static changeCallback = null; // Called when state changes
    
    static initialize(changeCallback) {
        this.tunePillsData = [];
        this.undoStack = [];
        this.redoStack = [];
        this.changeCallback = changeCallback;
    }
    
    static getTunePillsData() {
        return this.tunePillsData;
    }
    
    static setTunePillsData(data) {
        this.tunePillsData = data;
        if (this.changeCallback) {
            this.changeCallback();
        }
    }
    
    static saveToUndo() {
        this.undoStack.push(JSON.parse(JSON.stringify(this.tunePillsData)));
        this.redoStack.length = 0; // Clear redo stack when new action is performed
        
        // Limit undo stack size
        if (this.undoStack.length > this.maxUndoSize) {
            this.undoStack.shift();
        }
    }
    
    static undo() {
        if (this.undoStack.length === 0) return false;
        
        this.redoStack.push(JSON.parse(JSON.stringify(this.tunePillsData)));
        this.tunePillsData = this.undoStack.pop();
        
        if (this.changeCallback) {
            this.changeCallback();
        }
        return true;
    }
    
    static redo() {
        if (this.redoStack.length === 0) return false;
        
        this.undoStack.push(JSON.parse(JSON.stringify(this.tunePillsData)));
        this.tunePillsData = this.redoStack.pop();
        
        if (this.changeCallback) {
            this.changeCallback();
        }
        return true;
    }
    
    static canUndo() {
        return this.undoStack.length > 0;
    }
    
    static canRedo() {
        return this.redoStack.length > 0;
    }
    
    static getUndoStackSize() {
        return this.undoStack.length;
    }
    
    static getRedoStackSize() {
        return this.redoStack.length;
    }
    
    static clearHistory() {
        this.undoStack.length = 0;
        this.redoStack.length = 0;
    }
    
    static generateId() {
        return 'pill_' + Math.random().toString(36).substr(2, 9);
    }
    
    static convertTuneSetsToPills(tuneSets, skipCallback = false) {
        this.tunePillsData = [];
        
        if (!tuneSets || tuneSets.length === 0) {
            return;
        }
        
        tuneSets.forEach(tuneSet => {
            const setData = [];
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
    
    static addTuneSet(tuneSet) {
        this.saveToUndo();
        this.tunePillsData.push(tuneSet);
        if (this.changeCallback) {
            this.changeCallback();
        }
    }
    
    static removeTuneSet(setIndex) {
        if (setIndex >= 0 && setIndex < this.tunePillsData.length) {
            this.saveToUndo();
            this.tunePillsData.splice(setIndex, 1);
            if (this.changeCallback) {
                this.changeCallback();
            }
        }
    }
    
    static addTune(setIndex, tune, tuneIndex = -1) {
        if (setIndex >= 0 && setIndex < this.tunePillsData.length) {
            this.saveToUndo();
            if (tuneIndex === -1) {
                this.tunePillsData[setIndex].push(tune);
            } else {
                this.tunePillsData[setIndex].splice(tuneIndex, 0, tune);
            }
            if (this.changeCallback) {
                this.changeCallback();
            }
        }
    }
    
    static removeTune(setIndex, tuneIndex) {
        if (setIndex >= 0 && setIndex < this.tunePillsData.length &&
            tuneIndex >= 0 && tuneIndex < this.tunePillsData[setIndex].length) {
            this.saveToUndo();
            this.tunePillsData[setIndex].splice(tuneIndex, 1);
            
            // Remove empty sets
            if (this.tunePillsData[setIndex].length === 0) {
                this.tunePillsData.splice(setIndex, 1);
            }
            
            if (this.changeCallback) {
                this.changeCallback();
            }
        }
    }
    
    static updateTune(setIndex, tuneIndex, updates) {
        if (setIndex >= 0 && setIndex < this.tunePillsData.length &&
            tuneIndex >= 0 && tuneIndex < this.tunePillsData[setIndex].length) {
            this.saveToUndo();
            Object.assign(this.tunePillsData[setIndex][tuneIndex], updates);
            if (this.changeCallback) {
                this.changeCallback();
            }
        }
    }
    
    static findTuneById(tuneId) {
        for (let setIndex = 0; setIndex < this.tunePillsData.length; setIndex++) {
            for (let tuneIndex = 0; tuneIndex < this.tunePillsData[setIndex].length; tuneIndex++) {
                if (this.tunePillsData[setIndex][tuneIndex].id === tuneId) {
                    return { setIndex, tuneIndex, tune: this.tunePillsData[setIndex][tuneIndex] };
                }
            }
        }
        return null;
    }
    
    static getTuneCount() {
        return this.tunePillsData.reduce((count, set) => count + set.length, 0);
    }
    
    static getSetCount() {
        return this.tunePillsData.length;
    }
    
    static exportData() {
        return JSON.parse(JSON.stringify(this.tunePillsData));
    }
    
    static importData(data) {
        this.saveToUndo();
        this.tunePillsData = JSON.parse(JSON.stringify(data));
        if (this.changeCallback) {
            this.changeCallback();
        }
    }
}

// Export for use in other modules or global scope
window.StateManager = StateManager;