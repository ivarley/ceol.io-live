/**
 * DragDrop Module for Session Instance Detail Beta
 * Handles drag and drop functionality including desktop drag/drop, 
 * drop zones, drop indicators, and position detection
 * Note: General pill interactions (clicks, selection) are handled by PillInteraction module
 */

import { TunePill, TuneSet, TunePillsData } from './stateManager.js';

export interface DragState {
    draggedPillId: string;
    startX: number;
    startY: number;
    isMobile?: boolean;
}

export interface DropPosition {
    setIndex: number;
    pillIndex: number;
    position: 'before' | 'after' | 'newset';
}

export interface DragDropCallbacks {
    performDrop?(position: DropPosition, draggedIds: string[]): void;
    dropStructuredSetsAtNewPosition?(dragData: TuneSet[], insertAtSetIndex: number): void;
    pasteAtPosition?(dragData: TuneSet[], position: DropPosition): void;
    saveToUndo?(): void;
    showContextMenu?(event: MouseEvent, pillData: TunePill): void;
    hideContextMenu?(): void;
    applyLandingAnimation?(pillIds: string[]): void;
    setCursorPosition?(setIndex: number, pillIndex: number, position: string): void;
    clearSelection?(): void;
}

export interface DragDropDependencies {
    getPillSelection(): PillSelection;
    getStateManager(): StateManager;
    getCursorManager(): CursorManager;
    getPillInteraction(): PillInteraction;
}

export interface PillSelection {
    getSelectedPills(): Set<string>;
    isSelected(pillId: string): boolean;
    selectSingle(pillId: string): void;
}

export interface StateManager {
    getTunePillsData(): TunePillsData;
}

export interface CursorManager {
    getCursorPosition(): CursorPosition | null;
}

export interface CursorPosition {
    setIndex: number;
    pillIndex: number;
    position: string;
}

export interface PillInteraction {
    setupPillEventListeners(pillElement: HTMLElement, pillData: TunePill): void;
}

export class DragDrop {
    static dragState: DragState | null = null;
    static globalDragGhost: HTMLElement | null = null;
    static lastDropZone: HTMLElement | null = null;
    static lastDropZoneUpdate: number = 0;
    
    // External dependencies that need to be registered
    static getPillSelection: (() => PillSelection) | null = null;
    static getStateManager: (() => StateManager) | null = null;
    static getCursorManager: (() => CursorManager) | null = null;
    static getPillInteraction: (() => PillInteraction) | null = null;
    static performDrop: ((position: DropPosition, draggedIds: string[]) => void) | null = null;
    static dropStructuredSetsAtNewPosition: ((dragData: TuneSet[], insertAtSetIndex: number) => void) | null = null;
    static pasteAtPosition: ((dragData: TuneSet[], position: DropPosition) => void) | null = null;
    static saveToUndo: (() => void) | null = null;
    static showContextMenu: ((event: MouseEvent, pillData: TunePill) => void) | null = null;
    static hideContextMenu: (() => void) | null = null;
    static applyLandingAnimation: ((pillIds: string[]) => void) | null = null;
    static setCursorPosition: ((setIndex: number, pillIndex: number, position: string) => void) | null = null;
    static clearSelection: (() => void) | null = null;
    
    static initialize(options: Partial<DragDropDependencies> = {}): void {
        this.getPillSelection = options.getPillSelection || (() => (window as any).PillSelection);
        this.getStateManager = options.getStateManager || (() => (window as any).StateManager);
        this.getCursorManager = options.getCursorManager || (() => (window as any).CursorManager);
        this.getPillInteraction = options.getPillInteraction || (() => (window as any).PillInteraction);
        this.performDrop = (window as any).performDrop;
        this.dropStructuredSetsAtNewPosition = (window as any).dropStructuredSetsAtNewPosition;
        this.pasteAtPosition = (window as any).pasteAtPosition;
        this.saveToUndo = (window as any).saveToUndo;
        this.showContextMenu = (window as any).showContextMenu;
        this.hideContextMenu = (window as any).hideContextMenu;
        this.applyLandingAnimation = (window as any).applyLandingAnimation;
        this.setCursorPosition = (window as any).setCursorPosition;
        this.clearSelection = (window as any).clearSelection;
    }
    
    static registerCallbacks(callbacks: DragDropCallbacks): void {
        Object.assign(this, callbacks);
    }
    
