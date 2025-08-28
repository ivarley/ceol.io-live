// ClipboardManager - Handles clipboard operations (copy/cut/paste)

import { TunePill, TunePillsData, TuneSet } from './stateManager.js';

export interface ClipboardPosition {
    setIndex: number;
    pillIndex: number;
    position: 'before' | 'after' | 'newset';
}

export interface ClipboardCallbacks {
    saveToUndo(): void;
    generateId(): string;
    autoMatchTune(pill: TunePill): Promise<void>;
    updatePillAppearance(pill: TunePill): void;
    renderTunePills(): void;
    showMatchingResults(pills: TunePill[]): void;
    showMessage(message: string, type: 'success' | 'error'): void;
    applyLandingAnimation(pillIds: string[]): void;
}

export interface ClipboardDependencies {
    getPillSelection(): PillSelection;
    getCursorManager(): CursorManager;
    getStateManager(): StateManager;
}

export interface PillSelection {
    copySelectedPills(): TuneSet[] | null;
    cutSelectedPills(): TuneSet[] | null;
}

export interface CursorManager {
    getCursorPosition(): { setIndex: number; pillIndex: number; position: string } | null;
}

export interface StateManager {
    getTunePillsData(): TunePillsData;
    setTunePillsData(data: TunePillsData): void;
}

export class ClipboardManager {
    private clipboard: TuneSet[] = [];
    private pillSelection: PillSelection | null = null;
    private cursorManager: CursorManager | null = null;
    private stateManager: StateManager | null = null;
    private callbacks: ClipboardCallbacks = {} as ClipboardCallbacks;

    public initialize(dependencies: ClipboardDependencies): void {
        this.pillSelection = dependencies.getPillSelection();
        this.cursorManager = dependencies.getCursorManager();
        this.stateManager = dependencies.getStateManager();
    }

    public registerCallbacks(callbacks: Partial<ClipboardCallbacks>): void {
        this.callbacks = { ...this.callbacks, ...callbacks } as ClipboardCallbacks;
    }

    public copySelectedPills(): TuneSet[] | null {
        if (!this.pillSelection) return null;
        
        const copiedData = this.pillSelection.copySelectedPills();
        if (copiedData) {
            this.clipboard = copiedData;
        }
        return copiedData;
    }

    public cutSelectedPills(): TuneSet[] | null {
        if (!this.pillSelection) return null;
        
        const cutData = this.pillSelection.cutSelectedPills();
        if (cutData) {
            this.clipboard = cutData;
        }
        return cutData;
    }

