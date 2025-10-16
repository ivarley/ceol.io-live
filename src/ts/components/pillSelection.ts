/**
 * PillSelection Module for Session Instance Detail Beta
 * Handles pill selection state, visual feedback, and selection operations
 */

import { TunePill, TuneSet, TunePillsData } from './stateManager.js';

export interface PillSelectionCallbacks {
    renderTunePills?(): void;
    saveToUndo?(): void;
    showMessage?(message: string, type: 'success' | 'error'): void;
}

export interface PillSelectionDependencies {
    getStateManager(): StateManager;
    getAutoSaveManager(): AutoSaveManager;
    onSelectionChange?: () => void;
    selectedPills?: Set<string>;
}

export interface StateManager {
    getTunePillsData(): TunePillsData;
    findTuneById(id: string): TunePosition | null;
    removeTune(setIndex: number, tuneIndex: number): void;
}

export interface TunePosition {
    setIndex: number;
    tuneIndex: number;
    tune: TunePill;
}

export interface AutoSaveManager {
    forceCheckChanges(): void;
}

export interface CursorPosition {
    setIndex: number;
    pillIndex: number;
    position: string;
}

export interface PillInfo {
    pill: TunePill;
    setIndex: number;
    pillIndex: number;
}

export class PillSelection {
    static selectedPills: Set<string> = new Set();
    static getStateManager: (() => StateManager) | null = null; // Function to get StateManager reference
    static getAutoSaveManager: (() => AutoSaveManager) | null = null; // Function to get AutoSaveManager reference
    static onSelectionChange: (() => void) | null = null; // Callback for selection changes
    
    // External functions that need to be called (will be registered via callbacks)
    static renderTunePills: (() => void) | null = null;
    static saveToUndo: (() => void) | null = null;
    static showMessage: ((message: string, type: 'success' | 'error') => void) | null = null;
    
    static initialize(options: PillSelectionDependencies = {} as PillSelectionDependencies): void {
        this.getStateManager = options.getStateManager || (() => (window as any).StateManager);
        this.getAutoSaveManager = options.getAutoSaveManager || (() => (window as any).AutoSaveManager);
        this.onSelectionChange = options.onSelectionChange || null;
        this.selectedPills = options.selectedPills || new Set();
    }
    
    static getSelectedPills(): Set<string> {
        return this.selectedPills;
    }
    
    static selectSingle(pillId: string): void {
        // Hide any open context menu when selection changes
        if ((window as any).ContextMenu) {
            (window as any).ContextMenu.hideContextMenu();
        }
        
        this.selectedPills.clear();
        this.selectedPills.add(pillId);
        this.updateSelectionDisplay();
        
        if (this.onSelectionChange) {
            this.onSelectionChange();
        }
    }
    
    static toggleSelection(pillId: string): void {
        // Hide any open context menu when selection changes
        if ((window as any).ContextMenu) {
            (window as any).ContextMenu.hideContextMenu();
        }
        
        if (this.selectedPills.has(pillId)) {
            this.selectedPills.delete(pillId);
        } else {
            this.selectedPills.add(pillId);
        }
        this.updateSelectionDisplay();
        
        if (this.onSelectionChange) {
            this.onSelectionChange();
        }
    }
    
    static extendSelection(pillId: string): void {
        // Hide any open context menu when selection changes
        if ((window as any).ContextMenu) {
            (window as any).ContextMenu.hideContextMenu();
        }
        
        // For shift-click selection, we need to select from the last selected pill to this one
        if (this.selectedPills.size === 0) {
            // If no pills are selected, just select this one
            this.selectedPills.add(pillId);
        } else {
            // Find the range between the last selected pill and the current one
            const allPills = document.querySelectorAll('.tune-pill') as NodeListOf<HTMLElement>;
            const pillIds = Array.from(allPills).map(pill => pill.dataset.pillId!);
            
            // Find the indices of the last selected pill and the current pill
            const lastSelectedId = Array.from(this.selectedPills)[this.selectedPills.size - 1];
            const lastIndex = pillIds.indexOf(lastSelectedId);
            const currentIndex = pillIds.indexOf(pillId);
            
            if (lastIndex !== -1 && currentIndex !== -1) {
                // Select all pills between the last selected and current (inclusive)
                const startIndex = Math.min(lastIndex, currentIndex);
                const endIndex = Math.max(lastIndex, currentIndex);
                
                for (let i = startIndex; i <= endIndex; i++) {
                    this.selectedPills.add(pillIds[i]!);
                }
            } else {
                // Fallback: just add the current pill
                this.selectedPills.add(pillId);
            }
        }
        this.updateSelectionDisplay();
        
        if (this.onSelectionChange) {
            this.onSelectionChange();
        }
    }
    
