/**
 * PillInteraction Module for Session Instance Detail Beta
 * Handles all pill interaction events including clicks, touches, selection, and context menus
 * Delegates drag & drop specific functionality to the DragDrop module
 */

// Type definitions
export interface PillData {
    id: string;
    tuneId: number | null;
    tuneName: string;
    setting: string;
    tuneType: string;
    state: 'linked' | 'unlinked';
}

export interface PillSelection {
    isSelected(pillId: string): boolean;
    removeSelection(pillId: string): void;
    addSelection(pillId: string): void;
    getSelectionCount(): number;
    extendSelection(pillId: string): void;
    selectSingle(pillId: string): void;
    getSelectedPills(): string[];
}

export interface CursorManager {
    selectionAnchor: any;
}

export interface DragDrop {
    registerPillDragHandlers?(pillElement: HTMLElement, pillData: PillData): void;
    startMobileDrag?(event: TouchEvent, pillData: PillData): void;
    handleMobileDragMove?(event: TouchEvent): void;
    endMobileDrag?(event: TouchEvent): void;
    cancelMobileDrag?(event: TouchEvent): void;
}

export interface StateManager {
    // Define StateManager methods as needed
}

export interface PillInteractionCallbacks {
    [key: string]: any; // Allow dynamic callback assignment
}

export interface PillInteractionOptions {
    getPillSelection?: () => PillSelection;
    getStateManager?: () => StateManager;
    getCursorManager?: () => CursorManager;
    getDragDrop?: () => DragDrop;
    showContextMenu?: (event: MouseEvent | TouchEventLike, pillData: PillData) => void;
    hideContextMenu?: (pillId?: string) => void;
    isTyping?: () => boolean;
    finishTyping?: () => void;
}

// Custom type for fake touch events
export interface TouchEventLike {
    clientX: number;
    clientY: number;
    target: HTMLElement;
    preventDefault: () => void;
    stopPropagation: () => void;
}

export class PillInteraction {
    // External dependencies that need to be registered
    private static getPillSelection: (() => PillSelection) | null = null;
    private static getStateManager: (() => StateManager) | null = null;
    private static getCursorManager: (() => CursorManager) | null = null;
    private static getDragDrop: (() => DragDrop) | null = null;
    private static showContextMenu: ((event: MouseEvent | TouchEventLike, pillData: PillData) => void) | null = null;
    private static hideContextMenu: ((pillId?: string) => void) | null = null;
    private static isTyping: (() => boolean) | null = null;
    private static finishTyping: (() => void) | null = null;
    
    public static initialize(options: PillInteractionOptions = {}): void {
        this.getPillSelection = options.getPillSelection || (() => (window as any).PillSelection);
        this.getStateManager = options.getStateManager || (() => (window as any).StateManager);
        this.getCursorManager = options.getCursorManager || (() => (window as any).CursorManager);
        this.getDragDrop = options.getDragDrop || (() => (window as any).DragDrop);
        this.showContextMenu = options.showContextMenu || (window as any).showContextMenu;
        this.hideContextMenu = options.hideContextMenu || (window as any).hideContextMenu;
        this.isTyping = options.isTyping || (() => false);
        this.finishTyping = options.finishTyping || (() => {});
    }
    
    public static registerCallbacks(callbacks: PillInteractionCallbacks): void {
        Object.assign(this, callbacks);
    }
    