    public async pasteFromClipboard(): Promise<void> {
        if (!this.cursorManager || !this.stateManager) return;
        
        // First try to read from external clipboard
        let externalClipboardData: TuneSet[] | null = null;
        let isPlainTextPaste = false;
        
        if (navigator.clipboard && navigator.clipboard.readText) {
            try {
                const clipboardText = await navigator.clipboard.readText();
                if (clipboardText.trim()) {
                    // Try to parse as JSON first (for internal clipboard data)
                    try {
                        const parsedData = JSON.parse(clipboardText);
                        if (Array.isArray(parsedData)) {
                            // This is internal JSON data - use it as-is, no need to match
                            externalClipboardData = parsedData as TuneSet[];
                            isPlainTextPaste = false;
                        }
                    } catch (e) {
                        // Not JSON, treat as plain text tune names
                        // Each line is a set, tunes within a set are comma-separated
                        const lines = clipboardText.split('\n')
                            .map(line => line.trim())
                            .filter(line => line.length > 0);
                        
                        if (lines.length > 0) {
                            // Convert each line to a set of tune objects
                            externalClipboardData = lines.map(line => {
                                const tuneNames = line.split(',')
                                    .map(name => name.trim())
                                    .filter(name => name.length > 0);
                                
                                return tuneNames.map(tunename => ({
                                    id: this.callbacks.generateId(),
                                    orderNumber: 0,
                                    tuneId: null,
                                    tuneName: tunename,
                                    setting: '',
                                    tuneType: '',
                                    state: 'loading' as const  // Show loading spinner during matching
                                }));
                            });
                            isPlainTextPaste = true;
                        }
                    }
                }
            } catch (err) {
                console.error('External clipboard read failed:', err);
                // External clipboard read failed, fall back to internal clipboard
            }
        }
        
        // Use external clipboard data if available, otherwise fall back to internal clipboard
        const clipboardData = externalClipboardData || this.clipboard;
        
        if (!clipboardData || clipboardData.length === 0) return;
        
        // Paste at current cursor position if available, otherwise at the end
        let position: ClipboardPosition;
        const cursorPosition = this.cursorManager.getCursorPosition();
        if (cursorPosition) {
            position = {
                setIndex: cursorPosition.setIndex,
                pillIndex: cursorPosition.pillIndex,
                position: cursorPosition.position as 'before' | 'after' | 'newset'
            };
        } else {
            // Fallback: paste at the end
            const tunePillsData = this.stateManager.getTunePillsData();
            position = { setIndex: tunePillsData.length, pillIndex: 0, position: 'newset' };
        }
        this.pasteAtPosition(clipboardData, position);
        
        // If we pasted external plain text (not JSON), run matching
        if (isPlainTextPaste) {
            // Wait for the DOM to be fully updated before starting matching
            requestAnimationFrame(() => {
                setTimeout(async () => {
                    const originalTuneNames = clipboardData.flat().map(p => p.tuneName);
                    console.log('Starting tune matching for pasted pills:', originalTuneNames);
                    
                    // Find the actual pills that were inserted into tunePillsData
                    // Since pasteAtPosition creates new IDs, we need to find them by tune name
                    const actualPastedPills: TunePill[] = [];
                    const tunePillsData = this.stateManager!.getTunePillsData();
                    tunePillsData.forEach(tuneSet => {
                        tuneSet.forEach(pill => {
                            if (originalTuneNames.includes(pill.tuneName) && pill.state === 'loading') {
                                actualPastedPills.push(pill);
                            }
                        });
                    });
                    
                    console.log('Found actual pasted pills in tunePillsData:', actualPastedPills.map(p => `${p.tuneName} (${p.id})`));
                    
                    // Verify pills exist in DOM
                    const missingPills = actualPastedPills.filter(pill => 
                        !document.querySelector(`[data-pill-id="${pill.id}"]`)
                    );
                    if (missingPills.length > 0) {
                        console.warn('Some pills not found in DOM:', missingPills.map(p => p.id));
                    }
                    
                    // Create array of matching promises
                    const matchingPromises = actualPastedPills
                        .filter(pill => pill.state === 'loading')
                        .map(pill => {
                            console.log(`Attempting to match tune: "${pill.tuneName}"`);
                            return this.callbacks.autoMatchTune(pill).then(() => {
                                console.log(`Match result for "${pill.tuneName}": ${pill.state}`);
                                this.callbacks.updatePillAppearance(pill);
                            }).catch(err => {
                                console.error(`Error matching "${pill.tuneName}":`, err);
                            });
                        });
                    
                    // Wait for all matching operations to complete
                    await Promise.all(matchingPromises);
                    
                    // Force a complete re-render to ensure visual updates are applied
                    this.callbacks.renderTunePills();
                    
                    // Now show matching results with accurate pill states
                    console.log('All matching complete, showing results for pills:', actualPastedPills.map(p => `${p.tuneName}: ${p.state}`));
                    this.callbacks.showMatchingResults(actualPastedPills);
                }, 200); // Small additional delay after requestAnimationFrame
            });
        }
    }

