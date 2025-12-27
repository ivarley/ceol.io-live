/**
 * PillRenderer Module for Session Instance Detail Beta
 * Handles rendering of tune pills, sets, cursor positions, and UI elements
 */

import { TunePill, TuneSet, TunePillsData } from './stateManager.js';

export interface PillRendererCallbacks {
    cleanupDragGhosts?(): void;
    createHorizontalDropZone?(setIndex: number): HTMLElement;
    setupPillEventListeners?(pillElement: HTMLElement, pillData: TunePill): void;
    setCursorPosition?(setIndex: number, pillIndex: number, position: string, maintainKeyboard?: boolean): void;
    clearSelection?(): void;
}

export interface PillRendererDependencies {
    getStateManager(): StateManager;
    getCursorManager(): CursorManager;
    getAutoSaveManager(): AutoSaveManager;
    containerElement?: HTMLElement | null;
}

export interface StateManager {
    getTunePillsData(): TunePillsData;
}

export interface CursorManager {
    getCursorPosition(): CursorPosition | null;
    addCursorPosition?(parent: HTMLElement, setIndex: number, pillIndex: number, positionType: string): HTMLElement;
    addFinalCursor?(containerElement: HTMLElement): HTMLElement;
}

export interface CursorPosition {
    setIndex: number;
    pillIndex: number;
    position: string;
}

export interface AutoSaveManager {
    forceCheckChanges(): void;
}

export class PillRenderer {
    static getStateManager: (() => StateManager) | null = null; // Function to get StateManager reference
    static getCursorManager: (() => CursorManager) | null = null; // Function to get CursorManager reference
    static getAutoSaveManager: (() => AutoSaveManager) | null = null; // Function to get AutoSaveManager reference
    static containerElement: HTMLElement | null = null;
    
    // External functions that need to be called (will be registered via callbacks)
    static cleanupDragGhosts: (() => void) | null = null;
    static createHorizontalDropZone: ((setIndex: number) => HTMLElement) | null = null;
    static setupPillEventListeners: ((pillElement: HTMLElement, pillData: TunePill) => void) | null = null;
    static setCursorPosition: ((setIndex: number, pillIndex: number, position: string, maintainKeyboard?: boolean) => void) | null = null;
    static clearSelection: (() => void) | null = null;
    
    static initialize(options: PillRendererDependencies = {} as PillRendererDependencies): void {
        this.getStateManager = options.getStateManager || (() => (window as any).StateManager);
        this.getCursorManager = options.getCursorManager || (() => (window as any).CursorManager);
        this.getAutoSaveManager = options.getAutoSaveManager || (() => (window as any).AutoSaveManager);
        this.containerElement = options.containerElement || document.getElementById('tune-pills-container');
    }
    
    static renderTunePills(): void {
        const stateManager = this.getStateManager!();
        const cursorManager = this.getCursorManager!();
        const autoSaveManager = this.getAutoSaveManager!();
        const tunePillsData = stateManager.getTunePillsData();
        const cursorPosition = cursorManager.getCursorPosition();

        // Check if we're in view mode
        const isViewMode = (window as any).editorMode === 'view';

        // Check for data changes before rendering (safety net)
        autoSaveManager.forceCheckChanges();

        // Clean up any lingering drag ghosts before re-rendering
        if (this.cleanupDragGhosts) {
            this.cleanupDragGhosts();
        }

        const container = this.containerElement || document.getElementById('tune-pills-container')!;

        // Remember if the container was contentEditable before clearing (for mobile keyboard persistence)
        const wasContentEditable = container.contentEditable === 'true';
        const wasFocused = document.activeElement === container;

        container.innerHTML = '';

        // If we were contentEditable, restore it immediately after clearing (unless in view mode or modal is open)
        // Check body.modal-open class which is set BEFORE the modal is displayed
        const hasOpenModal = document.body.classList.contains('modal-open');
        if (wasContentEditable && !isViewMode && !hasOpenModal) {
            container.contentEditable = 'true';
            (container as any).inputMode = 'text';
        }

        if (tunePillsData.length === 0) {
            this.renderEmptyState(container);
            return;
        }

        tunePillsData.forEach((tuneSet, setIndex) => {
            // Add horizontal drop zone before each set (except the first one) - only in edit mode
            if (setIndex > 0 && this.createHorizontalDropZone && !isViewMode) {
                const dropZone = this.createHorizontalDropZone(setIndex);
                container.appendChild(dropZone);
            }

            const setDiv = this.createTuneSetElement(tuneSet, setIndex);
            container.appendChild(setDiv);
        });

        // Add final cursor position at the end - only in edit mode
        if (!isViewMode) {
            this.addFinalCursor(container);
        }

        // Set default cursor position at the end if none exists - only in edit mode
        if (isViewMode) {
            return; // Skip cursor positioning in view mode
        }

        if (!cursorPosition) {
            if (this.setCursorPosition) {
                this.setCursorPosition(tunePillsData.length, 0, 'newset');
            }
        } else {
            // Restore cursor position after re-render
            // Pass maintainKeyboard flag if we were contentEditable before
            if (this.setCursorPosition) {
                this.setCursorPosition(cursorPosition.setIndex, cursorPosition.pillIndex, cursorPosition.position, wasContentEditable);
            }
        }
    }
    
