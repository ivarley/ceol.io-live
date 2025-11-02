/**
 * Context Menu Module
 * Handles the creation and management of context menus for tune pills
 */

import { TunePill } from './stateManager.js';

export interface MatchResult {
    tune_id: number;
    tune_name: string;
    tune_type: string;
}

export interface ExtendedTunePill extends TunePill {
    matchResults?: MatchResult[] | null;
}

export interface ContextMenuDependencies {
    PillRenderer: {
        updatePillAppearance(pill: TunePill): void;
        renderTunePills(): void;
    };
    AutoSaveManager: {
        forceCheckChanges(): void;
    };
    PillSelection: {
        getSelectionCount(): number;
        deleteSelectedPills(): void;
    };
    StateManager: {
        getTunePillsData(): import('./stateManager.js').TunePillsData;
        setTunePillsData(data: import('./stateManager.js').TunePillsData): void;
        findTuneById(id: string): import('./stateManager.js').TunePosition | null;
        generateId(): string;
    };
    undoRedoManager: {
        saveToUndo(): void;
    };
    ModalManager: {
        showModalWithInput(modalId: string, inputSelector: string, value: string, selectText: boolean): void;
    };
    CursorManager: {
        setCursorPosition(setIndex: number, pillIndex: number, position: string): void;
        updateCursorWithText(): void;
        getCursorPosition(): { setIndex: number; pillIndex: number; position: string } | null;
    };
    findPillPosition?: (pillId: string) => import('./stateManager.js').TunePosition | null;
    textInput?: {
        typing: boolean;
        isTyping: boolean;
        typingPill: ExtendedTunePill | null;
        typingBuffer: string;
        typingTimeout: number | null;
        finishTyping: (keepKeyboard?: boolean) => void;
        insertTunesAtCursor: (tunes: any[], keepKeyboard?: boolean) => void;
    };
}

declare global {
    interface Window {
        ContextMenu: typeof ContextMenu;
        currentLinkingPill: TunePill;
        currentEditingPill: TunePill;
        PillRenderer: ContextMenuDependencies['PillRenderer'];
        AutoSaveManager: ContextMenuDependencies['AutoSaveManager'];
        PillSelection: ContextMenuDependencies['PillSelection'];
        StateManager: ContextMenuDependencies['StateManager'];
        undoRedoManager: ContextMenuDependencies['undoRedoManager'];
        ModalManager: ContextMenuDependencies['ModalManager'];
        CursorManager: ContextMenuDependencies['CursorManager'];
        findPillPosition: ContextMenuDependencies['findPillPosition'];
        textInput: ContextMenuDependencies['textInput'];
        temporaryEmptySet: number | null;
    }
}

export class ContextMenu {
    // Store event listeners so we can remove them when hiding
    private static activeMenuListeners: Array<{hideMenu: (e: Event) => void, hideOnScroll: () => void}> = [];

    /**
     * Remove all context menus and reset chevron states
     * @param pillId - Optional pill ID for specific targeting
     */
    static hideContextMenu(pillId?: string): void {
        // Remove all context menus and reset chevron states
        document.querySelectorAll('.tune-context-menu').forEach(menu => menu.remove());
        document.querySelectorAll('.chevron.open').forEach(chevron => chevron.classList.remove('open'));

        // Remove any lingering event listeners
        this.activeMenuListeners.forEach(({hideMenu, hideOnScroll}) => {
            document.removeEventListener('click', hideMenu);
            document.removeEventListener('scroll', hideOnScroll, true);
        });
        this.activeMenuListeners = [];
    }
    
    /**
     * Remove match results menu for specific pill
     * @param pillId - The pill ID to hide match results for
     */
    static hideMatchResultsMenu(pillId: string): void {
        const menu = document.querySelector(`.match-results-menu[data-pill-id="${pillId}"]`);
        if (menu) {
            menu.remove();
        }
    }
    
