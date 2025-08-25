/**
 * DragDrop Module for Session Instance Detail Beta
 * Handles all drag and drop functionality including touch drag, desktop drag/drop, 
 * drop zones, drop indicators, and position detection
 */

class DragDrop {
    static dragState = null;
    static globalDragGhost = null;
    
    // External dependencies that need to be registered
    static getPillSelection = null;
    static getStateManager = null;
    static getCursorManager = null;
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
        this.performDrop = options.performDrop || window.performDrop;
        this.dropStructuredSetsAtNewPosition = options.dropStructuredSetsAtNewPosition || window.dropStructuredSetsAtNewPosition;
        this.pasteAtPosition = options.pasteAtPosition || window.pasteAtPosition;
        this.saveToUndo = options.saveToUndo || window.saveToUndo;
        this.showContextMenu = options.showContextMenu || window.showContextMenu;
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
    
    // Create drop indicator
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
    
    // Setup event listeners for pills
    static setupPillEventListeners(pillElement, pillData) {
        const pillSelection = this.getPillSelection();
        
        // Click to select or show context menu
        pillElement.addEventListener('click', (e) => {
            // Calculate if click is on the left side (chevron area)
            const rect = pillElement.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const isChevronArea = clickX <= 30; // Chevron area is approximately 30px
            
            if (isChevronArea) {
                // Clicked on chevron - toggle context menu
                e.preventDefault();
                e.stopPropagation();
                
                // Check if menu is already open for this pill
                const existingMenu = document.querySelector(`.tune-context-menu[data-pill-id="${pillData.id}"]`);
                if (existingMenu) {
                    // Menu is open, close it
                    this.hideContextMenu(pillData.id);
                } else {
                    // Menu is closed, open it
                    this.showContextMenu(e, pillData);
                }
            } else {
                // Clicked on tune name area - handle selection
                e.preventDefault();
                e.stopPropagation();
                
                if (e.ctrlKey || e.metaKey) {
                    // Toggle selection for this pill
                    if (pillSelection.isSelected(pillData.id)) {
                        pillSelection.removeSelection(pillData.id);
                    } else {
                        pillSelection.addSelection(pillData.id);
                    }
                } else if (e.shiftKey && pillSelection.getSelectionCount() > 0) {
                    // Range selection
                    pillSelection.extendSelection(pillData.id);
                } else {
                    // Single selection
                    pillSelection.selectSingle(pillData.id);
                }
            }
        });
        
        // Touch handling for mobile drag & drop
        let touchStartTime = 0;
        let longPressTimer = null;
        let isDragMode = false;
        let touchStartX = 0, touchStartY = 0;
        
        pillElement.addEventListener('touchstart', (e) => {
            touchStartTime = Date.now();
            clearTimeout(longPressTimer);
            isDragMode = false;
            
            const touch = e.touches[0];
            touchStartX = touch.clientX;
            touchStartY = touch.clientY;
            
            // Calculate if touch is on the left side (chevron area)
            const rect = pillElement.getBoundingClientRect();
            const touchX = touch.clientX - rect.left;
            const isChevronArea = touchX <= 30;
            
            // Store chevron state for later use
            pillElement.dataset.touchOnChevron = isChevronArea;
            
            if (!isChevronArea) {
                // Only set up long press for drag if not on chevron
                longPressTimer = setTimeout(() => {
                    // Enter drag mode
                    isDragMode = true;
                    pillElement.classList.add('dragging');
                    
                    // If pill isn't selected, select it
                    if (!pillSelection.isSelected(pillData.id)) {
                        pillSelection.selectSingle(pillData.id);
                    }
                    
                    // Add dragging class to all selected pills
                    pillSelection.getSelectedPills().forEach(pillId => {
                        const pill = document.querySelector(`[data-pill-id="${pillId}"]`);
                        if (pill && pill !== pillElement) {
                            pill.classList.add('dragging');
                        }
                    });
                    
                    // Provide haptic feedback if available
                    if (navigator.vibrate) {
                        navigator.vibrate(10);
                    }
                }, 500); // 500ms long press
            }
            
            e.stopPropagation();
        });
        
        // Track last drop zone and throttle updates
        let lastDropZone = null;
        let lastDropZoneUpdate = 0;
        const DROP_ZONE_UPDATE_THROTTLE = 50; // ms - reduced for more responsive feedback
        
        pillElement.addEventListener('touchmove', (e) => {
            clearTimeout(longPressTimer);
            
            if (isDragMode) {
                // Prevent scrolling during drag
                e.preventDefault();
                
                const touch = e.touches[0];
                
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
                    this.globalDragGhost.textContent = pillSelection.getSelectionCount() > 1 ? `${pillSelection.getSelectionCount()} pills` : pillData.tuneName;
                    document.body.appendChild(this.globalDragGhost);
                }
                
                // Update ghost position smoothly
                this.globalDragGhost.style.left = (touch.clientX - 30) + 'px';
                this.globalDragGhost.style.top = (touch.clientY - 15) + 'px';
                
                // Check for drop zone under finger every 50ms to show color feedback
                const now = Date.now();
                if (now - lastDropZoneUpdate > DROP_ZONE_UPDATE_THROTTLE) {
                    lastDropZoneUpdate = now;
                    
                    // Get element below finger
                    const elementBelow = document.elementFromPoint(touch.clientX, touch.clientY);
                    
                    // Find potential drop zone
                    let currentDropZone = null;
                    let dropSide = null; // 'left' or 'right' for pills
                    
                    if (elementBelow) {
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
                                dropSide = touch.clientX > pillCenterX ? 'right' : 'left';
                            }
                        }
                        
                        // If not over a pill or horizontal zone, check for tune-set
                        if (!currentDropZone) {
                            const tuneSet = elementBelow.closest('.tune-set');
                            if (tuneSet) {
                                const pills = Array.from(tuneSet.querySelectorAll('.tune-pill'));
                                
                                // Check if we're in a gap between pills
                                let inGap = false;
                                for (let i = 0; i < pills.length - 1; i++) {
                                    const currentPill = pills[i];
                                    const nextPill = pills[i + 1];
                                    
                                    const currentRect = currentPill.getBoundingClientRect();
                                    const nextRect = nextPill.getBoundingClientRect();
                                    
                                    // Check if on same row and in horizontal gap
                                    const sameRow = Math.abs(currentRect.top - nextRect.top) < 10;
                                    if (sameRow && touch.clientX > currentRect.right + 5 && touch.clientX < nextRect.left - 5) {
                                        if (touch.clientY >= Math.min(currentRect.top, nextRect.top) - 5 && 
                                            touch.clientY <= Math.max(currentRect.bottom, nextRect.bottom) + 5) {
                                            // We're in the gap between these pills
                                            currentDropZone = tuneSet;
                                            currentDropZone.dataset.gapAfterPillIndex = i.toString();
                                            dropSide = 'gap';
                                            break;
                                        }
                                    }
                                }
                                
                                // If not in a gap, check for end-of-row drop or regular tune-set drop
                                if (!inGap && !currentDropZone) {
                                    const tuneSetRect = tuneSet.getBoundingClientRect();
                                    
                                    // If we're in the tune-set bounds
                                    if (touch.clientX >= tuneSetRect.left - 10 && touch.clientX <= tuneSetRect.right + 10 &&
                                        touch.clientY >= tuneSetRect.top - 10 && touch.clientY <= tuneSetRect.bottom + 10) {
                                        
                                        // Check if we're clearly beyond all pills on the last row (end-of-row drop)
                                        const lastRow = this.getLastRowOfPills(tuneSet);
                                        const rightmostPillOnRow = lastRow.length > 0 ? lastRow[lastRow.length - 1] : null;
                                        
                                        if (rightmostPillOnRow && touch.clientX > rightmostPillOnRow.getBoundingClientRect().right + 10) {
                                            currentDropZone = tuneSet;
                                            currentDropZone.dataset.virtualDropType = 'end-of-row';
                                            dropSide = 'end'; // Special indicator for blank space positioning
                                        } else {
                                            // Regular tune-set drop
                                            currentDropZone = tuneSet;
                                        }
                                    }
                                } else {
                                    inGap = true;
                                }
                            }
                        }
                        
                        // If not over anything specific, check if we're in the container's empty area
                        if (!currentDropZone) {
                            const container = elementBelow.closest('#tune-pills-container');
                            if (container) {
                                const containerRect = container.getBoundingClientRect();
                                
                                // Check if we're in the bottom empty area below all sets
                                if (touch.clientY > containerRect.bottom - 50) {
                                    // We're in the bottom empty area - create new set
                                    currentDropZone = container;
                                    currentDropZone.dataset.virtualDropType = 'end-of-list';
                                    dropSide = 'end';
                                }
                            }
                        }
                    }
                    
                    // Track if target or side changed
                    const dropKey = currentDropZone ? `${currentDropZone.id || currentDropZone.className}-${dropSide}` : null;
                    const lastDropKey = lastDropZone ? `${lastDropZone.id || lastDropZone.className}-${lastDropZone.dataset.dropSide}` : null;
                    
                    // Only update if target or side changed
                    if (dropKey !== lastDropKey) {
                        // Remove classes from previous target
                        if (lastDropZone) {
                            lastDropZone.classList.remove('mobile-drop-target', 'drop-before', 'drop-after', 'drop-at-end', 'drop-in-gap');
                            delete lastDropZone.dataset.dropSide;
                            delete lastDropZone.dataset.gapAfterPillIndex;
                            lastDropZone.style.removeProperty('--gap-indicator-left');
                            lastDropZone.style.removeProperty('--gap-indicator-top');
                        }
                        
                        // Add classes to new target
                        if (currentDropZone) {
                            currentDropZone.classList.add('mobile-drop-target');
                            
                            // Debug for container
                            if (currentDropZone.id === 'tune-pills-container') {
                                // Container drop target styling handled by CSS
                            }
                            
                            // Add side indicator for pills
                            if (currentDropZone.classList.contains('tune-pill') && dropSide && dropSide !== 'end') {
                                currentDropZone.classList.add(dropSide === 'right' ? 'drop-after' : 'drop-before');
                                currentDropZone.dataset.dropSide = dropSide;
                            }
                            
                            // Add position indicator for blank space drops
                            if ((currentDropZone.id === 'tune-pills-container' || currentDropZone.classList.contains('tune-set')) && dropSide === 'end') {
                                currentDropZone.classList.add('drop-at-end');
                                currentDropZone.dataset.dropSide = dropSide;
                            }
                            
                            // Add position indicator for gap drops
                            if (currentDropZone.classList.contains('tune-set') && dropSide === 'gap') {
                                currentDropZone.classList.add('drop-in-gap');
                                currentDropZone.dataset.dropSide = dropSide;
                                
                                // Position the indicator between the pills
                                const gapAfterIndex = parseInt(currentDropZone.dataset.gapAfterPillIndex);
                                const pills = Array.from(currentDropZone.querySelectorAll('.tune-pill'));
                                if (gapAfterIndex >= 0 && gapAfterIndex < pills.length) {
                                    const afterPill = pills[gapAfterIndex];
                                    const beforePill = pills[gapAfterIndex + 1];
                                    
                                    if (afterPill && beforePill) {
                                        const afterRect = afterPill.getBoundingClientRect();
                                        const beforeRect = beforePill.getBoundingClientRect();
                                        const setRect = currentDropZone.getBoundingClientRect();
                                        
                                        const gapCenterX = (afterRect.right + beforeRect.left) / 2;
                                        const gapCenterY = (afterRect.top + afterRect.bottom) / 2;
                                        
                                        currentDropZone.style.setProperty('--gap-indicator-left', `${gapCenterX - setRect.left - 2}px`);
                                        currentDropZone.style.setProperty('--gap-indicator-top', `${gapCenterY - setRect.top - 12}px`);
                                    }
                                }
                            }
                        }
                        
                        lastDropZone = currentDropZone;
                    }
                }
            }
        });
        
        pillElement.addEventListener('touchend', (e) => {
            clearTimeout(longPressTimer);
            
            if (isDragMode) {
                e.preventDefault();
                e.stopPropagation();
                
                const touch = e.changedTouches[0];
                const elementBelow = document.elementFromPoint(touch.clientX, touch.clientY);
                
                // Clean up all drag ghosts
                this.cleanupDragGhosts();
                
                // Remove classes from the last drop zone
                if (lastDropZone) {
                    lastDropZone.classList.remove('mobile-drop-target', 'drop-before', 'drop-after', 'drop-at-end', 'drop-in-gap');
                    delete lastDropZone.dataset.dropSide;
                    delete lastDropZone.dataset.gapAfterPillIndex;
                    lastDropZone.style.removeProperty('--gap-indicator-left');
                    lastDropZone.style.removeProperty('--gap-indicator-top');
                }
                
                // Remove dragging class from all pills
                pillSelection.getSelectedPills().forEach(pillId => {
                    const pill = document.querySelector(`[data-pill-id="${pillId}"]`);
                    if (pill) {
                        pill.classList.remove('dragging');
                    }
                });
                
                // Reset drag mode
                isDragMode = false;
                
                // Find drop position based on final touch position
                if (elementBelow) {
                    let dropPosition = null;
                    
                    // Check for horizontal drop zone
                    const horizontalZone = elementBelow.closest('.horizontal-drop-zone');
                    if (horizontalZone) {
                        const setIndex = parseInt(horizontalZone.dataset.insertAtSetIndex);
                        dropPosition = { setIndex: setIndex, pillIndex: 0, position: 'newset' };
                    }
                    
                    // Check for pill drop
                    if (!dropPosition) {
                        const targetPill = elementBelow.closest('.tune-pill');
                        if (targetPill && !targetPill.classList.contains('dragging')) {
                            dropPosition = this.calculatePillDropPosition(targetPill, touch.clientX);
                        }
                    }
                    
                    // Check for tune-set drop
                    if (!dropPosition) {
                        const tuneSet = elementBelow.closest('.tune-set');
                        if (tuneSet) {
                            dropPosition = this.calculateTuneSetDropPosition(tuneSet, touch.clientX, touch.clientY);
                        }
                    }
                    
                    // Check for container drop
                    if (!dropPosition) {
                        const container = elementBelow.closest('#tune-pills-container');
                        if (container) {
                            const stateManager = this.getStateManager();
                            const tunePillsData = stateManager.getTunePillsData();
                            dropPosition = { setIndex: tunePillsData.length, pillIndex: 0, position: 'newset' };
                        }
                    }
                    
                    if (dropPosition) {
                        // Call the existing drop handler with correct parameters
                        const draggedIds = Array.from(pillSelection.getSelectedPills());
                        this.performDrop(dropPosition, draggedIds);
                    }
                }
            } else {
                // Not in drag mode - handle as selection or context menu
                const touchDuration = Date.now() - touchStartTime;
                const isChevronArea = pillElement.dataset.touchOnChevron === 'true';
                
                // Check for significant movement (scroll/swipe)
                const touch = e.changedTouches[0];
                const deltaX = Math.abs(touch.clientX - touchStartX);
                const deltaY = Math.abs(touch.clientY - touchStartY);
                const hasMoved = deltaX > 10 || deltaY > 10;
                
                if (!hasMoved) {
                    if (isChevronArea) {
                        // Clicked on chevron - toggle context menu
                        e.preventDefault();
                        e.stopPropagation();
                        
                        // Check if menu is already open for this pill
                        const existingMenu = document.querySelector(`.tune-context-menu[data-pill-id="${pillData.id}"]`);
                        if (existingMenu) {
                            // Menu is open, close it
                            this.hideContextMenu(pillData.id);
                        } else {
                            // Menu is closed, open it
                            this.showContextMenu(e, pillData);
                        }
                    } else if (touchDuration < 500) {
                        // Short tap on tune name area - handle selection
                        e.preventDefault();
                        e.stopPropagation();
                        
                        if (pillSelection.isSelected(pillData.id) && pillSelection.getSelectionCount() === 1) {
                            // Single selected pill tapped - deselect
                            pillSelection.clearSelection();
                        } else {
                            // Select this pill
                            pillSelection.selectSingle(pillData.id);
                        }
                    }
                }
            }
            
            // Clean up
            delete pillElement.dataset.touchOnChevron;
        });
        
        // Handle touch cancel (e.g., incoming call, system gesture)
        pillElement.addEventListener('touchcancel', (e) => {
            clearTimeout(longPressTimer);
            
            // Clean up any drag ghosts
            this.cleanupDragGhosts();
            
            // Reset drag state
            if (isDragMode) {
                // Remove dragging class from all pills
                pillSelection.getSelectedPills().forEach(pillId => {
                    const pill = document.querySelector(`[data-pill-id="${pillId}"]`);
                    if (pill) {
                        pill.classList.remove('dragging');
                    }
                });
                isDragMode = false;
            }
            
            // Clean up
            delete pillElement.dataset.touchOnChevron;
        });
        
        // Context menu handler
        pillElement.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.showContextMenu(e, pillData);
        });
        
        // Drag and drop functionality
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
    
    // Helper method to get the last row of pills in a tune-set
    static getLastRowOfPills(tuneSet) {
        const pills = Array.from(tuneSet.querySelectorAll('.tune-pill'));
        if (pills.length === 0) return [];
        
        // Get the bottom-most row
        const lastPill = pills[pills.length - 1];
        const lastPillRect = lastPill.getBoundingClientRect();
        
        // Find all pills in the same row as the last pill
        const lastRow = pills.filter(pill => {
            const pillRect = pill.getBoundingClientRect();
            return Math.abs(pillRect.top - lastPillRect.top) < 10; // Same row if within 10px vertically
        });
        
        return lastRow;
    }
    
    // Helper method to calculate drop position for pill drops
    static calculatePillDropPosition(targetPill, clientX) {
        const containerElement = document.getElementById('tune-pills-container');
        const setElement = targetPill.closest('.tune-set');
        const setIndex = Array.from(containerElement.querySelectorAll('.tune-set')).indexOf(setElement);
        const pillIndex = Array.from(setElement.querySelectorAll('.tune-pill')).indexOf(targetPill);
        
        const rect = targetPill.getBoundingClientRect();
        const isAfter = clientX > rect.left + rect.width / 2;
        
        return {
            setIndex: setIndex,
            pillIndex: isAfter ? pillIndex + 1 : pillIndex,
            position: isAfter ? 'after' : 'before'
        };
    }
    
    // Helper method to calculate drop position for tune-set drops
    static calculateTuneSetDropPosition(tuneSet, clientX, clientY) {
        const containerElement = document.getElementById('tune-pills-container');
        const setIndex = Array.from(containerElement.querySelectorAll('.tune-set')).indexOf(tuneSet);
        const pills = Array.from(tuneSet.querySelectorAll('.tune-pill'));
        
        // Check for end-of-set drop (after all pills)
        if (pills.length > 0) {
            const lastPill = pills[pills.length - 1];
            const lastRect = lastPill.getBoundingClientRect();
            
            if (clientX > lastRect.right + 10) {
                return {
                    setIndex: setIndex,
                    pillIndex: pills.length,
                    position: 'after'
                };
            }
        }
        
        // Default: add to end of set
        return {
            setIndex: setIndex,
            pillIndex: pills.length,
            position: 'after'
        };
    }
    
    // Clear drop indicators
    static clearDropIndicators() {
        document.querySelectorAll('.drop-indicator').forEach(indicator => {
            indicator.remove();
        });
    }
    
    // Show drop indicator
    static showDropIndicator(position) {
        this.clearDropIndicators();
        
        const containerElement = document.getElementById('tune-pills-container');
        const sets = containerElement.querySelectorAll('.tune-set');
        
        if (position.position === 'newset') {
            // Show indicator at end of container
            const indicator = this.createDropIndicator();
            indicator.classList.add('active');
            containerElement.appendChild(indicator);
        } else {
            const targetSet = sets[position.setIndex];
            const pills = targetSet.querySelectorAll('.tune-pill');
            
            if (position.position === 'before' && pills[position.pillIndex]) {
                const indicator = this.createDropIndicator();
                indicator.classList.add('active');
                targetSet.insertBefore(indicator, pills[position.pillIndex]);
            } else {
                // After last pill or specific position
                const indicator = this.createDropIndicator();
                indicator.classList.add('active');
                targetSet.appendChild(indicator);
            }
        }
    }
    
    // Setup container drag & drop event listeners
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

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.DragDrop = DragDrop;
}