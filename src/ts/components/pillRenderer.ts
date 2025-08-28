/**
 * PillRenderer Module for Session Instance Detail Beta
 * Handles rendering of tune pills, sets, cursor positions, and UI elements
 */

import { TunePill, TuneSet, TunePillsData } from './stateManager.js';

export interface PillRendererCallbacks {
    cleanupDragGhosts?(): void;
    createHorizontalDropZone?(setIndex: number): HTMLElement;
    setupPillEventListeners?(pillElement: HTMLElement, pillData: TunePill): void;
    setCursorPosition?(setIndex: number, pillIndex: number, position: string, maintainKeyboard?: boolean): void;
    clearSelection?(): void;
}

export interface PillRendererDependencies {
    getStateManager(): StateManager;
    getCursorManager(): CursorManager;
    getAutoSaveManager(): AutoSaveManager;
    containerElement?: HTMLElement | null;
}

export interface StateManager {
    getTunePillsData(): TunePillsData;
}

export interface CursorManager {
    getCursorPosition(): CursorPosition | null;
    addCursorPosition?(parent: HTMLElement, setIndex: number, pillIndex: number, positionType: string): HTMLElement;
    addFinalCursor?(containerElement: HTMLElement): HTMLElement;
}

export interface CursorPosition {
    setIndex: number;
    pillIndex: number;
    position: string;
}

export interface AutoSaveManager {
    forceCheckChanges(): void;
}

export class PillRenderer {
    static getStateManager: (() => StateManager) | null = null; // Function to get StateManager reference
    static getCursorManager: (() => CursorManager) | null = null; // Function to get CursorManager reference
    static getAutoSaveManager: (() => AutoSaveManager) | null = null; // Function to get AutoSaveManager reference
    static containerElement: HTMLElement | null = null;
    
    // External functions that need to be called (will be registered via callbacks)
    static cleanupDragGhosts: (() => void) | null = null;
    static createHorizontalDropZone: ((setIndex: number) => HTMLElement) | null = null;
    static setupPillEventListeners: ((pillElement: HTMLElement, pillData: TunePill) => void) | null = null;
    static setCursorPosition: ((setIndex: number, pillIndex: number, position: string, maintainKeyboard?: boolean) => void) | null = null;
    static clearSelection: (() => void) | null = null;
    
    static initialize(options: PillRendererDependencies = {} as PillRendererDependencies): void {
        this.getStateManager = options.getStateManager || (() => (window as any).StateManager);
        this.getCursorManager = options.getCursorManager || (() => (window as any).CursorManager);
        this.getAutoSaveManager = options.getAutoSaveManager || (() => (window as any).AutoSaveManager);
        this.containerElement = options.containerElement || document.getElementById('tune-pills-container');
    }
    
