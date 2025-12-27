/**
 * TextInput module for handling text input, typing, and tune entry
 * Handles all typing interactions, auto-matching, and text-based tune insertion
 */

import { TunePill, TunePillsData } from './stateManager.js';

export interface TypingPill extends TunePill {
    previousTuneType?: string | null;
    matchResults?: MatchResult[] | null;
}

export interface MatchResult {
    tune_id: number;
    tune_name: string;
    tune_type: string;
}

export interface TypingContext {
    tuneSet: HTMLElement;
    insertionPoint: Node | null;
}

export interface CursorPosition {
    setIndex: number;
    pillIndex: number;
    position: string;
}

declare global {
    interface Window {
        TextInput: typeof TextInput;
        tunePillsData: TunePillsData;
        temporaryEmptySet: number | null;
        CursorManager: {
            getCursorPosition(): CursorPosition | null;
            setCursorPosition(setIndex: number, pillIndex: number, position: string, keepKeyboard?: boolean): void;
            updateCursorWithText(): void;
            isMobileDevice(): boolean;
        };
        StateManager: {
            generateId(): string;
            getTunePillsData(): TunePillsData;
            setTunePillsData(data: TunePillsData): void;
        };
        PillRenderer: {
            renderTunePills(): void;
        };
        PillSelection: {
            hasSelection(): boolean;
            deleteSelectedPills(): void;
        };
        undoRedoManager: {
            saveToUndo(): void;
        };
        autoMatchTune: (pill: TypingPill, stillTyping?: boolean) => Promise<void>;
        showMatchingResults: (pills: TunePill[]) => void;
        deleteTuneAtCursor: () => void;
    }
}

export class TextInput {
    // Typing state
    public isTyping: boolean = false;
    public typingBuffer: string = '';
    public isKeepingKeyboardOpen: boolean = false;
    public typingTimeout: number | null = null;  // For 3-second pause matching
    public typingPill: TypingPill | null = null;     // Temporary pill being typed
    
    // Track the original cursor context during typing
    public typingContext: TypingContext | null = null;
    
    // Track if we need to re-render after typing finishes
    public pendingRender: boolean = false;

    constructor() {}

    /**
     * Handle text input character by character
     */
    handleTextInput(char: string): void {
        if (!this.isTyping) {
            this.isTyping = true;
            this.typingBuffer = '';
            this.typingPill = null;
        }
        
        // Remove any existing typing match menu when user continues typing
        this.removeTypingMatchResults();
        
        // Clear any existing typing timeout
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
            this.typingTimeout = null;
        }
        
        // Handle comma and semicolon as immediate tune separators
        if (char === ',' || char === ';') {
            // If we have content in the buffer, finish the current tune first
            if (this.typingBuffer.trim()) {
                const tuneName = this.typingBuffer.trim();
                this.typingBuffer = '';
                
                // Insert the current tune and start matching
                this.insertTunesAtCursor([tuneName], true); // Keep keyboard open for continued typing
                
                // Continue in typing mode for the next tune
                window.CursorManager.updateCursorWithText();
            }
            // Don't add the comma/semicolon to the buffer
            return;
        }
        
        this.typingBuffer += char;
        window.CursorManager.updateCursorWithText();
        
