/**
 * UndoRedoManager - Handles undo/redo functionality
 * Acts as a wrapper around StateManager's undo/redo functionality
 */

import { StateManager } from './stateManager.js';

// Type definitions
export interface UndoRedoCallbacks {
    onUndoRedo?: () => void;
}

export interface AutoSaveManager {
    forceCheckChanges(): void;
}

export interface Dependencies {
    getStateManager(): typeof StateManager;
    getAutoSaveManager(): AutoSaveManager;
}

export class UndoRedoManager {
    private stateManager: typeof StateManager | null = null;
    private autoSaveManager: AutoSaveManager | null = null;
    private callbacks: UndoRedoCallbacks = {};

    constructor() {
        this.stateManager = null;
        this.autoSaveManager = null;
        this.callbacks = {};
    }

    public initialize(dependencies: Dependencies): void {
        this.stateManager = dependencies.getStateManager();
        this.autoSaveManager = dependencies.getAutoSaveManager();
    }

    public registerCallbacks(callbacks: UndoRedoCallbacks): void {
        this.callbacks = { ...this.callbacks, ...callbacks };
    }

    public saveToUndo(): void {
        if (!this.stateManager) {
            throw new Error('UndoRedoManager not initialized - call initialize() first');
        }
        
        this.stateManager.saveToUndo();
        
        // Mark as dirty when any change is made
        if (this.autoSaveManager) {
            this.autoSaveManager.forceCheckChanges();
        }
    }

    public undo(): boolean {
        if (!this.stateManager) {
            throw new Error('UndoRedoManager not initialized - call initialize() first');
        }
        
        if (this.stateManager.undo()) {
            if (this.callbacks.onUndoRedo) {
                this.callbacks.onUndoRedo();
            }
            return true;
        }
        return false;
    }

    public redo(): boolean {
        if (!this.stateManager) {
            throw new Error('UndoRedoManager not initialized - call initialize() first');
        }
        
        if (this.stateManager.redo()) {
            if (this.callbacks.onUndoRedo) {
                this.callbacks.onUndoRedo();
            }
            return true;
        }
        return false;
    }

    public canUndo(): boolean {
        if (!this.stateManager) return false;
        return this.stateManager.canUndo();
    }

    public canRedo(): boolean {
        if (!this.stateManager) return false;
        return this.stateManager.canRedo();
    }
}

// Create singleton instance
const undoRedoManager = new UndoRedoManager();

// Export for use in other modules or global scope
declare global {
    interface Window {
        undoRedoManager: UndoRedoManager;
    }
}

(window as any).undoRedoManager = undoRedoManager;