    public static setupPillEventListeners(pillElement: HTMLElement, pillData: PillData): void {
        const pillSelection = this.getPillSelection?.();
        const dragDrop = this.getDragDrop?.();
        
        if (!pillSelection) {
            console.warn('PillSelection not available');
            return;
        }
        
        // Click to select or show context menu
        pillElement.addEventListener('click', (e: MouseEvent) => {
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
                    this.hideContextMenu && this.hideContextMenu(pillData.id);
                } else {
                    // Menu is closed, open it
                    this.showContextMenu && this.showContextMenu(e, pillData);
                }
            } else {
                // Clicked on tune name area - handle selection
                e.preventDefault();
                e.stopPropagation();
                
                // If user is typing, finish typing first
                if (this.isTyping && this.isTyping()) {
                    this.finishTyping && this.finishTyping();
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
                    const cursorManager = this.getCursorManager?.();
                    if (cursorManager && cursorManager.selectionAnchor !== null) {
                        cursorManager.selectionAnchor = null;
                    }
                }
            }
        });
        
        // Touch handling for mobile interactions
        let touchStartTime = 0;
        let longPressTimer: number | null = null;
        let isDragMode = false;
        let touchStartX = 0, touchStartY = 0;
        
        pillElement.addEventListener('touchstart', (e: TouchEvent) => {
            touchStartTime = Date.now();
            if (longPressTimer) {
                clearTimeout(longPressTimer);
            }
            isDragMode = false;
            
            const touch = e.touches[0];
            if (!touch) return;
            
            touchStartX = touch.clientX;
            touchStartY = touch.clientY;
            
            // Calculate if touch is on the left side (chevron area)
            const rect = pillElement.getBoundingClientRect();
            const touchX = touch.clientX - rect.left;
            const isChevronArea = touchX <= 30;
            
            // Store chevron state for later use
            pillElement.dataset.touchOnChevron = isChevronArea.toString();
            
            if (!isChevronArea) {
                // Only set up long press for drag if not on chevron
                longPressTimer = window.setTimeout(() => {
                    // Enter drag mode
                    isDragMode = true;
                    pillElement.classList.add('dragging');

                    // Hide any open context menu when entering drag mode
                    this.hideContextMenu && this.hideContextMenu();

                    // If pill isn't selected, select it
                    if (!pillSelection.isSelected(pillData.id)) {
                        pillSelection.selectSingle(pillData.id);
                    }
                    
                    // Add dragging class to all selected pills
                    pillSelection.getSelectedPills().forEach(pillId => {
                        const pill = document.querySelector(`[data-pill-id="${pillId}"]`) as HTMLElement;
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
        
        pillElement.addEventListener('touchmove', (e: TouchEvent) => {
            const touch = e.touches[0];
            if (!touch) return;

            // If not yet in drag mode, check if user moved too much - cancel the long press
            if (!isDragMode && longPressTimer) {
                const deltaX = Math.abs(touch.clientX - touchStartX);
                const deltaY = Math.abs(touch.clientY - touchStartY);
                // If moved more than 10px, cancel the long press timer (user is scrolling)
                if (deltaX > 10 || deltaY > 10) {
                    clearTimeout(longPressTimer);
                    longPressTimer = null;
                }
            }

            if (isDragMode && dragDrop && dragDrop.handleMobileDragMove) {
                // Only prevent default if the event is cancelable (not already scrolling)
                if (e.cancelable) {
                    e.preventDefault();
                }
                dragDrop.handleMobileDragMove(e);
            }
        }, { passive: false }); // passive: false allows us to call preventDefault
        
        pillElement.addEventListener('touchend', (e: TouchEvent) => {
            if (longPressTimer) {
                clearTimeout(longPressTimer);
            }
            
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
                if (!touch) return;
                
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
                            this.hideContextMenu && this.hideContextMenu(pillData.id);
                        } else {
                            // Menu is closed, open it
                            // Create a fake event with the touch coordinates
                            const fakeEvent: TouchEventLike = {
                                clientX: touch.clientX,
                                clientY: touch.clientY,
                                target: pillElement,
                                preventDefault: () => {},
                                stopPropagation: () => {}
                            };
                            this.showContextMenu && this.showContextMenu(fakeEvent, pillData);
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
        
        pillElement.addEventListener('touchcancel', (e: TouchEvent) => {
            if (longPressTimer) {
                clearTimeout(longPressTimer);
            }
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
        
        // Right-click context menu (desktop only - mobile uses chevron)
        pillElement.addEventListener('contextmenu', (e: MouseEvent) => {
            e.preventDefault();
            // On mobile/touch devices, don't show context menu on long-press
            // Users should use the chevron instead
            const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
            if (!isTouchDevice) {
                this.showContextMenu && this.showContextMenu(e, pillData);
            }
        });
        
        // Register drag event handlers with DragDrop module
        if (dragDrop && dragDrop.registerPillDragHandlers) {
            dragDrop.registerPillDragHandlers(pillElement, pillData);
        }
    }
}

// Export for use in other modules or global scope
declare global {
    interface Window {
        PillInteraction: typeof PillInteraction;
    }
}

(window as any).PillInteraction = PillInteraction;