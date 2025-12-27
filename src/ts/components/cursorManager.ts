/**
 * CursorManager Module for Session Instance Detail Beta
 * Handles cursor positioning, navigation, and text input cursor management
 */

import { TunePillsData } from './stateManager.js';

export interface CursorPosition {
    setIndex: number;
    pillIndex: number;
    position: string;
}

export interface CursorManagerCallbacks {
    finishTyping?(): void;
    removeTemporaryEmptySet?(): boolean;
    renderTunePills?(): void;
    handleTextInput?(char: string): void;
    handleBackspace?(): void;
}

export interface CursorManagerDependencies {
    onCursorChange?: (position: CursorPosition) => void;
    onSelectionChange?: () => void;
    getStateManager(): StateManager;
    temporaryEmptySet?: number | null;
}

export interface StateManager {
    getTunePillsData(): TunePillsData;
}

export interface TypingContext {
    tuneSet: HTMLElement;
    insertionPoint: Node | null;
}

export class CursorManager {
    static cursorPosition: CursorPosition | null = null; // { setIndex, pillIndex, position }
    static selectionAnchor: CursorPosition | null = null; // For shift+arrow selection
    static isTyping: (() => boolean) = () => false; // Callback function set from external code
    static onCursorChange: ((position: CursorPosition) => void) | null = null; // Callback for cursor position changes
    static onSelectionChange: (() => void) | null = null; // Callback for selection changes
    static getStateManager: (() => StateManager) | null = null; // Function to get StateManager reference
    // Selection is now managed by PillSelection module
    static temporaryEmptySet: number | null = null;
    static typingContext: TypingContext | null = null; // Typing context for updateCursorWithText
    
    // Callback functions that need to be set by other modules
    static finishTyping: (() => void) | null = null;
    static removeTemporaryEmptySet: (() => boolean) | null = null;
    static renderTunePills: (() => void) | null = null;
    static handleTextInput: ((char: string) => void) | null = null;
    static handleBackspace: (() => void) | null = null;
    static typingBuffer: (() => string) | null = null; // Will be set by callbacks
    static isKeepingKeyboardOpen: boolean = false; // Will be set by callbacks
    
    static initialize(options: CursorManagerDependencies = {} as CursorManagerDependencies): void {
        this.onCursorChange = options.onCursorChange || null;
        this.onSelectionChange = options.onSelectionChange || null;
        this.getStateManager = options.getStateManager || (() => (window as any).StateManager);
        // Selection is now managed by PillSelection module
        this.temporaryEmptySet = options.temporaryEmptySet || null;
        this.cursorPosition = null;
        this.selectionAnchor = null;
    }
    
    static getCursorPosition(): CursorPosition | null {
        return this.cursorPosition;
    }
    
    static setCursorPosition(setIndex: number, pillIndex: number, positionType: string, maintainKeyboard: boolean = false): void {
        // Use the internal complex setCursorPosition implementation
        this.setCursorPositionOriginal(setIndex, pillIndex, positionType, maintainKeyboard);
        
        // Update selection if shift key is being used
        if (this.selectionAnchor && this.onSelectionChange) {
            this.updateSelection();
        }
    }
    
    static addCursorPosition(parent: HTMLElement, setIndex: number, pillIndex: number, positionType: string): HTMLElement {
        const cursorPos = document.createElement('span');
        cursorPos.className = 'cursor-position';
        cursorPos.dataset.setIndex = setIndex.toString();
        cursorPos.dataset.pillIndex = pillIndex.toString();
        cursorPos.dataset.positionType = positionType;
        
        // Add click handler for cursor positioning
        cursorPos.addEventListener('click', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            
            // If user is typing, finish typing first
            if (this.isTyping && this.isTyping()) {
                this.finishTyping?.();
            }
            
            // Clear selection when clicking to move cursor
            this.clearSelection();
            
            // Remove temporary empty set if clicking away from it
            if (this.removeTemporaryEmptySet && this.removeTemporaryEmptySet()) {
                this.renderTunePills?.();
            }
            
            this.setCursorPosition(setIndex, pillIndex, positionType);
        });
        