        // Set a timeout to trigger matching after 3 seconds of no typing
        this.typingTimeout = window.setTimeout(() => {
            if (this.isTyping && this.typingBuffer.trim()) {
                // Trigger matching but stay in typing mode
                this.performTypingMatch();
            }
        }, 3000);
    }

    /**
     * Perform matching while still in typing mode
     */
    performTypingMatch(): void {
        if (!this.isTyping || !this.typingBuffer.trim()) return;
        
        // Create a temporary pill for matching
        if (!this.typingPill) {
            this.typingPill = {
                id: 'typing-' + Date.now(),
                orderNumber: 0,
                tuneId: null,
                tuneName: this.typingBuffer.trim(),
                setting: '',
                tuneType: '',
                state: 'typing'
            };
        } else {
            this.typingPill.tuneName = this.typingBuffer.trim();
        }
        
        // Find the previous tune type if we're in a set
        let previousTuneType: string | null = null;
        const cursorPosition = window.CursorManager.getCursorPosition();
        if (cursorPosition) {
            const { setIndex, pillIndex, position } = cursorPosition;
            const tunePillsData = window.StateManager.getTunePillsData();
            if (setIndex < tunePillsData.length) {
                const set = tunePillsData[setIndex]!;

                // Different logic based on cursor position
                if (position === 'after' && pillIndex >= 0 && pillIndex < set.length) {
                    // Cursor is after a pill - look backwards from current pill
                    for (let i = pillIndex; i >= 0; i--) {
                        if (set[i]!.tuneType) {
                            previousTuneType = set[i]!.tuneType;
                            break;
                        }
                    }
                } else if (position === 'before' && pillIndex > 0 && pillIndex <= set.length) {
                    // Cursor is before a pill but not the first - look at previous pill
                    for (let i = pillIndex - 1; i >= 0; i--) {
                        if (set[i]!.tuneType) {
                            previousTuneType = set[i]!.tuneType;
                            break;
                        }
                    }
                } else if (position === 'newset' && setIndex > 0) {
                    // Starting a new set - check the last tune of the previous set
                    const prevSet = tunePillsData[setIndex - 1]!;
                    if (prevSet && prevSet.length > 0) {
                        for (let i = prevSet.length - 1; i >= 0; i--) {
                            if (prevSet[i]!.tuneType) {
                                previousTuneType = prevSet[i]!.tuneType;
                                break;
                            }
                        }
                    }
                }
            }
        }
        
        // Store previous tune type on the pill for the API call
        this.typingPill.previousTuneType = previousTuneType;
        
        // Call autoMatchTune with stillTyping flag
        // Note: autoMatchTune will handle showing the match results menu via ContextMenu.showMatchResultsMenu
        window.autoMatchTune(this.typingPill, true);
    }

    /**
     * Show match results for the tune being typed
     */
    showTypingMatchResults(pill: TypingPill): void {
        // Hide any existing typing match results
        const existingMenu = document.querySelector('.typing-match-menu');
        if (existingMenu) {
            existingMenu.remove();
        }
        
        if (!pill.matchResults || pill.matchResults.length === 0) {
            return;
        }
        
        // Find the typing text element
        const typingText = document.querySelector('.typing-text') as HTMLElement;
        if (!typingText) {
            return;
        }
        
        const menu = document.createElement('div');
        menu.className = 'tune-context-menu typing-match-menu';
        menu.style.display = 'block';
        
        const rect = typingText.getBoundingClientRect();
        
        // Position menu below the typing text
        menu.style.position = 'fixed';
        menu.style.left = rect.left + 'px';
        menu.style.top = (rect.bottom + 5) + 'px';
        menu.style.width = 'auto';
        menu.style.minWidth = Math.max(200, rect.width) + 'px';
        menu.style.maxWidth = Math.min(600, window.innerWidth - rect.left - 20) + 'px';
        
        // Use a neutral background for the menu
        menu.style.backgroundColor = 'white';
        menu.style.color = '#212529';
        menu.style.border = '1px solid #dee2e6';
        menu.style.borderRadius = '4px';
        menu.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
        menu.style.zIndex = '1000';
        
        // Add match results as menu items
        pill.matchResults.forEach((result, index) => {
            const item = document.createElement('a');
            item.style.display = 'block';
            item.style.padding = '8px 12px';
            item.style.cursor = 'pointer';
            item.style.borderBottom = index < pill.matchResults!.length - 1 ? '1px solid #f0f0f0' : 'none';
            item.style.color = '#212529';
            item.style.textDecoration = 'none';
            
            // Show tune name and type
            const nameSpan = document.createElement('span');
            nameSpan.textContent = result.tune_name;
            nameSpan.style.fontWeight = '500';
            item.appendChild(nameSpan);
            
            if (result.tune_type) {
                const typeSpan = document.createElement('span');
                typeSpan.textContent = ` (${result.tune_type})`;
                typeSpan.style.color = '#6c757d';
                typeSpan.style.fontSize = '0.9em';
                item.appendChild(typeSpan);
            }
            
            // Hover effect
            item.addEventListener('mouseenter', () => {
                item.style.backgroundColor = '#f8f9fa';
            });
            item.addEventListener('mouseleave', () => {
                item.style.backgroundColor = 'transparent';
            });
            
            // Click to select this match
            item.addEventListener('click', () => {
                // Apply the selected match to the typing buffer
                this.typingBuffer = result.tune_name;
                window.CursorManager.updateCursorWithText();
                
                // Store the match info for when we finish typing
                this.typingPill!.tuneId = result.tune_id;
                this.typingPill!.tuneName = result.tune_name;
                this.typingPill!.tuneType = result.tune_type;
                this.typingPill!.state = 'matched';
                
                // Hide the menu
                menu.remove();
                
                // Finish typing and insert the matched tune
                this.finishTyping(true);
            });
            
            menu.appendChild(item);
        });
        
        document.body.appendChild(menu);
    }

    /**
     * Remove typing match results menu
     */
    removeTypingMatchResults(): void {
        // Remove any match results menu (both typing-match-menu and match-results-menu)
        const existingMenus = document.querySelectorAll('.typing-match-menu, .match-results-menu');
        existingMenus.forEach(menu => menu.remove());
    }

    /**
     * Handle backspace during typing and editing
     */
    handleBackspace(): void {
        // If multiple pills are selected, delete them all
        if (window.PillSelection.hasSelection()) {
            window.PillSelection.deleteSelectedPills();
            return;
        }
        
        if (this.isTyping && this.typingBuffer.length > 0) {
            this.typingBuffer = this.typingBuffer.slice(0, -1);
            window.CursorManager.updateCursorWithText();
        } else if (window.CursorManager.getCursorPosition() && !this.isTyping) {
            const cursorPosition = window.CursorManager.getCursorPosition()!;
            const { setIndex, pillIndex, position } = cursorPosition;
            
            // Special case: At the beginning of an empty line (after deleting leftmost tune)
            const tunePillsData = window.StateManager.getTunePillsData();
            if (position === 'before' && pillIndex === 0 && tunePillsData[setIndex]!.length === 0) {
                // Don't do anything if this is the first line
                if (setIndex === 0) {
                    return;
                }
                
                // Delete the set break and merge with previous line
                window.undoRedoManager.saveToUndo();
                
                // Just remove the empty set and position cursor at end of previous set
                tunePillsData.splice(setIndex, 1);
                
                // Update StateManager with the modified data
                window.StateManager.setTunePillsData(tunePillsData);
                
                // Position cursor at end of previous set
                window.PillRenderer.renderTunePills();
                const updatedTunePillsData = window.StateManager.getTunePillsData();
                if (setIndex - 1 >= 0 && updatedTunePillsData[setIndex - 1]!.length > 0) {
                    window.CursorManager.setCursorPosition(setIndex - 1, updatedTunePillsData[setIndex - 1]!.length - 1, 'after');
                } else {
                    window.CursorManager.setCursorPosition(0, 0, 'before');
                }
                return;
            }
            
            // Check for another special case: At the beginning of a line with content
            if (position === 'before' && pillIndex === 0 && tunePillsData[setIndex]!.length > 0 && setIndex > 0) {
                // At the beginning of a line with content - merge current set with previous set
                window.undoRedoManager.saveToUndo();
                const prevSet = tunePillsData[setIndex - 1]!;
                const currentSet = tunePillsData[setIndex]!;
                const prevSetOriginalLength = prevSet.length;
                
                // Append all pills from current set to previous set
                prevSet.push(...currentSet);
                
                // Remove the current set
                tunePillsData.splice(setIndex, 1);
                
                // Update StateManager with the modified data
                window.StateManager.setTunePillsData(tunePillsData);
                
                // Position cursor where the merge happened
                window.PillRenderer.renderTunePills();
                window.CursorManager.setCursorPosition(setIndex - 1, prevSetOriginalLength, 'after');
                return;
            }
            
            // Normal backspace behavior: delete tune to the left
            window.deleteTuneAtCursor();
        }
    }

    /**
     * Handle delete key during typing and editing
     */
    handleDelete(): void {
        // If multiple pills are selected, delete them all
        if (window.PillSelection.hasSelection()) {
            window.PillSelection.deleteSelectedPills();
            return;
        }
        
        const cursorPosition = window.CursorManager.getCursorPosition();
        if (!cursorPosition || this.isTyping) return;
        
        const { setIndex, pillIndex, position } = cursorPosition;
        
        // Special case: On an empty temporary line - just remove the empty line
        const tunePillsData = window.StateManager.getTunePillsData();
        if (position === 'before' && pillIndex === 0 && tunePillsData[setIndex]!.length === 0) {
            // First line, do nothing
            if (setIndex === 0) {
                return;
            }
            
            // Just remove the empty set without merging anything
            window.undoRedoManager.saveToUndo();
            tunePillsData.splice(setIndex, 1);
            
            // Update StateManager with the modified data
            window.StateManager.setTunePillsData(tunePillsData);
            
            // Position cursor at end of previous set
            window.PillRenderer.renderTunePills();
            const updatedTunePillsData2 = window.StateManager.getTunePillsData();
            if (setIndex - 1 >= 0 && updatedTunePillsData2[setIndex - 1]!.length > 0) {
                window.CursorManager.setCursorPosition(setIndex - 1, updatedTunePillsData2[setIndex - 1]!.length - 1, 'after');
            } else {
                window.CursorManager.setCursorPosition(0, 0, 'before');
            }
            return;
        }
        
        // Special case: At the end of a line - merge next line's content into current line
        if (position === 'after' && pillIndex === tunePillsData[setIndex]!.length - 1) {
            // Check if there's a next set to merge
            if (setIndex + 1 < tunePillsData.length) {
                window.undoRedoManager.saveToUndo();
                const currentSet = tunePillsData[setIndex]!;
                const nextSet = tunePillsData[setIndex + 1]!;
                const currentSetOriginalLength = currentSet.length;
                
                // Append all pills from next set to current set
                currentSet.push(...nextSet);
                
                // Remove the next set
                tunePillsData.splice(setIndex + 1, 1);
                
                // Update StateManager with the modified data
                window.StateManager.setTunePillsData(tunePillsData);
                
                // Keep cursor at end of original current set content
                window.PillRenderer.renderTunePills();
                window.CursorManager.setCursorPosition(setIndex, currentSetOriginalLength - 1, 'after');
                return;
            }
        }
        
        // Normal delete behavior: delete tune to the right
        let tuneToDelete: {setIndex: number; pillIndex: number} | null = null;
        let newCursorPosition: CursorPosition | null = null;
        
        if (position === 'before') {
            // Delete the pill at the current position
            if (pillIndex < tunePillsData[setIndex]!.length) {
                tuneToDelete = { setIndex, pillIndex };
                // Cursor stays in the same position (before the next pill)
                newCursorPosition = { setIndex, pillIndex, position: 'before' };
            }
        } else if (position === 'after') {
            // Delete the next pill if it exists
            if (pillIndex + 1 < tunePillsData[setIndex]!.length) {
                tuneToDelete = { setIndex, pillIndex: pillIndex + 1 };
                // Cursor stays after the current pill
                newCursorPosition = { setIndex, pillIndex, position: 'after' };
            } else if (setIndex + 1 < tunePillsData.length && tunePillsData[setIndex + 1]!.length > 0) {
                // At end of set, delete first pill of next set
                tuneToDelete = { setIndex: setIndex + 1, pillIndex: 0 };
                // Cursor stays at end of current set
                newCursorPosition = { setIndex, pillIndex, position: 'after' };
            }
        }
        
        if (tuneToDelete) {
            window.undoRedoManager.saveToUndo();
            const targetSet = tunePillsData[tuneToDelete.setIndex]!;
            const wasLastPillInSet = targetSet.length === 1; // Check before deletion
            
            // Delete the pill
            targetSet.splice(tuneToDelete.pillIndex, 1);
            
            const shouldCreateTemporaryEmpty = (targetSet.length === 0 && 
                tuneToDelete.setIndex > 0 && 
                tuneToDelete.setIndex < tunePillsData.length - 1);
                
            const setWasRemoved = targetSet.length === 0 && !shouldCreateTemporaryEmpty;
            
            if (targetSet.length === 0 && !shouldCreateTemporaryEmpty) {
                // Remove the empty set entirely
                tunePillsData.splice(tuneToDelete.setIndex, 1);
                
                // Adjust cursor position if the set was removed
                if (tuneToDelete.setIndex <= newCursorPosition!.setIndex) {
                    if (tuneToDelete.setIndex === newCursorPosition!.setIndex) {
                        // The cursor was in the deleted set - move to end of previous set or beginning of next
                        if (tuneToDelete.setIndex > 0) {
                            // Move to end of previous set
                            const prevSetLength = tunePillsData[tuneToDelete.setIndex - 1]!.length;
                            newCursorPosition = {
                                setIndex: tuneToDelete.setIndex - 1,
                                pillIndex: prevSetLength > 0 ? prevSetLength - 1 : 0,
                                position: prevSetLength > 0 ? 'after' : 'before'
                            };
                        } else if (tunePillsData.length > 0) {
                            // Move to beginning of first set
                            newCursorPosition = { setIndex: 0, pillIndex: 0, position: 'before' };
                        }
                    } else {
                        // Cursor was in a later set - adjust setIndex down by 1
                        newCursorPosition!.setIndex--;
                    }
                }
            } else if (shouldCreateTemporaryEmpty) {
                window.temporaryEmptySet = tuneToDelete.setIndex;
            }
            
            // Update StateManager with the modified data
            window.StateManager.setTunePillsData(tunePillsData);
            
            window.PillRenderer.renderTunePills();
            
            // Set the cursor position
            const finalTunePillsData = window.StateManager.getTunePillsData();
            if (newCursorPosition && newCursorPosition.setIndex < finalTunePillsData.length) {
                const setLength = finalTunePillsData[newCursorPosition.setIndex]!.length;
                if (newCursorPosition.pillIndex >= setLength) {
                    newCursorPosition.pillIndex = Math.max(0, setLength - 1);
                    newCursorPosition.position = setLength > 0 ? 'after' : 'before';
                }
                window.CursorManager.setCursorPosition(newCursorPosition.setIndex, newCursorPosition.pillIndex, newCursorPosition.position);
            } else {
                // Fallback to a safe position
                window.CursorManager.setCursorPosition(0, 0, 'before');
            }
        }
    }

    /**
     * Handle enter key to create new set
     */
    handleEnterKey(): void {
        const cursorPosition = window.CursorManager.getCursorPosition();
        if (!cursorPosition || this.isTyping) return;
        
        window.undoRedoManager.saveToUndo();
        
        const { setIndex, pillIndex, position } = cursorPosition;
        
        // Create a new empty set after the current one
        const newSetIndex = setIndex + 1;
        const tunePillsData = window.StateManager.getTunePillsData();
        tunePillsData.splice(newSetIndex, 0, []);
        
        // Update StateManager with the modified data
        window.StateManager.setTunePillsData(tunePillsData);
        
        window.PillRenderer.renderTunePills();
        
        // Position cursor at the beginning of the new set
        window.CursorManager.setCursorPosition(newSetIndex, 0, 'before');
        
        window.temporaryEmptySet = newSetIndex;
    }

    /**
     * Finish typing and insert tunes
     */
    finishTyping(keepKeyboardOpen: boolean = false): void {
        // Clear any typing timeout
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
            this.typingTimeout = null;
        }
        
        // Hide any typing match menu
        const typingMenu = document.querySelector('.typing-match-menu');
        if (typingMenu) {
            typingMenu.remove();
        }
        
        // If we're trying to keep keyboard open, set the flag
        if (keepKeyboardOpen) {
            this.isKeepingKeyboardOpen = true;
            // Clear the flag after a delay to allow processing to complete
            setTimeout(() => {
                this.isKeepingKeyboardOpen = false;
            }, 1000);
        }
        
        if (this.isTyping && this.typingBuffer.trim()) {
            const tuneNames = this.typingBuffer.split(/[,;]/).map(name => name.trim()).filter(name => name);
            this.insertTunesAtCursor(tuneNames, keepKeyboardOpen);
        }
        
        this.typingBuffer = '';
        this.isTyping = false;
        this.typingPill = null;
        window.CursorManager.updateCursorWithText();
        
        // On mobile, only hide keyboard if not continuing to type
        if (window.CursorManager.isMobileDevice() && !keepKeyboardOpen) {
            const container = document.getElementById('tune-pills-container') as HTMLElement;
            if (container) {
                container.contentEditable = 'false';
                container.blur();
            }
        } else if (window.CursorManager.isMobileDevice() && keepKeyboardOpen) {
            // When keeping keyboard open, ensure the container stays focused and editable
            // BUT NOT if a modal is open - modals need exclusive keyboard access
            const hasOpenModal = document.body.classList.contains('modal-open');
            const container = document.getElementById('tune-pills-container') as HTMLElement;
            if (container && !hasOpenModal) {
                // Keep contentEditable true and don't blur
                container.contentEditable = 'true';
                (container as any).inputMode = 'text';

                // Re-focus after a longer delay to ensure everything is complete
                setTimeout(() => {
                    if (!(window as any).popoutActive) {
                        container.focus();
                    }
                }, 300);
            }
        }
    }

    /**
     * Cancel typing without inserting
     */
    cancelTyping(): void {
        // Clear any typing timeout
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
            this.typingTimeout = null;
        }
        
        // Hide any typing match menu
        const typingMenu = document.querySelector('.typing-match-menu');
        if (typingMenu) {
            typingMenu.remove();
        }
        
        this.typingBuffer = '';
        this.isTyping = false;
        this.typingPill = null;
        window.CursorManager.updateCursorWithText();
        
        // On mobile, remove contenteditable to hide keyboard
        if (window.CursorManager.isMobileDevice()) {
            const container = document.getElementById('tune-pills-container') as HTMLElement;
            if (container) {
                container.contentEditable = 'false';
                container.blur();
            }
        }
    }

    /**
     * Insert tunes at cursor position
     */
    insertTunesAtCursor(tuneNames: string[], keepKeyboardOpen: boolean = false): void {
        const cursorPosition = window.CursorManager.getCursorPosition();
        if (!cursorPosition || tuneNames.length === 0) return;
        
        // If we're adding tunes to a temporary empty set, make it permanent
        if (window.temporaryEmptySet !== null && cursorPosition.setIndex === window.temporaryEmptySet) {
            window.temporaryEmptySet = null;
        }
        
        window.undoRedoManager.saveToUndo();
        
        const { setIndex, pillIndex, position } = cursorPosition;
        
        // Calculate the previous tune type based on cursor position before inserting pills
        let previousTuneType: string | null = null;

        const tunePillsData = window.StateManager.getTunePillsData();
        if (setIndex < tunePillsData.length) {
            const set = tunePillsData[setIndex]!;

            if (position === 'after' && pillIndex >= 0 && pillIndex < set.length) {
                // Cursor is after a pill - look backwards from current pill
                for (let i = pillIndex; i >= 0; i--) {
                    if (set[i]!.tuneType) {
                        previousTuneType = set[i]!.tuneType;
                        break;
                    }
                }
            } else if (position === 'before' && pillIndex > 0) {
                // Cursor is before a pill but not the first - look at previous pill
                for (let i = pillIndex - 1; i >= 0; i--) {
                    if (set[i]!.tuneType) {
                        previousTuneType = set[i]!.tuneType;
                        break;
                    }
                }
            }
        } else if (position === 'newset' && setIndex > 0) {
            // Starting a new set - check the last tune of the previous set
            const currentTunePillsData = window.StateManager.getTunePillsData();
            const prevSet = currentTunePillsData[setIndex - 1]!;
            if (prevSet && prevSet.length > 0) {
                for (let i = prevSet.length - 1; i >= 0; i--) {
                    if (prevSet[i]!.tuneType) {
                        previousTuneType = prevSet[i]!.tuneType;
                        break;
                    }
                }
            }
        }

        // Create new pills with the calculated previous tune type
        const newPills: TypingPill[] = tuneNames.map(name => ({
            id: window.StateManager.generateId(),
            orderNumber: 0,
            tuneId: null,
            tuneName: name,
            setting: '',
            tuneType: '',
            state: 'loading',  // Show loading spinner until API responds
            previousTuneType: previousTuneType,  // Store for API call
            startedByPersonId: null,
            loggedByFirstName: (window as any).sessionConfig?.currentUserFirstName || null,
            loggedByLastName: (window as any).sessionConfig?.currentUserLastName || null,
            orderPosition: null,  // Will be generated by backend on save
            sessionInstanceTuneId: null  // Will be assigned by backend on save
        }));
        
        // Attempt to auto-match each tune via API
        const matchPromises = newPills.map(pill => window.autoMatchTune(pill));
        
        // Wait for all matching to complete, then show appropriate message
        Promise.all(matchPromises).then(() => {
            window.showMatchingResults(newPills);
        });
        
        const finalTunePillsData = window.StateManager.getTunePillsData();
        if (position === 'newset') {
            if (setIndex >= finalTunePillsData.length) {
                // Create new set at end
                finalTunePillsData.push(newPills);
                // Position cursor after the last inserted pill in this new set
                window.CursorManager.setCursorPosition(finalTunePillsData.length - 1, newPills.length - 1, 'after', keepKeyboardOpen);
            } else {
                // Create new set at specific index (insert between existing sets)
                finalTunePillsData.splice(setIndex, 0, newPills);
                // Position cursor after the last inserted pill in this new set
                window.CursorManager.setCursorPosition(setIndex, newPills.length - 1, 'after', keepKeyboardOpen);
            }
        } else {
            // Insert into existing set
            const targetSet = finalTunePillsData[setIndex]!;
            let insertIndex = pillIndex;
            
            if (position === 'before') {
                insertIndex = Math.max(0, pillIndex);
            } else if (position === 'after') {
                insertIndex = Math.min(targetSet.length, pillIndex + 1);
            }
            
            // Insert all new pills at the position
            newPills.forEach((pill, index) => {
                targetSet.splice(insertIndex + index, 0, pill);
            });
            
            // Move cursor to after the inserted pills
            const newCursorPillIndex = insertIndex + newPills.length - 1;
            window.CursorManager.setCursorPosition(setIndex, newCursorPillIndex, 'after', keepKeyboardOpen);
        }
        
        // Update StateManager with the modified data
        window.StateManager.setTunePillsData(finalTunePillsData);
        
        window.PillRenderer.renderTunePills();
    }

    /**
     * Wrapper function for cursor text updates (backward compatibility)
     */
    updateCursorWithText(): void {
        return window.CursorManager.updateCursorWithText();
    }

    // Getters for accessing typing state (for other modules)
    get typing(): boolean {
        return this.isTyping;
    }

    get buffer(): string {
        return this.typingBuffer;
    }

    get keepingKeyboardOpen(): boolean {
        return this.isKeepingKeyboardOpen;
    }
}

// Export for use in other modules
(window as any).TextInput = TextInput;