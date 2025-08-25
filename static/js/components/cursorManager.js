/**
 * CursorManager Module for Session Instance Detail Beta
 * Handles cursor positioning, navigation, and text input cursor management
 */

class CursorManager {
    static cursorPosition = null; // { setIndex, pillIndex, position }
    static selectionAnchor = null; // For shift+arrow selection
    static isTyping = () => false; // Callback function set from external code
    static onCursorChange = null; // Callback for cursor position changes
    static onSelectionChange = null; // Callback for selection changes
    static getStateManager = null; // Function to get StateManager reference
    // Selection is now managed by PillSelection module
    static temporaryEmptySet = null;
    static typingContext = null; // Typing context for updateCursorWithText
    
    static initialize(options = {}) {
        this.onCursorChange = options.onCursorChange;
        this.onSelectionChange = options.onSelectionChange;
        this.getStateManager = options.getStateManager || (() => window.StateManager);
        // Selection is now managed by PillSelection module
        this.temporaryEmptySet = options.temporaryEmptySet || null;
        this.cursorPosition = null;
        this.selectionAnchor = null;
    }
    
    static getCursorPosition() {
        return this.cursorPosition;
    }
    
    static setCursorPosition(setIndex, pillIndex, positionType, maintainKeyboard = false) {
        // Use the internal complex setCursorPosition implementation
        this.setCursorPositionOriginal(setIndex, pillIndex, positionType, maintainKeyboard);
        
        // Update selection if shift key is being used
        if (this.selectionAnchor && this.onSelectionChange) {
            this.updateSelection();
        }
    }
    