    // Clean up any existing drag ghosts
    static cleanupDragGhosts(): void {
        // Remove the global ghost if it exists
        if (this.globalDragGhost) {
            this.globalDragGhost.remove();
            this.globalDragGhost = null;
        }
        // Also remove any orphaned ghosts by class name
        document.querySelectorAll('.mobile-drag-ghost').forEach(ghost => ghost.remove());
    }
    
    // Create drop indicator element
    static createDropIndicator(): HTMLElement {
        const indicator = document.createElement('div');
        indicator.className = 'drop-indicator';
        return indicator;
    }
    
    // Create horizontal drop zone between sets
    static createHorizontalDropZone(insertAtSetIndex: number): HTMLElement {
        const dropZone = document.createElement('div');
        dropZone.className = 'horizontal-drop-zone';
        dropZone.dataset.insertAtSetIndex = insertAtSetIndex.toString();
        
        // Click handler - position cursor for typing new set
        dropZone.addEventListener('click', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Clear selection and selection anchor when clicking to move cursor
            this.clearSelection?.();
            
            this.setCursorPosition?.(insertAtSetIndex, 0, 'newset');
        });
        
        // Drag and drop handlers
        dropZone.addEventListener('dragover', (e: DragEvent) => {
            e.preventDefault();
            e.dataTransfer!.dropEffect = 'move';
            dropZone.classList.add('drag-over');
        });
        
        dropZone.addEventListener('dragleave', (e: DragEvent) => {
            dropZone.classList.remove('drag-over');
        });
        
        dropZone.addEventListener('drop', (e: DragEvent) => {
            e.preventDefault();
            e.stopPropagation(); // IMPORTANT: Stop the event from bubbling to the container
            dropZone.classList.remove('drag-over');
            
            if (this.dragState) {
                // Internal drag and drop - use drag data to preserve set structure
                try {
                    const dragData = JSON.parse(e.dataTransfer!.getData('text/json'));
                    if (dragData && Array.isArray(dragData)) {
                        // Use the existing performDrop logic but with the structured data
                        this.dropStructuredSetsAtNewPosition?.(dragData, insertAtSetIndex);
                    } else {
                        // Fallback to old method if drag data is invalid
                        const pillSelection = this.getPillSelection!();
                        const draggedIds = Array.from(pillSelection.getSelectedPills());
                        const position: DropPosition = { setIndex: insertAtSetIndex, pillIndex: 0, position: 'newset' };
                        this.performDrop?.(position, draggedIds);
                    }
                } catch (err) {
                    // Fallback to old method if drag data parsing fails
                    const pillSelection = this.getPillSelection!();
                    const draggedIds = Array.from(pillSelection.getSelectedPills());
                    const position: DropPosition = { setIndex: insertAtSetIndex, pillIndex: 0, position: 'newset' };
                    this.performDrop?.(position, draggedIds);
                }
            } else {
                // External drag or paste
                try {
                    const dragData = JSON.parse(e.dataTransfer!.getData('text/json'));
                    if (dragData && Array.isArray(dragData)) {
                        const position: DropPosition = { setIndex: insertAtSetIndex, pillIndex: 0, position: 'newset' };
                        this.pasteAtPosition?.(dragData, position);
                    }
                } catch (err) {
                    // Ignore external drop if can't parse
                }
            }
        });
        