    static renderEmptyState(container: HTMLElement): void {
        const isViewMode = (window as any).editorMode === 'view';

        if (isViewMode) {
            // View mode: Simple message
            container.innerHTML = '<p style="color: var(--disabled-text); font-style: italic; margin: 0; text-align: center; padding: 40px 20px;">No tunes have been logged yet. Click Edit to start.</p>';
        } else {
            // Edit mode: Instructions for typing
            container.innerHTML = '<p style="color: var(--disabled-text); font-style: italic; margin: 0; text-align: center; padding: 40px 20px;">No tunes recorded for this session yet.<br><strong>Click anywhere to position cursor, then start typing...</strong><br><small>Use Enter, Tab, semicolon, or comma to finish entering tunes</small></p>';

            // Add a cursor position for empty container
            const emptyPos = document.createElement('span');
            emptyPos.className = 'cursor-position';
            emptyPos.dataset.setIndex = '0';
            emptyPos.dataset.pillIndex = '0';
            emptyPos.dataset.positionType = 'newset';
            emptyPos.style.position = 'absolute';
            emptyPos.style.top = '50%';
            emptyPos.style.left = '50%';
            emptyPos.style.transform = 'translate(-50%, -50%)';

            emptyPos.addEventListener('click', (e: MouseEvent) => {
                e.preventDefault();
                e.stopPropagation();

                // Clear selection and selection anchor when clicking to move cursor
                if (this.clearSelection) {
                    this.clearSelection();
                }

                if (this.setCursorPosition) {
                    this.setCursorPosition(0, 0, 'newset');
                }
            });

            container.appendChild(emptyPos);

            // Set initial cursor position
            if (this.setCursorPosition) {
                this.setCursorPosition(0, 0, 'newset');
            }
        }
    }
    
    static pluralizeTuneType(tuneType: string): string {
        // Handle special cases for pluralization
        const pluralMap: { [key: string]: string } = {
            'Jig': 'Jigs',
            'Reel': 'Reels',
            'Hornpipe': 'Hornpipes',
            'Polka': 'Polkas',
            'Slide': 'Slides',
            'Waltz': 'Waltzes',
            'Barndance': 'Barndances',
            'Mazurka': 'Mazurkas',
            'Strathspey': 'Strathspeys',
            'March': 'Marches',
            'Air': 'Airs',
            'Slip Jig': 'Slip Jigs',
            'Single Jig': 'Single Jigs',
            'Set Dance': 'Set Dances',
            'Fling': 'Flings',
            'Schottische': 'Schottisches'
        };

        return pluralMap[tuneType] || tuneType + 's';
    }

    static createTypeLabel(tuneSet: TuneSet): HTMLElement {
        // Calculate the predominant tune type in the set
        const typeLabel = document.createElement('span');
        typeLabel.className = 'tune-type-label';

        // Count tune types, only considering linked tunes
        const typeCounts: { [key: string]: number } = {};
        let linkedCount = 0;

        tuneSet.forEach(pill => {
            if (pill.state === 'linked' && pill.tuneType) {
                typeCounts[pill.tuneType] = (typeCounts[pill.tuneType] || 0) + 1;
                linkedCount++;
            }
        });

        // Determine the label text
        let labelText = '';
        if (linkedCount === 0) {
            // No linked tunes, show "Unknown"
            labelText = 'Unknown';
        } else {
            const types = Object.keys(typeCounts);
            if (types.length === 1) {
                // All linked tunes are the same type
                const tuneType = types[0]!;
                // Pluralize if there's more than one tune in the set
                if (tuneSet.length > 1) {
                    labelText = this.pluralizeTuneType(tuneType);
                } else {
                    labelText = tuneType;
                }
            } else if (types.length > 1) {
                // Multiple types - find the majority
                let maxCount = 0;
                let majorityType = '';
                for (const type in typeCounts) {
                    if (typeCounts[type]! > maxCount) {
                        maxCount = typeCounts[type]!;
                        majorityType = type;
                    }
                }

                // Check if there's a clear majority (more than 50%)
                if (maxCount > linkedCount / 2) {
                    // Pluralize the majority type if there's more than one tune
                    if (tuneSet.length > 1) {
                        labelText = this.pluralizeTuneType(majorityType);
                    } else {
                        labelText = majorityType;
                    }
                } else {
                    labelText = 'Mixed';
                }
            }
        }

        typeLabel.textContent = labelText;

        // Make the label clickable to toggle the set popout
        // Set contentEditable false so clicks work properly inside the editable container
        typeLabel.contentEditable = 'false';
        typeLabel.style.cursor = 'pointer';
        typeLabel.addEventListener('click', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            this.toggleSetPopout(typeLabel, tuneSet);
        });
        // Also handle touchend for more responsive mobile interaction
        typeLabel.addEventListener('touchend', (e: TouchEvent) => {
            e.preventDefault();
            e.stopPropagation();
            this.toggleSetPopout(typeLabel, tuneSet);
        });

        // Detect mobile vs desktop
        const isMobile = window.innerWidth <= 768;

