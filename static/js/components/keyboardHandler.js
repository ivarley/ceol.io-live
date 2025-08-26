/**
 * KeyboardHandler Module for Session Instance Detail Beta
 * Centralizes all keyboard event handling including shortcuts, navigation, and text input
 */

class KeyboardHandler {
    // External dependencies that need to be registered
    static getCursorManager = null;
    static getPillSelection = null;
    static isTyping = null;
    
    // External functions that need to be called (will be registered via callbacks)
    static handleTextInput = null;
    static handleBackspace = null;
    static handleDelete = null;
    static handleEnterKey = null;
    static finishTyping = null;
    static cancelTyping = null;
    static undo = null;
    static redo = null;
    static copySelectedPills = null;
    static cutSelectedPills = null;
    static pasteFromClipboard = null;
    static hideLinkModal = null;
    static hideEditModal = null;
    static hideSessionEditModal = null;
    static confirmLink = null;
    static confirmEdit = null;
    static removeTypingMatchResults = null;
    static getModalManager = null;
    
    static initialize(options = {}) {
        this.getCursorManager = options.getCursorManager || (() => window.CursorManager);
        this.getPillSelection = options.getPillSelection || (() => window.PillSelection);
        this.isTyping = options.isTyping || (() => false);
        this.getModalManager = options.getModalManager || (() => window.ModalManager);
    }
    
    static registerCallbacks(callbacks) {
        Object.assign(this, callbacks);
    }
    
    static setupKeyboardListeners() {
        // Single unified keyboard handler for all contexts
        document.addEventListener('keydown', (e) => this.handleAllKeydown(e));
    }
    
    static handleAllKeydown(e) {
        // First check for modal-specific handling
        const modalOverlay = e.target.closest('.modal-overlay');
        if (modalOverlay) {
            this.handleModalKeydown(e, modalOverlay);
            return;
        }
        
        // Check for typing match results (document-level temporary menus)
        if (document.querySelector('.typing-match-menu')) {
            this.handleTypingMatchKeydown(e);
            return;
        }
        
        // Handle main application keyboard events
        this.handleMainKeydown(e);
    }
    
    static handleModalKeydown(e, modalOverlay) {
        const modalId = modalOverlay.id;
        
        // Handle Escape key for all modals
        if (e.key === 'Escape') {
            e.preventDefault();
            this.handleModalEscape(e);
            return;
        }
        
        // Handle Enter key for specific modals with inputs
        if (e.key === 'Enter') {
            e.preventDefault();
            
            switch (modalId) {
                case 'link-tune-modal':
                    this.confirmLink && this.confirmLink();
                    break;
                case 'edit-tune-modal':
                    this.confirmEdit && this.confirmEdit();
                    break;
                case 'edit-session-instance-modal':
                    // Could be extended for session edit modal if needed
                    break;
            }
            return;
        }
    }
    
    static handleTypingMatchKeydown(e) {
        // Any keypress removes the typing match results menu
        this.removeTypingMatchResults && this.removeTypingMatchResults();
    }
    
    static handleMainKeydown(e) {
        // Don't handle keyboard events if container is contentEditable (mobile typing mode)
        const container = document.getElementById('tune-pills-container');
        if (container && container.contentEditable === 'true') {
            return;
        }
        
        const cursorManager = this.getCursorManager();
        const pillSelection = this.getPillSelection();
        
        // Handle typing at cursor position
        if (!e.ctrlKey && !e.metaKey && cursorManager.getCursorPosition() && e.key.length === 1) {
            e.preventDefault();
            this.handleTextInput && this.handleTextInput(e.key);
            return;
        }
        
        // Handle special keys for typing when cursor is active
        if (cursorManager.getCursorPosition() && !e.ctrlKey && !e.metaKey) {
            if (this.handleTypingKeys(e)) return;
        }
        
        // Handle modifier key combinations
        if (e.ctrlKey || e.metaKey) {
            this.handleModifierKeys(e);
        } else if (e.key === 'Delete' || e.key === 'Backspace') {
            // Handle selection deletion
            if (pillSelection.hasSelection()) {
                e.preventDefault();
                pillSelection.deleteSelectedPills();
            }
        }
    }
    
    static handleTypingKeys(e) {
        const cursorManager = this.getCursorManager();
        
        switch(e.key) {
            case 'Backspace':
                e.preventDefault();
                this.handleBackspace && this.handleBackspace();
                return true;
            case 'Delete':
                e.preventDefault();
                this.handleDelete && this.handleDelete();
                return true;
            case 'Enter':
                e.preventDefault();
                if (this.isTyping && this.isTyping()) {
                    this.finishTyping && this.finishTyping();
                } else {
                    this.handleEnterKey && this.handleEnterKey();
                }
                return true;
            case 'Tab':
            case ';':
            case ',':
                e.preventDefault();
                this.finishTyping && this.finishTyping();
                return true;
            case 'Escape':
                e.preventDefault();
                this.cancelTyping && this.cancelTyping();
                return true;
            case 'ArrowLeft':
                e.preventDefault();
                cursorManager.moveCursorLeft(e.shiftKey);
                return true;
            case 'ArrowRight':
                e.preventDefault();
                cursorManager.moveCursorRight(e.shiftKey);
                return true;
            case 'ArrowUp':
                e.preventDefault();
                cursorManager.moveCursorUp(e.shiftKey);
                return true;
            case 'ArrowDown':
                e.preventDefault();
                cursorManager.moveCursorDown(e.shiftKey);
                return true;
        }
        
        return false; // Key not handled
    }
    
    static handleModifierKeys(e) {
        const pillSelection = this.getPillSelection();
        
        switch(e.key) {
            case 'z':
                e.preventDefault();
                if (e.shiftKey) {
                    this.redo && this.redo();
                } else {
                    this.undo && this.undo();
                }
                break;
            case 'y':
                e.preventDefault();
                this.redo && this.redo();
                break;
            case 'a':
                e.preventDefault();
                pillSelection.selectAll();
                break;
            case 'c':
                e.preventDefault();
                this.copySelectedPills && this.copySelectedPills();
                break;
            case 'x':
                e.preventDefault();
                this.cutSelectedPills && this.cutSelectedPills();
                break;
            case 'v':
                e.preventDefault();
                this.pasteFromClipboard && this.pasteFromClipboard();
                break;
        }
    }
    
    static handleModalEscape(e) {
        // Use ModalManager if available, otherwise fall back to individual functions
        const modalManager = this.getModalManager && this.getModalManager();
        if (modalManager && modalManager.hideAllModals) {
            modalManager.hideAllModals();
        } else {
            // Fallback to individual modal hide functions
            this.hideLinkModal && this.hideLinkModal();
            this.hideEditModal && this.hideEditModal();
            this.hideSessionEditModal && this.hideSessionEditModal();
        }
    }
}

// Export for use in other modules or global scope
window.KeyboardHandler = KeyboardHandler;