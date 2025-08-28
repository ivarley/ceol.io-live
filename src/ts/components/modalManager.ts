/**
 * ModalManager - Site-wide Modal and UI Components Management
 * 
 * ARCHITECTURE:
 * - Modal HTML stays in each template (page-specific)
 * - ModalManager provides generic utility functions (no page-specific knowledge)
 * - Each page configures its own modals using generic methods
 * 
 * USAGE:
 * 1. Include modalManager.js in your template
 * 2. Keep your modal HTML in the template
 * 3. Use ModalManager.showModal() or helper methods like showModalWithInput()
 * 4. Handle page-specific business logic in your template's functions
 * 
 * This maintains clean separation of concerns and avoids coupling the
 * ModalManager to specific page knowledge.
 */

// Type definitions
export interface ModalInputConfig {
    selector: string;
    value?: string;
    placeholder?: string;
    select?: boolean;
}

export interface ModalConfig {
    input?: ModalInputConfig;
    data?: Record<string, any>;
    display?: string;
    autoFocus?: boolean;
    closeOnOutsideClick?: boolean;
    populateForm?: boolean;
}

export interface MessageOptions {
    position?: Record<string, string>;
    duration?: number;
}

export type MessageType = 'success' | 'error' | 'warning' | 'info';

export class ModalManager {
    // Current modal state
    private static currentModals = new Set<string>();
    private static messageTimeout: number | null = null;
    
    /**
     * Show a modal by ID with optional configuration
     * @param modalId - The ID of the modal to show
     * @param config - Modal configuration options
     */
    public static showModal(modalId: string, config: ModalConfig = {}): HTMLElement | null {
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.warn(`ModalManager: Modal with ID "${modalId}" not found`);
            return null;
        }
        
        // Apply configuration options
        if (config.input) {
            this.configureInput(modal, config.input);
        }
        
        if (config.data) {
            this.populateModal(modal, config.data);
        }
        
        // Show the modal
        modal.style.display = config.display || 'flex';
        
        // Track active modal
        this.currentModals.add(modalId);
        
        // Focus first input if exists and autoFocus is not disabled
        if (config.autoFocus !== false) {
            this.focusFirstInput(modal);
        }
        
        // Store modal data if provided
        if (config.data) {
            this.storeModalData(modalId, config.data);
        }
        
        // Set up one-time event listeners for this modal instance
        this.setupModalEvents(modal, modalId, config);
        