        if (isMobile) {
            // Mobile: Folder tab style that sits outside and above the set container
            typeLabel.style.display = 'inline-block';
            typeLabel.style.minWidth = '78px'; // 2px shorter
            typeLabel.style.maxWidth = '78px';
            typeLabel.style.padding = '0px 8px 0px 8px'; // No top or bottom padding (text moved up 2px)
            typeLabel.style.marginRight = '0px';
            typeLabel.style.marginLeft = '0px';
            typeLabel.style.marginTop = '0px';
            typeLabel.style.marginBottom = '0px';
            typeLabel.style.backgroundColor = '#4a4a4a'; // Dark grey
            typeLabel.style.color = 'white';
            typeLabel.style.borderRadius = '6px 6px 0 0'; // Rounded top corners
            typeLabel.style.fontSize = '0.7em'; // Smaller font for mobile
            typeLabel.style.textAlign = 'center';
            typeLabel.style.fontWeight = '500';
            typeLabel.style.whiteSpace = 'nowrap';
            typeLabel.style.overflow = 'hidden';
            typeLabel.style.textOverflow = 'ellipsis';
            typeLabel.style.position = 'relative';
            typeLabel.style.boxSizing = 'border-box';
        } else {
            // Desktop: End cap style spanning full set height
            typeLabel.style.display = 'inline-flex';
            typeLabel.style.alignItems = 'center';
            typeLabel.style.justifyContent = 'center';
            typeLabel.style.minWidth = '100px'; // Enough for "Barndances" and "Hornpipes"
            typeLabel.style.maxWidth = '100px';
            typeLabel.style.paddingLeft = '9px';
            typeLabel.style.paddingRight = '9px';
            typeLabel.style.paddingTop = '7px'; // Shift text down 3px
            typeLabel.style.paddingBottom = '6px'; // Reduce bottom to maintain total height
            typeLabel.style.marginRight = '8px';
            typeLabel.style.marginLeft = '-6px'; // Offset the set padding to make it flush
            typeLabel.style.marginTop = '-4px'; // Offset set padding to align with top edge
            typeLabel.style.marginBottom = '-8px'; // Extend to bottom edge
            typeLabel.style.backgroundColor = '#4a4a4a'; // Dark grey
            typeLabel.style.color = 'white';
            typeLabel.style.borderRadius = '8px 0 0 8px'; // Rounded left, flat right
            typeLabel.style.fontSize = '0.85em';
            typeLabel.style.textAlign = 'center';
            typeLabel.style.verticalAlign = 'top';
            typeLabel.style.fontWeight = '500';
            typeLabel.style.whiteSpace = 'nowrap';
            typeLabel.style.overflow = 'hidden';
            typeLabel.style.textOverflow = 'ellipsis';
            typeLabel.style.height = '100%';
            typeLabel.style.boxSizing = 'border-box';
        }

