/**
 * KeyboardHandler Module for Session Instance Detail Beta
 * Centralizes all keyboard event handling including shortcuts, navigation, and text input
 */

// Type definitions
export interface CursorManager {
    getCursorPosition(): any;
    moveCursorLeft(shiftKey: boolean): void;
    moveCursorRight(shiftKey: boolean): void;
    moveCursorUp(shiftKey: boolean): void;
    moveCursorDown(shiftKey: boolean): void;
}

export interface PillSelection {
    hasSelection(): boolean;
    deleteSelectedPills(): void;
    selectAll(): void;
}

export interface ModalManager {
    hideAllModals(): void;
}

export interface KeyboardHandlerCallbacks {
    handleTextInput?: (key: string) => void;
    handleBackspace?: () => void;
    handleDelete?: () => void;
    handleEnterKey?: () => void;
    finishTyping?: () => void;
    cancelTyping?: () => void;
    undo?: () => void;
    redo?: () => void;
    copySelectedPills?: () => void;
    cutSelectedPills?: () => void;
    pasteFromClipboard?: () => void;
    hideLinkModal?: () => void;
    hideEditModal?: () => void;
    hideSessionEditModal?: () => void;
    confirmLink?: () => void;
    confirmEdit?: () => void;
    removeTypingMatchResults?: () => void;
}

export interface KeyboardHandlerOptions {
    getCursorManager?: () => CursorManager;
    getPillSelection?: () => PillSelection;
    isTyping?: () => boolean;
    getModalManager?: () => ModalManager;
}

export class KeyboardHandler {
    // External dependencies that need to be registered
    private static getCursorManager: (() => CursorManager) | null = null;
    private static getPillSelection: (() => PillSelection) | null = null;
    private static isTyping: (() => boolean) | null = null;
    private static getModalManager: (() => ModalManager) | null = null;
    
    // External functions that need to be called (will be registered via callbacks)
    private static handleTextInput: ((key: string) => void) | null = null;
    private static handleBackspace: (() => void) | null = null;
    private static handleDelete: (() => void) | null = null;
    private static handleEnterKey: (() => void) | null = null;
    private static finishTyping: (() => void) | null = null;
    private static cancelTyping: (() => void) | null = null;
    private static undo: (() => void) | null = null;
    private static redo: (() => void) | null = null;
    private static copySelectedPills: (() => void) | null = null;
    private static cutSelectedPills: (() => void) | null = null;
    private static pasteFromClipboard: (() => void) | null = null;
    private static hideLinkModal: (() => void) | null = null;
    private static hideEditModal: (() => void) | null = null;
    private static hideSessionEditModal: (() => void) | null = null;
    private static confirmLink: (() => void) | null = null;
    private static confirmEdit: (() => void) | null = null;
    private static removeTypingMatchResults: (() => void) | null = null;
    
    public static initialize(options: KeyboardHandlerOptions = {}): void {
        this.getCursorManager = options.getCursorManager || (() => (window as any).CursorManager);
        this.getPillSelection = options.getPillSelection || (() => (window as any).PillSelection);
        this.isTyping = options.isTyping || (() => false);
        this.getModalManager = options.getModalManager || (() => (window as any).ModalManager);
    }
    
    public static registerCallbacks(callbacks: KeyboardHandlerCallbacks): void {
        Object.assign(this, callbacks);
    }
    
    public static setupKeyboardListeners(): void {
        // Single unified keyboard handler for all contexts
        document.addEventListener('keydown', (e) => this.handleAllKeydown(e));
    }
    
    private static handleAllKeydown(e: KeyboardEvent): void {
        // First check if any modal is open - if so, only handle modal-specific keys
        const openModal = document.querySelector('.modal-overlay[style*="display: flex"], .modal-overlay[style*="display:flex"]') as HTMLElement;
        if (openModal) {
            this.handleModalKeydown(e, openModal);
            return;
        }

        // Check for modal-specific handling based on event target
        const modalOverlay = (e.target as Element).closest('.modal-overlay') as HTMLElement;
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
    
    private static handleModalKeydown(e: KeyboardEvent, modalOverlay: HTMLElement): void {
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

        // For all other keys, allow normal input behavior (don't preventDefault, don't handle)
        // This allows typing in modal input fields
    }
    
    private static handleTypingMatchKeydown(e: KeyboardEvent): void {
        // Any keypress removes the typing match results menu
        this.removeTypingMatchResults && this.removeTypingMatchResults();
    }
    
    private static handleMainKeydown(e: KeyboardEvent): void {
        // Don't handle keyboard events in view mode
        if ((window as any).editorMode === 'view') {
            return;
        }

        const cursorManager = this.getCursorManager?.();
        const pillSelection = this.getPillSelection?.();

        if (!cursorManager || !pillSelection) {
            return; // Dependencies not available
        }
        
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
    
    private static handleTypingKeys(e: KeyboardEvent): boolean {
        const cursorManager = this.getCursorManager?.();
        if (!cursorManager) return false;
        
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
    
    private static handleModifierKeys(e: KeyboardEvent): void {
        const pillSelection = this.getPillSelection?.();
        if (!pillSelection) return;
        
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
    
    private static handleModalEscape(e: KeyboardEvent): void {
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
declare global {
    interface Window {
        KeyboardHandler: typeof KeyboardHandler;
    }
}

(window as any).KeyboardHandler = KeyboardHandler;