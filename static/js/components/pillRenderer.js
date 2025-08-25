/**
 * PillRenderer Module for Session Instance Detail Beta
 * Handles rendering of tune pills, sets, cursor positions, and UI elements
 */

class PillRenderer {
    static getStateManager = null; // Function to get StateManager reference
    static getCursorManager = null; // Function to get CursorManager reference
    static getAutoSaveManager = null; // Function to get AutoSaveManager reference
    static containerElement = null;
    
    // External functions that need to be called (will be registered via callbacks)
    static cleanupDragGhosts = null;
    static createHorizontalDropZone = null;
    static setupPillEventListeners = null;
    static setCursorPosition = null;
    
    static initialize(options = {}) {
        this.getStateManager = options.getStateManager || (() => window.StateManager);
        this.getCursorManager = options.getCursorManager || (() => window.CursorManager);
        this.getAutoSaveManager = options.getAutoSaveManager || (() => window.AutoSaveManager);
        this.containerElement = options.containerElement || document.getElementById('tune-pills-container');
    }
    
    static renderTunePills() {
        const stateManager = this.getStateManager();
        const cursorManager = this.getCursorManager();
        const autoSaveManager = this.getAutoSaveManager();
        const tunePillsData = stateManager.getTunePillsData();
        const cursorPosition = cursorManager.getCursorPosition();
        
        // Check for data changes before rendering (safety net)
        autoSaveManager.forceCheckChanges();
        
        // Clean up any lingering drag ghosts before re-rendering
        if (this.cleanupDragGhosts) {
            this.cleanupDragGhosts();
        }
        
        const container = this.containerElement || document.getElementById('tune-pills-container');
        
        // Remember if the container was contentEditable before clearing (for mobile keyboard persistence)
        const wasContentEditable = container.contentEditable === 'true';
        const wasFocused = document.activeElement === container;
        
        container.innerHTML = '';
        
        // If we were contentEditable, restore it immediately after clearing
        if (wasContentEditable) {
            container.contentEditable = 'true';
            container.inputMode = 'text';
        }
        
        if (tunePillsData.length === 0) {
            this.renderEmptyState(container);
            return;
        }
        
        tunePillsData.forEach((tuneSet, setIndex) => {
            // Add horizontal drop zone before each set (except the first one)
            if (setIndex > 0 && this.createHorizontalDropZone) {
                const dropZone = this.createHorizontalDropZone(setIndex);
                container.appendChild(dropZone);
            }
            
            const setDiv = this.createTuneSetElement(tuneSet, setIndex);
            container.appendChild(setDiv);
        });
        
        // Add final cursor position at the end
        this.addFinalCursor(container);
        
        // Set default cursor position at the end if none exists
        if (!cursorPosition) {
            if (this.setCursorPosition) {
                this.setCursorPosition(tunePillsData.length, 0, 'newset');
            }
        } else {
            // Restore cursor position after re-render
            // Pass maintainKeyboard flag if we were contentEditable before
            if (this.setCursorPosition) {
                this.setCursorPosition(cursorPosition.setIndex, cursorPosition.pillIndex, cursorPosition.position, wasContentEditable);
            }
        }
    }
    