        return typeLabel;
    }

    static createStartedByName(tuneSet: TuneSet): HTMLElement | null {
        // Calculate the majority startedByPersonId from the tune set
        const counts: Map<number, number> = new Map();
        for (const tune of tuneSet) {
            if (tune.startedByPersonId !== null && tune.startedByPersonId !== undefined) {
                counts.set(tune.startedByPersonId, (counts.get(tune.startedByPersonId) || 0) + 1);
            }
        }

        if (counts.size === 0) {
            return null;
        }

        // Find the majority person ID
        let majorityPersonId: number | null = null;
        let maxCount = 0;
        for (const [personId, count] of counts) {
            if (count > maxCount) {
                maxCount = count;
                majorityPersonId = personId;
            }
        }

        if (majorityPersonId === null) {
            return null;
        }

        // Look up the person's name from the cached attendees
        const sessionInstanceId = (window as any).sessionConfig?.sessionInstanceId;
        if (!sessionInstanceId) {
            return null;
        }

        const cacheKey = `session_attendees_${sessionInstanceId}`;
        const cached = localStorage.getItem(cacheKey);
        if (!cached) {
            return null;
        }

        let personName: string | null = null;
        try {
            const attendees = JSON.parse(cached);
            const person = attendees.find((a: any) => a.person_id === majorityPersonId);
            if (person) {
                personName = person.display_name;
            }
        } catch (e) {
            return null;
        }

        if (!personName) {
            return null;
        }

        // Create the label element
        const isMobile = window.innerWidth <= 768;
        const label = document.createElement('span');
        label.className = 'started-by-name';
        label.textContent = personName;
        label.style.fontStyle = 'italic';
        label.style.opacity = '0.6';
        label.style.whiteSpace = 'nowrap';
        label.style.overflow = 'hidden';
        label.style.textOverflow = 'ellipsis';

        if (isMobile) {
            label.style.fontSize = '0.65em';
            label.style.maxWidth = '150px';
            label.style.lineHeight = '1';
            label.style.position = 'absolute';
            label.style.right = '8px';
            label.style.top = '2px';
            label.style.padding = '2px 4px';
        } else {
            label.style.fontSize = '0.75em';
            label.style.maxWidth = '150px';
            label.style.position = 'absolute';
            label.style.right = '8px';
            label.style.top = '50%';
            label.style.transform = 'translateY(-50%)';
            label.style.padding = '2px 4px';
        }

        return label;
    }

    // Static flag to prevent rapid re-entry during touch/click events
    static isTogglingPopout: boolean = false;

    static toggleSetPopout(typeLabel: HTMLElement, tuneSet: TuneSet): void {
        // Debounce: prevent rapid re-entry (e.g., touchend + click firing together)
        if (PillRenderer.isTogglingPopout) {
            return;
        }
        PillRenderer.isTogglingPopout = true;
        setTimeout(() => { PillRenderer.isTogglingPopout = false; }, 300);

        const isMobile = window.innerWidth <= 768;

        // Find the associated tune-set element
        let tuneSetElement: HTMLElement | null = null;
        let wrapper: HTMLElement | null = null;

        if (isMobile) {
            // On mobile, the label is in the wrapper, tune-set is a sibling
            wrapper = typeLabel.parentElement;
            if (wrapper && wrapper.classList.contains('tune-set-wrapper')) {
                tuneSetElement = wrapper.querySelector('.tune-set') as HTMLElement;
            }
        } else {
            // On desktop, the label is inside the tune-set
            tuneSetElement = typeLabel.closest('.tune-set') as HTMLElement;
        }

        if (!tuneSetElement) {
            console.error('Could not find tune-set element');
            return;
        }

        // Check if popout already exists (both mobile and desktop now use _popout reference)
        const existingPopout = (typeLabel as any)._popout as HTMLElement | null;

        // Close all existing popouts first
        const allPopouts = document.querySelectorAll('.set-popout');
        const allActiveLabels = document.querySelectorAll('.tune-type-label.popout-active');
        allPopouts.forEach(p => p.remove());
        allActiveLabels.forEach(label => {
            (label as HTMLElement).style.backgroundColor = '#4a4a4a';
            label.classList.remove('popout-active');
            // Clear the popout reference
            (label as any)._popout = null;
        });

        // If we clicked on the same label that was open, just close it (already done above)
        if (existingPopout) {
            return;
        }

        // Change the label to blue tint to indicate active state
        typeLabel.style.backgroundColor = '#2a4a6a';
        typeLabel.classList.add('popout-active');

        // Create the popout element
        const popout = document.createElement('div');
        popout.className = 'set-popout';
        // Prevent contentEditable from affecting form elements inside
        popout.contentEditable = 'false';

        // Stop clicks on the popout background from propagating, but allow child elements to work normally
        popout.addEventListener('click', (e) => {
            if (e.target === popout) {
                e.stopPropagation();
            }
        });

        // Get the session instance ID from the page config
        const sessionInstanceId = (window as any).sessionConfig?.sessionInstanceId;

        // Calculate the majority startedByPersonId from the tune set
        const getStartedByMajority = (): number | null => {
            const counts: Map<number, number> = new Map();
            let firstPersonId: number | null = null;

            for (const tune of tuneSet) {
                if (tune.startedByPersonId !== null && tune.startedByPersonId !== undefined) {
                    if (firstPersonId === null) {
                        firstPersonId = tune.startedByPersonId;
                    }
                    counts.set(tune.startedByPersonId, (counts.get(tune.startedByPersonId) || 0) + 1);
                }
            }

            if (counts.size === 0) return null;

            // Find the majority (most frequent)
            let maxCount = 0;
            let maxPersonId: number | null = null;
            for (const [personId, count] of counts) {
                if (count > maxCount) {
                    maxCount = count;
                    maxPersonId = personId;
                }
            }

            // If there's no clear majority (tie), return the first one found
            const maxCountOccurrences = Array.from(counts.values()).filter(c => c === maxCount).length;
            if (maxCountOccurrences > 1) {
                return firstPersonId;
            }

            return maxPersonId;
        };

        const currentStartedBy = getStartedByMajority();

        // Find the set index in the state
        const stateManager = (window as any).StateManager;
        let setIndex = -1;
        if (stateManager) {
            const allSets = stateManager.getTunePillsData();
            for (let i = 0; i < allSets.length; i++) {
                if (allSets[i] === tuneSet || (tuneSet.length > 0 && allSets[i].length > 0 && allSets[i][0]?.id === tuneSet[0]?.id)) {
                    setIndex = i;
                    break;
                }
            }
        }

        // Calculate the logged-by name from the tune set
        const getLoggedByName = (): string | null => {
            // Find the first tune with logged-by info (they should all be the same for a set)
            for (const tune of tuneSet) {
                if (tune.loggedByLastName || tune.loggedByFirstName) {
                    const firstName = tune.loggedByFirstName || '';
                    const lastInitial = tune.loggedByLastName ? tune.loggedByLastName.charAt(0) : '';
                    if (firstName && lastInitial) {
                        return `${firstName} ${lastInitial}`;
                    } else if (firstName) {
                        return firstName;
                    } else if (lastInitial) {
                        return lastInitial;
                    }
                }
            }
            return null;
        };

        const loggedByName = getLoggedByName();

        // Initial loading state
        popout.innerHTML = `
            <div class="set-popout-content">
                <div class="set-popout-row">
                    <label>Started by:</label>
                    <select class="set-started-by" disabled>
                        <option>Loading...</option>
                    </select>
                </div>
                <div class="set-popout-row">
                    <label>Logged by:</label>
                    <span class="set-logged-by">${loggedByName || '—'}</span>
                </div>
            </div>
        `;

        // Fetch attendees and populate the dropdown
        if (sessionInstanceId) {
            const cacheKey = `session_attendees_${sessionInstanceId}`;
            const cached = localStorage.getItem(cacheKey);

            const populateDropdown = (attendees: any[]) => {
                const select = popout.querySelector('.set-started-by') as HTMLSelectElement;
                if (!select) return;

                select.innerHTML = '<option value="">— Select —</option>';
                attendees.forEach((attendee: any) => {
                    const option = document.createElement('option');
                    option.value = attendee.person_id;
                    option.textContent = attendee.display_name;
                    select.appendChild(option);
                });

                // Add "Someone else..." option
                const someoneElseOption = document.createElement('option');
                someoneElseOption.value = '__someone_else__';
                someoneElseOption.textContent = 'Someone else...';
                someoneElseOption.style.fontStyle = 'italic';
                select.appendChild(someoneElseOption);

                // Pre-select the current value if set
                if (currentStartedBy !== null) {
                    select.value = String(currentStartedBy);
                }

                select.disabled = false;

                // Handle selection changes
                select.addEventListener('change', async () => {
                    if (select.value === '__someone_else__') {
                        const sessionPath = (window as any).sessionConfig?.sessionPath;
                        if (sessionPath && sessionInstanceId) {
                            // Try to save first if there are unsaved changes
                            const autoSaveManager = (window as any).AutoSaveManager;
                            if (autoSaveManager && autoSaveManager.hasUnsavedChanges && autoSaveManager.hasUnsavedChanges()) {
                                try {
                                    await autoSaveManager.saveSession();
                                } catch (e) {
                                    console.error('Failed to save before navigating:', e);
                                }
                            }
                            // Store message to show on Players page
                            sessionStorage.setItem('playersPageToast', 'Add the player here to be able to choose them for starting a set.');
                            // Navigate to Players tab
                            window.location.href = `/sessions/${sessionPath}/${sessionInstanceId}/players`;
                        }
                    } else if (setIndex >= 0) {
                        const personId = select.value ? parseInt(select.value, 10) : null;

                        // Update the local state immediately
                        for (const tune of tuneSet) {
                            tune.startedByPersonId = personId;
                        }

                        // Update the started-by name display immediately
                        const newStartedByName = this.createStartedByName(tuneSet);
                        const existingStartedBy = isMobile
                            ? wrapper?.querySelector('.started-by-name')
                            : tuneSetElement?.querySelector('.started-by-name');

                        if (existingStartedBy) {
                            if (newStartedByName) {
                                existingStartedBy.replaceWith(newStartedByName);
                            } else {
                                existingStartedBy.remove();
                            }
                        } else if (newStartedByName) {
                            const parentEl = isMobile ? wrapper : tuneSetElement;
                            const labelEl = parentEl?.querySelector('.tune-type-label');
                            if (labelEl) {
                                labelEl.after(newStartedByName);
                            }
                        }

                        // Close the popout immediately (closePopout is defined later but available in this async handler)
                        closePopout();

                        // Save to API in the background (fire and forget)
                        fetch(`/api/session_instance/${sessionInstanceId}/sets/${setIndex}/started_by`, {
                            method: 'PUT',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ person_id: personId }),
                        })
                        .then(response => response.json())
                        .then(result => {
                            if (!result.success) {
                                console.error('Failed to save started_by:', result.message);
                            }
                        })
                        .catch(e => {
                            console.error('Error saving started_by:', e);
                        });
                    }
                });
            };

            // Use cached data from page load (attendees are populated server-side)
            if (cached) {
                try {
                    const cachedData = JSON.parse(cached);
                    populateDropdown(cachedData);
                } catch (e) {
                    localStorage.removeItem(cacheKey);
                    const select = popout.querySelector('.set-started-by') as HTMLSelectElement;
                    if (select) {
                        select.innerHTML = '<option value="">No players found - refresh page</option>';
                    }
                }
            } else {
                // No cached data - user needs to refresh
                const select = popout.querySelector('.set-started-by') as HTMLSelectElement;
                if (select) {
                    select.innerHTML = '<option value="">No players found - refresh page</option>';
                }
            }
        }

        // Function to update popout position (used for initial positioning and scroll updates)
        const updatePopoutPosition = () => {
            if (isMobile) {
                const tabRect = typeLabel.getBoundingClientRect();
                popout.style.top = `${tabRect.bottom}px`;
                popout.style.left = `${tabRect.left}px`;
                popout.style.width = `calc(100vw - ${tabRect.left + 20}px)`;
            } else {
                const labelRect = typeLabel.getBoundingClientRect();
                const setRect = tuneSetElement.getBoundingClientRect();
                popout.style.top = `${setRect.top}px`;
                popout.style.left = `${labelRect.right - 2}px`;
                popout.style.width = `${setRect.right - labelRect.right + 2}px`;
                popout.style.minHeight = `${setRect.height}px`;
            }
        };

        if (isMobile) {
            // Mobile: Use fixed positioning and append to body to avoid contentEditable issues
            popout.style.cssText = `
                position: fixed;
                max-width: 350px;
                background-color: #2a4a6a;
                color: white;
                border-radius: 0 8px 8px 8px;
                padding: 12px 16px;
                box-sizing: border-box;
                font-size: 14px;
                z-index: 9999;
            `;
        } else {
            // Desktop: Use fixed positioning and append to body to avoid contentEditable issues
            popout.style.cssText = `
                position: fixed;
                background-color: #2a4a6a;
                color: white;
                border-radius: 0 8px 8px 0;
                padding: 12px 16px;
                box-sizing: border-box;
                font-size: 14px;
                z-index: 9999;
                box-shadow: 4px 4px 12px rgba(0, 0, 0, 0.3);
            `;
        }

        // Set initial position
        updatePopoutPosition();

        // Append to body to escape contentEditable container
        document.body.appendChild(popout);

        // Store reference to popout on the label for cleanup
        (typeLabel as any)._popout = popout;

        // Set global flag to prevent container from stealing focus
        (window as any).popoutActive = true;

        // Temporarily make the container non-focusable to prevent it from stealing focus
        const container = document.getElementById('tune-pills-container');
        const originalTabIndex = container?.getAttribute('tabindex');
        const originalContentEditable = container?.contentEditable;

        if (container) {
            // Disable the container completely while popout is open
            container.style.pointerEvents = 'none';
            container.removeAttribute('tabindex');
            container.setAttribute('contenteditable', 'false');
            container.blur();

            // Override contentEditable setter to block external code from re-enabling it while popout is open
            Object.defineProperty(container, 'contentEditable', {
                get: function() {
                    return this.getAttribute('contenteditable') || 'inherit';
                },
                set: function(value) {
                    // Block attempts to set contenteditable to true while popout is active
                    if ((window as any).popoutActive && value === 'true') {
                        return;
                    }
                    this.setAttribute('contenteditable', value);
                },
                configurable: true
            });
        }

        // Function to clean up all event listeners and close the popout
        const closePopout = () => {
            popout.remove();
            typeLabel.style.backgroundColor = '#4a4a4a';
            typeLabel.classList.remove('popout-active');
            (typeLabel as any)._popout = null;
            (window as any).popoutActive = false;  // Clear the flag
            // Restore container focusability
            if (container) {
                // Remove the setter override
                delete (container as any).contentEditable;
                container.style.pointerEvents = '';
                if (originalTabIndex) {
                    container.setAttribute('tabindex', originalTabIndex);
                }
                container.setAttribute('contenteditable', originalContentEditable || 'true');
            }
            document.removeEventListener('click', closeOnClickOutside, true);
            window.removeEventListener('scroll', onScroll, true);
        };

        // Add click-outside handler to close the popout
        const closeOnClickOutside = (e: MouseEvent) => {
            const target = e.target as HTMLElement;
            // Don't close if clicking inside the popout or on the type label
            if (popout.contains(target) || typeLabel.contains(target)) {
                return;
            }
            closePopout();
        };

        // Add scroll handler to update popout position
        const onScroll = () => {
            updatePopoutPosition();
        };

        // Use capture phase to catch clicks before they're stopped by other handlers
        // Use setTimeout to avoid catching the current click/touch that opened the popout
        // Longer delay (100ms) to ensure all touch-related events have finished
        setTimeout(() => {
            document.addEventListener('click', closeOnClickOutside, true);
        }, 100);

        // Listen for scroll events on window (capture phase to catch all scroll events)
        window.addEventListener('scroll', onScroll, true);
    }

    static createTuneSetElement(tuneSet: TuneSet, setIndex: number): HTMLElement {
        const isViewMode = (window as any).editorMode === 'view';
        const isMobile = window.innerWidth <= 768;

        // Create a wrapper for mobile that includes the label outside the set
        const wrapper = document.createElement('div');
        wrapper.className = isMobile ? 'tune-set-wrapper' : '';
        if (isMobile) {
            wrapper.style.position = 'relative';
        }

        const setDiv = document.createElement('div');
        setDiv.className = 'tune-set';
        setDiv.dataset.setIndex = setIndex.toString();
        if (!isMobile) {
            setDiv.style.position = 'relative';
        }

        // Handle empty sets (especially temporary ones)
        if (tuneSet.length === 0) {
            // Add cursor position for empty set - only in edit mode
            if (!isViewMode) {
                this.addCursorPosition(setDiv, setIndex, 0, 'before');
            }

            // Add some minimal height so the empty set is visible
            setDiv.style.minHeight = '25px';

            if (isMobile) {
                wrapper.appendChild(setDiv);
                return wrapper;
            }
            return setDiv;
        }

        // Add type label
        const typeLabel = this.createTypeLabel(tuneSet);

        // Add started-by name (if available)
        const startedByName = this.createStartedByName(tuneSet);

        if (isMobile) {
            // On mobile, add label to wrapper (outside the set)
            wrapper.appendChild(typeLabel);
            if (startedByName) {
                wrapper.appendChild(startedByName);
            }
            wrapper.appendChild(setDiv);
        } else {
            // On desktop, add label inside the set
            setDiv.appendChild(typeLabel);
            if (startedByName) {
                setDiv.appendChild(startedByName);
            }
        }

        tuneSet.forEach((pill, pillIndex) => {
            // Add cursor position before the first pill only - only in edit mode
            if (pillIndex === 0 && !isViewMode) {
                this.addCursorPosition(setDiv, setIndex, pillIndex, 'before');
            }

            const pillElement = this.createPillElement(pill, setIndex, pillIndex);
            setDiv.appendChild(pillElement);

            // Add cursor position after each pill (this becomes the "before" position for the next pill) - only in edit mode
            if (!isViewMode) {
                this.addCursorPosition(setDiv, setIndex, pillIndex, 'after');
            }

            // Add spacing between pills
            if (pillIndex < tuneSet.length - 1) {
                const spacer = document.createElement('span');
                spacer.textContent = ' ';
                setDiv.appendChild(spacer);
            }
        });

        // After initial render, check for line wrapping and improve cursor positioning - only in edit mode
        if (!isViewMode) {
            setTimeout(() => {
                this.enhanceWrappedCursorVisibility(setDiv, setIndex);
            }, 10);
        }

        // Return wrapper on mobile, setDiv on desktop
        if (isMobile) {
            return wrapper;
        }
        return setDiv;
    }
    
    static enhanceWrappedCursorVisibility(setDiv: HTMLElement, setIndex: number): void {
        // Find all tune pills in this set
        const pills = Array.from(setDiv.querySelectorAll('.tune-pill')) as HTMLElement[];
        
        if (pills.length <= 1) {
            return; // No wrapping possible with 0 or 1 pills
        }
        
        // Remove any existing wrap cursors first
        setDiv.querySelectorAll('.cursor-position.wrap-cursor').forEach(cursor => cursor.remove());
        
        // Group pills by their top position (same line)
        const lines: HTMLElement[][] = [];
        let currentLine: HTMLElement[] = [];
        let currentTop: number | null = null;
        
        pills.forEach((pill, index) => {
            const rect = pill.getBoundingClientRect();
            const top = Math.round(rect.top);
            
            if (currentTop === null) {
                currentTop = top;
                currentLine.push(pill);
            } else if (Math.abs(top - currentTop) < 5) { // Same line (within 5px tolerance)
                currentLine.push(pill);
            } else {
                // New line detected
                if (currentLine.length > 0) {
                    lines.push(currentLine);
                }
                currentLine = [pill];
                currentTop = top;
            }
        });
        
        if (currentLine.length > 0) {
            lines.push(currentLine);
        }
        
        // If we have multiple lines, enhance cursor visibility for drop zones
        if (lines.length > 1) {
            // Mark all cursor positions in wrapped content for better visibility
            setDiv.querySelectorAll('.cursor-position').forEach(cursor => {
                // Enhanced visibility for wrapped content cursors
                (cursor as HTMLElement).style.backgroundColor = 'rgba(0, 123, 255, 0.05)';
                (cursor as HTMLElement).style.minWidth = '6px'; // Make them slightly wider for easier targeting
            });
        }
    }
    
    static createWrapCursorPosition(setIndex: number, pillIndex: number, wrapType: string): HTMLElement {
        const cursorPos = document.createElement('span');
        cursorPos.className = 'cursor-position wrap-cursor';
        cursorPos.dataset.setIndex = setIndex.toString();
        cursorPos.dataset.pillIndex = pillIndex.toString();
        
        // Set the correct position type based on wrap type
        if (wrapType === 'line-start') {
            cursorPos.dataset.positionType = 'before';
        } else if (wrapType === 'after-pill') {
            cursorPos.dataset.positionType = 'after';
        } else {
            cursorPos.dataset.positionType = 'after'; // default
        }
        
        cursorPos.dataset.wrapType = wrapType;
        
        cursorPos.addEventListener('click', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Clear selection when clicking to move cursor
            if (this.clearSelection) {
                this.clearSelection();
            }
            
            if (this.setCursorPosition) {
                this.setCursorPosition(setIndex, pillIndex, cursorPos.dataset.positionType!);
            }
        });
        
        return cursorPos;
    }
    
    static createPillElement(pill: TunePill, setIndex: number, pillIndex: number): HTMLElement {
        const isViewMode = (window as any).editorMode === 'view';
        const pillDiv = document.createElement('div');
        pillDiv.className = `tune-pill ${pill.state}`;
        pillDiv.dataset.pillId = pill.id;
        pillDiv.dataset.setIndex = setIndex.toString();
        pillDiv.dataset.pillIndex = pillIndex.toString();
        // Make pills draggable only in edit mode
        pillDiv.draggable = !isViewMode;

        // Add chevron
        const chevron = document.createElement('div');
        chevron.className = 'chevron';
        pillDiv.appendChild(chevron);

        // Add text
        const text = document.createElement('span');
        text.className = 'text';
        text.textContent = pill.tuneName;
        pillDiv.appendChild(text);

        // Add loading spinner if pill is in loading state
        if (pill.state === 'loading') {
            const spinner = document.createElement('span');
            spinner.className = 'loading-spinner';
            pillDiv.appendChild(spinner);
        }

        // Add event listeners only in edit mode
        if (this.setupPillEventListeners && !isViewMode) {
            this.setupPillEventListeners(pillDiv, pill);
        }

        return pillDiv;
    }
    
    static addCursorPosition(parent: HTMLElement, setIndex: number, pillIndex: number, positionType: string): HTMLElement {
        const cursorManager = this.getCursorManager!();
        if (cursorManager && cursorManager.addCursorPosition) {
            return cursorManager.addCursorPosition(parent, setIndex, pillIndex, positionType);
        }
        
        // Fallback implementation if CursorManager not available
        const cursorPos = document.createElement('span');
        cursorPos.className = 'cursor-position';
        cursorPos.dataset.setIndex = setIndex.toString();
        cursorPos.dataset.pillIndex = pillIndex.toString();
        cursorPos.dataset.positionType = positionType;
        
        cursorPos.addEventListener('click', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Clear selection and selection anchor when clicking to move cursor
            if (this.clearSelection) {
                this.clearSelection();
            }
            
            if (this.setCursorPosition) {
                this.setCursorPosition(setIndex, pillIndex, positionType);
            }
        });
        
        parent.appendChild(cursorPos);
        return cursorPos;
    }
    
    static addFinalCursor(containerElement: HTMLElement): HTMLElement {
        const cursorManager = this.getCursorManager!();
        if (cursorManager && cursorManager.addFinalCursor) {
            return cursorManager.addFinalCursor(containerElement);
        }
        
        // Fallback implementation if CursorManager not available
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        const finalPos = document.createElement('span');
        finalPos.className = 'cursor-position';
        finalPos.dataset.setIndex = tunePillsData.length.toString();
        finalPos.dataset.pillIndex = '0';
        finalPos.dataset.positionType = 'newset';
        
        finalPos.addEventListener('click', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Clear selection and selection anchor when clicking to move cursor
            if (this.clearSelection) {
                this.clearSelection();
            }
            
            if (this.setCursorPosition) {
                this.setCursorPosition(tunePillsData.length, 0, 'newset');
            }
        });
        
        containerElement.appendChild(finalPos);
        return finalPos;
    }
    
    static getContainerElement(): HTMLElement | null {
        return this.containerElement || document.getElementById('tune-pills-container');
    }
    
    static setContainerElement(element: HTMLElement): void {
        this.containerElement = element;
    }
    
    // Helper method to register external functions that PillRenderer needs to call
    static registerCallbacks(callbacks: PillRendererCallbacks = {}): void {
        this.cleanupDragGhosts = callbacks.cleanupDragGhosts || null;
        this.createHorizontalDropZone = callbacks.createHorizontalDropZone || null;
        this.setupPillEventListeners = callbacks.setupPillEventListeners || null;
        this.setCursorPosition = callbacks.setCursorPosition || null;
        this.clearSelection = callbacks.clearSelection || null;
    }
    
    // Update the appearance of a single pill without re-rendering everything
    static updatePillAppearance(pill: TunePill): void {
        const pillElement = document.querySelector(`[data-pill-id="${pill.id}"]`) as HTMLElement;
        if (!pillElement) {
            // If the pill element is not found, it might be a typing pill that hasn't been rendered yet
            // or has been removed during typing. This is not necessarily an error.
            if (pill.id.startsWith('typing-')) {
            } else {
                console.error(`Could not find pill element with ID: ${pill.id}`);
            }
            return;
        }

        // Update the CSS class to reflect the new state
        pillElement.className = `tune-pill ${pill.state}`;

        // Update the text content in case it changed (e.g., canonical name from API)
        const textElement = pillElement.querySelector('.text') as HTMLElement;
        if (textElement) {
            textElement.textContent = pill.tuneName;
        } else {
            console.error('Could not find .text element within pill');
        }

        // Remove any existing spinner
        const existingSpinner = pillElement.querySelector('.loading-spinner');
        if (existingSpinner) {
            existingSpinner.remove();
        }

        // Add spinner if still loading
        if (pill.state === 'loading') {
            const spinner = document.createElement('span');
            spinner.className = 'loading-spinner';
            pillElement.appendChild(spinner);
        }

        // Update the type label for the set this pill belongs to
        this.updateSetTypeLabel(pillElement);
    }

    // Update the type label for a set
    static updateSetTypeLabel(pillElement: HTMLElement): void {
        const setElement = pillElement.closest('.tune-set') as HTMLElement;
        if (!setElement) {
            return;
        }

        const setIndex = parseInt(setElement.dataset.setIndex || '0', 10);
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();

        if (setIndex < 0 || setIndex >= tunePillsData.length) {
            return;
        }

        const tuneSet = tunePillsData[setIndex]!;

        // On mobile, the label is in a wrapper outside the set; on desktop it's inside
        const isMobile = window.innerWidth <= 768;
        let existingLabel: HTMLElement | null = null;

        if (isMobile) {
            // Look for label in the wrapper (parent of set element)
            const wrapper = setElement.parentElement;
            if (wrapper && wrapper.classList.contains('tune-set-wrapper')) {
                existingLabel = wrapper.querySelector('.tune-type-label') as HTMLElement;
            }
        } else {
            // Look for label inside the set element
            existingLabel = setElement.querySelector('.tune-type-label') as HTMLElement;
        }

        if (existingLabel) {
            const newLabel = this.createTypeLabel(tuneSet);
            existingLabel.replaceWith(newLabel);
        }

        // Also update the started-by name
        let existingStartedBy: HTMLElement | null = null;
        let parentForStartedBy: HTMLElement | null = null;

        if (isMobile) {
            const wrapper = setElement.parentElement;
            if (wrapper && wrapper.classList.contains('tune-set-wrapper')) {
                existingStartedBy = wrapper.querySelector('.started-by-name') as HTMLElement;
                parentForStartedBy = wrapper;
            }
        } else {
            existingStartedBy = setElement.querySelector('.started-by-name') as HTMLElement;
            parentForStartedBy = setElement;
        }

        const newStartedByName = this.createStartedByName(tuneSet);

        if (existingStartedBy) {
            if (newStartedByName) {
                existingStartedBy.replaceWith(newStartedByName);
            } else {
                existingStartedBy.remove();
            }
        } else if (newStartedByName && parentForStartedBy) {
            // Insert after the type label
            const typeLabel = parentForStartedBy.querySelector('.tune-type-label');
            if (typeLabel && typeLabel.nextSibling) {
                parentForStartedBy.insertBefore(newStartedByName, typeLabel.nextSibling);
            } else if (typeLabel) {
                typeLabel.after(newStartedByName);
            }
        }
    }

    // Apply landing animation to pills that have been moved
    static applyLandingAnimation(pillIds: string[]): void {
        pillIds.forEach(pillId => {
            const pillElement = document.querySelector(`[data-pill-id="${pillId}"]`) as HTMLElement;
            if (pillElement) {
                pillElement.classList.add('just-landed');
                setTimeout(() => {
                    pillElement.classList.remove('just-landed');
                }, 3000);
            }
        });
    }
}

// Export for use in other modules or global scope
declare global {
    interface Window {
        PillRenderer: typeof PillRenderer;
    }
}

(window as any).PillRenderer = PillRenderer;