    static updateSelectionDisplay(): void {
        document.querySelectorAll('.tune-pill').forEach(pill => {
            const htmlPill = pill as HTMLElement;
            if (this.selectedPills.has(htmlPill.dataset.pillId!)) {
                htmlPill.classList.add('selected');
            } else {
                htmlPill.classList.remove('selected');
            }
        });
    }
    
    static selectAll(): void {
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        this.selectedPills.clear();
        tunePillsData.forEach(set => {
            set.forEach(pill => this.selectedPills.add(pill.id));
        });
        this.updateSelectionDisplay();
        
        if (this.onSelectionChange) {
            this.onSelectionChange();
        }
    }
    
    static selectNone(): void {
        this.selectedPills.clear();
        this.updateSelectionDisplay();
        
        if (this.onSelectionChange) {
            this.onSelectionChange();
        }
    }
    
    static hasSelection(): boolean {
        return this.selectedPills.size > 0;
    }
    
    static getSelectionCount(): number {
        return this.selectedPills.size;
    }
    
    static isSelected(pillId: string): boolean {
        return this.selectedPills.has(pillId);
    }
    
    static deleteSelectedPills(): void {
        if (this.selectedPills.size === 0) return;
        
        const stateManager = this.getStateManager!();
        const autoSaveManager = this.getAutoSaveManager!();
        
        if (this.saveToUndo) {
            this.saveToUndo();
        }
        
        // Remove selected pills
        this.selectedPills.forEach(pillId => {
            const result = stateManager.findTuneById(pillId);
            if (result) {
                stateManager.removeTune(result.setIndex, result.tuneIndex);
            }
        });
        
        // Force check for changes after data modification
        autoSaveManager.forceCheckChanges();
        
        this.selectedPills.clear();
        
        if (this.renderTunePills) {
            this.renderTunePills();
        }
        
        if (this.onSelectionChange) {
            this.onSelectionChange();
        }
    }
    
    static copySelectedPills(): TuneSet[] | null {
        if (this.selectedPills.size === 0) return null;
        
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        // Group selected pills by their sets, preserving order and set structure
        const selectedBySet = new Map<number, Array<{pill: TunePill; originalPillIndex: number}>>();
        
        tunePillsData.forEach((tuneSet, setIndex) => {
            tuneSet.forEach((pill, pillIndex) => {
                if (this.selectedPills.has(pill.id)) {
                    if (!selectedBySet.has(setIndex)) {
                        selectedBySet.set(setIndex, []);
                    }
                    selectedBySet.get(setIndex)!.push({
                        pill: JSON.parse(JSON.stringify(pill)),
                        originalPillIndex: pillIndex
                    });
                }
            });
        });
        
        // Convert to array of sets, preserving set breaks
        const clipboard = Array.from(selectedBySet.values()).map(setData => 
            setData.map(item => item.pill)
        );
        
        // Copy to external clipboard - both JSON format and plain text tune names
        if (navigator.clipboard && navigator.clipboard.writeText) {
            // Create plain text version with sets on separate lines, tunes in sets separated by commas
            const tuneNames = clipboard.map(set => 
                set.map(pill => pill.tuneName).join(', ')
            ).join('\n');
            
            // Try to write plain text tune names to external clipboard
            navigator.clipboard.writeText(tuneNames).then(() => {
            }).catch(err => {
                console.warn('Failed to write tune names to clipboard, trying JSON fallback:', err);
                // Fallback to JSON format if plain text fails
                const jsonData = JSON.stringify(clipboard);
                navigator.clipboard.writeText(jsonData).catch(err => {
                    console.error('Failed to write JSON to clipboard:', err);
                });
            });
        }
        
        const totalPills = clipboard.reduce((sum, set) => sum + set.length, 0);
        const setCount = clipboard.length;
        
        if (this.showMessage) {
            this.showMessage(`Copied ${totalPills} tune(s) in ${setCount} set(s)`, 'success');
        }
        
        return clipboard;
    }
    
