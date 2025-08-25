/**
 * PillInteraction Module for Session Instance Detail Beta
 * Handles all pill interaction events including clicks, touches, selection, and context menus
 * Delegates drag & drop specific functionality to the DragDrop module
 */

class PillInteraction {
    // External dependencies that need to be registered
    static getPillSelection = null;
    static getStateManager = null;
    static getCursorManager = null;
    static getDragDrop = null;
    static showContextMenu = null;
    static hideContextMenu = null;
    static isTyping = null;
    static finishTyping = null;
    
    static initialize(options = {}) {
        this.getPillSelection = options.getPillSelection || (() => window.PillSelection);
        this.getStateManager = options.getStateManager || (() => window.StateManager);
        this.getCursorManager = options.getCursorManager || (() => window.CursorManager);
        this.getDragDrop = options.getDragDrop || (() => window.DragDrop);
        this.showContextMenu = options.showContextMenu || window.showContextMenu;
        this.hideContextMenu = options.hideContextMenu || window.hideContextMenu;
        this.isTyping = options.isTyping || (() => false);
        this.finishTyping = options.finishTyping || (() => {});
    }
    
    static registerCallbacks(callbacks) {
        Object.assign(this, callbacks);
    }
    
    static setupPillEventListeners(pillElement, pillData) {
        const pillSelection = this.getPillSelection();
        const dragDrop = this.getDragDrop();
        
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
                
                // If user is typing, finish typing first
                if (this.isTyping && this.isTyping()) {
                    this.finishTyping();
                }
                
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
                    
                    // If we had a selection anchor from shift+arrow, clear it
                    const cursorManager = this.getCursorManager();
                    if (cursorManager && cursorManager.selectionAnchor !== null) {
                        cursorManager.selectionAnchor = null;
                    }
                }
            }
        });
        
        // Touch handling for mobile interactions
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
                    
                    // Start mobile drag if DragDrop module supports it
                    if (dragDrop && dragDrop.startMobileDrag) {
                        dragDrop.startMobileDrag(e, pillData);
                    }
                }, 500); // 500ms long press
            }
        });
        
        pillElement.addEventListener('touchmove', (e) => {
            if (isDragMode && dragDrop && dragDrop.handleMobileDragMove) {
                e.preventDefault();
                dragDrop.handleMobileDragMove(e);
            }
        });
        
        pillElement.addEventListener('touchend', (e) => {
            clearTimeout(longPressTimer);
            
            if (isDragMode) {
                // End drag mode
                if (dragDrop && dragDrop.endMobileDrag) {
                    dragDrop.endMobileDrag(e);
                }
                
                // Remove dragging class from all pills
                document.querySelectorAll('.tune-pill.dragging').forEach(pill => {
                    pill.classList.remove('dragging');
                });
                
                isDragMode = false;
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
                            // Create a fake event with the touch coordinates
                            const fakeEvent = {
                                clientX: touch.clientX,
                                clientY: touch.clientY,
                                target: pillElement,
                                preventDefault: () => {},
                                stopPropagation: () => {}
                            };
                            this.showContextMenu(fakeEvent, pillData);
                        }
                    } else if (touchDuration < 500) {
                        // Short tap on tune name area - handle selection
                        e.preventDefault();
                        e.stopPropagation();
                        pillSelection.selectSingle(pillData.id);
                    }
                }
            }
            
            // Clean up
            delete pillElement.dataset.touchOnChevron;
        });
        
        pillElement.addEventListener('touchcancel', (e) => {
            clearTimeout(longPressTimer);
            isDragMode = false;
            
            // Clean up dragging state
            document.querySelectorAll('.tune-pill.dragging').forEach(pill => {
                pill.classList.remove('dragging');
            });
            
            if (dragDrop && dragDrop.cancelMobileDrag) {
                dragDrop.cancelMobileDrag(e);
            }
            
            delete pillElement.dataset.touchOnChevron;
        });
        
        // Right-click context menu
        pillElement.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.showContextMenu(e, pillData);
        });
        
        // Register drag event handlers with DragDrop module
        if (dragDrop && dragDrop.registerPillDragHandlers) {
            dragDrop.registerPillDragHandlers(pillElement, pillData);
        }
    }
}

// Export for use in other modules or global scope
window.PillInteraction = PillInteraction;