    static renderEmptyState(container) {
        container.innerHTML = '<p style="color: var(--disabled-text); font-style: italic; margin: 0; text-align: center; padding: 40px 20px;">No tunes recorded for this session yet.<br><strong>Click anywhere to position cursor, then start typing...</strong><br><small>Use Enter, Tab, semicolon, or comma to finish entering tunes</small></p>';
        
        // Add a cursor position for empty container
        const emptyPos = document.createElement('span');
        emptyPos.className = 'cursor-position';
        emptyPos.dataset.setIndex = '0';
        emptyPos.dataset.pillIndex = '0';
        emptyPos.dataset.positionType = 'newset';
        emptyPos.style.position = 'absolute';
        emptyPos.style.top = '50%';
        emptyPos.style.left = '50%';
        emptyPos.style.transform = 'translate(-50%, -50%)';
        
        emptyPos.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (this.setCursorPosition) {
                this.setCursorPosition(0, 0, 'newset');
            }
        });
        
        container.appendChild(emptyPos);
        
        // Set initial cursor position
        if (this.setCursorPosition) {
            this.setCursorPosition(0, 0, 'newset');
        }
    }
    
    static createTuneSetElement(tuneSet, setIndex) {
        const setDiv = document.createElement('div');
        setDiv.className = 'tune-set';
        setDiv.dataset.setIndex = setIndex;
        
        // Handle empty sets (especially temporary ones)
        if (tuneSet.length === 0) {
            // Add cursor position for empty set
            this.addCursorPosition(setDiv, setIndex, 0, 'before');
            
            // Add some minimal height so the empty set is visible
            setDiv.style.minHeight = '25px';
            return setDiv;
        }
        
        tuneSet.forEach((pill, pillIndex) => {
            // Add cursor position before first pill only
            if (pillIndex === 0) {
                this.addCursorPosition(setDiv, setIndex, pillIndex, 'before');
            }
            
            const pillElement = this.createPillElement(pill, setIndex, pillIndex);
            setDiv.appendChild(pillElement);
            
            // Add cursor position after each pill (this becomes the "before" position for next pill)
            this.addCursorPosition(setDiv, setIndex, pillIndex, 'after');
            
            // Add spacing between pills
            if (pillIndex < tuneSet.length - 1) {
                const spacer = document.createElement('span');
                spacer.textContent = ' ';
                setDiv.appendChild(spacer);
            }
        });
        
        return setDiv;
    }
    
    static createPillElement(pill, setIndex, pillIndex) {
        const pillDiv = document.createElement('div');
        pillDiv.className = `tune-pill ${pill.state}`;
        pillDiv.dataset.pillId = pill.id;
        pillDiv.dataset.setIndex = setIndex;
        pillDiv.dataset.pillIndex = pillIndex;
        pillDiv.draggable = true;
        
        // Add chevron
        const chevron = document.createElement('div');
        chevron.className = 'chevron';
        pillDiv.appendChild(chevron);
        
        // Add text
        const text = document.createElement('span');
        text.className = 'text';
        text.textContent = pill.tuneName;
        pillDiv.appendChild(text);
        
        // Add loading spinner if pill is in loading state
        if (pill.state === 'loading') {
            const spinner = document.createElement('span');
            spinner.className = 'loading-spinner';
            pillDiv.appendChild(spinner);
        }
        
        // Add event listeners
        if (this.setupPillEventListeners) {
            this.setupPillEventListeners(pillDiv, pill);
        }
        
        return pillDiv;
    }
    
    static addCursorPosition(parent, setIndex, pillIndex, positionType) {
        const cursorManager = this.getCursorManager();
        if (cursorManager && cursorManager.addCursorPosition) {
            return cursorManager.addCursorPosition(parent, setIndex, pillIndex, positionType);
        }
        
        // Fallback implementation if CursorManager not available
        const cursorPos = document.createElement('span');
        cursorPos.className = 'cursor-position';
        cursorPos.dataset.setIndex = setIndex;
        cursorPos.dataset.pillIndex = pillIndex;
        cursorPos.dataset.positionType = positionType;
        
        cursorPos.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (this.setCursorPosition) {
                this.setCursorPosition(setIndex, pillIndex, positionType);
            }
        });
        
        parent.appendChild(cursorPos);
        return cursorPos;
    }
    
    static addFinalCursor(containerElement) {
        const cursorManager = this.getCursorManager();
        if (cursorManager && cursorManager.addFinalCursor) {
            return cursorManager.addFinalCursor(containerElement);
        }
        
        // Fallback implementation if CursorManager not available
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
            if (this.setCursorPosition) {
                this.setCursorPosition(tunePillsData.length, 0, 'newset');
            }
        });
        
        containerElement.appendChild(finalPos);
        return finalPos;
    }
    
    static getContainerElement() {
        return this.containerElement || document.getElementById('tune-pills-container');
    }
    
    static setContainerElement(element) {
        this.containerElement = element;
    }
    
    // Helper method to register external functions that PillRenderer needs to call
    static registerCallbacks(callbacks = {}) {
        this.cleanupDragGhosts = callbacks.cleanupDragGhosts;
        this.createHorizontalDropZone = callbacks.createHorizontalDropZone;
        this.setupPillEventListeners = callbacks.setupPillEventListeners;
        this.setCursorPosition = callbacks.setCursorPosition;
    }
}

// Export for use in other modules or global scope
window.PillRenderer = PillRenderer;