    static cutSelectedPills(): TuneSet[] | null {
        if (this.selectedPills.size === 0) return null;
        
        const clipboard = this.copySelectedPills();
        this.deleteSelectedPills();
        return clipboard;
    }
    
    static addDraggingClass(): void {
        // Visual feedback - apply dragging class to all selected pills
        this.selectedPills.forEach(pillId => {
            const pill = document.querySelector(`[data-pill-id="${pillId}"]`) as HTMLElement;
            if (pill) {
                pill.classList.add('dragging');
            }
        });
    }
    
    static removeDraggingClass(): void {
        // Remove dragging visual feedback from all selected pills
        this.selectedPills.forEach(pillId => {
            const pill = document.querySelector(`[data-pill-id="${pillId}"]`) as HTMLElement;
            if (pill) {
                pill.classList.remove('dragging');
            }
        });
    }
    
    static getSelectedPillsData(): Map<number, Array<{pill: TunePill; setIndex: number; pillIndex: number}>> {
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        // Group selected pills by their sets, preserving order and set structure
        const selectedBySet = new Map<number, Array<{pill: TunePill; setIndex: number; pillIndex: number}>>();
        
        tunePillsData.forEach((tuneSet, setIndex) => {
            tuneSet.forEach((pill, pillIndex) => {
                if (this.selectedPills.has(pill.id)) {
                    if (!selectedBySet.has(setIndex)) {
                        selectedBySet.set(setIndex, []);
                    }
                    selectedBySet.get(setIndex)!.push({
                        pill: JSON.parse(JSON.stringify(pill)),
                        setIndex: setIndex,
                        pillIndex: pillIndex
                    });
                }
            });
        });
        
        return selectedBySet;
    }
    
    static selectFromCursorRange(startCursorPos: CursorPosition, endCursorPos: CursorPosition): void {
        if (!startCursorPos || !endCursorPos) return;
        
        // Hide any open context menu when selection changes
        if ((window as any).ContextMenu) {
            (window as any).ContextMenu.hideContextMenu();
        }
        
        this.selectedPills.clear();
        
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        // Get all pills in order for indexing
        const allPills: PillInfo[] = [];
        tunePillsData.forEach((set, setIndex) => {
            set.forEach((pill, pillIndex) => {
                allPills.push({ pill, setIndex, pillIndex });
            });
        });
        
        // Define what range of pills should be selected based on cursor positions
        const pillsToSelect = this.getPillRangeBetweenCursors(startCursorPos, endCursorPos, allPills);
        
        // Select the determined pills
        pillsToSelect.forEach(pillInfo => {
            this.selectedPills.add(pillInfo.pill.id);
        });
        
        this.updateSelectionDisplay();
        
        if (this.onSelectionChange) {
            this.onSelectionChange();
        }
    }
    
    static getPillRangeBetweenCursors(startCursor: CursorPosition, endCursor: CursorPosition, allPills: PillInfo[]): PillInfo[] {
        // SIMPLIFIED APPROACH: Select pills based on what's between the cursor positions
        
        const startBoundary = this.getCursorPillBoundary(startCursor, allPills);
        const endBoundary = this.getCursorPillBoundary(endCursor, allPills);
        
        if (startBoundary === -1 || endBoundary === -1) return [];
        
        const selectedPills: PillInfo[] = [];
        const minBoundary = Math.min(startBoundary, endBoundary);
        const maxBoundary = Math.max(startBoundary, endBoundary);
        
        // Select pills between the boundaries (exclusive of boundaries)
        for (let i = minBoundary; i < maxBoundary && i < allPills.length; i++) {
            selectedPills.push(allPills[i]!);
        }
        
        return selectedPills;
    }
    
    static getCursorPillBoundary(cursor: CursorPosition, allPills: PillInfo[]): number {
        const { setIndex, pillIndex, position } = cursor;
        
        if (position === 'newset') {
            // Newset position is after all pills - return boundary after last pill
            return allPills.length;
        }
        
        const pillArrayIndex = allPills.findIndex(p => 
            p.setIndex === setIndex && p.pillIndex === pillIndex
        );
        
        if (pillArrayIndex === -1) return -1;
        
        // BOUNDARY LOGIC: Cursor positions represent boundaries, not pills themselves
        if (position === 'before') {
            // "before pill N" = boundary just before pill N
            // First pill that would be selected when extending FROM here is pill N
            return pillArrayIndex;
        } else if (position === 'after') {
            // "after pill N" = boundary just after pill N  
            // First pill that would be selected when extending FROM here is pill N+1
            return pillArrayIndex + 1;
        }
        
        return pillArrayIndex;
    }
    