    /**
     * Show context menu for a pill
     * @param event - The click event that triggered the menu
     * @param pillData - The pill data object
     */
    static showContextMenu(event: MouseEvent, pillData: ExtendedTunePill): void {
        // Remove existing context menus and reset all chevrons
        ContextMenu.hideContextMenu();
        
        const menu = document.createElement('div');
        menu.className = 'tune-context-menu';
        menu.style.display = 'block';
        menu.dataset.pillId = pillData.id; // Track which pill this menu belongs to
        
        // Find the pill element to match its dimensions and color
        const pillElement = (event.target as Element).closest('.tune-pill') as HTMLElement;
        const rect = pillElement.getBoundingClientRect();
        
        // Set chevron to open state
        const chevron = pillElement.querySelector('.chevron') as HTMLElement;
        chevron.classList.add('open');
        
        // Position menu
        menu.style.position = 'fixed';
        menu.style.left = rect.left + 'px';
        menu.style.top = (rect.bottom + 5) + 'px';
        
        // For unmatched pills with results, make menu wider to accommodate content
        if (pillData.state === 'unmatched' && pillData.matchResults && pillData.matchResults.length > 0) {
            menu.style.width = 'auto';
            menu.style.minWidth = Math.max(250, rect.width) + 'px';
            menu.style.maxWidth = Math.min(500, window.innerWidth - rect.left - 20) + 'px';
        } else if (pillData.state === 'unlinked') {
            // For unlinked pills, cap menu width at 250px
            menu.style.width = 'auto';
            menu.style.minWidth = rect.width + 'px';
            menu.style.maxWidth = '250px';
        } else {
            // Match pill width for other states
            menu.style.width = rect.width + 'px';
            menu.style.minWidth = 'unset';
        }
        
        // Match pill background color based on state
        const computedStyle = window.getComputedStyle(pillElement);
        menu.style.backgroundColor = computedStyle.backgroundColor;
        menu.style.color = computedStyle.color;
        menu.style.borderColor = computedStyle.borderColor;
        
        // Create menu items based on pill state
        if (pillData.state === 'linked') {
            // Linked tune options
            ContextMenu.addMenuItem(menu, 'Dots', () => {
                const url = `https://thesession.org/tunes/${pillData.tuneId}${pillData.setting ? '#setting' + pillData.setting : ''}`;
                window.open(url, '_blank');
                ContextMenu.hideContextMenu();
            });
            
            ContextMenu.addMenuItem(menu, 'Info', () => {
                ContextMenu.hideContextMenu();
                // Show the tune detail modal instead of navigating
                if (typeof (window as any).showTuneDetail === 'function') {
                    (window as any).showTuneDetail(pillData.tuneId, pillData.tuneName, pillData.tuneType);
                } else {
                    // Fallback to old behavior if showTuneDetail is not available
                    const sessionPath = (window as any).sessionConfig?.sessionPath;
                    const sessionDate = (window as any).sessionConfig?.sessionDate;
                    window.location.href = `/sessions/${sessionPath}/tunes/${pillData.tuneId}?from_date=${sessionDate}`;
                }
            });
            
            ContextMenu.addMenuItem(menu, 'Relink', () => {
                ContextMenu.hideContextMenu();
                ContextMenu.showLinkModal(pillData);
            });
        } else if (pillData.state === 'unmatched' && pillData.matchResults && pillData.matchResults.length > 0) {
            // Show match results first
            pillData.matchResults.forEach(result => {
                const item = document.createElement('a');
                item.style.display = 'block';
                item.style.padding = '8px 12px';
                item.style.cursor = 'pointer';
                item.style.borderBottom = '1px solid rgba(255,255,255,0.2)';
                
                // Show tune name and type
                const nameSpan = document.createElement('span');
                nameSpan.textContent = result.tune_name;
                nameSpan.style.fontWeight = '500';
                item.appendChild(nameSpan);
                
                if (result.tune_type) {
                    const typeSpan = document.createElement('span');
                    typeSpan.textContent = ` (${result.tune_type})`;
                    typeSpan.style.opacity = '0.8';
                    typeSpan.style.fontSize = '0.9em';
                    item.appendChild(typeSpan);
                }
                
                // Click to select this match
                item.addEventListener('click', () => {
                    // Apply the selected match
                    pillData.tuneId = result.tune_id;
                    pillData.tuneName = result.tune_name;
                    pillData.tuneType = result.tune_type;
                    pillData.state = 'linked';
                    pillData.matchResults = null;

                    // Find the pill in StateManager's data and update it there too
                    const pillPosition = window.StateManager.findTuneById(pillData.id);
                    if (pillPosition) {
                        const tunePillsData = window.StateManager.getTunePillsData();
                        const tuneSet = tunePillsData[pillPosition.setIndex];

                        if (tuneSet && pillPosition.pillIndex >= 0 && pillPosition.pillIndex < tuneSet.length) {
                            const actualPill = tuneSet[pillPosition.pillIndex];
                            if (actualPill) {
                                // Update the actual pill in StateManager
                                actualPill.tuneId = result.tune_id;
                                actualPill.tuneName = result.tune_name;
                                actualPill.tuneType = result.tune_type;
                                actualPill.state = 'linked';
                                actualPill.matchResults = null;

                                // Update StateManager to ensure the changes are tracked
                                window.StateManager.setTunePillsData(tunePillsData);
                            }
                        }
                    }

                    // Update the pill appearance (this will also update the set type label)
                    window.PillRenderer.updatePillAppearance(pillData);

                    // Force check for changes (includes timer reset and dirty state)
                    window.AutoSaveManager.forceCheckChanges();
                    ContextMenu.hideContextMenu();
                });
                
                menu.appendChild(item);
            });
            
            // Add separator
            const separator = document.createElement('div');
            separator.style.borderTop = '1px solid rgba(255,255,255,0.3)';
            separator.style.margin = '4px 0';
            menu.appendChild(separator);

            // Add Search By Name option
            ContextMenu.addMenuItem(menu, 'Search By Name', () => {
                ContextMenu.hideContextMenu();
                ContextMenu.showTuneSearchModal(pillData);
            });

            // Add manual link option
            ContextMenu.addMenuItem(menu, 'Manual Link...', () => {
                ContextMenu.hideContextMenu();
                ContextMenu.showLinkModal(pillData);
            });
        } else {
            // Unlinked tune options - add informative header first
            const infoHeader = document.createElement('div');
            infoHeader.style.padding = '8px 12px';
            infoHeader.style.fontSize = '0.85em';
            infoHeader.style.fontStyle = 'italic';
            infoHeader.style.color = 'rgba(255,255,255,0.7)';
            infoHeader.style.cursor = 'default';
            infoHeader.style.borderBottom = '1px solid rgba(255,255,255,0.3)';
            infoHeader.style.marginBottom = '4px';
            infoHeader.style.whiteSpace = 'normal';
            infoHeader.style.wordWrap = 'break-word';
            infoHeader.style.lineHeight = '1.4';
            infoHeader.textContent = 'This entry has not been matched to a known tune; you can link it manually, edit the text, delete it, or leave it as is.';
            menu.appendChild(infoHeader);

            // Add Search By Name option below description
            ContextMenu.addMenuItem(menu, 'Search By Name', () => {
                ContextMenu.hideContextMenu();
                ContextMenu.showTuneSearchModal(pillData);
            });

            ContextMenu.addMenuItem(menu, 'Manually Link', () => {
                ContextMenu.hideContextMenu();
                ContextMenu.showLinkModal(pillData);
            });
        }
        
        // Common options
        ContextMenu.addMenuItem(menu, 'Edit Text', () => {
            ContextMenu.hideContextMenu();
            ContextMenu.showEditModal(pillData);
        });
        
        if (window.PillSelection.getSelectionCount() <= 1) {
            ContextMenu.addMenuItem(menu, 'Delete', () => {
                ContextMenu.deletePill(pillData.id);
                ContextMenu.hideContextMenu();
            });
        } else {
            ContextMenu.addMenuItem(menu, `Delete Selected (${window.PillSelection.getSelectionCount()})`, () => {
                window.PillSelection.deleteSelectedPills();
                ContextMenu.hideContextMenu();
            });
        }
        
        document.body.appendChild(menu);

        // Hide menu when clicking elsewhere or scrolling
        setTimeout(() => {
            const hideMenu = (e: Event) => {
                if (!menu.contains(e.target as Node)) {
                    ContextMenu.hideContextMenu();
                }
            };

            const hideOnScroll = () => {
                ContextMenu.hideContextMenu();
            };

            // Store the listeners so we can remove them later
            this.activeMenuListeners.push({hideMenu, hideOnScroll});

            document.addEventListener('click', hideMenu);
            // Use capture phase to catch scroll on any element
            document.addEventListener('scroll', hideOnScroll, true);
        }, 0);
    }
    