        parent.appendChild(cursorPos);
        return cursorPos;
    }
    
    static addFinalCursor(containerElement: HTMLElement): HTMLElement {
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
            
            // Clear selection when clicking to move cursor
            this.clearSelection();
            
            this.setCursorPosition(tunePillsData.length, 0, 'newset');
        });
        
        containerElement.appendChild(finalPos);
        return finalPos;
    }
    
    static isMobileDevice(): boolean {
        return ('ontouchstart' in window || navigator.maxTouchPoints > 0) && 
               (window.innerWidth <= 768 || /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent));
    }
    
    static moveCursorLeft(shiftKey: boolean = false): void {
        if (!this.cursorPosition) return;
        
        // If user is typing, finish typing first
        if (this.isTyping && this.isTyping()) {
            this.finishTyping?.();
        }
        
        // Remove temporary empty set if moving away from it
        if (this.removeTemporaryEmptySet && this.removeTemporaryEmptySet()) {
            this.renderTunePills?.();
        }
        
        let { setIndex, pillIndex, position } = this.cursorPosition;
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        // Set selection anchor if shift is pressed and we don't have one
        if (shiftKey && !this.selectionAnchor) {
            // Set anchor to current position BEFORE moving cursor
            this.selectionAnchor = { setIndex, pillIndex, position };
        } else if (!shiftKey) {
            // Clear selection anchor if shift is not pressed
            this.selectionAnchor = null;
            this.clearSelection();
        }
        
        let newSetIndex = setIndex;
        let newPillIndex = pillIndex;
        let newPosition = position;
        
        if (position === 'after') {
            // Move to 'before' the same pill (this selects the current pill)
            newPosition = 'before';
        } else if (position === 'before' && pillIndex > 0) {
            // Move to 'before' the previous pill (this selects the previous pill)
            newPillIndex = pillIndex - 1;
            newPosition = 'before';
        } else if (position === 'before' && pillIndex === 0 && setIndex > 0) {
            // Move to beginning of previous set
            const prevSetLength = tunePillsData[setIndex - 1]!.length;
            newSetIndex = setIndex - 1;
            newPillIndex = prevSetLength - 1;
            newPosition = 'before';
        } else {
            // Can't move further left
            return;
        }
        
        this.setCursorPosition(newSetIndex, newPillIndex, newPosition);
        
        // Update selection if shift key is pressed
        if (shiftKey && this.selectionAnchor) {
            this.updateSelection();
        }
    }
    
    static moveCursorRight(shiftKey: boolean = false): void {
        if (!this.cursorPosition) return;
        
        // If user is typing, finish typing first
        if (this.isTyping && this.isTyping()) {
            this.finishTyping?.();
        }
        
        // Remove temporary empty set if moving away from it
        if (this.removeTemporaryEmptySet && this.removeTemporaryEmptySet()) {
            this.renderTunePills?.();
        }
        
        let { setIndex, pillIndex, position } = this.cursorPosition;
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        // Set selection anchor if shift is pressed and we don't have one
        if (shiftKey && !this.selectionAnchor) {
            // Set anchor to current position BEFORE moving cursor
            this.selectionAnchor = { setIndex, pillIndex, position };
        } else if (!shiftKey) {
            // Clear selection anchor if shift is not pressed
            this.selectionAnchor = null;
            this.clearSelection();
        }
        
        let newSetIndex = setIndex;
        let newPillIndex = pillIndex;
        let newPosition = position;
        
        if (position === 'before') {
            // Move to 'after' the same pill (this selects the current pill)
            newPosition = 'after';
        } else if (position === 'after' && pillIndex < tunePillsData[setIndex]!.length - 1) {
            // Move to 'after' the next pill (this selects the next pill)
            newPillIndex = pillIndex + 1;
            newPosition = 'after';
        } else if (position === 'after' && setIndex < tunePillsData.length - 1) {
            // Move to after the first pill of next set (so it gets selected immediately)
            newSetIndex = setIndex + 1;
            newPillIndex = 0;
            newPosition = 'after';
        } else if (position === 'after' && setIndex === tunePillsData.length - 1) {
            // Move to final position (new set)
            newSetIndex = tunePillsData.length;
            newPillIndex = 0;
            newPosition = 'newset';
        } else {
            // Can't move further right
            return;
        }
        
        this.setCursorPosition(newSetIndex, newPillIndex, newPosition);
        
        // Update selection if shift key is pressed
        if (shiftKey && this.selectionAnchor) {
            this.updateSelection();
        }
    }
    
    static moveCursorUp(shiftKey: boolean = false): void {
        if (!this.cursorPosition) return;
        
        let { setIndex, pillIndex, position } = this.cursorPosition;
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        // Set selection anchor if shift is pressed and we don't have one
        if (shiftKey && !this.selectionAnchor) {
            this.selectionAnchor = { setIndex, pillIndex, position };
        } else if (!shiftKey) {
            this.selectionAnchor = null;
            this.clearSelection();
        }
        
        let newSetIndex = setIndex;
        let newPillIndex = pillIndex;
        let newPosition = position;
        
        // Move to previous set if possible
        if (setIndex > 0) {
            newSetIndex = setIndex - 1;
            const prevSetLength = tunePillsData[newSetIndex]!.length;
            
            // Try to maintain similar position within the set
            if (position === 'newset') {
                newPillIndex = Math.min(pillIndex, prevSetLength - 1);
                newPosition = 'after';
            } else {
                newPillIndex = Math.min(pillIndex, prevSetLength - 1);
                // Keep the same position type if possible
            }
        } else {
            // Already at the top
            return;
        }
        
        this.setCursorPosition(newSetIndex, newPillIndex, newPosition);
        
        if (shiftKey && this.selectionAnchor) {
            this.updateSelection();
        }
    }
    
    static moveCursorDown(shiftKey: boolean = false): void {
        if (!this.cursorPosition) return;
        
        let { setIndex, pillIndex, position } = this.cursorPosition;
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        // Set selection anchor if shift is pressed and we don't have one
        if (shiftKey && !this.selectionAnchor) {
            this.selectionAnchor = { setIndex, pillIndex, position };
        } else if (!shiftKey) {
            this.selectionAnchor = null;
            this.clearSelection();
        }
        
        let newSetIndex = setIndex;
        let newPillIndex = pillIndex;
        let newPosition = position;
        
        // Move to next set if possible
        if (setIndex < tunePillsData.length) {
            newSetIndex = setIndex + 1;
            
            if (newSetIndex === tunePillsData.length) {
                // Moving to the final position
                newPillIndex = 0;
                newPosition = 'newset';
            } else {
                const nextSetLength = tunePillsData[newSetIndex]!.length;
                newPillIndex = Math.min(pillIndex, nextSetLength - 1);
                // Keep the same position type if possible
            }
        } else {
            // Already at the bottom
            return;
        }
        
        this.setCursorPosition(newSetIndex, newPillIndex, newPosition);
        
        if (shiftKey && this.selectionAnchor) {
            this.updateSelection();
        }
    }
    
    static updateCursorWithTextOriginal(): void {
        // Find the active cursor element
        const activeCursor = document.getElementById('active-cursor');
        if (!activeCursor) return;
        
        if (this.isTyping && this.isTyping() && this.typingBuffer && this.typingBuffer()) {
            // On first keystroke, capture the typing context
            if (!this.typingContext) {
                const cursorPosition = activeCursor.parentNode as HTMLElement;
                const tuneSet = cursorPosition?.parentNode as HTMLElement;
                
                if (tuneSet && tuneSet.classList.contains('tune-set')) {
                    this.typingContext = {
                        tuneSet: tuneSet,
                        insertionPoint: cursorPosition.nextSibling
                    };
                } else {
                    // Fallback context
                    this.typingContext = {
                        tuneSet: cursorPosition?.parentNode as HTMLElement,
                        insertionPoint: cursorPosition?.nextSibling
                    };
                }
            }
            
            // Remove any existing typing display and cursor
            document.querySelectorAll('.typing-text').forEach(el => el.remove());
            activeCursor.remove();
            
            // Create typing text
            const textSpan = document.createElement('span');
            textSpan.className = 'typing-text';
            
            // Simple styling that behaves like natural text
            textSpan.style.color = 'var(--primary)';
            textSpan.style.backgroundColor = 'rgba(0, 123, 255, 0.1)';
            textSpan.style.padding = '1px 3px';
            textSpan.style.borderRadius = '3px';
            textSpan.style.fontWeight = 'normal';
            textSpan.style.fontStyle = 'normal';
            textSpan.style.display = 'inline';
            textSpan.style.whiteSpace = 'nowrap';
            textSpan.textContent = this.typingBuffer();
            
            // Create new cursor
            const newCursor = document.createElement('div');
            newCursor.className = 'text-cursor';
            newCursor.id = 'active-cursor';
            
            // Insert both text and cursor using stable context
            if (this.typingContext && this.typingContext.tuneSet) {
                this.typingContext.tuneSet.insertBefore(textSpan, this.typingContext.insertionPoint);
                this.typingContext.tuneSet.insertBefore(newCursor, textSpan.nextSibling);
            } else {
                // Emergency fallback - typing context unavailable
            }
            
            // Debug the actual layout
        } else {
            // Remove any typing text display and reset context
            document.querySelectorAll('.typing-text').forEach(el => el.remove());
            
            // Before resetting context, restore cursor to current position if typing just ended
            if (this.typingContext && this.cursorPosition) {
                // Re-render the cursor at the current position to ensure it's in the right place
                const { setIndex, pillIndex, position } = this.cursorPosition;
                this.setCursorPositionOriginal(setIndex, pillIndex, position);
            }
            
            this.typingContext = null;
        }
    }
    
    static updateCursorWithText(): void {
        // Use the internal complex updateCursorWithText implementation
        return this.updateCursorWithTextOriginal();
    }
    
    static clearSelection(): void {
        // Clear selection using PillSelection module
        if ((window as any).PillSelection) {
            (window as any).PillSelection.selectNone();
        }
        
        // Call selection change callback if it exists  
        if (this.onSelectionChange) {
            this.onSelectionChange();
        }
        
        // Clear selection anchor so cursor becomes visible again
        this.selectionAnchor = null;
        
        // Re-render cursor to make it visible again after clearing selection
        if (this.cursorPosition) {
            this.setCursorPositionOriginal(
                this.cursorPosition.setIndex, 
                this.cursorPosition.pillIndex, 
                this.cursorPosition.position
            );
        }
    }
    
    static updateSelection(): void {
        if (!this.selectionAnchor || !this.cursorPosition || !this.onSelectionChange) return;
        
        // Calculate pills between anchor and current cursor position
        const startCursorPos: CursorPosition = { 
            setIndex: this.selectionAnchor.setIndex, 
            pillIndex: this.selectionAnchor.pillIndex, 
            position: this.selectionAnchor.position || 'before'
        };
        const endCursorPos = this.cursorPosition;
        
        // Use PillSelection to handle cursor-based range selection
        if ((window as any).PillSelection && (window as any).PillSelection.selectFromCursorRange) {
            (window as any).PillSelection.selectFromCursorRange(startCursorPos, endCursorPos);
        }
        
        this.onSelectionChange();
    }
    
    static setTypingMode(isTyping: boolean): void {
        // This method is deprecated - isTyping should be set as callback from external code
        this.isTyping = () => isTyping;
    }
    
    static getTypingMode(): boolean {
        return this.isTyping && this.isTyping();
    }
    
    static hasValidCursor(): boolean {
        return this.cursorPosition !== null;
    }
    
    static resetCursor(): void {
        this.cursorPosition = null;
        this.selectionAnchor = null;
        this.isTyping = () => false;
        
        // Remove all active cursor highlights
        document.querySelectorAll('.cursor-position.active').forEach(cursor => {
            cursor.classList.remove('active');
        });
    }
    
    static setDefaultCursor(): void {
        const stateManager = this.getStateManager!();
        const tunePillsData = stateManager.getTunePillsData();
        
        if (tunePillsData.length > 0) {
            this.setCursorPosition(0, 0, 'before');
        } else {
            this.setCursorPosition(0, 0, 'newset');
        }
    }
    
    static setCursorPositionOriginal(setIndex: number, pillIndex: number, positionType: string, maintainKeyboard: boolean = false): void {
        console.log('[setCursorPosition] called with', { setIndex, pillIndex, positionType, maintainKeyboard });

        // Update internal cursor position
        this.cursorPosition = { setIndex, pillIndex, position: positionType };
        
        // Always remove existing cursors before creating new one
        // The cursor should always be visible, whether in selection mode or not

        // Remove all existing cursors so we can place the new one
        document.querySelectorAll('.text-cursor').forEach(cursor => cursor.remove());
        
        // Add cursor at the specified position
        const selector = `.cursor-position[data-set-index="${setIndex}"][data-pill-index="${pillIndex}"][data-position-type="${positionType}"]`;
        const cursorElements = document.querySelectorAll(selector);

        if (cursorElements.length > 0) {
            const cursor = document.createElement('div');
            cursor.className = 'text-cursor';
            cursor.id = 'active-cursor';
            cursorElements[0]!.appendChild(cursor);

            // Only scroll cursor into view for user-initiated actions (not after drag/drop)
            // Skip scrolling to prevent unwanted view changes after move operations
        } else {
            // Fallback - add cursor at the end
            const cursor = document.createElement('div');
            cursor.className = 'text-cursor';
            cursor.id = 'active-cursor';
            document.getElementById('tune-pills-container')!.appendChild(cursor);
        }
        
        // Focus the container for keyboard input
        const container = document.getElementById('tune-pills-container')!;
        
        // On mobile devices, make container contenteditable to trigger keyboard
        // BUT NOT if a modal is open - modals need exclusive keyboard access
        const hasOpenModal = document.body.classList.contains('modal-open');
        if (this.isMobileDevice() && !hasOpenModal) {
            // Check if contentEditable is already true (keyboard already open)
            const wasAlreadyEditable = container.contentEditable === 'true';

            // Make the container contenteditable temporarily
            container.contentEditable = 'true';
            (container as any).inputMode = 'text';
            
            // Focus - with special handling for maintaining keyboard
            // But don't steal focus if a popout is open (user might be interacting with it)
            const popoutActive = (window as any).popoutActive === true;

            if (popoutActive) {
                console.log('[setCursorPosition] skipping focus - popout is active');
            } else if (maintainKeyboard) {
                // When maintaining keyboard, always focus to keep it visible
                container.focus();

                // Add a delayed re-focus attempt for stubborn mobile browsers
                setTimeout(() => {
                    // Check again for popout before re-focusing
                    if (container.contentEditable === 'true' && !(window as any).popoutActive) {
                        container.focus();
                    }
                }, 100);
            } else {
                // Normal focus for new keyboard activation
                container.focus();
            }
            
            // Place the selection at the cursor position
            const selection = window.getSelection()!;
            const range = document.createRange();
            
            // Try to position the caret near the cursor element
            const cursorElement = document.getElementById('active-cursor');
            if (cursorElement && cursorElement.parentNode) {
                range.setStartBefore(cursorElement);
                range.collapse(true);
                selection.removeAllRanges();
                selection.addRange(range);
            }
            
            // Handle input on the contenteditable container
            if (!container.hasAttribute('data-mobile-input-setup')) {
                container.setAttribute('data-mobile-input-setup', 'true');
                
                // Prevent default contenteditable behavior
                container.addEventListener('beforeinput', (e: Event) => {
                    const inputEvent = e as InputEvent;
                    e.preventDefault();
                    
                    if (inputEvent.inputType === 'insertText' && inputEvent.data) {
                        // Handle text input
                        for (let char of inputEvent.data) {
                            if (char === ',' || char === ';') {
                                this.finishTyping?.();
                            } else {
                                this.handleTextInput?.(char);
                            }
                        }
                    } else if (inputEvent.inputType === 'deleteContentBackward') {
                        // Handle backspace
                        this.handleBackspace?.();
                    } else if (inputEvent.inputType === 'insertParagraph' || inputEvent.inputType === 'insertLineBreak') {
                        // Handle enter key - keep keyboard open for continued typing
                        e.preventDefault();
                        
                        // Store that we want to keep keyboard open
                        const shouldKeepKeyboard = this.isTyping && this.isTyping() && this.typingBuffer && this.typingBuffer().trim();
                        
                        this.finishTyping?.();
                    }
                });
                
                // Prevent any actual content changes to the container
                container.addEventListener('input', (e: Event) => {
                    e.preventDefault();
                    e.stopPropagation();
                });
                
                // Clean up on blur
                container.addEventListener('blur', (e: Event) => {
                    // Only remove contenteditable if we're really blurring
                    setTimeout(() => {
                        const activeEl = document.activeElement;
                        if (activeEl !== container && !container.contains(activeEl)) {
                            // Don't interfere if we're intentionally keeping keyboard open
                            if (!this.isKeepingKeyboardOpen) {
                                container.contentEditable = 'false';
                                if (this.isTyping && this.isTyping() && this.typingBuffer && this.typingBuffer().trim()) {
                                    this.finishTyping?.();
                                }
                            }
                        }
                    }, 100);
                });
            }
        } else {
            // Desktop behavior - just focus normally
            if (!(window as any).popoutActive) {
                container.focus();
            }
        }
        
        // Trigger cursor change callback
        if (this.onCursorChange) {
            this.onCursorChange(this.cursorPosition);
        }
    }
    
    // Helper method to register external functions that CursorManager needs to call
    static registerCallbacks(callbacks: CursorManagerCallbacks = {}): void {
        this.finishTyping = callbacks.finishTyping || null;
        this.removeTemporaryEmptySet = callbacks.removeTemporaryEmptySet || null;
        this.renderTunePills = callbacks.renderTunePills || null;
        this.handleTextInput = callbacks.handleTextInput || null;
        this.handleBackspace = callbacks.handleBackspace || null;
        this.typingBuffer = null; // Will be set by callbacks
        this.isKeepingKeyboardOpen = false; // Will be set by callbacks
    }
}

// Export for use in other modules or global scope
declare global {
    interface Window {
        CursorManager: typeof CursorManager;
    }
}

(window as any).CursorManager = CursorManager;