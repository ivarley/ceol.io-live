/**
 * CursorManager Module for Session Instance Detail Beta
 * Handles cursor positioning, navigation, and text input cursor management
 */

class CursorManager {
    static cursorPosition = null; // { setIndex, pillIndex, position }
    static selectionAnchor = null; // For shift+arrow selection
    static isTyping = false;
    static onCursorChange = null; // Callback for cursor position changes
    static onSelectionChange = null; // Callback for selection changes
    static getStateManager = null; // Function to get StateManager reference
    static selectedPills = null; // Reference to selectedPills Set
    static temporaryEmptySet = null;
    
    static initialize(options = {}) {
        this.onCursorChange = options.onCursorChange;
        this.onSelectionChange = options.onSelectionChange;
        this.getStateManager = options.getStateManager || (() => window.StateManager);
        this.selectedPills = options.selectedPills || new Set();
        this.temporaryEmptySet = options.temporaryEmptySet || null;
        this.cursorPosition = null;
        this.selectionAnchor = null;
    }
    
    static getCursorPosition() {
        return this.cursorPosition;
    }
    
    static setCursorPosition(setIndex, pillIndex, positionType, maintainKeyboard = false) {
        this.cursorPosition = { setIndex, pillIndex, position: positionType };
        
        // Use the original complex setCursorPosition function from the template
        if (window.setCursorPositionOriginal) {
            window.setCursorPositionOriginal(setIndex, pillIndex, positionType, maintainKeyboard);
        }
        
        // Update selection if shift key is being used
        if (this.selectionAnchor && this.onSelectionChange) {
            this.updateSelection();
        }
        
        // Trigger cursor change callback
        if (this.onCursorChange) {
            this.onCursorChange(this.cursorPosition);
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
            if (this.isTyping) {
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
        if (this.isTyping) {
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
            this.selectionAnchor = { setIndex, pillIndex };
        } else if (!shiftKey) {
            // Clear selection anchor if shift is not pressed
            this.selectionAnchor = null;
            this.clearSelection();
        }
        
        let newSetIndex = setIndex;
        let newPillIndex = pillIndex;
        let newPosition = position;
        
        if (position === 'after' && pillIndex > 0) {
            // Move to 'after' the previous pill (which is the same as 'before' current pill)
            newPillIndex = pillIndex - 1;
            newPosition = 'after';
        } else if (position === 'after' && pillIndex === 0) {
            // At beginning of set, try to move to 'before' position if it exists
            newPillIndex = 0;
            newPosition = 'before';
        } else if (position === 'before' && pillIndex === 0 && setIndex > 0) {
            // Move to end of previous set
            const prevSetLength = tunePillsData[setIndex - 1].length;
            newSetIndex = setIndex - 1;
            newPillIndex = prevSetLength - 1;
            newPosition = 'after';
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
    
    static moveCursorRight(shiftKey = false) {
        if (!this.cursorPosition) return;
        
        // If user is typing, finish typing first
        if (this.isTyping) {
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
            this.selectionAnchor = { setIndex, pillIndex };
        } else if (!shiftKey) {
            // Clear selection anchor if shift is not pressed
            this.selectionAnchor = null;
            this.clearSelection();
        }
        
        let newSetIndex = setIndex;
        let newPillIndex = pillIndex;
        let newPosition = position;
        
        if (position === 'before') {
            // Move to 'after' the same pill
            newPosition = 'after';
        } else if (position === 'after' && pillIndex < tunePillsData[setIndex].length - 1) {
            // Move to 'before' the next pill (which is the same as 'after' current pill)
            newPillIndex = pillIndex + 1;
            newPosition = 'before';
        } else if (position === 'after' && setIndex < tunePillsData.length - 1) {
            // Move to beginning of next set
            newSetIndex = setIndex + 1;
            newPillIndex = 0;
            newPosition = 'before';
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
    
    static moveCursorUp(shiftKey = false) {
        if (!this.cursorPosition) return;
        
        let { setIndex, pillIndex, position } = this.cursorPosition;
        const stateManager = this.getStateManager();
        const tunePillsData = stateManager.getTunePillsData();
        
        // Set selection anchor if shift is pressed and we don't have one
        if (shiftKey && !this.selectionAnchor) {
            this.selectionAnchor = { setIndex, pillIndex };
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
            this.selectionAnchor = { setIndex, pillIndex };
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
    
    static updateCursorWithText() {
        // Use the original complex updateCursorWithText function from the template
        if (window.updateCursorWithTextOriginal) {
            return window.updateCursorWithTextOriginal();
        }
        
        // Fallback if original function not available
        const activeCursor = document.getElementById('active-cursor');
        if (!activeCursor) return;
        
        const cursorPosition = activeCursor.parentNode;
        const tuneSet = cursorPosition?.parentNode;
        
        return {
            activeCursor,
            cursorPosition,
            tuneSet,
            insertionPoint: cursorPosition?.nextSibling
        };
    }
    
    static clearSelection() {
        if (this.selectedPills) {
            this.selectedPills.clear();
            if (this.onSelectionChange) {
                this.onSelectionChange();
            }
        }
    }
    
    static updateSelection() {
        if (!this.selectionAnchor || !this.cursorPosition || !this.onSelectionChange) return;
        
        // Calculate pills between anchor and current cursor position
        this.onSelectionChange();
    }
    
    static setTypingMode(isTyping) {
        this.isTyping = isTyping;
    }
    
    static getTypingMode() {
        return this.isTyping;
    }
    
    static hasValidCursor() {
        return this.cursorPosition !== null;
    }
    
    static resetCursor() {
        this.cursorPosition = null;
        this.selectionAnchor = null;
        this.isTyping = false;
        
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
    
    // Helper method to register external functions that CursorManager needs to call
    static registerCallbacks(callbacks = {}) {
        this.finishTyping = callbacks.finishTyping;
        this.removeTemporaryEmptySet = callbacks.removeTemporaryEmptySet;
        this.renderTunePills = callbacks.renderTunePills;
    }
}

// Export for use in other modules or global scope
window.CursorManager = CursorManager;