    static addCursorPosition(parent, setIndex, pillIndex, positionType) {
        const cursorPos = document.createElement('span');
        cursorPos.className = 'cursor-position';
        cursorPos.dataset.setIndex = setIndex;
        cursorPos.dataset.pillIndex = pillIndex;
        cursorPos.dataset.positionType = positionType;
        
        // Add click handler for cursor positioning
        cursorPos.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            // If user is typing, finish typing first
            if (this.isTyping && this.isTyping()) {
                this.finishTyping();
            }
            
            // Clear selection when clicking to move cursor
            this.clearSelection();
            
            // Remove temporary empty set if clicking away from it
            if (this.removeTemporaryEmptySet && this.removeTemporaryEmptySet()) {
                this.renderTunePills && this.renderTunePills();
            }
            
            this.setCursorPosition(setIndex, pillIndex, positionType);
        });
        
        parent.appendChild(cursorPos);
        return cursorPos;
    }
    
    static addFinalCursor(containerElement) {
        const stateManager = this.getStateManager();
        const tunePillsData = stateManager.getTunePillsData();
        
        const finalPos = document.createElement('span');
        finalPos.className = 'cursor-position';
        finalPos.dataset.setIndex = tunePillsData.length;
        finalPos.dataset.pillIndex = 0;
        finalPos.dataset.positionType = 'newset';
        
        finalPos.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Clear selection when clicking to move cursor
            this.clearSelection();
            
            this.setCursorPosition(tunePillsData.length, 0, 'newset');
        });
        
        containerElement.appendChild(finalPos);
        return finalPos;
    }
    
    static isMobileDevice() {
        return ('ontouchstart' in window || navigator.maxTouchPoints > 0) && 
               (window.innerWidth <= 768 || /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent));
    }
    
    static moveCursorLeft(shiftKey = false) {
        if (!this.cursorPosition) return;
        
        // If user is typing, finish typing first
        if (this.isTyping && this.isTyping()) {
            this.finishTyping && this.finishTyping();
        }
        
        // Remove temporary empty set if moving away from it
        if (this.removeTemporaryEmptySet && this.removeTemporaryEmptySet()) {
            this.renderTunePills && this.renderTunePills();
        }
        
        let { setIndex, pillIndex, position } = this.cursorPosition;
        const stateManager = this.getStateManager();
        const tunePillsData = stateManager.getTunePillsData();
        
        // Set selection anchor if shift is pressed and we don't have one
        if (shiftKey && !this.selectionAnchor) {
            // Set anchor to current position BEFORE moving cursor
            this.selectionAnchor = { setIndex, pillIndex, position };
            console.log('CursorManager.moveCursorLeft: Setting selection anchor to:', this.selectionAnchor);
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
            const prevSetLength = tunePillsData[setIndex - 1].length;
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
            console.log('CursorManager.moveCursorLeft: Updating selection after cursor move');
            console.log('  Selection anchor:', this.selectionAnchor);
            console.log('  Current cursor:', this.cursorPosition);
            this.updateSelection();
            console.log('  Selection update complete');
        }
    }
    
    static moveCursorRight(shiftKey = false) {
        if (!this.cursorPosition) return;
        
        // If user is typing, finish typing first
        if (this.isTyping && this.isTyping()) {
            this.finishTyping && this.finishTyping();
        }
        
        // Remove temporary empty set if moving away from it
        if (this.removeTemporaryEmptySet && this.removeTemporaryEmptySet()) {
            this.renderTunePills && this.renderTunePills();
        }
        
        let { setIndex, pillIndex, position } = this.cursorPosition;
        const stateManager = this.getStateManager();
        const tunePillsData = stateManager.getTunePillsData();
        
        // Set selection anchor if shift is pressed and we don't have one
        if (shiftKey && !this.selectionAnchor) {
            // Set anchor to current position BEFORE moving cursor
            this.selectionAnchor = { setIndex, pillIndex, position };
            console.log('CursorManager.moveCursorRight: Setting selection anchor to:', this.selectionAnchor);
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
        } else if (position === 'after' && pillIndex < tunePillsData[setIndex].length - 1) {
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
            console.log('CursorManager.moveCursorRight: Updating selection after cursor move');
            console.log('  Selection anchor:', this.selectionAnchor);
            console.log('  Current cursor:', this.cursorPosition);
            this.updateSelection();
            console.log('  Selection update complete');
        }
    }
    
    static moveCursorUp(shiftKey = false) {
        if (!this.cursorPosition) return;
        
        let { setIndex, pillIndex, position } = this.cursorPosition;
        const stateManager = this.getStateManager();
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
            const prevSetLength = tunePillsData[newSetIndex].length;
            
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
    
    static moveCursorDown(shiftKey = false) {
        if (!this.cursorPosition) return;
        
        let { setIndex, pillIndex, position } = this.cursorPosition;
        const stateManager = this.getStateManager();
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
                const nextSetLength = tunePillsData[newSetIndex].length;
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
    
    static updateCursorWithTextOriginal() {
        // Find the active cursor element
        const activeCursor = document.getElementById('active-cursor');
        if (!activeCursor) return;
        
        if (this.isTyping && this.isTyping() && this.typingBuffer && this.typingBuffer()) {
            // On first keystroke, capture the typing context
            if (!this.typingContext) {
                const cursorPosition = activeCursor.parentNode;
                const tuneSet = cursorPosition?.parentNode;
                
                if (tuneSet && tuneSet.classList.contains('tune-set')) {
                    this.typingContext = {
                        tuneSet: tuneSet,
                        insertionPoint: cursorPosition.nextSibling
                    };
                } else {
                    // Fallback context
                    this.typingContext = {
                        tuneSet: cursorPosition?.parentNode,
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
                // Emergency fallback
                console.error('CursorManager: No typing context available!');
            }
            
            // Debug the actual layout
        } else {
            // Remove any typing text display and reset context
            document.querySelectorAll('.typing-text').forEach(el => el.remove());
            this.typingContext = null;
        }
    }
    
    static updateCursorWithText() {
        // Use the internal complex updateCursorWithText implementation
        return this.updateCursorWithTextOriginal();
    }
    
    static clearSelection() {
        console.log('CursorManager.clearSelection: Called');
        // Clear selection using PillSelection module
        if (window.PillSelection) {
            window.PillSelection.selectNone();
        }
        
        // Call selection change callback if it exists  
        if (this.onSelectionChange) {
            this.onSelectionChange();
        }
        
        // Clear selection anchor so cursor becomes visible again
        this.selectionAnchor = null;
        
        // Re-render cursor to make it visible again after clearing selection
        if (this.cursorPosition) {
            console.log('CursorManager.clearSelection: Re-rendering cursor at', this.cursorPosition);
            this.setCursorPositionOriginal(
                this.cursorPosition.setIndex, 
                this.cursorPosition.pillIndex, 
                this.cursorPosition.position
            );
        }
    }
    
    static updateSelection() {
        if (!this.selectionAnchor || !this.cursorPosition || !this.onSelectionChange) return;
        
        // Calculate pills between anchor and current cursor position
        const startCursorPos = { 
            setIndex: this.selectionAnchor.setIndex, 
            pillIndex: this.selectionAnchor.pillIndex, 
            position: this.selectionAnchor.position || 'before'
        };
        const endCursorPos = this.cursorPosition;
        
        // Use PillSelection to handle cursor-based range selection
        if (window.PillSelection && window.PillSelection.selectFromCursorRange) {
            window.PillSelection.selectFromCursorRange(startCursorPos, endCursorPos);
        }
        
        this.onSelectionChange();
    }
    
    static setTypingMode(isTyping) {
        // This method is deprecated - isTyping should be set as callback from external code
        this.isTyping = () => isTyping;
    }
    
    static getTypingMode() {
        return this.isTyping && this.isTyping();
    }
    
    static hasValidCursor() {
        return this.cursorPosition !== null;
    }
    
    static resetCursor() {
        this.cursorPosition = null;
        this.selectionAnchor = null;
        this.isTyping = () => false;
        
        // Remove all active cursor highlights
        document.querySelectorAll('.cursor-position.active').forEach(cursor => {
            cursor.classList.remove('active');
        });
    }
    
    static setDefaultCursor() {
        const stateManager = this.getStateManager();
        const tunePillsData = stateManager.getTunePillsData();
        
        if (tunePillsData.length > 0) {
            this.setCursorPosition(0, 0, 'before');
        } else {
            this.setCursorPosition(0, 0, 'newset');
        }
    }
    
    static setCursorPositionOriginal(setIndex, pillIndex, positionType, maintainKeyboard = false) {
        // Update internal cursor position
        this.cursorPosition = { setIndex, pillIndex, position: positionType };
        
        // Always remove existing cursors before creating new one
        // The cursor should always be visible, whether in selection mode or not
        const hasSelection = this.selectionAnchor !== null;
        console.log('CursorManager.setCursorPositionOriginal: hasSelection =', hasSelection, 'position =', {setIndex, pillIndex, positionType});
        
        // Remove all existing cursors so we can place the new one
        document.querySelectorAll('.text-cursor').forEach(cursor => cursor.remove());
        
        // Add cursor at the specified position
        const selector = `.cursor-position[data-set-index="${setIndex}"][data-pill-index="${pillIndex}"][data-position-type="${positionType}"]`;
        const cursorElements = document.querySelectorAll(selector);
        
        console.log('CursorManager.setCursorPositionOriginal: Adding cursor, selector =', selector, 'found elements:', cursorElements.length);
        
        if (cursorElements.length > 0) {
            const cursor = document.createElement('div');
            cursor.className = 'text-cursor';
            cursor.id = 'active-cursor';
            cursorElements[0].appendChild(cursor);
            console.log('CursorManager.setCursorPositionOriginal: Added cursor to cursor-position element');
            console.log('  Cursor element:', cursor);
            console.log('  Cursor parent:', cursorElements[0]);
            console.log('  Cursor in DOM:', document.getElementById('active-cursor'));
            
            // Check if cursor is still there after a short delay
            setTimeout(() => {
                const stillThere = document.getElementById('active-cursor');
                console.log('CursorManager.setCursorPositionOriginal: Cursor still in DOM after 100ms:', stillThere);
                if (stillThere) {
                    console.log('  Cursor parent after delay:', stillThere.parentNode);
                    console.log('  Cursor computed style display:', getComputedStyle(stillThere).display);
                    console.log('  Cursor computed style visibility:', getComputedStyle(stillThere).visibility);
                }
            }, 100);
            
            // Only scroll cursor into view for user-initiated actions (not after drag/drop)
            // Skip scrolling to prevent unwanted view changes after move operations
        } else {
            // Fallback - add cursor at the end
            const cursor = document.createElement('div');
            cursor.className = 'text-cursor';
            cursor.id = 'active-cursor';
            document.getElementById('tune-pills-container').appendChild(cursor);
            console.log('CursorManager.setCursorPositionOriginal: Added cursor to container (fallback)');
            console.log('  Cursor element:', cursor);
            console.log('  Cursor in DOM:', document.getElementById('active-cursor'));
        }
        
        // Focus the container for keyboard input
        const container = document.getElementById('tune-pills-container');
        
        // On mobile devices, make container contenteditable to trigger keyboard
        if (this.isMobileDevice()) {
            // Check if contentEditable is already true (keyboard already open)
            const wasAlreadyEditable = container.contentEditable === 'true';
            
            // Make the container contenteditable temporarily
            container.contentEditable = 'true';
            container.inputMode = 'text';
            
            // Focus - with special handling for maintaining keyboard
            if (maintainKeyboard) {
                // When maintaining keyboard, always focus to keep it visible
                container.focus();
                
                // Add a delayed re-focus attempt for stubborn mobile browsers
                setTimeout(() => {
                    if (container.contentEditable === 'true') {
                        container.focus();
                    }
                }, 100);
            } else {
                // Normal focus for new keyboard activation
                container.focus();
            }
            
            // Place the selection at the cursor position
            const selection = window.getSelection();
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
                container.addEventListener('beforeinput', (e) => {
                    e.preventDefault();
                    
                    if (e.inputType === 'insertText' && e.data) {
                        // Handle text input
                        for (let char of e.data) {
                            if (char === ',' || char === ';') {
                                this.finishTyping && this.finishTyping();
                            } else {
                                this.handleTextInput && this.handleTextInput(char);
                            }
                        }
                    } else if (e.inputType === 'deleteContentBackward') {
                        // Handle backspace
                        this.handleBackspace && this.handleBackspace();
                    } else if (e.inputType === 'insertParagraph' || e.inputType === 'insertLineBreak') {
                        // Handle enter key - keep keyboard open for continued typing
                        e.preventDefault();
                        
                        // Store that we want to keep keyboard open
                        const shouldKeepKeyboard = this.isTyping && this.isTyping() && this.typingBuffer && this.typingBuffer.trim();
                        
                        this.finishTyping && this.finishTyping(shouldKeepKeyboard);
                    }
                });
                
                // Prevent any actual content changes to the container
                container.addEventListener('input', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                });
                
                // Clean up on blur
                container.addEventListener('blur', (e) => {
                    // Only remove contenteditable if we're really blurring
                    setTimeout(() => {
                        const activeEl = document.activeElement;
                        if (activeEl !== container && !container.contains(activeEl)) {
                            // Don't interfere if we're intentionally keeping keyboard open
                            if (!this.isKeepingKeyboardOpen) {
                                container.contentEditable = 'false';
                                if (this.isTyping && this.isTyping() && this.typingBuffer && this.typingBuffer.trim()) {
                                    this.finishTyping && this.finishTyping();
                                }
                            }
                        }
                    }, 100);
                });
            }
        } else {
            // Desktop behavior - just focus normally
            container.focus();
        }
        
        // Trigger cursor change callback
        if (this.onCursorChange) {
            this.onCursorChange(this.cursorPosition);
        }
    }
    
    // Helper method to register external functions that CursorManager needs to call
    static registerCallbacks(callbacks = {}) {
        this.finishTyping = callbacks.finishTyping;
        this.removeTemporaryEmptySet = callbacks.removeTemporaryEmptySet;
        this.renderTunePills = callbacks.renderTunePills;
        this.handleTextInput = callbacks.handleTextInput;
        this.handleBackspace = callbacks.handleBackspace;
        this.typingBuffer = null; // Will be set by callbacks
        this.isKeepingKeyboardOpen = false; // Will be set by callbacks
    }
}

// Export for use in other modules or global scope
window.CursorManager = CursorManager;