    /**
     * Show match results menu for a pill during typing
     * @param pill - The pill data object with match results
     */
    static showMatchResultsMenu(pill: ExtendedTunePill): void {
        // Remove any existing match results menu for this pill
        ContextMenu.hideMatchResultsMenu(pill.id);
        
        if (!pill.matchResults || pill.matchResults.length === 0) {
            return;
        }
        
        // For typing pills, find the typing text element instead of a pill element
        let elementToPosition: HTMLElement | null = null;
        let rect: DOMRect;
        
        if (pill.id.startsWith('typing-')) {
            // This is a typing pill - find the typing text element
            elementToPosition = document.querySelector('.typing-text') as HTMLElement;
            if (!elementToPosition) {
                return;
            }
        } else {
            // Regular pill - find the pill element
            elementToPosition = document.querySelector(`[data-pill-id="${pill.id}"]`) as HTMLElement;
            if (!elementToPosition) {
                console.error(`Could not find pill element for ID: ${pill.id}`);
                return;
            }
        }
        
        rect = elementToPosition.getBoundingClientRect();
        
        const menu = document.createElement('div');
        menu.className = 'tune-context-menu match-results-menu';
        menu.style.display = 'block';
        menu.dataset.pillId = pill.id;
        
        // Position menu below the pill
        menu.style.position = 'fixed';
        menu.style.left = rect.left + 'px';
        menu.style.top = (rect.bottom + 5) + 'px';
        menu.style.width = 'auto';
        menu.style.minWidth = Math.max(200, rect.width) + 'px';
        menu.style.maxWidth = Math.min(600, window.innerWidth - rect.left - 20) + 'px';
        
        // Use theme-aware styling for the menu
        const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark';
        if (isDarkMode) {
            menu.style.backgroundColor = 'var(--dropdown-bg)';
            menu.style.color = 'var(--text-color)';
            menu.style.border = '1px solid var(--border-color)';
        } else {
            menu.style.backgroundColor = 'white';
            menu.style.color = '#212529';
            menu.style.border = '1px solid #dee2e6';
        }
        menu.style.borderRadius = '4px';
        menu.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
        
        // Add match results as menu items
        pill.matchResults.forEach(result => {
            const item = document.createElement('a');
            item.style.display = 'block';
            item.style.padding = '8px 12px';
            item.style.cursor = 'pointer';
            item.style.borderBottom = isDarkMode ? '1px solid var(--border-color)' : '1px solid #f0f0f0';
            item.style.color = isDarkMode ? 'var(--text-color)' : '#212529';
            item.style.textDecoration = 'none';
            
            // Show tune name and type
            const nameSpan = document.createElement('span');
            nameSpan.textContent = result.tune_name;
            nameSpan.style.fontWeight = '500';
            item.appendChild(nameSpan);
            
            if (result.tune_type) {
                const typeSpan = document.createElement('span');
                typeSpan.textContent = ` (${result.tune_type})`;
                typeSpan.style.color = isDarkMode ? 'var(--disabled-text)' : '#6c757d';
                typeSpan.style.fontSize = '0.9em';
                item.appendChild(typeSpan);
            }
            
            // Hover effect
            item.addEventListener('mouseenter', () => {
                item.style.backgroundColor = isDarkMode ? 'var(--hover-bg)' : '#f8f9fa';
            });
            item.addEventListener('mouseleave', () => {
                item.style.backgroundColor = 'transparent';
            });
            
            // Click to select this match
            item.addEventListener('click', () => {
                // Apply the selected match
                pill.tuneId = result.tune_id;
                pill.tuneName = result.tune_name;
                pill.tuneType = result.tune_type;
                pill.state = 'linked';
                pill.matchResults = null;
                
                // Handle typing pills differently than regular pills
                if (pill.id.startsWith('typing-')) {
                    // For typing pills, use the same approach as Tab completion
                    if (window.textInput && window.textInput.typing) {
                        // Save scroll position before finishTyping
                        const scrollY = window.scrollY;
                        const scrollX = window.scrollX;
                        
                        // Update the typing pill with the selected match
                        window.textInput.typingPill = pill;
                        window.textInput.typingBuffer = result.tune_name;
                        
                        // Remove any typing match menus
                        const menus = document.querySelectorAll('.typing-match-menu, .match-results-menu');
                        menus.forEach(menu => menu.remove());
                        
                        // Temporarily override scrollIntoView during finishTyping
                        const originalScrollIntoView = Element.prototype.scrollIntoView;
                        Element.prototype.scrollIntoView = function() { /* prevent scrolling */ };
                        
                        // Use the normal finishTyping flow
                        window.textInput.finishTyping(false);
                        
                        // Restore scrollIntoView and scroll position
                        Element.prototype.scrollIntoView = originalScrollIntoView;
                        window.scrollTo(scrollX, scrollY);
                    }
                } else {
                    // Regular pill - update its appearance
                    window.PillRenderer.updatePillAppearance(pill);
                    
                    // Force check for changes (includes timer reset and dirty state)
                    window.AutoSaveManager.forceCheckChanges();
                }
                
                // Hide the menu
                ContextMenu.hideMatchResultsMenu(pill.id);
            });
            
            menu.appendChild(item);
        });
        
        document.body.appendChild(menu);
        
        // Hide menu when clicking elsewhere or scrolling
        setTimeout(() => {
            const hideMenu = (e: Event) => {
                if (!menu.contains(e.target as Node)) {
                    ContextMenu.hideMatchResultsMenu(pill.id);
                    document.removeEventListener('click', hideMenu);
                    document.removeEventListener('scroll', hideOnScroll, true);
                }
            };
            
            const hideOnScroll = () => {
                ContextMenu.hideMatchResultsMenu(pill.id);
                document.removeEventListener('click', hideMenu);
                document.removeEventListener('scroll', hideOnScroll, true);
            };
            
            document.addEventListener('click', hideMenu);
            // Use capture phase to catch scroll on any element
            document.addEventListener('scroll', hideOnScroll, true);
        }, 0);
    }
    
