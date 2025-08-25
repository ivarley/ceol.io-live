/**
 * DragDrop Module for Session Instance Detail Beta
 * Handles drag and drop functionality including desktop drag/drop, 
 * drop zones, drop indicators, and position detection
 * Note: General pill interactions (clicks, selection) are handled by PillInteraction module
 */

class DragDrop {
    static dragState = null;
    static globalDragGhost = null;
    static lastDropZone = null;
    static lastDropZoneUpdate = 0;
    
    // External dependencies that need to be registered
    static getPillSelection = null;
    static getStateManager = null;
    static getCursorManager = null;
    static getPillInteraction = null;
    static performDrop = null;
    static dropStructuredSetsAtNewPosition = null;
    static pasteAtPosition = null;
    static saveToUndo = null;
    static showContextMenu = null;
    static hideContextMenu = null;
    static applyLandingAnimation = null;
    static setCursorPosition = null;
    static clearSelection = null;
    
    static initialize(options = {}) {
        this.getPillSelection = options.getPillSelection || (() => window.PillSelection);
        this.getStateManager = options.getStateManager || (() => window.StateManager);
        this.getCursorManager = options.getCursorManager || (() => window.CursorManager);
        this.getPillInteraction = options.getPillInteraction || (() => window.PillInteraction);
        this.performDrop = options.performDrop || window.performDrop;
        this.dropStructuredSetsAtNewPosition = options.dropStructuredSetsAtNewPosition || window.dropStructuredSetsAtNewPosition;
        this.pasteAtPosition = options.pasteAtPosition || window.pasteAtPosition;
        this.saveToUndo = options.saveToUndo || window.saveToUndo;
        this.showContextMenu = options.showContextMenu || window.showContextMenu;
        this.hideContextMenu = options.hideContextMenu || window.hideContextMenu;
        this.applyLandingAnimation = options.applyLandingAnimation || window.applyLandingAnimation;
        this.setCursorPosition = options.setCursorPosition || window.setCursorPosition;
        this.clearSelection = options.clearSelection || window.clearSelection;
    }
    
    static registerCallbacks(callbacks) {
        Object.assign(this, callbacks);
    }
    
    // Clean up any existing drag ghosts
    static cleanupDragGhosts() {
        // Remove the global ghost if it exists
        if (this.globalDragGhost) {
            this.globalDragGhost.remove();
            this.globalDragGhost = null;
        }
        // Also remove any orphaned ghosts by class name
        document.querySelectorAll('.mobile-drag-ghost').forEach(ghost => ghost.remove());
    }
    