        return modal;
    }
    
    /**
     * Hide a modal by ID
     * @param modalId - The ID of the modal to hide
     */
    public static hideModal(modalId: string): void {
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.warn(`ModalManager: Modal with ID "${modalId}" not found`);
            return;
        }
        
        modal.style.display = 'none';
        this.currentModals.delete(modalId);
        
        // Clear stored modal data
        this.clearModalData(modalId);
        
        // Remove modal-specific event listeners
        this.cleanupModalEvents(modal);
    }
    
    /**
     * Hide all currently open modals
     */
    public static hideAllModals(): void {
        this.currentModals.forEach(modalId => {
            this.hideModal(modalId);
        });
    }
    
    /**
     * Check if any modals are currently open
     */
    public static hasOpenModals(): boolean {
        return this.currentModals.size > 0;
    }
    
    /**
     * Get list of currently open modal IDs
     */
    public static getOpenModals(): string[] {
        return Array.from(this.currentModals);
    }
    
    /**
     * Configure input field in modal
     */
    private static configureInput(modal: HTMLElement, inputConfig: ModalInputConfig): void {
        const input = modal.querySelector(inputConfig.selector) as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
        if (input) {
            if (inputConfig.value !== undefined) {
                input.value = inputConfig.value;
            }
            if (inputConfig.placeholder !== undefined && 'placeholder' in input) {
                input.placeholder = inputConfig.placeholder;
            }
            if (inputConfig.select && 'select' in input) {
                setTimeout(() => input.select(), 0);
            }
        }
    }
    
    /**
     * Populate modal with data
     */
    private static populateModal(modal: HTMLElement, data: Record<string, any>): void {
        // Look for elements with data-field attributes and populate them
        modal.querySelectorAll('[data-field]').forEach(element => {
            const field = element.getAttribute('data-field');
            if (field && data[field] !== undefined) {
                if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA' || element.tagName === 'SELECT') {
                    (element as HTMLInputElement).value = data[field];
                } else {
                    element.textContent = data[field];
                }
            }
        });
    }
    
    /**
     * Focus first input in modal
     */
    private static focusFirstInput(modal: HTMLElement): void {
        const firstInput = modal.querySelector('input, textarea, select') as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
        if (firstInput) {
            setTimeout(() => {
                firstInput.focus();
                if ('type' in firstInput && (firstInput.type === 'text' || firstInput.type === 'url') && 'select' in firstInput) {
                    firstInput.select();
                }
            }, 0);
        }
    }
    
    /**
     * Store modal data for later retrieval
     */
    private static storeModalData(modalId: string, data: Record<string, any>): void {
        (window as any)[`current${this.capitalizeFirst(modalId)}Data`] = data;
    }
    
    /**
     * Clear stored modal data
     */
    private static clearModalData(modalId: string): void {
        const dataKey = `current${this.capitalizeFirst(modalId)}Data`;
        if ((window as any)[dataKey]) {
            delete (window as any)[dataKey];
        }
    }
    
    /**
     * Set up modal-specific event listeners
     */
    private static setupModalEvents(modal: HTMLElement, modalId: string, config: ModalConfig): void {
        // Click outside to close (if enabled)
        if (config.closeOnOutsideClick !== false) {
            const handler = (e: Event) => {
                if (e.target === modal) {
                    this.hideModal(modalId);
                }
            };
            modal.addEventListener('click', handler);
            (modal as any)._outsideClickHandler = handler;
        }
        
        // Close button handling
        const closeBtn = modal.querySelector('.modal-close, .btn-close, [data-dismiss="modal"]') as HTMLElement;
        if (closeBtn) {
            const closeHandler = (e: Event) => {
                e.preventDefault();
                this.hideModal(modalId);
            };
            closeBtn.addEventListener('click', closeHandler);
            (closeBtn as any)._closeHandler = closeHandler;
        }
    }
    
    /**
     * Clean up modal event listeners
     */
    private static cleanupModalEvents(modal: HTMLElement): void {
        if ((modal as any)._outsideClickHandler) {
            modal.removeEventListener('click', (modal as any)._outsideClickHandler);
            delete (modal as any)._outsideClickHandler;
        }
        
        const closeBtn = modal.querySelector('.modal-close, .btn-close, [data-dismiss="modal"]') as HTMLElement;
        if (closeBtn && (closeBtn as any)._closeHandler) {
            closeBtn.removeEventListener('click', (closeBtn as any)._closeHandler);
            delete (closeBtn as any)._closeHandler;
        }
    }
    
    /**
     * Show a toast message
     * @param message - The message to display
     * @param type - Message type: 'success', 'error', 'warning', 'info'
     * @param options - Display options
     */
    public static showMessage(message: string, type: MessageType = 'success', options: MessageOptions = {}): HTMLElement {
        // Remove any existing messages first
        const existingMessages = document.querySelectorAll('.message');
        existingMessages.forEach(msg => msg.remove());
        
        // Clear existing timeout
        if (this.messageTimeout) {
            clearTimeout(this.messageTimeout);
        }
        
        // Create message element using the base template's existing styles
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = message;
        
        // Apply custom positioning if specified
        if (options.position) {
            Object.assign(messageDiv.style, options.position);
        }
        
        // Add to body (the base template styles handle positioning)
        document.body.appendChild(messageDiv);
        
        // Trigger the slide-in animation using the base template's .show class
        setTimeout(() => {
            messageDiv.classList.add('show');
        }, 50);
        
        // Auto-hide after specified duration (default 4 seconds)
        const duration = options.duration !== undefined ? options.duration : 4000;
        if (duration > 0) {
            this.messageTimeout = window.setTimeout(() => {
                this.hideMessage(messageDiv);
            }, duration);
        }
        
        return messageDiv;
    }
    
    /**
     * Hide a message element
     */
    public static hideMessage(messageElement: HTMLElement): void {
        messageElement.classList.remove('show');
        setTimeout(() => {
            if (messageElement.parentNode) {
                messageElement.remove();
            }
        }, 300);
    }
    
    /**
     * Hide all messages
     */
    public static hideAllMessages(): void {
        const messages = document.querySelectorAll('.message');
        messages.forEach(msg => this.hideMessage(msg as HTMLElement));
    }
    
    /**
     * Confirm dialog using native browser prompt or custom modal
     * @param message - Confirmation message
     * @param onConfirm - Callback for confirmation
     * @param onCancel - Callback for cancellation
     */
    public static confirm(message: string, onConfirm?: () => void, onCancel?: () => void): void {
        // Use native confirm for now - can be enhanced with custom modal later
        if (window.confirm(message)) {
            onConfirm && onConfirm();
        } else {
            onCancel && onCancel();
        }
    }
    
    /**
     * Set up global modal keyboard handling
     * This integrates with KeyboardHandler if available
     */
    private static setupGlobalEvents(): void {
        // ESC key handling for modals (if KeyboardHandler is not available)
        if (!(window as any).KeyboardHandler) {
            document.addEventListener('keydown', (e: KeyboardEvent) => {
                if (e.key === 'Escape' && this.hasOpenModals()) {
                    const openModals = this.getOpenModals();
                    // Close the most recently opened modal
                    if (openModals.length > 0) {
                        this.hideModal(openModals[openModals.length - 1]!);
                    }
                }
            });
        }
    }
    
    /**
     * Utility function to capitalize first letter
     */
    private static capitalizeFirst(str: string): string {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
    
    // Generic helper methods for common patterns (no page-specific knowledge)
    
    /**
     * Show a modal with input configuration
     * @param modalId - The modal ID
     * @param inputSelector - The input element selector
     * @param inputValue - The value to set
     * @param selectText - Whether to select the text
     * @param additionalConfig - Additional configuration
     */
    public static showModalWithInput(
        modalId: string, 
        inputSelector: string, 
        inputValue: string = '', 
        selectText: boolean = false, 
        additionalConfig: ModalConfig = {}
    ): HTMLElement | null {
        return this.showModal(modalId, {
            input: {
                selector: inputSelector,
                value: inputValue,
                select: selectText
            },
            ...additionalConfig
        });
    }
    
    /**
     * Show a modal with form data population
     * @param modalId - The modal ID
     * @param formData - Data to populate form fields
     * @param additionalConfig - Additional configuration
     */
    public static showModalWithData(
        modalId: string, 
        formData: Record<string, any> = {}, 
        additionalConfig: ModalConfig = {}
    ): HTMLElement | null {
        return this.showModal(modalId, {
            data: formData,
            populateForm: true,
            ...additionalConfig
        });
    }
    
    /**
     * Initialize the ModalManager
     */
    public static initialize(): void {
        this.setupGlobalEvents();
        console.log('ModalManager initialized');
    }
}

// Auto-initialize when script loads
document.addEventListener('DOMContentLoaded', () => {
    ModalManager.initialize();
});

// Export for use in other modules or global scope
declare global {
    interface Window {
        ModalManager: typeof ModalManager;
    }
}

(window as any).ModalManager = ModalManager;