    /**
     * Add a menu item to a context menu
     * @param menu - The menu element to add the item to
     * @param text - The text for the menu item
     * @param callback - The callback function when clicked
     */
    static addMenuItem(menu: HTMLElement, text: string, callback: () => void): void {
        const item = document.createElement('a');
        item.textContent = text;
        item.addEventListener('click', callback);
        menu.appendChild(item);
    }
    
    /**
     * Show link modal for a pill
     * @param pillData - The pill data object
     */
    static showLinkModal(pillData: TunePill): void {
        // Add modal-open class IMMEDIATELY to prevent enterEditMode from focusing container
        document.body.classList.add('modal-open');

        const inputValue = pillData.tuneId ? `https://thesession.org/tunes/${pillData.tuneId}` : '';
        window.ModalManager.showModalWithInput('link-tune-modal', '#tune-link-input', inputValue, false);
        // Store current pill for linking (backward compatibility)
        window.currentLinkingPill = pillData;
    }
    
    /**
     * Show edit modal for a pill
     * @param pillData - The pill data object
     */
    static showEditModal(pillData: TunePill): void {
        window.ModalManager.showModalWithInput('edit-tune-modal', '#edit-tune-name-input', pillData.tuneName, true);
        // Store current pill for editing (backward compatibility)
        window.currentEditingPill = pillData;
    }