    // Create drop indicator element
    static createDropIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'drop-indicator';
        return indicator;
    }
    
    // Create horizontal drop zone between sets
    static createHorizontalDropZone(insertAtSetIndex) {
        const dropZone = document.createElement('div');
        dropZone.className = 'horizontal-drop-zone';
        dropZone.dataset.insertAtSetIndex = insertAtSetIndex;
        
        // Click handler - position cursor for typing new set
        dropZone.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Clear selection and selection anchor when clicking to move cursor
            this.clearSelection();
            
            this.setCursorPosition(insertAtSetIndex, 0, 'newset');
        });
        
        // Drag and drop handlers
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            dropZone.classList.add('drag-over');
        });
        
        dropZone.addEventListener('dragleave', (e) => {
            dropZone.classList.remove('drag-over');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation(); // IMPORTANT: Stop the event from bubbling to the container
            dropZone.classList.remove('drag-over');
            
            if (this.dragState) {
                // Internal drag and drop - use drag data to preserve set structure
                try {
                    const dragData = JSON.parse(e.dataTransfer.getData('text/json'));
                    if (dragData && Array.isArray(dragData)) {
                        // Use the existing performDrop logic but with the structured data
                        this.dropStructuredSetsAtNewPosition(dragData, insertAtSetIndex);
                    } else {
                        // Fallback to old method if drag data is invalid
                        const pillSelection = this.getPillSelection();
                        const draggedIds = Array.from(pillSelection.getSelectedPills());
                        const position = { setIndex: insertAtSetIndex, pillIndex: 0, position: 'newset' };
                        this.performDrop(position, draggedIds);
                    }
                } catch (err) {
                    // Fallback to old method if drag data parsing fails
                    const pillSelection = this.getPillSelection();
                    const draggedIds = Array.from(pillSelection.getSelectedPills());
                    const position = { setIndex: insertAtSetIndex, pillIndex: 0, position: 'newset' };
                    this.performDrop(position, draggedIds);
                }
            } else {
                // External drag or paste
                try {
                    const dragData = JSON.parse(e.dataTransfer.getData('text/json'));
                    if (dragData && Array.isArray(dragData)) {
                        const position = { setIndex: insertAtSetIndex, pillIndex: 0, position: 'newset' };
                        this.pasteAtPosition(dragData, position);
                    }
                } catch (err) {
                    // Ignore external drop if can't parse
                }
            }
        });
        
        return dropZone;
    }
    
    // Find drop position based on mouse coordinates
    static findDropPosition(x, y) {
        const containerElement = document.getElementById('tune-pills-container');
        
        // First check for horizontal drop zones
        const horizontalZones = containerElement.querySelectorAll('.horizontal-drop-zone');
        for (let i = 0; i < horizontalZones.length; i++) {
            const zoneElement = horizontalZones[i];
            const zoneRect = zoneElement.getBoundingClientRect();
            
            if (y >= zoneRect.top && y <= zoneRect.bottom) {
                const insertAtSetIndex = parseInt(zoneElement.dataset.insertAtSetIndex);
                return { setIndex: insertAtSetIndex, pillIndex: 0, position: 'newset' };
            }
        }
        
        // Then check tune sets
        const sets = containerElement.querySelectorAll('.tune-set');
        
        for (let setIndex = 0; setIndex < sets.length; setIndex++) {
            const setElement = sets[setIndex];
            const setRect = setElement.getBoundingClientRect();
            
            if (y >= setRect.top && y <= setRect.bottom) {
                const pills = setElement.querySelectorAll('.tune-pill');
                
                for (let pillIndex = 0; pillIndex < pills.length; pillIndex++) {
                    const pillRect = pills[pillIndex].getBoundingClientRect();
                    
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
    static setupPillEventListeners(pillElement, pillData) {
        const pillInteraction = this.getPillInteraction();
        if (pillInteraction) {
            return pillInteraction.setupPillEventListeners(pillElement, pillData);
        }
        // Fallback - just register drag handlers if PillInteraction not available
        this.registerPillDragHandlers(pillElement, pillData);
    }
    
    // Register only drag-specific event handlers for a pill element
    static registerPillDragHandlers(pillElement, pillData) {
        const pillSelection = this.getPillSelection();
        
        // Desktop drag and drop
        pillElement.addEventListener('dragstart', (e) => {
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
                const pill = document.querySelector(`[data-pill-id="${pillId}"]`);
                if (pill) {
                    pill.classList.add('dragging');
                }
            });
            
            // Set drag data (for clipboard compatibility) - preserve set structure
            const stateManager = this.getStateManager();
            const tunePillsData = stateManager.getTunePillsData();
            const selectedBySet = new Map();
            
            tunePillsData.forEach((tuneSet, setIndex) => {
                tuneSet.forEach((pill, pillIndex) => {
                    if (pillSelection.isSelected(pill.id)) {
                        if (!selectedBySet.has(setIndex)) {
                            selectedBySet.set(setIndex, []);
                        }
                        selectedBySet.get(setIndex).push(JSON.parse(JSON.stringify(pill)));
                    }
                });
            });
            
            // Convert to array of sets, preserving set breaks
            const dragData = Array.from(selectedBySet.values()).filter(set => set && set.length > 0);
            
            e.dataTransfer.setData('text/json', JSON.stringify(dragData));
            e.dataTransfer.effectAllowed = 'move';
        });
        
        pillElement.addEventListener('dragend', (e) => {
            // Remove dragging class from all pills that might have it
            document.querySelectorAll('.tune-pill.dragging').forEach(pill => {
                pill.classList.remove('dragging');
            });
            this.clearDropIndicators();
            this.dragState = null;
        });
    }
    
    // Mobile drag support methods
    static startMobileDrag(e, pillData) {
        const touch = e.touches[0];
        this.dragState = {
            draggedPillId: pillData.id,
            startX: touch.clientX,
            startY: touch.clientY,
            isMobile: true
        };
    }
    
    static handleMobileDragMove(e) {
        if (!this.dragState || !this.dragState.isMobile) return;
        
        const touch = e.touches[0];
        const pillSelection = this.getPillSelection();
        
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
    
    static updateMobileDropZone(x, y) {
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
        let currentDropZone = null;
        let dropSide = null;
        
        // Check for horizontal drop zone first
        currentDropZone = elementBelow.closest('.horizontal-drop-zone');
        
        // If not, check for pill (but not if it's being dragged)
        if (!currentDropZone) {
            const pill = elementBelow.closest('.tune-pill');
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
            const tuneSet = elementBelow.closest('.tune-set');
            if (tuneSet) {
                currentDropZone = tuneSet;
                dropSide = 'set';
            }
        }
        
        // If not over anything specific, check container
        if (!currentDropZone) {
            currentDropZone = elementBelow.closest('#tune-pills-container');
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
    
    static endMobileDrag(e) {
        if (!this.dragState || !this.dragState.isMobile) return;
        
        const touch = e.changedTouches[0];
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
            const pillSelection = this.getPillSelection();
            const draggedIds = Array.from(pillSelection.getSelectedPills());
            this.performDrop(dropPosition, draggedIds);
        }
        
        // Reset drag state
        this.dragState = null;
    }
    
    static cancelMobileDrag() {
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
    static findPillById(pillId) {
        const stateManager = this.getStateManager();
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
    static getLastRowOfPills(tuneSet) {
        const pills = Array.from(tuneSet.querySelectorAll('.tune-pill'));
        if (pills.length === 0) return [];
        
        // Get the bottom-most row
        const lastPill = pills[pills.length - 1];
        const lastPillRect = lastPill.getBoundingClientRect();
        const lastRowTop = lastPillRect.top;
        
        // Find all pills on the same row as the last pill
        return pills.filter(pill => {
            const rect = pill.getBoundingClientRect();
            return Math.abs(rect.top - lastRowTop) < 10; // Within 10px vertically
        });
    }
    
    // Calculate drop position when dropping on a pill
    static calculatePillDropPosition(targetPill, clientX) {
        const rect = targetPill.getBoundingClientRect();
        const setElement = targetPill.closest('.tune-set');
        const containerElement = document.getElementById('tune-pills-container');
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
    static calculateTuneSetDropPosition(tuneSet, clientX, clientY) {
        const containerElement = document.getElementById('tune-pills-container');
        const setIndex = Array.from(containerElement.querySelectorAll('.tune-set')).indexOf(tuneSet);
        const pills = Array.from(tuneSet.querySelectorAll('.tune-pill'));
        
        // Find the nearest pill
        for (let i = 0; i < pills.length; i++) {
            const pillRect = pills[i].getBoundingClientRect();
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
    static clearDropIndicators() {
        document.querySelectorAll('.drop-indicator').forEach(indicator => {
            indicator.classList.remove('active');
        });
        document.querySelectorAll('.horizontal-drop-zone').forEach(zone => {
            zone.classList.remove('drag-over');
        });
    }
    
    // Show drop indicator at position
    static showDropIndicator(position) {
        this.clearDropIndicators();
        
        if (!position) return;
        
        const container = document.getElementById('tune-pills-container');
        const sets = container.querySelectorAll('.tune-set');
        
        if (position.position === 'newset') {
            // Show horizontal drop zone indicator
            const horizontalZones = container.querySelectorAll('.horizontal-drop-zone');
            horizontalZones.forEach(zone => {
                if (parseInt(zone.dataset.insertAtSetIndex) === position.setIndex) {
                    zone.classList.add('drag-over');
                }
            });
        } else if (position.setIndex < sets.length) {
            // Show pill-level drop indicator
            const targetSet = sets[position.setIndex];
            const pills = targetSet.querySelectorAll('.tune-pill');
            
            // Find or create drop indicator
            let indicator = targetSet.querySelector(`.drop-indicator[data-position="${position.pillIndex}"]`);
            if (!indicator) {
                indicator = this.createDropIndicator();
                indicator.dataset.position = position.pillIndex;
                
                if (position.pillIndex === 0) {
                    targetSet.insertBefore(indicator, targetSet.firstChild);
                } else if (position.pillIndex >= pills.length) {
                    targetSet.appendChild(indicator);
                } else {
                    targetSet.insertBefore(indicator, pills[position.pillIndex]);
                }
            }
            
            indicator.classList.add('active');
        }
    }
    
    // Setup container-level drag event listeners
    static setupContainerDragListeners() {
        const tuneContainer = document.getElementById('tune-pills-container');
        
        tuneContainer.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            
            const position = this.findDropPosition(e.clientX, e.clientY);
            this.showDropIndicator(position);
        });
        
        tuneContainer.addEventListener('dragleave', (e) => {
            // Only clear if we're really leaving the container
            if (!tuneContainer.contains(e.relatedTarget)) {
                this.clearDropIndicators();
            }
        });
        
        tuneContainer.addEventListener('drop', (e) => {
            e.preventDefault();
            this.clearDropIndicators();
            
            const position = this.findDropPosition(e.clientX, e.clientY);
            
            if (this.dragState) {
                // Internal drag and drop
                const pillSelection = this.getPillSelection();
                const draggedIds = Array.from(pillSelection.getSelectedPills());
                this.performDrop(position, draggedIds);
            } else {
                // External drag or paste
                try {
                    const dragData = JSON.parse(e.dataTransfer.getData('text/json'));
                    if (dragData && Array.isArray(dragData)) {
                        this.pasteAtPosition(dragData, position);
                    }
                } catch (err) {
                    // Ignore external drop if can't parse
                }
            }
        });
    }
    
    // Get drag state
    static getDragState() {
        return this.dragState;
    }
    
    // Set drag state
    static setDragState(state) {
        this.dragState = state;
    }
    
    // Clear drag state
    static clearDragState() {
        this.dragState = null;
    }
}

// Export for use in other modules or global scope
window.DragDrop = DragDrop;