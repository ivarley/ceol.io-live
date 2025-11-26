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
        typeLabel.style.cursor = 'pointer';
        typeLabel.dataset.clickable = 'true'; // Debug marker
        typeLabel.addEventListener('click', (e: MouseEvent) => {
            console.log('Type label clicked!', typeLabel.textContent);
            e.preventDefault();
            e.stopPropagation();
            this.toggleSetPopout(typeLabel, tuneSet);
        });
        // Also add touch event for mobile
        typeLabel.addEventListener('touchend', (e: TouchEvent) => {
            console.log('Type label touched!', typeLabel.textContent);
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

    static toggleSetPopout(typeLabel: HTMLElement, tuneSet: TuneSet): void {
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

        // Check if popout already exists
        const existingPopout = isMobile
            ? wrapper?.querySelector('.set-popout')
            : tuneSetElement.querySelector('.set-popout');

        // Close all existing popouts first
        const allPopouts = document.querySelectorAll('.set-popout');
        const allActiveLabels = document.querySelectorAll('.tune-type-label.popout-active');
        allPopouts.forEach(p => p.remove());
        allActiveLabels.forEach(label => {
            (label as HTMLElement).style.backgroundColor = '#4a4a4a';
            label.classList.remove('popout-active');
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

        // Sample content for prototype
        popout.innerHTML = `
            <div class="set-popout-content">
                <p><strong>Set Options</strong></p>
                <p>This is a prototype popout for the "${typeLabel.textContent}" set.</p>
                <p>Number of tunes: ${tuneSet.length}</p>
                <p>Future features could include:</p>
                <ul>
                    <li>Add tune to this set</li>
                    <li>Delete entire set</li>
                    <li>Reorder tunes</li>
                    <li>Set metadata</li>
                </ul>
            </div>
        `;

        if (isMobile) {
            // Mobile: Absolute positioned panel that appears as extension of the tab
            // Get the tab's position to align the popout
            const tabRect = typeLabel.getBoundingClientRect();
            const wrapperRect = wrapper!.getBoundingClientRect();

            popout.style.cssText = `
                position: absolute;
                top: ${tabRect.bottom - wrapperRect.top}px;
                left: 6px;
                width: 92%;
                background-color: #2a4a6a;
                color: white;
                border-radius: 0 8px 8px 8px;
                padding: 12px 16px;
                box-sizing: border-box;
                font-size: 14px;
            `;

            // Insert into the wrapper
            if (wrapper) {
                wrapper.appendChild(popout);
            }
        } else {
            // Desktop: Absolute positioned panel that hovers over the tune-set
            // Slight overlap (-2px) so label covers the seam (label has higher z-index)
            const labelRect = typeLabel.getBoundingClientRect();
            const setRect = tuneSetElement.getBoundingClientRect();
            const leftOffset = labelRect.right - setRect.left - 2;

            popout.style.cssText = `
                position: absolute;
                top: 0;
                left: ${leftOffset}px;
                right: 0;
                background-color: #2a4a6a;
                color: white;
                border-radius: 0 8px 8px 0;
                padding: 12px 16px;
                box-sizing: border-box;
                font-size: 14px;
                min-height: 100%;
            `;

            // Make the tune-set position relative for absolute positioning
            tuneSetElement.style.position = 'relative';

            // Append the popout to the tune-set
            tuneSetElement.appendChild(popout);
        }
    }

    static createTuneSetElement(tuneSet: TuneSet, setIndex: number): HTMLElement {
        const isViewMode = (window as any).editorMode === 'view';
        const isMobile = window.innerWidth <= 768;

        // Create a wrapper for mobile that includes the label outside the set
        const wrapper = document.createElement('div');
        wrapper.className = isMobile ? 'tune-set-wrapper' : '';

        const setDiv = document.createElement('div');
        setDiv.className = 'tune-set';
        setDiv.dataset.setIndex = setIndex.toString();

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

        if (isMobile) {
            // On mobile, add label to wrapper (outside the set)
            wrapper.appendChild(typeLabel);
            wrapper.appendChild(setDiv);
        } else {
            // On desktop, add label inside the set
            setDiv.appendChild(typeLabel);
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