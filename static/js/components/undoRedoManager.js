// UndoRedoManager - Handles undo/redo functionality
class UndoRedoManager {
    constructor() {
        this.stateManager = null;
        this.autoSaveManager = null;
        this.callbacks = {};
    }

    initialize(dependencies) {
        this.stateManager = dependencies.getStateManager();
        this.autoSaveManager = dependencies.getAutoSaveManager();
    }

    registerCallbacks(callbacks) {
        this.callbacks = { ...this.callbacks, ...callbacks };
    }

    saveToUndo() {
        this.stateManager.saveToUndo();
        // Mark as dirty when any change is made
        this.autoSaveManager.forceCheckChanges();
    }

    undo() {
        if (this.stateManager.undo()) {
            if (this.callbacks.onUndoRedo) {
                this.callbacks.onUndoRedo();
            }
            return true;
        }
        return false;
    }

    redo() {
        if (this.stateManager.redo()) {
            if (this.callbacks.onUndoRedo) {
                this.callbacks.onUndoRedo();
            }
            return true;
        }
        return false;
    }
}

// Create singleton instance
const undoRedoManager = new UndoRedoManager();