    /**
     * Show tune search modal for a pill
     * @param pillData - The pill data object
     */
    static showTuneSearchModal(pillData: TunePill): void {
        // Store current pill for linking
        window.currentLinkingPill = pillData;

        // Show the tune search modal
        const modal = document.getElementById('tune-search-modal');

        if (modal) {
            // Add modal-open class to prevent body scrolling
            document.body.classList.add('modal-open');

            // Add show class to make modal visible (handles opacity transition)
            modal.classList.add('show');

            // Pre-populate the search input with the pill's current text
            const searchInput = document.getElementById('tune-search-modal-input') as HTMLInputElement;
            if (searchInput) {
                // Set the value to the pill's text
                searchInput.value = pillData.tuneName || '';

                setTimeout(() => {
                    searchInput.focus();
                    // Select all text so user can immediately start typing to replace
                    searchInput.select();

                    // Trigger search with the pre-populated text
                    const event = new Event('input', { bubbles: true });
                    searchInput.dispatchEvent(event);
                }, 100);
            }
        }
    }

    /**
     * Delete a pill by ID
     * @param pillId - The ID of the pill to delete
     */
    static deletePill(pillId: string): void {
        // Find and remove the pill
        const tunePillsData = window.StateManager.getTunePillsData();
        for (let setIndex = 0; setIndex < tunePillsData.length; setIndex++) {
            const pillIndex = tunePillsData[setIndex]!.findIndex(p => p.id === pillId);
            if (pillIndex !== -1) {
                window.undoRedoManager.saveToUndo();
                tunePillsData[setIndex]!.splice(pillIndex, 1);
                
                // Remove empty sets
                if (tunePillsData[setIndex]!.length === 0) {
                    tunePillsData.splice(setIndex, 1);
                }
                
                // Update StateManager with the modified data
                window.StateManager.setTunePillsData(tunePillsData);
                
                window.PillRenderer.renderTunePills();
                break;
            }
        }
    }
}

// Export the ContextMenu class for use in other modules
(window as any).ContextMenu = ContextMenu;