    static getCursorLogicalPosition(cursor: CursorPosition, allPills: PillInfo[]): number | null {
        const { setIndex, pillIndex, position } = cursor;
        
        if (position === 'newset') {
            // Newset position is after all existing pills
            return allPills.length;
        }
        
        const pillArrayIndex = allPills.findIndex(p => 
            p.setIndex === setIndex && p.pillIndex === pillIndex
        );
        
        if (pillArrayIndex === -1) return null;
        
        // CORRECTED LOGIC FOR PROPER DESELECTION:
        // - "before" pill N means logical position N (just before the pill)
        // - "after" pill N means logical position N+1 (just after the pill)
        // This way moving from "after" to "before" the same pill changes the selection range
        
        if (position === 'before') {
            return pillArrayIndex;
        } else if (position === 'after') {
            return pillArrayIndex + 1;
        }
        
        return pillArrayIndex;
    }
    
    static findPillIndexFromCursor(cursor: CursorPosition, allPills: PillInfo[]): number {
        const { setIndex, pillIndex, position } = cursor;
        
        if (position === 'newset') {
            return -1; // Newset doesn't correspond to existing pills
        }
        
        // Find the pill this cursor position is "associated with"
        const pillArrayIndex = allPills.findIndex(p => 
            p.setIndex === setIndex && p.pillIndex === pillIndex
        );
        
        if (pillArrayIndex === -1) return -1;
        
        // Both "before" and "after" positions are associated with the same pill
        // The difference is only in cursor movement, not selection logic
        return pillArrayIndex;
    }
    
    static cursorPositionToPillBoundary(cursorPos: CursorPosition, allPills: PillInfo[]): number {
        const { setIndex, pillIndex, position } = cursorPos;
        
        if (position === 'newset') {
            // Newset positions don't correspond to existing pills
            return -1;
        }
        
        // Find the pill index in the flat array
        const pillIndexInArray = allPills.findIndex(p => 
            p.setIndex === setIndex && p.pillIndex === pillIndex
        );
        
        if (pillIndexInArray === -1) return -1;
        
        // CORRECT LOGIC: Cursor positions represent selection boundaries, not pills themselves
        
        if (position === 'before') {
            // "before" pill N means the selection boundary is just before pill N
            // So if we're selecting FROM here, pill N is the FIRST pill to include
            return pillIndexInArray;
        } else if (position === 'after') {
            // "after" pill N means the selection boundary is just after pill N  
            // So if we're selecting TO here, pill N is the LAST pill to include
            // But if we're selecting FROM here, pill N+1 would be the first to include
            return pillIndexInArray;
        }
        
        return pillIndexInArray;
    }
    
    static getPillsFromCursorPosition(cursorPos: CursorPosition): Array<{setIndex: number; pillIndex: number}> {
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        // Convert a cursor position to the pills it represents for selection purposes
        const { setIndex, pillIndex, position } = cursorPos;
        
        if (position === 'newset' || setIndex >= tunePillsData.length || tunePillsData[setIndex]!.length === 0) {
            return [];
        }
        
        if (position === 'before') {
            // Before a pill - for selection purposes, we want to start FROM this pill (inclusive)
            if (pillIndex < tunePillsData[setIndex]!.length) {
                return [{ setIndex, pillIndex }];
            }
        } else if (position === 'after') {
            // After a pill - for selection purposes, we want to end AT this pill (inclusive)
            // But we need to be careful about range boundaries
            if (pillIndex >= 0 && pillIndex < tunePillsData[setIndex]!.length) {
                return [{ setIndex, pillIndex }];
            }
        }
        
        return [];
    }
    
    // Helper method to register external functions that PillSelection needs to call
    static registerCallbacks(callbacks: PillSelectionCallbacks = {}): void {
        this.renderTunePills = callbacks.renderTunePills || null;
        this.saveToUndo = callbacks.saveToUndo || null;
        this.showMessage = callbacks.showMessage || null;
    }
}

// Export for use in other modules or global scope
declare global {
    interface Window {
        PillSelection: typeof PillSelection;
    }
}

(window as any).PillSelection = PillSelection;