        return dropZone;
    }
    
    // Find drop position based on mouse coordinates
    static findDropPosition(x: number, y: number): DropPosition {
        const containerElement = document.getElementById('tune-pills-container')!;
        
        // First check for horizontal drop zones
        const horizontalZones = containerElement.querySelectorAll('.horizontal-drop-zone');
        for (let i = 0; i < horizontalZones.length; i++) {
            const zoneElement = horizontalZones[i] as HTMLElement;
            const zoneRect = zoneElement.getBoundingClientRect();
            
            if (y >= zoneRect.top && y <= zoneRect.bottom) {
                const insertAtSetIndex = parseInt(zoneElement.dataset.insertAtSetIndex!);
                return { setIndex: insertAtSetIndex, pillIndex: 0, position: 'newset' };
            }
        }
        
        // Enhanced logic: Check all cursor positions directly for better wrapping support
        const allCursorPositions = containerElement.querySelectorAll('.cursor-position');
        let closestCursor: HTMLElement | null = null;
        let closestDistance = Infinity;
        
        allCursorPositions.forEach(cursor => {
            const htmlCursor = cursor as HTMLElement;
            const cursorRect = htmlCursor.getBoundingClientRect();
            const cursorCenterX = cursorRect.left + cursorRect.width / 2;
            const cursorCenterY = cursorRect.top + cursorRect.height / 2;
            
            // Calculate distance from mouse to cursor center
            const distance = Math.sqrt(Math.pow(x - cursorCenterX, 2) + Math.pow(y - cursorCenterY, 2));
            
            // Only consider cursors that are reasonably close (within 40px)
            if (distance < 40 && distance < closestDistance) {
                closestDistance = distance;
                closestCursor = htmlCursor;
            }
        });
        
        if (closestCursor) {
            const setIndex = parseInt(closestCursor.dataset.setIndex!);
            const pillIndex = parseInt(closestCursor.dataset.pillIndex!);
            const positionType = closestCursor.dataset.positionType!;
            
            return { 
                setIndex, 
                pillIndex: positionType === 'after' ? pillIndex + 1 : pillIndex, 
                position: positionType === 'after' ? 'before' : positionType as 'before' | 'after' | 'newset'
            };
        }
        
        // Fallback to original pill-based logic
        const sets = containerElement.querySelectorAll('.tune-set');
        
        for (let setIndex = 0; setIndex < sets.length; setIndex++) {
            const setElement = sets[setIndex] as HTMLElement;
            const setRect = setElement.getBoundingClientRect();
            
            if (y >= setRect.top && y <= setRect.bottom) {
                const pills = setElement.querySelectorAll('.tune-pill');
                
                for (let pillIndex = 0; pillIndex < pills.length; pillIndex++) {
                    const pillElement = pills[pillIndex] as HTMLElement;
                    const pillRect = pillElement.getBoundingClientRect();
                    
                    if (x < pillRect.left + pillRect.width / 2) {
                        return { setIndex, pillIndex, position: 'before' };
                    }
                }
                
                // After last pill in this set
                return { setIndex, pillIndex: pills.length, position: 'after' };
            }
        }
        
        // After last set
        return { setIndex: sets.length, pillIndex: 0, position: 'newset' };
    }
    
    // Legacy wrapper - delegates to PillInteraction module
    static setupPillEventListeners(pillElement: HTMLElement, pillData: TunePill): void {
        const pillInteraction = this.getPillInteraction?.();
        if (pillInteraction) {
            return pillInteraction.setupPillEventListeners(pillElement, pillData);
        }
        // Fallback - just register drag handlers if PillInteraction not available
        this.registerPillDragHandlers(pillElement, pillData);
    }
    
    // Register only drag-specific event handlers for a pill element
    static registerPillDragHandlers(pillElement: HTMLElement, pillData: TunePill): void {
        const pillSelection = this.getPillSelection!();
        
        // Desktop drag and drop
        pillElement.addEventListener('dragstart', (e: DragEvent) => {
            // Hide any open context menu when starting drag
            if ((window as any).ContextMenu) {
                (window as any).ContextMenu.hideContextMenu();
            }
            
            this.dragState = {
                draggedPillId: pillData.id,
                startX: e.clientX,
                startY: e.clientY
            };
            
            // If the pill being dragged isn't selected, select it first
            if (!pillSelection.isSelected(pillData.id)) {
                pillSelection.selectSingle(pillData.id);
            }
            
            // Visual feedback - apply dragging class to all selected pills
            pillSelection.getSelectedPills().forEach(pillId => {
                const pill = document.querySelector(`[data-pill-id="${pillId}"]`) as HTMLElement;
                if (pill) {
                    pill.classList.add('dragging');
                }
            });
            
            // Set drag data (for clipboard compatibility) - preserve set structure
            const stateManager = this.getStateManager!();
            const tunePillsData = stateManager.getTunePillsData();
            const selectedBySet = new Map<number, TunePill[]>();
            
            tunePillsData.forEach((tuneSet, setIndex) => {
                tuneSet.forEach((pill, pillIndex) => {
                    if (pillSelection.isSelected(pill.id)) {
                        if (!selectedBySet.has(setIndex)) {
                            selectedBySet.set(setIndex, []);
                        }
                        selectedBySet.get(setIndex)!.push(JSON.parse(JSON.stringify(pill)));
                    }
                });
            });
            
            // Convert to array of sets, preserving set breaks
            const dragData = Array.from(selectedBySet.values()).filter(set => set && set.length > 0);
            
            e.dataTransfer!.setData('text/json', JSON.stringify(dragData));
            e.dataTransfer!.effectAllowed = 'move';
        });
        
        pillElement.addEventListener('dragend', (e: DragEvent) => {
            // Remove dragging class from all pills that might have it
            document.querySelectorAll('.tune-pill.dragging').forEach(pill => {
                pill.classList.remove('dragging');
            });
            this.clearDropIndicators();
            this.dragState = null;
        });
    }
    
    // Mobile drag support methods
    static startMobileDrag(e: TouchEvent, pillData: TunePill): void {
        // Hide any open context menu when starting mobile drag
        if ((window as any).ContextMenu) {
            (window as any).ContextMenu.hideContextMenu();
        }
        
        const touch = e.touches[0]!;
        this.dragState = {
            draggedPillId: pillData.id,
            startX: touch.clientX,
            startY: touch.clientY,
            isMobile: true
        };
    }
    
    static handleMobileDragMove(e: TouchEvent): void {
        if (!this.dragState || !this.dragState.isMobile) return;
        
        const touch = e.touches[0]!;
        const pillSelection = this.getPillSelection!();
        
        // Clean up any existing ghosts first
        this.cleanupDragGhosts();
        
        // Create new drag ghost
        if (!this.globalDragGhost) {
            this.globalDragGhost = document.createElement('div');
            this.globalDragGhost.className = 'mobile-drag-ghost';
            this.globalDragGhost.style.cssText = `
                position: fixed;
                pointer-events: none;
                z-index: 10000;
                background: #007AFF;
                color: white;
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 12px;
                transform: rotate(2deg);
                opacity: 0.8;
            `;
            const pillData = this.findPillById(this.dragState.draggedPillId);
            this.globalDragGhost.textContent = pillSelection.getSelectionCount() > 1 ? 
                `${pillSelection.getSelectionCount()} pills` : 
                (pillData ? pillData.tuneName : 'Pill');
            document.body.appendChild(this.globalDragGhost);
        }
        
        // Update ghost position smoothly
        this.globalDragGhost.style.left = (touch.clientX - 30) + 'px';
        this.globalDragGhost.style.top = (touch.clientY - 15) + 'px';
        
        // Update drop zone highlighting
        this.updateMobileDropZone(touch.clientX, touch.clientY);
    }
    
    static updateMobileDropZone(x: number, y: number): void {
        const now = Date.now();
        const DROP_ZONE_UPDATE_THROTTLE = 50;
        
        if (now - this.lastDropZoneUpdate < DROP_ZONE_UPDATE_THROTTLE) {
            return;
        }
        
        this.lastDropZoneUpdate = now;
        
        // Get element below finger
        const elementBelow = document.elementFromPoint(x, y);
        if (!elementBelow) return;
        
        // Find potential drop zone
        let currentDropZone: HTMLElement | null = null;
        let dropSide: string | null = null;
        
        // Check for horizontal drop zone first
        currentDropZone = elementBelow.closest('.horizontal-drop-zone') as HTMLElement;
        
        // If not, check for pill (but not if it's being dragged)
        if (!currentDropZone) {
            const pill = elementBelow.closest('.tune-pill') as HTMLElement;
            if (pill && !pill.classList.contains('dragging')) {
                currentDropZone = pill;
                
                // Determine if we're over the right half (drop after) or left half (drop before)
                const pillRect = pill.getBoundingClientRect();
                const pillCenterX = pillRect.left + pillRect.width / 2;
                dropSide = x > pillCenterX ? 'right' : 'left';
            }
        }
        
        // If not over a pill or horizontal zone, check for tune-set
        if (!currentDropZone) {
            const tuneSet = elementBelow.closest('.tune-set') as HTMLElement;
            if (tuneSet) {
                currentDropZone = tuneSet;
                dropSide = 'set';
            }
        }
        
        // If not over anything specific, check container
        if (!currentDropZone) {
            currentDropZone = elementBelow.closest('#tune-pills-container') as HTMLElement;
            if (currentDropZone) {
                dropSide = 'container';
            }
        }
        
        // Update drop zone highlighting
        if (this.lastDropZone !== currentDropZone) {
            // Remove classes from previous target
            if (this.lastDropZone) {
                this.lastDropZone.classList.remove('mobile-drop-target', 'drop-before', 'drop-after', 'drop-at-end');
            }
            
            // Add classes to new target
            if (currentDropZone) {
                currentDropZone.classList.add('mobile-drop-target');
                
                // Add side indicator for pills
                if (currentDropZone.classList.contains('tune-pill') && dropSide) {
                    currentDropZone.classList.add(dropSide === 'right' ? 'drop-after' : 'drop-before');
                }
            }
            
            this.lastDropZone = currentDropZone;
        }
    }
    
    static endMobileDrag(e: TouchEvent): void {
        if (!this.dragState || !this.dragState.isMobile) return;
        
        const touch = e.changedTouches[0]!;
        const elementBelow = document.elementFromPoint(touch.clientX, touch.clientY);
        
        // Clean up drag visuals
        this.cleanupDragGhosts();
        
        // Remove drop zone highlighting
        if (this.lastDropZone) {
            this.lastDropZone.classList.remove('mobile-drop-target', 'drop-before', 'drop-after', 'drop-at-end');
            this.lastDropZone = null;
        }
        
        // Find drop position
        const dropPosition = this.findDropPosition(touch.clientX, touch.clientY);
        
        if (dropPosition) {
            // Perform the drop
            const pillSelection = this.getPillSelection!();
            const draggedIds = Array.from(pillSelection.getSelectedPills());
            this.performDrop?.(dropPosition, draggedIds);
        }
        
        // Reset drag state
        this.dragState = null;
    }
    
    static cancelMobileDrag(): void {
        // Clean up any drag ghosts
        this.cleanupDragGhosts();
        
        // Remove drop zone highlighting
        if (this.lastDropZone) {
            this.lastDropZone.classList.remove('mobile-drop-target', 'drop-before', 'drop-after', 'drop-at-end');
            this.lastDropZone = null;
        }
        
        // Reset drag state
        this.dragState = null;
    }
    
    // Helper to find pill by ID
    static findPillById(pillId: string): TunePill | null {
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        for (const set of tunePillsData) {
            for (const pill of set) {
                if (pill.id === pillId) {
                    return pill;
                }
            }
        }
        return null;
    }
    
    // Helper method to get the last row of pills in a tune-set
    static getLastRowOfPills(tuneSet: HTMLElement): HTMLElement[] {
        const pills = Array.from(tuneSet.querySelectorAll('.tune-pill')) as HTMLElement[];
        if (pills.length === 0) return [];
        
        // Get the bottom-most row
        const lastPill = pills[pills.length - 1]!;
        const lastPillRect = lastPill.getBoundingClientRect();
        const lastRowTop = lastPillRect.top;
        
        // Find all pills on the same row as the last pill
        return pills.filter(pill => {
            const rect = pill.getBoundingClientRect();
            return Math.abs(rect.top - lastRowTop) < 10; // Within 10px vertically
        });
    }
    
    // Calculate drop position when dropping on a pill
    static calculatePillDropPosition(targetPill: HTMLElement, clientX: number): DropPosition {
        const rect = targetPill.getBoundingClientRect();
        const setElement = targetPill.closest('.tune-set') as HTMLElement;
        const containerElement = document.getElementById('tune-pills-container')!;
        const setIndex = Array.from(containerElement.querySelectorAll('.tune-set')).indexOf(setElement);
        const pillIndex = Array.from(setElement.querySelectorAll('.tune-pill')).indexOf(targetPill);
        
        const isAfter = clientX > rect.left + rect.width / 2;
        return {
            setIndex: setIndex,
            pillIndex: isAfter ? pillIndex + 1 : pillIndex,
            position: isAfter ? 'after' : 'before'
        };
    }
    
    // Calculate drop position when dropping on a tune-set
    static calculateTuneSetDropPosition(tuneSet: HTMLElement, clientX: number, clientY: number): DropPosition {
        const containerElement = document.getElementById('tune-pills-container')!;
        const setIndex = Array.from(containerElement.querySelectorAll('.tune-set')).indexOf(tuneSet);
        const pills = Array.from(tuneSet.querySelectorAll('.tune-pill')) as HTMLElement[];
        
        // Find the nearest pill
        for (let i = 0; i < pills.length; i++) {
            const pillRect = pills[i]!.getBoundingClientRect();
            if (clientY >= pillRect.top && clientY <= pillRect.bottom) {
                // We're on the same row as this pill
                if (clientX < pillRect.left + pillRect.width / 2) {
                    return { setIndex: setIndex, pillIndex: i, position: 'before' };
                }
            }
        }
        
        // Default to end of set
        return { setIndex: setIndex, pillIndex: pills.length, position: 'after' };
    }
    
    // Clear all drop indicators
    static clearDropIndicators(): void {
        // Remove drop-active class from cursor positions
        document.querySelectorAll('.cursor-position.drop-active').forEach(cursorPos => {
            cursorPos.classList.remove('drop-active');
        });
        // Still remove old-style drop indicators if they exist
        document.querySelectorAll('.drop-indicator').forEach(indicator => {
            indicator.classList.remove('active');
        });
        document.querySelectorAll('.horizontal-drop-zone').forEach(zone => {
            zone.classList.remove('drag-over');
        });
    }
    
    // Show drop indicator at position
    static showDropIndicator(position: DropPosition | null): void {
        this.clearDropIndicators();
        
        if (!position) return;
        
        const container = document.getElementById('tune-pills-container')!;
        const sets = container.querySelectorAll('.tune-set');
        
        if (position.position === 'newset') {
            // Show horizontal drop zone indicator
            const horizontalZones = container.querySelectorAll('.horizontal-drop-zone');
            horizontalZones.forEach(zone => {
                const htmlZone = zone as HTMLElement;
                if (parseInt(htmlZone.dataset.insertAtSetIndex!) === position.setIndex) {
                    htmlZone.classList.add('drag-over');
                }
            });
        } else if (position.setIndex < sets.length) {
            // Use existing cursor positions instead of creating new drop indicators
            const targetSet = sets[position.setIndex] as HTMLElement;
            const cursorPositions = targetSet.querySelectorAll('.cursor-position');
            
            // Find the matching cursor position
            cursorPositions.forEach(cursorPos => {
                const htmlCursor = cursorPos as HTMLElement;
                const cursorSetIndex = parseInt(htmlCursor.dataset.setIndex!);
                const cursorPillIndex = parseInt(htmlCursor.dataset.pillIndex!);
                const cursorPositionType = htmlCursor.dataset.positionType!;
                
                // Match based on position
                let matches = false;
                
                if (position.position === 'before') {
                    // Dropping before pill at pillIndex
                    if (position.pillIndex === 0) {
                        // Special case: before first pill
                        matches = (cursorPositionType === 'before' && cursorPillIndex === 0);
                    } else {
                        // Between pills: this is the 'after' position of the previous pill
                        matches = (cursorPositionType === 'after' && cursorPillIndex === position.pillIndex - 1);
                    }
                } else if (position.position === 'after') {
                    // Dropping after the last pill in set
                    matches = (cursorPositionType === 'after' && cursorPillIndex === position.pillIndex - 1);
                }
                
                if (matches) {
                    htmlCursor.classList.add('drop-active');
                }
            });
        }
    }
    
    // Setup container-level drag event listeners
    static setupContainerDragListeners(): void {
        const tuneContainer = document.getElementById('tune-pills-container')!;
        
        tuneContainer.addEventListener('dragover', (e: DragEvent) => {
            e.preventDefault();
            e.dataTransfer!.dropEffect = 'move';
            
            const position = this.findDropPosition(e.clientX, e.clientY);
            this.showDropIndicator(position);
        });
        
        tuneContainer.addEventListener('dragleave', (e: DragEvent) => {
            // Only clear if we're really leaving the container
            if (!tuneContainer.contains(e.relatedTarget as Node)) {
                this.clearDropIndicators();
            }
        });
        
        tuneContainer.addEventListener('drop', (e: DragEvent) => {
            e.preventDefault();
            this.clearDropIndicators();
            
            const position = this.findDropPosition(e.clientX, e.clientY);
            
            if (this.dragState) {
                // Internal drag and drop
                const pillSelection = this.getPillSelection!();
                const draggedIds = Array.from(pillSelection.getSelectedPills());
                this.performDrop?.(position, draggedIds);
            } else {
                // External drag or paste
                try {
                    const dragData = JSON.parse(e.dataTransfer!.getData('text/json'));
                    if (dragData && Array.isArray(dragData)) {
                        this.pasteAtPosition?.(dragData, position);
                    }
                } catch (err) {
                    // Ignore external drop if can't parse
                }
            }
        });
    }
    
    // Get drag state
    static getDragState(): DragState | null {
        return this.dragState;
    }
    
    // Set drag state
    static setDragState(state: DragState | null): void {
        this.dragState = state;
    }
    
    // Clear drag state
    static clearDragState(): void {
        this.dragState = null;
    }
}

// Export for use in other modules or global scope
declare global {
    interface Window {
        DragDrop: typeof DragDrop;
    }
}

(window as any).DragDrop = DragDrop;