    private pasteAtPosition(pillsData: TuneSet[], position: ClipboardPosition): void {
        if (!pillsData || pillsData.length === 0 || !this.stateManager) return;
        
        this.callbacks.saveToUndo();
        
        // Get current tunePillsData
        let tunePillsData = this.stateManager.getTunePillsData();
        
        // Check if pillsData is a flat array (old format) or array of sets (new format)
        const isNewFormat = Array.isArray(pillsData[0]);
        
        if (isNewFormat) {
            // New format: array of sets with preserved set breaks
            const newSets = pillsData.map(set => 
                set.map(pill => ({
                    ...pill,
                    id: this.callbacks.generateId(),
                    orderNumber: 0
                }))
            );
            
            let insertPosition = position.setIndex;
            
            if (position.position === 'newset') {
                // Insert sets starting at the specified position
                if (insertPosition >= tunePillsData.length) {
                    // Add at end
                    tunePillsData.push(...newSets);
                } else {
                    // Insert between existing sets
                    tunePillsData.splice(insertPosition, 0, ...newSets);
                }
            } else {
                // Insert into/split existing set
                const targetSetIndex = position.setIndex;
                
                if (targetSetIndex >= tunePillsData.length) {
                    // Add sets at end
                    tunePillsData.push(...newSets);
                } else {
                    const targetSet = tunePillsData[targetSetIndex];
                    let insertIndex = position.pillIndex;
                    
                    // Handle position type
                    if (position.position === 'before') {
                        insertIndex = Math.max(0, position.pillIndex);
                    } else if (position.position === 'after') {
                        insertIndex = Math.min(targetSet.length, position.pillIndex + 1);
                    }
                    
                    if (newSets.length === 1) {
                        // Single set - insert pills into existing set
                        newSets[0]!.forEach((pill, index) => {
                            targetSet.splice(insertIndex + index, 0, pill);
                        });
                    } else {
                        // Multiple sets - split the target set
                        const beforePills = targetSet.slice(0, insertIndex);
                        const afterPills = targetSet.slice(insertIndex);
                        
                        // Replace target set with: before pills + new sets + after pills
                        const allSets = [];
                        if (beforePills.length > 0) allSets.push(beforePills);
                        allSets.push(...newSets);
                        if (afterPills.length > 0) allSets.push(afterPills);
                        
                        tunePillsData.splice(targetSetIndex, 1, ...allSets);
                    }
                }
            }
            
            const totalPills = newSets.reduce((sum, set) => sum + set.length, 0);
            this.callbacks.showMessage(`Pasted ${totalPills} tune(s) in ${newSets.length} set(s)`, 'success');
            
            // Apply landing animation to pasted pills
            const pastedPillIds = newSets.flat().map(pill => pill.id);
            setTimeout(() => {
                this.callbacks.applyLandingAnimation(pastedPillIds);
            }, 50);
        } else {
            // Old format: flat array of pills - use original logic
            const newPills = (pillsData as unknown as TunePill[]).map(pill => ({
                ...pill,
                id: this.callbacks.generateId(),
                orderNumber: 0
            }));
            
            if (position.position === 'newset') {
                const targetSetIndex = position.setIndex;
                if (targetSetIndex >= tunePillsData.length) {
                    tunePillsData.push(newPills);
                } else {
                    tunePillsData.splice(targetSetIndex, 0, newPills);
                }
            } else {
                let targetSetIndex = position.setIndex;
                if (targetSetIndex >= tunePillsData.length) {
                    tunePillsData.push(newPills);
                } else {
                    const targetSet = tunePillsData[targetSetIndex];
                    if (!targetSet) return;
                    
                    let insertIndex = position.pillIndex;
                    
                    if (position.position === 'before') {
                        insertIndex = Math.max(0, position.pillIndex);
                    } else if (position.position === 'after') {
                        insertIndex = Math.min(targetSet.length, position.pillIndex + 1);
                    }
                    
                    newPills.forEach((pill, index) => {
                        targetSet.splice(insertIndex + index, 0, pill);
                    });
                }
            }
            
            this.callbacks.showMessage(`Pasted ${newPills.length} tune(s)`, 'success');
            
            // Apply landing animation to pasted pills
            const pastedPillIds = newPills.map(pill => pill.id);
            setTimeout(() => {
                this.callbacks.applyLandingAnimation(pastedPillIds);
            }, 50);
        }
        
        // Update StateManager with the modified data
        this.stateManager.setTunePillsData(tunePillsData);
        
        this.callbacks.renderTunePills();
    }
}

// Create singleton instance
const clipboardManager = new ClipboardManager();

// Export for use in other modules or global scope
declare global {
    interface Window {
        clipboardManager: ClipboardManager;
    }
}

(window as any).clipboardManager = clipboardManager;