    static renderTunePills(): void {
        const stateManager = this.getStateManager!();
        const cursorManager = this.getCursorManager!();
        const autoSaveManager = this.getAutoSaveManager!();
        const tunePillsData = stateManager.getTunePillsData();
        const cursorPosition = cursorManager.getCursorPosition();
        
        // Check for data changes before rendering (safety net)
        autoSaveManager.forceCheckChanges();
        
        // Clean up any lingering drag ghosts before re-rendering
        if (this.cleanupDragGhosts) {
            this.cleanupDragGhosts();
        }
        
        const container = this.containerElement || document.getElementById('tune-pills-container')!;
        
        // Remember if the container was contentEditable before clearing (for mobile keyboard persistence)
        const wasContentEditable = container.contentEditable === 'true';
        const wasFocused = document.activeElement === container;
        
        container.innerHTML = '';
        
        // If we were contentEditable, restore it immediately after clearing
        if (wasContentEditable) {
            container.contentEditable = 'true';
            (container as any).inputMode = 'text';
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
    
    static renderEmptyState(container: HTMLElement): void {
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
        
        emptyPos.addEventListener('click', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Clear selection and selection anchor when clicking to move cursor
            if (this.clearSelection) {
                this.clearSelection();
            }
            
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
    
    static createTuneSetElement(tuneSet: TuneSet, setIndex: number): HTMLElement {
        const setDiv = document.createElement('div');
        setDiv.className = 'tune-set';
        setDiv.dataset.setIndex = setIndex.toString();
        
        // Handle empty sets (especially temporary ones)
        if (tuneSet.length === 0) {
            // Add cursor position for empty set
            this.addCursorPosition(setDiv, setIndex, 0, 'before');
            
            // Add some minimal height so the empty set is visible
            setDiv.style.minHeight = '25px';
            return setDiv;
        }
        
        tuneSet.forEach((pill, pillIndex) => {
            // Add cursor position before the first pill only
            if (pillIndex === 0) {
                this.addCursorPosition(setDiv, setIndex, pillIndex, 'before');
            }
            
            const pillElement = this.createPillElement(pill, setIndex, pillIndex);
            setDiv.appendChild(pillElement);
            
            // Add cursor position after each pill (this becomes the "before" position for the next pill)
            this.addCursorPosition(setDiv, setIndex, pillIndex, 'after');
            
            // Add spacing between pills
            if (pillIndex < tuneSet.length - 1) {
                const spacer = document.createElement('span');
                spacer.textContent = ' ';
                setDiv.appendChild(spacer);
            }
        });
        
        // After initial render, check for line wrapping and improve cursor positioning
        setTimeout(() => {
            this.enhanceWrappedCursorVisibility(setDiv, setIndex);
        }, 10);
        
        return setDiv;
    }
    
    static enhanceWrappedCursorVisibility(setDiv: HTMLElement, setIndex: number): void {
        // Find all tune pills in this set
        const pills = Array.from(setDiv.querySelectorAll('.tune-pill')) as HTMLElement[];
        
        if (pills.length <= 1) {
            return; // No wrapping possible with 0 or 1 pills
        }
        
        // Remove any existing wrap cursors first
        setDiv.querySelectorAll('.cursor-position.wrap-cursor').forEach(cursor => cursor.remove());
        
        // Group pills by their top position (same line)
        const lines: HTMLElement[][] = [];
        let currentLine: HTMLElement[] = [];
        let currentTop: number | null = null;
        
        pills.forEach((pill, index) => {
            const rect = pill.getBoundingClientRect();
            const top = Math.round(rect.top);
            
            if (currentTop === null) {
                currentTop = top;
                currentLine.push(pill);
            } else if (Math.abs(top - currentTop) < 5) { // Same line (within 5px tolerance)
                currentLine.push(pill);
            } else {
                // New line detected
                if (currentLine.length > 0) {
                    lines.push(currentLine);
                }
                currentLine = [pill];
                currentTop = top;
            }
        });
        
        if (currentLine.length > 0) {
            lines.push(currentLine);
        }
        
        // If we have multiple lines, enhance cursor visibility for drop zones
        if (lines.length > 1) {
            // Mark all cursor positions in wrapped content for better visibility
            setDiv.querySelectorAll('.cursor-position').forEach(cursor => {
                // Enhanced visibility for wrapped content cursors
                (cursor as HTMLElement).style.backgroundColor = 'rgba(0, 123, 255, 0.05)';
                (cursor as HTMLElement).style.minWidth = '6px'; // Make them slightly wider for easier targeting
            });
        }
    }
    
    static createWrapCursorPosition(setIndex: number, pillIndex: number, wrapType: string): HTMLElement {
        const cursorPos = document.createElement('span');
        cursorPos.className = 'cursor-position wrap-cursor';
        cursorPos.dataset.setIndex = setIndex.toString();
        cursorPos.dataset.pillIndex = pillIndex.toString();
        
        // Set the correct position type based on wrap type
        if (wrapType === 'line-start') {
            cursorPos.dataset.positionType = 'before';
        } else if (wrapType === 'after-pill') {
            cursorPos.dataset.positionType = 'after';
        } else {
            cursorPos.dataset.positionType = 'after'; // default
        }
        
        cursorPos.dataset.wrapType = wrapType;
        
        cursorPos.addEventListener('click', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Clear selection when clicking to move cursor
            if (this.clearSelection) {
                this.clearSelection();
            }
            
            if (this.setCursorPosition) {
                this.setCursorPosition(setIndex, pillIndex, cursorPos.dataset.positionType!);
            }
        });
        
        return cursorPos;
    }
    
    static createPillElement(pill: TunePill, setIndex: number, pillIndex: number): HTMLElement {
        const pillDiv = document.createElement('div');
        pillDiv.className = `tune-pill ${pill.state}`;
        pillDiv.dataset.pillId = pill.id;
        pillDiv.dataset.setIndex = setIndex.toString();
        pillDiv.dataset.pillIndex = pillIndex.toString();
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
    
    static addCursorPosition(parent: HTMLElement, setIndex: number, pillIndex: number, positionType: string): HTMLElement {
        const cursorManager = this.getCursorManager!();
        if (cursorManager && cursorManager.addCursorPosition) {
            return cursorManager.addCursorPosition(parent, setIndex, pillIndex, positionType);
        }
        
        // Fallback implementation if CursorManager not available
        const cursorPos = document.createElement('span');
        cursorPos.className = 'cursor-position';
        cursorPos.dataset.setIndex = setIndex.toString();
        cursorPos.dataset.pillIndex = pillIndex.toString();
        cursorPos.dataset.positionType = positionType;
        
        cursorPos.addEventListener('click', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Clear selection and selection anchor when clicking to move cursor
            if (this.clearSelection) {
                this.clearSelection();
            }
            
            if (this.setCursorPosition) {
                this.setCursorPosition(setIndex, pillIndex, positionType);
            }
        });
        
        parent.appendChild(cursorPos);
        return cursorPos;
    }
    
    static addFinalCursor(containerElement: HTMLElement): HTMLElement {
        const cursorManager = this.getCursorManager!();
        if (cursorManager && cursorManager.addFinalCursor) {
            return cursorManager.addFinalCursor(containerElement);
        }
        
        // Fallback implementation if CursorManager not available
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
            
            // Clear selection and selection anchor when clicking to move cursor
            if (this.clearSelection) {
                this.clearSelection();
            }
            
            if (this.setCursorPosition) {
                this.setCursorPosition(tunePillsData.length, 0, 'newset');
            }
        });
        
        containerElement.appendChild(finalPos);
        return finalPos;
    }
    
    static getContainerElement(): HTMLElement | null {
        return this.containerElement || document.getElementById('tune-pills-container');
    }
    
    static setContainerElement(element: HTMLElement): void {
        this.containerElement = element;
    }
    
    // Helper method to register external functions that PillRenderer needs to call
    static registerCallbacks(callbacks: PillRendererCallbacks = {}): void {
        this.cleanupDragGhosts = callbacks.cleanupDragGhosts || null;
        this.createHorizontalDropZone = callbacks.createHorizontalDropZone || null;
        this.setupPillEventListeners = callbacks.setupPillEventListeners || null;
        this.setCursorPosition = callbacks.setCursorPosition || null;
        this.clearSelection = callbacks.clearSelection || null;
    }
    
    // Update the appearance of a single pill without re-rendering everything
    static updatePillAppearance(pill: TunePill): void {
        console.log(`Updating appearance for pill ID: ${pill.id}, state: ${pill.state}, name: ${pill.tuneName}`);
        const pillElement = document.querySelector(`[data-pill-id="${pill.id}"]`) as HTMLElement;
        if (!pillElement) {
            console.error(`Could not find pill element with ID: ${pill.id}`);
            return;
        }
        
        console.log(`Found pill element, updating class from "${pillElement.className}" to "tune-pill ${pill.state}"`);
        // Update the CSS class to reflect the new state
        pillElement.className = `tune-pill ${pill.state}`;
        
        // Update the text content in case it changed (e.g., canonical name from API)
        const textElement = pillElement.querySelector('.text') as HTMLElement;
        if (textElement) {
            console.log(`Updating text content from "${textElement.textContent}" to "${pill.tuneName}"`);
            textElement.textContent = pill.tuneName;
        } else {
            console.error('Could not find .text element within pill');
        }
        
        // Remove any existing spinner
        const existingSpinner = pillElement.querySelector('.loading-spinner');
        if (existingSpinner) {
            existingSpinner.remove();
        }
        
        // Add spinner if still loading
        if (pill.state === 'loading') {
            const spinner = document.createElement('span');
            spinner.className = 'loading-spinner';
            pillElement.appendChild(spinner);
        }
    }
    
    // Apply landing animation to pills that have been moved
    static applyLandingAnimation(pillIds: string[]): void {
        pillIds.forEach(pillId => {
            const pillElement = document.querySelector(`[data-pill-id="${pillId}"]`) as HTMLElement;
            if (pillElement) {
                pillElement.classList.add('just-landed');
                setTimeout(() => {
                    pillElement.classList.remove('just-landed');
                }, 3000);
            }
        });
    }
}

// Export for use in other modules or global scope
declare global {
    interface Window {
        PillRenderer: typeof PillRenderer;
    }
}

(window as any).PillRenderer = PillRenderer;