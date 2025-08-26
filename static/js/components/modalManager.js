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

class ModalManager {
    // Current modal state
    static currentModals = new Set();
    static messageTimeout = null;
    
    /**
     * Show a modal by ID with optional configuration
     * @param {string} modalId - The ID of the modal to show
     * @param {Object} config - Modal configuration options
     */
    static showModal(modalId, config = {}) {
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.warn(`ModalManager: Modal with ID "${modalId}" not found`);
            return;
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
     * @param {string} modalId - The ID of the modal to hide
     */
    static hideModal(modalId) {
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
    static hideAllModals() {
        this.currentModals.forEach(modalId => {
            this.hideModal(modalId);
        });
    }
    
    /**
     * Check if any modals are currently open
     */
    static hasOpenModals() {
        return this.currentModals.size > 0;
    }
    
    /**
     * Get list of currently open modal IDs
     */
    static getOpenModals() {
        return Array.from(this.currentModals);
    }
    
    /**
     * Configure input field in modal
     */
    static configureInput(modal, inputConfig) {
        const input = modal.querySelector(inputConfig.selector);
        if (input) {
            if (inputConfig.value !== undefined) {
                input.value = inputConfig.value;
            }
            if (inputConfig.placeholder !== undefined) {
                input.placeholder = inputConfig.placeholder;
            }
            if (inputConfig.select) {
                setTimeout(() => input.select(), 0);
            }
        }
    }
    
    /**
     * Populate modal with data
     */
    static populateModal(modal, data) {
        // Look for elements with data-field attributes and populate them
        modal.querySelectorAll('[data-field]').forEach(element => {
            const field = element.getAttribute('data-field');
            if (data[field] !== undefined) {
                if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA' || element.tagName === 'SELECT') {
                    element.value = data[field];
                } else {
                    element.textContent = data[field];
                }
            }
        });
    }
    
    /**
     * Focus first input in modal
     */
    static focusFirstInput(modal) {
        const firstInput = modal.querySelector('input, textarea, select');
        if (firstInput) {
            setTimeout(() => {
                firstInput.focus();
                if (firstInput.type === 'text' || firstInput.type === 'url') {
                    firstInput.select();
                }
            }, 0);
        }
    }
    
    /**
     * Store modal data for later retrieval
     */
    static storeModalData(modalId, data) {
        window[`current${this.capitalizeFirst(modalId)}Data`] = data;
    }
    
    /**
     * Clear stored modal data
     */
    static clearModalData(modalId) {
        const dataKey = `current${this.capitalizeFirst(modalId)}Data`;
        if (window[dataKey]) {
            delete window[dataKey];
        }
    }
    
    /**
     * Set up modal-specific event listeners
     */
    static setupModalEvents(modal, modalId, config) {
        // Click outside to close (if enabled)
        if (config.closeOnOutsideClick !== false) {
            const handler = (e) => {
                if (e.target === modal) {
                    this.hideModal(modalId);
                }
            };
            modal.addEventListener('click', handler);
            modal._outsideClickHandler = handler;
        }
        
        // Close button handling
        const closeBtn = modal.querySelector('.modal-close, .btn-close, [data-dismiss="modal"]');
        if (closeBtn) {
            const closeHandler = (e) => {
                e.preventDefault();
                this.hideModal(modalId);
            };
            closeBtn.addEventListener('click', closeHandler);
            closeBtn._closeHandler = closeHandler;
        }
    }
    
    /**
     * Clean up modal event listeners
     */
    static cleanupModalEvents(modal) {
        if (modal._outsideClickHandler) {
            modal.removeEventListener('click', modal._outsideClickHandler);
            delete modal._outsideClickHandler;
        }
        
        const closeBtn = modal.querySelector('.modal-close, .btn-close, [data-dismiss="modal"]');
        if (closeBtn && closeBtn._closeHandler) {
            closeBtn.removeEventListener('click', closeBtn._closeHandler);
            delete closeBtn._closeHandler;
        }
    }
    
    /**
     * Show a toast message
     * @param {string} message - The message to display
     * @param {string} type - Message type: 'success', 'error', 'warning', 'info'
     * @param {Object} options - Display options
     */
    static showMessage(message, type = 'success', options = {}) {
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
            this.messageTimeout = setTimeout(() => {
                this.hideMessage(messageDiv);
            }, duration);
        }
        
        return messageDiv;
    }
    
    /**
     * Hide a message element
     */
    static hideMessage(messageElement) {
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
    static hideAllMessages() {
        const messages = document.querySelectorAll('.message');
        messages.forEach(msg => this.hideMessage(msg));
    }
    
    /**
     * Confirm dialog using native browser prompt or custom modal
     * @param {string} message - Confirmation message
     * @param {Function} onConfirm - Callback for confirmation
     * @param {Function} onCancel - Callback for cancellation
     */
    static confirm(message, onConfirm, onCancel = null) {
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
    static setupGlobalEvents() {
        // ESC key handling for modals (if KeyboardHandler is not available)
        if (!window.KeyboardHandler) {
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.hasOpenModals()) {
                    const openModals = this.getOpenModals();
                    // Close the most recently opened modal
                    if (openModals.length > 0) {
                        this.hideModal(openModals[openModals.length - 1]);
                    }
                }
            });
        }
    }
    
    /**
     * Utility function to capitalize first letter
     */
    static capitalizeFirst(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
    
    // Generic helper methods for common patterns (no page-specific knowledge)
    
    /**
     * Show a modal with input configuration
     * @param {string} modalId - The modal ID
     * @param {string} inputSelector - The input element selector
     * @param {string} inputValue - The value to set
     * @param {boolean} selectText - Whether to select the text
     * @param {Object} additionalConfig - Additional configuration
     */
    static showModalWithInput(modalId, inputSelector, inputValue = '', selectText = false, additionalConfig = {}) {
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
     * @param {string} modalId - The modal ID
     * @param {Object} formData - Data to populate form fields
     * @param {Object} additionalConfig - Additional configuration
     */
    static showModalWithData(modalId, formData = {}, additionalConfig = {}) {
        return this.showModal(modalId, {
            data: formData,
            populateForm: true,
            ...additionalConfig
        });
    }
    
    /**
     * Initialize the ModalManager
     */
    static initialize() {
        this.setupGlobalEvents();
        console.log('ModalManager initialized');
    }
}

// Auto-initialize when script loads
document.addEventListener('DOMContentLoaded', () => {
    ModalManager.initialize();
});

// Export for use in other modules or global scope
window.ModalManager = ModalManager;