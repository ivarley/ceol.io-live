/**
 * Javascript for session instance detail beta editor
 */

// Get configuration from window.sessionConfig (passed from template)
const sessionPath = window.sessionConfig.sessionPath;
const sessionDate = window.sessionConfig.sessionDate;
const isCancelled = window.sessionConfig.isCancelled;
const isSessionAdmin = window.sessionConfig.isSessionAdmin;
const isLogComplete = window.sessionConfig.isLogComplete;

// Session instance data for editing
const sessionInstanceData = window.sessionConfig.sessionInstanceData;

// Beta Editor State - core data now managed by StateManager
// selectedPills now fully managed by PillSelection module
// dragState now managed by DragDrop module
// cursorPosition now managed by CursorManager - keep reference for backward compatibility
let cursorPosition = null;

// Core data array - will be replaced by StateManager calls
let tunePillsData = [];

// Save state tracking - now managed by AutoSaveManager

// State change tracking now handled directly by AutoSaveManager

// Text input handling now managed by TextInput module
let textInput = null;

// Global mobile drag ghost management now handled by DragDrop module

// Drag ghost cleanup now handled by DragDrop module


// Save functionality - now handled directly by AutoSaveManager

// AutoSave functions now handled directly by AutoSaveManager module

// Initialize the editor on page load
document.addEventListener('DOMContentLoaded', function() {
    if (!isCancelled) {
        // Initialize StateManager with change callback
        StateManager.initialize(() => {
            tunePillsData = StateManager.getTunePillsData();
            AutoSaveManager.forceCheckChanges();
        });
        
        // Initialize CursorManager 
        CursorManager.initialize({
            getStateManager: () => StateManager,
            onCursorChange: (newPosition) => {
                // Update global reference for backward compatibility
                cursorPosition = newPosition;
            },
            onSelectionChange: () => {
                PillSelection.updateSelectionDisplay();
            }
        });
        
        // Initialize TextInput module
        textInput = new TextInput();
        
        // Expose textInput to window for access from other modules
        window.textInput = textInput;
        
        // Register callbacks that CursorManager needs
        CursorManager.registerCallbacks({
            finishTyping: (keepKeyboard) => finishTypingWithKeyboardFix(keepKeyboard),
            removeTemporaryEmptySet: () => removeTemporaryEmptySet(),
            renderTunePills: () => PillRenderer.renderTunePills(),
            handleTextInput: (char) => textInput.handleTextInput(char),
            handleBackspace: () => textInput.handleBackspace(),
            syncNativeCursor: () => syncNativeCursorPosition()
        });
        
        // Set typing-related variables that CursorManager needs access to
        CursorManager.isTyping = () => textInput.typing;
        CursorManager.typingBuffer = () => textInput.buffer;
        CursorManager.isKeepingKeyboardOpen = () => textInput.keepingKeyboardOpen;
        
        // Initialize PillRenderer
        PillRenderer.initialize({
            getStateManager: () => StateManager,
            getCursorManager: () => CursorManager,
            getAutoSaveManager: () => AutoSaveManager
        });
        
        // Register callbacks that PillRenderer needs
        PillRenderer.registerCallbacks({
            cleanupDragGhosts: () => DragDrop.cleanupDragGhosts(),
            createHorizontalDropZone: (setIndex) => DragDrop.createHorizontalDropZone(setIndex),
            setupPillEventListeners: (pillElement, pillData) => DragDrop.setupPillEventListeners(pillElement, pillData),
            setCursorPosition: (setIndex, pillIndex, positionType, maintainKeyboard) => CursorManager.setCursorPosition(setIndex, pillIndex, positionType, maintainKeyboard),
            clearSelection: () => CursorManager.clearSelection()
        });
        
        // Initialize PillSelection
        PillSelection.initialize({
            getStateManager: () => StateManager,
            getAutoSaveManager: () => AutoSaveManager,
            onSelectionChange: () => {
                PillSelection.updateSelectionDisplay();
            }
        });
        
        // Register callbacks that PillSelection needs
        PillSelection.registerCallbacks({
            renderTunePills: () => PillRenderer.renderTunePills(),
            saveToUndo: () => undoRedoManager.saveToUndo(),
            showMessage: (message, type) => showMessage(message, type)
        });
        
        // Initialize PillInteraction
        PillInteraction.initialize({
            getPillSelection: () => PillSelection,
            getStateManager: () => StateManager,
            getCursorManager: () => CursorManager,
            getDragDrop: () => DragDrop,
            showContextMenu: (e, pillData) => ContextMenu.showContextMenu(e, pillData),
            hideContextMenu: (pillId) => ContextMenu.hideContextMenu(pillId),
            isTyping: () => textInput.typing,
            finishTyping: () => textInput.finishTyping(CursorManager.isMobileDevice())
        });
        
        // Initialize DragDrop
        DragDrop.initialize({
            getPillSelection: () => PillSelection,
            getStateManager: () => StateManager,
            getCursorManager: () => CursorManager,
            getPillInteraction: () => PillInteraction
        });
        
        // Register callbacks that DragDrop needs
        DragDrop.registerCallbacks({
            performDrop: (position, draggedIds) => performDrop(position, draggedIds),
            dropStructuredSetsAtNewPosition: (dragData, targetSetIndex) => dropStructuredSetsAtNewPosition(dragData, targetSetIndex),
            pasteAtPosition: (dragData, position) => clipboardManager.pasteAtPosition(dragData, position),
            saveToUndo: () => undoRedoManager.saveToUndo(),
            showContextMenu: (e, pillData) => ContextMenu.showContextMenu(e, pillData),
            hideContextMenu: (pillId) => ContextMenu.hideContextMenu(pillId),
            applyLandingAnimation: (movedPillIds) => PillRenderer.applyLandingAnimation(movedPillIds),
            setCursorPosition: (setIndex, pillIndex, positionType, maintainKeyboard) => CursorManager.setCursorPosition(setIndex, pillIndex, positionType, maintainKeyboard),
            clearSelection: () => CursorManager.clearSelection()
        });
        
        // Initialize UndoRedoManager
        undoRedoManager.initialize({
            getStateManager: () => StateManager,
            getAutoSaveManager: () => AutoSaveManager
        });
        
        // Register callbacks that UndoRedoManager needs
        undoRedoManager.registerCallbacks({
            onUndoRedo: () => {
                tunePillsData = StateManager.getTunePillsData();
                PillRenderer.renderTunePills();
            }
        });
        
        // Initialize ClipboardManager
        clipboardManager.initialize({
            getPillSelection: () => PillSelection,
            getCursorManager: () => CursorManager,
            getStateManager: () => StateManager
        });
        
        // Register callbacks that ClipboardManager needs
        clipboardManager.registerCallbacks({
            saveToUndo: () => undoRedoManager.saveToUndo(),
            generateId: () => StateManager.generateId(),
            renderTunePills: () => PillRenderer.renderTunePills(),
            showMessage: (message, type) => showMessage(message, type),
            applyLandingAnimation: (pillIds) => PillRenderer.applyLandingAnimation(pillIds),
            autoMatchTune: (pill) => autoMatchTune(pill),
            updatePillAppearance: (pill) => PillRenderer.updatePillAppearance(pill),
            showMatchingResults: (pills) => showMatchingResults(pills)
        });
        
        // Initialize KeyboardHandler
        KeyboardHandler.initialize({
            getCursorManager: () => CursorManager,
            getPillSelection: () => PillSelection,
            isTyping: () => textInput.typing,
            getModalManager: () => ModalManager
        });
        
        // Register callbacks that KeyboardHandler needs
        KeyboardHandler.registerCallbacks({
            handleTextInput: (char) => textInput.handleTextInput(char),
            handleBackspace: () => textInput.handleBackspace(),
            handleDelete: () => textInput.handleDelete(),
            handleEnterKey: () => textInput.handleEnterKey(),
            finishTyping: () => finishTypingFromKeyboard(),
            cancelTyping: () => textInput.cancelTyping(),
            undo: () => undoRedoManager.undo(),
            redo: () => undoRedoManager.redo(),
            copySelectedPills: () => clipboardManager.copySelectedPills(),
            cutSelectedPills: () => clipboardManager.cutSelectedPills(),
            pasteFromClipboard: () => clipboardManager.pasteFromClipboard(),
            hideLinkModal: () => hideLinkModal(),
            hideEditModal: () => hideEditModal(),
            hideSessionEditModal: () => hideSessionEditModal(),
            confirmLink: () => confirmLink(),
            confirmEdit: () => confirmEdit(),
            removeTypingMatchResults: () => textInput.removeTypingMatchResults()
        });
        
        // Convert server-side tune sets data to pills format
        const initialTuneSets = window.sessionConfig.initialTuneSets;
        convertTuneSetsToPills(initialTuneSets, true); // Skip callback during initialization
        PillRenderer.renderTunePills();
        setupEventListeners();
        
        // Initialize AutoSaveManager after tunePillsData is created
        AutoSaveManager.initialize(sessionPath, sessionDate, () => StateManager.getTunePillsData(), {
            isUserLoggedIn: window.sessionConfig.isUserLoggedIn,
            userAutoSave: window.sessionConfig.userAutoSave,
            userAutoSaveInterval: window.sessionConfig.userAutoSaveInterval
        });
        
        // Initialize save state - mark as clean since we just loaded
        const currentData = StateManager.getTunePillsData();
        AutoSaveManager.lastSavedData = JSON.parse(JSON.stringify(currentData));
        AutoSaveManager.lastCheckedData = JSON.parse(JSON.stringify(currentData));
        AutoSaveManager.isDirty = false;
        
        // Ensure save button is disabled on initial load
        const saveBtn = document.getElementById('save-session-btn');
        if (saveBtn) {
            saveBtn.disabled = true;
        }
    }
    
    setupSessionEditListeners();
    setupSaveListeners();
    
    // Initialize auto-save preference
    AutoSaveManager.initializeAutoSavePreference();
    
    // Set up responsive option text
    AutoSaveManager.updateOptionText();
    window.addEventListener('resize', AutoSaveManager.updateOptionText);
    
    // Set up mobile keyboard management
    setupMobileKeyboardManagement();
});

// Convert tune sets to pills data format - delegated to StateManager
function convertTuneSetsToPills(tuneSets, skipCallback = false) {
    StateManager.convertTuneSetsToPills(tuneSets, skipCallback);
    tunePillsData = StateManager.getTunePillsData();
}

// Module functions are now called directly


// Specialized function for dropping structured sets at a new position (horizontal zones)
function dropStructuredSetsAtNewPosition(dragData, targetSetIndex) {
    if (!dragData || dragData.length === 0) return;
    
    // Filter out any empty sets from drag data
    dragData = dragData.filter(set => set && set.length > 0);
    
    if (dragData.length === 0) {
        return;
    }
    
    undoRedoManager.saveToUndo();
    
    // Remove dragged pills from their current positions (same logic as performDrop)
    const draggedPillIds = Array.from(PillSelection.getSelectedPills());
    const setsToRemove = new Set();
    
    
    draggedPillIds.forEach(pillId => {
        for (let setIndex = 0; setIndex < tunePillsData.length; setIndex++) {
            const pillIndex = tunePillsData[setIndex].findIndex(p => p.id === pillId);
            if (pillIndex !== -1) {
                tunePillsData[setIndex].splice(pillIndex, 1);
                if (tunePillsData[setIndex].length === 0) {
                    setsToRemove.add(setIndex);
                }
                break;
            }
        }
    });
    
    // Clean up empty sets BEFORE calculating target position
    tunePillsData = tunePillsData.filter(set => set.length > 0);
    
    // Calculate adjusted target index AFTER cleanup
    let adjustedTargetIndex = targetSetIndex;
    for (let i = 0; i < targetSetIndex; i++) {
        if (setsToRemove.has(i)) {
            adjustedTargetIndex--;
        }
    }
    
    
    // Create new sets with new IDs
    const newSets = dragData.map(set => 
        set.map(pill => ({
            ...pill,
            id: StateManager.generateId(),
            orderNumber: null
        }))
    );
    
    // Insert the new sets at the adjusted position
    if (adjustedTargetIndex >= tunePillsData.length) {
        tunePillsData.push(...newSets);
    } else {
        tunePillsData.splice(adjustedTargetIndex, 0, ...newSets);
    }
    
    // Update StateManager with the modified data
    StateManager.setTunePillsData(tunePillsData);
    
    PillRenderer.renderTunePills();
    
    // Apply landing animation
    const movedPillIds = newSets.flat().map(pill => pill.id);
    setTimeout(() => {
        PillRenderer.applyLandingAnimation(movedPillIds);
    }, 50);
}

function performDrop(position, draggedPillIds) {
    if (!draggedPillIds || draggedPillIds.length === 0) return;
    
    undoRedoManager.saveToUndo();
    
    // Track which sets will become empty after removal
    const originalSetCount = tunePillsData.length;
    const setsToRemove = new Set();
    
    // Remove dragged pills from their current positions
    const draggedPills = [];
    draggedPillIds.forEach(pillId => {
        for (let setIndex = 0; setIndex < tunePillsData.length; setIndex++) {
            const pillIndex = tunePillsData[setIndex].findIndex(p => p.id === pillId);
            if (pillIndex !== -1) {
                draggedPills.push(tunePillsData[setIndex].splice(pillIndex, 1)[0]);
                if (tunePillsData[setIndex].length === 0) {
                    setsToRemove.add(setIndex);
                }
                break;
            }
        }
    });
    
    // Calculate how many sets before target position will be removed
    let adjustedTargetIndex = position.setIndex;
    for (let i = 0; i < position.setIndex; i++) {
        if (setsToRemove.has(i)) {
            adjustedTargetIndex--;
        }
    }
    
    // Clean up empty sets
    tunePillsData = tunePillsData.filter(set => set.length > 0);
    
    // Insert at new position
    if (position.position === 'newset') {
        if (adjustedTargetIndex >= tunePillsData.length) {
            // Create new set at end
            tunePillsData.push(draggedPills);
        } else {
            // Create new set at specific index (insert between existing sets)
            tunePillsData.splice(adjustedTargetIndex, 0, draggedPills);
        }
    } else {
        // Use the adjusted target index for existing sets too
        if (adjustedTargetIndex >= tunePillsData.length) {
            // Create new set at end
            tunePillsData.push(draggedPills);
        } else {
            // Insert into existing set
            const targetSet = tunePillsData[adjustedTargetIndex];
            let insertIndex;
            
            if (position.position === 'before') {
                insertIndex = position.pillIndex;
            } else { // 'after'
                insertIndex = position.pillIndex;
            }
            
            // Insert pills into target set at the specified position
            targetSet.splice(insertIndex, 0, ...draggedPills);
        }
    }
    
    // Update StateManager with the modified data
    StateManager.setTunePillsData(tunePillsData);
    
    PillRenderer.renderTunePills();
    
    // Apply landing animation to moved pills
    const movedPillIds = draggedPills.map(pill => pill.id);
    setTimeout(() => {
        PillRenderer.applyLandingAnimation(movedPillIds);
    }, 50); // Small delay to ensure pills are rendered
}

// Drag and drop support functions
function findPillById(pillId) {
    for (const set of tunePillsData) {
        for (const pill of set) {
            if (pill.id === pillId) {
                return pill;
            }
        }
    }
    return null;
}

// Context menu functions now handled by ContextMenu module



function findPillPosition(pillId) {
    for (let setIndex = 0; setIndex < tunePillsData.length; setIndex++) {
        const set = tunePillsData[setIndex];
        const pillIndex = set.findIndex(p => p.id === pillId);
        if (pillIndex !== -1) {
            return { setIndex, pillIndex };
        }
    }
    return null;
}


// All clipboard and undo/redo functions now use modules directly

function removeTemporaryEmptySet() {
    if (temporaryEmptySet !== null && temporaryEmptySet < tunePillsData.length && tunePillsData[temporaryEmptySet].length === 0) {
        tunePillsData.splice(temporaryEmptySet, 1);
        temporaryEmptySet = null;
        
        // Update StateManager with the modified data
        StateManager.setTunePillsData(tunePillsData);
        
        return true;
    }
    temporaryEmptySet = null;
    return false;
}

// Track selection anchor for shift+arrow selection  
let selectionAnchor = null;

// Track temporary empty line
let temporaryEmptySet = null;


function selectPillsBetweenPositions(startPos, endPos) {
    // Convert positions to cursor format and use PillSelection method
    const startCursor = { setIndex: startPos.setIndex, pillIndex: startPos.pillIndex, position: 'after' };
    const endCursor = { setIndex: endPos.setIndex, pillIndex: endPos.pillIndex, position: 'after' };
    PillSelection.selectFromCursorRange(startCursor, endCursor);
}

function selectPillsBetweenCursorPositions(startCursorPos, endCursorPos) {
    // Use PillSelection method directly
    PillSelection.selectFromCursorRange(startCursorPos, endCursorPos);
}


function findPillIndex(allPills, pillPos) {
    if (!pillPos) return -1;
    
    for (let i = 0; i < allPills.length; i++) {
        if (allPills[i].setIndex === pillPos.setIndex && allPills[i].pillIndex === pillPos.pillIndex) {
            return i;
        }
    }
    return -1;
}

// Show results after all tune matching completes
function showMatchingResults(pills) {
    // Check if any pills failed due to authentication
    const authFailedCount = pills.filter(pill => pill.authenticationFailed).length;
    if (authFailedCount > 0) {
        // Don't show the generic message if authentication failed
        // The auth-specific message was already shown
        return;
    }
    
    const linkedCount = pills.filter(pill => pill.state === 'linked').length;
    const unlinkedCount = pills.filter(pill => pill.state === 'unlinked').length;
    const totalCount = pills.length;
    
    let message, type;
    
    if (linkedCount === totalCount) {
        // All tunes matched
        message = totalCount === 1 ? 'Tune matched' : `All ${totalCount} tunes matched`;
        type = 'success';
    } else if (linkedCount === 0) {
        // No tunes matched
        message = totalCount === 1 ? 'Tune not matched' : `${totalCount} tunes not matched`;
        type = 'error';
    } else {
        // Some matched, some didn't
        message = `${linkedCount} of ${totalCount} tunes matched`;
        type = 'success';
    }
    
    showMessage(message, type);
}

// Auto-match a tune against the database without saving
async function autoMatchTune(pill, stillTyping = false) {
    try {
        // Find the previous tune type if this pill is in a set
        let previousTuneType = null;
        
        // Check if the pill already has a previousTuneType set (for typing pills)
        if (pill.previousTuneType !== undefined) {
            previousTuneType = pill.previousTuneType;
            console.log(`Using pre-calculated previous tune type: ${previousTuneType}`);
        } else {
            // Find which set this pill belongs to
            for (let setIndex = 0; setIndex < tunePillsData.length; setIndex++) {
                const set = tunePillsData[setIndex];
                const pillIndex = set.findIndex(p => p.id === pill.id);
                
                if (pillIndex > 0) {
                    // This pill is not the first in the set, check previous pills for tune type
                    for (let i = pillIndex - 1; i >= 0; i--) {
                        if (set[i].tuneType) {
                            previousTuneType = set[i].tuneType;
                            break;
                        }
                    }
                    break;
                }
            }
        }
        
        const response = await fetch(`/api/sessions/${sessionPath}/${sessionDate}/match_tune`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                tune_name: pill.tuneName,
                previous_tune_type: previousTuneType
            })
        });
        
        // Check for authentication error specifically
        if (response.status === 401) {
            console.warn('Authentication required for tune matching');
            // Show message to user
            showMessage('You must log in to match tunes', 'warning');
            // Set pill to unlinked state so it's not spinning
            pill.state = 'unlinked';
            pill.authenticationFailed = true;  // Mark that this failed due to auth
            pill.matchResults = null;
            // Skip updating appearance for typing pills as they don't exist in the DOM yet
            if (!pill.id.startsWith('typing-')) {
                PillRenderer.updatePillAppearance(pill);
            }
            return;
        }
        
        if (!response.ok) {
            console.warn(`Failed to match tune "${pill.tuneName}": ${response.status}`);
            // Try to get error details if response is JSON
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                const errorData = await response.json();
                console.warn('Error response:', errorData);
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success && result.results) {
            // Store the results on the pill for later use
            pill.matchResults = result.results;
            
            if (result.results.length === 1 && result.exact_match) {
                // Single exact match - automatically apply it
                const match = result.results[0];
                pill.tuneId = match.tune_id;
                pill.tuneName = match.tune_name;
                pill.tuneType = match.tune_type;
                pill.state = 'linked';
                pill.matchResults = null; // Clear stored results
                console.log(`Successfully matched "${pill.tuneName}" -> "${match.tune_name}" (ID: ${match.tune_id})`);
                
                // Mark as dirty since we changed the pill
                AutoSaveManager.forceCheckChanges();
                
            } else if (result.results.length > 1) {
                // Multiple matches - mark as unmatched and store results
                pill.state = 'unmatched';
                console.log(`Multiple matches found for "${pill.tuneName}": ${result.results.length} results`);
                
                // Mark as dirty since we changed the pill state
                AutoSaveManager.forceCheckChanges();
                
                // Show context menu with results if still typing/editing
                if (stillTyping) {
                    ContextMenu.showMatchResultsMenu(pill);
                } else {
                    // User has exited text entry - hide any existing menu
                    ContextMenu.hideMatchResultsMenu(pill.id);
                }
                
            } else if (result.results.length === 1 && !result.exact_match) {
                // Single wildcard match
                if (stillTyping) {
                    // While typing, just show the option but don't auto-apply
                    pill.state = 'unmatched';
                    AutoSaveManager.forceCheckChanges();
                    ContextMenu.showMatchResultsMenu(pill);
                } else {
                    // When finished typing, auto-apply single wildcard match
                    const match = result.results[0];
                    pill.tuneId = match.tune_id;
                    pill.tuneName = match.tune_name;
                    pill.tuneType = match.tune_type;
                    pill.state = 'linked';
                    pill.matchResults = null;
                    console.log(`Auto-applied single wildcard match: "${pill.tuneName}" -> "${match.tune_name}" (ID: ${match.tune_id})`);
                    
                    // Mark as dirty since we changed the pill
                    AutoSaveManager.forceCheckChanges();
                }
                
            } else {
                // No matches at all
                pill.state = 'unlinked';
                pill.matchResults = null;
                console.log(`No match found for "${pill.tuneName}"`);
                
                // Mark as dirty since we changed the pill state
                AutoSaveManager.forceCheckChanges();
            }
        } else {
            // Error or unexpected response format
            pill.state = 'unlinked';
            pill.matchResults = null;
            console.warn(`Unexpected response format for "${pill.tuneName}"`);
            
            // Mark as dirty since we changed the pill state
            AutoSaveManager.markDirty();
        }
        
        // Update just this pill instead of re-rendering everything
        // Skip updating appearance for typing pills as they don't exist in the DOM yet
        if (!pill.id.startsWith('typing-')) {
            PillRenderer.updatePillAppearance(pill);
        }
    } catch (error) {
        console.error(`Network error matching tune "${pill.tuneName}":`, error);
        // Network error - pill becomes unlinked
        pill.state = 'unlinked';
        pill.matchResults = null;
        
        // Mark as dirty since we changed the pill state
        AutoSaveManager.markDirty();
        
        // Skip updating appearance for typing pills as they don't exist in the DOM yet
        if (!pill.id.startsWith('typing-')) {
            PillRenderer.updatePillAppearance(pill);
        }
    }
}


function deleteTuneAtCursor() {
    const cursorPosition = CursorManager.getCursorPosition();
    if (!cursorPosition) return;
    
    const { setIndex, pillIndex, position } = cursorPosition;
    
    // Always delete the pill immediately to the left of the cursor (backspace behavior)
    let tuneToDelete = null;
    let newCursorPosition = null;
    
    if (position === 'after') {
        // Cursor is after a pill - delete that pill
        tuneToDelete = { setIndex, pillIndex };
        // After deletion, if there's a pill to the left, position after it
        if (pillIndex > 0) {
            newCursorPosition = { setIndex, pillIndex: pillIndex - 1, position: 'after' };
        } else {
            // Deleting first pill of the set - check if it's the only pill
            if (tunePillsData[setIndex].length === 1) {
                // This is the only pill in the set - set should become a temporary empty line
                newCursorPosition = { setIndex, pillIndex: 0, position: 'before' };
            } else {
                // There are other pills in the set, position before the next pill
                newCursorPosition = { setIndex, pillIndex: 0, position: 'before' };
            }
        }
    } else if (position === 'before' && pillIndex > 0) {
        // Cursor is before a pill - delete the previous pill
        tuneToDelete = { setIndex, pillIndex: pillIndex - 1 };
        // After deletion, cursor stays before the same pill (which now has a lower index)
        newCursorPosition = { setIndex, pillIndex: pillIndex - 1, position: 'before' };
    } else if (position === 'before' && pillIndex === 0) {
        // Cursor is at the beginning of a set - for backspace, we don't delete anything here
        // This case should be handled by the caller (e.g., merge with previous line if empty)
        return;
    } else if (position === 'newset' && setIndex > 0 && tunePillsData[setIndex - 1].length > 0) {
        // Cursor is at a new set position - delete the last pill of the previous set
        const prevSetIndex = setIndex - 1;
        const prevSetLength = tunePillsData[prevSetIndex].length;
        tuneToDelete = { setIndex: prevSetIndex, pillIndex: prevSetLength - 1 };
        newCursorPosition = { setIndex: prevSetIndex, pillIndex: prevSetLength - 1, position: 'after' };
    }
    
    if (tuneToDelete) {
        undoRedoManager.saveToUndo();
        const targetSet = tunePillsData[tuneToDelete.setIndex];
        const wasLastPillInSet = targetSet.length === 1; // Check before deletion
        targetSet.splice(tuneToDelete.pillIndex, 1);
        
        // Check if this deletion creates a temporary empty set
        // This happens when deleting the only pill in a set and cursor stays in that set
        const shouldCreateTemporaryEmpty = (targetSet.length === 0 && 
                                            wasLastPillInSet &&
                                            newCursorPosition && 
                                            newCursorPosition.setIndex === tuneToDelete.setIndex &&
                                            newCursorPosition.position === 'before');
        
        // Handle empty sets
        const setWasRemoved = targetSet.length === 0 && !shouldCreateTemporaryEmpty;
        if (setWasRemoved) {
            tunePillsData.splice(tuneToDelete.setIndex, 1);
        } else if (shouldCreateTemporaryEmpty) {
            // Mark this as a temporary empty set
            temporaryEmptySet = tuneToDelete.setIndex;
        }
        
        // Update StateManager with the modified data
        StateManager.setTunePillsData(tunePillsData);
        
        // Render first, then set cursor position
        PillRenderer.renderTunePills();
        
        // Apply the cursor position after rendering when cursor position elements exist
        if (setWasRemoved) {
            // Set was removed - use the stored cursor position but adjust for removed set
            if (newCursorPosition.setIndex < tuneToDelete.setIndex) {
                // Cursor position is in a set before the deleted one, no adjustment needed
                CursorManager.setCursorPosition(newCursorPosition.setIndex, newCursorPosition.pillIndex, newCursorPosition.position);
            } else if (newCursorPosition.setIndex === tuneToDelete.setIndex) {
                // Cursor was in the deleted set, position at the beginning of next set or end
                if (tuneToDelete.setIndex < tunePillsData.length) {
                    CursorManager.setCursorPosition(tuneToDelete.setIndex, 0, 'before');
                } else if (tuneToDelete.setIndex > 0) {
                    // No next set, go to end of previous set
                    CursorManager.setCursorPosition(tuneToDelete.setIndex - 1, tunePillsData[tuneToDelete.setIndex - 1].length - 1, 'after');
                } else {
                    // No sets left
                    CursorManager.setCursorPosition(0, 0, 'newset');
                }
            } else {
                // Cursor position is after deleted set, adjust index
                CursorManager.setCursorPosition(newCursorPosition.setIndex - 1, newCursorPosition.pillIndex, newCursorPosition.position);
            }
        } else if (shouldCreateTemporaryEmpty) {
            // Set exists but is now empty (temporary empty set)
            // Position cursor at the beginning of the empty set
            CursorManager.setCursorPosition(newCursorPosition.setIndex, 0, 'before');
        } else {
            // Set still exists and has pills, use the calculated new cursor position
            if (newCursorPosition.pillIndex >= targetSet.length) {
                // Position is beyond the end of the set, position after last pill
                CursorManager.setCursorPosition(newCursorPosition.setIndex, targetSet.length - 1, 'after');
            } else if (newCursorPosition.pillIndex < 0) {
                // Position is before the beginning, position before first pill
                CursorManager.setCursorPosition(newCursorPosition.setIndex, 0, 'before');
            } else {
                // Position is valid
                CursorManager.setCursorPosition(newCursorPosition.setIndex, newCursorPosition.pillIndex, newCursorPosition.position);
            }
        }
    }
}

// Cursor movement functions
// Cursor movement functions now handled directly by CursorManager

// Event listeners setup
function setupEventListeners() {
    // Container click to focus
    const tuneContainer = document.getElementById('tune-pills-container');
    tuneContainer.addEventListener('click', (e) => {
        
        // Don't handle clicks on tune pills or their children (they have their own handlers)
        if (e.target.closest('.tune-pill')) {
            return;
        }
        
        // Don't handle clicks on context menus
        if (e.target.closest('.tune-context-menu')) {
            return;
        }
        
        // Check if click is on a cursor position element (they handle themselves)
        if (e.target.classList.contains('cursor-position')) {
            return;
        }
        
        // Check if clicking on a tune-set - find the best cursor position
        if (e.target.classList.contains('tune-set')) {
            const setIndex = parseInt(e.target.dataset.setIndex);
            const rect = e.target.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const setWidth = rect.width;
            const setLength = tunePillsData[setIndex]?.length || 0;
            
            
            // Find the actual position of tune pills within the set
            const pillElements = e.target.querySelectorAll('.tune-pill');
            let bestPosition = null;
            let closestDistance = Infinity;
            
            // Check distance to each pill to find the closest cursor position
            pillElements.forEach((pill, pillIndex) => {
                const pillRect = pill.getBoundingClientRect();
                const pillCenterX = pillRect.left + pillRect.width / 2 - rect.left;
                const pillEndX = pillRect.right - rect.left;
                
                // Distance to "before" position (left edge of pill)
                const distanceToBefore = Math.abs(clickX - (pillRect.left - rect.left));
                if (distanceToBefore < closestDistance) {
                    closestDistance = distanceToBefore;
                    bestPosition = { pillIndex, position: 'before' };
                }
                
                // Distance to "after" position (right edge of pill)
                const distanceToAfter = Math.abs(clickX - pillEndX);
                if (distanceToAfter < closestDistance) {
                    closestDistance = distanceToAfter;
                    bestPosition = { pillIndex, position: 'after' };
                }
            });
            
            // If click is beyond the last pill, always position at end
            if (pillElements.length > 0) {
                const lastPillRect = pillElements[pillElements.length - 1].getBoundingClientRect();
                const lastPillEnd = lastPillRect.right - rect.left;
                if (clickX > lastPillEnd) {
                    bestPosition = { pillIndex: setLength - 1, position: 'after' };
                }
            }
            
            // Fallback: if no pills or click is before first pill
            if (!bestPosition) {
                bestPosition = { pillIndex: 0, position: 'before' };
            }
            
            
            // If user is typing, finish typing first
            if (textInput && textInput.typing) {
                textInput.finishTyping(CursorManager.isMobileDevice());
            }
            
            // Clear selection and selection anchor when clicking to move cursor
            CursorManager.clearSelection();
            
            CursorManager.setCursorPosition(setIndex, bestPosition.pillIndex, bestPosition.position);
            return;
        }
        
        // For clicks in other empty space, set cursor at end
        
        // If user is typing, finish typing first
        if (textInput && textInput.typing) {
            textInput.finishTyping(CursorManager.isMobileDevice());
        }
        
        // Clear selection and selection anchor when clicking to move cursor
        CursorManager.clearSelection();
        
        CursorManager.setCursorPosition(tunePillsData.length, 0, 'newset');
    });
    
    // Mobile touch handling for container (cursor placement and scrolling)
    let containerTouchStart = null;
    let containerTouchMoved = false;
    
    tuneContainer.addEventListener('touchstart', (e) => {
        // Don't handle touches on tune pills (they have their own handlers)
        if (e.target.closest('.tune-pill')) {
            return;
        }
        
        // Don't handle touches on context menus or cursor positions
        if (e.target.closest('.tune-context-menu') || e.target.classList.contains('cursor-position')) {
            return;
        }
        
        containerTouchStart = {
            x: e.touches[0].clientX,
            y: e.touches[0].clientY,
            time: Date.now(),
            target: e.target
        };
        containerTouchMoved = false;
    });
    
    tuneContainer.addEventListener('touchmove', (e) => {
        if (containerTouchStart) {
            containerTouchMoved = true;
            // Let browser handle scrolling
        }
    });
    
    tuneContainer.addEventListener('touchend', (e) => {
        if (!containerTouchStart) return;
        
        const touchDuration = Date.now() - containerTouchStart.time;
        
        // If it was a quick tap without movement, treat as cursor placement
        if (!containerTouchMoved && touchDuration < 500) {
            const touch = e.changedTouches[0];
            
            // Create a synthetic click event to reuse existing click logic
            const clickEvent = new MouseEvent('click', {
                clientX: touch.clientX,
                clientY: touch.clientY,
                bubbles: true,
                cancelable: true
            });
            
            // Set the target and trigger the existing click handler logic
            Object.defineProperty(clickEvent, 'target', { value: containerTouchStart.target });
            
            // Manually execute the cursor positioning logic
            if (containerTouchStart.target.classList.contains('tune-set')) {
                const setIndex = parseInt(containerTouchStart.target.dataset.setIndex);
                const rect = containerTouchStart.target.getBoundingClientRect();
                const clickX = touch.clientX - rect.left;
                const setWidth = rect.width;
                const setLength = tunePillsData[setIndex]?.length || 0;
                
                // Find best cursor position (reusing click logic)
                let bestPosition = null;
                
                if (setLength > 0) {
                    // Find position relative to pills
                    const relativePosition = clickX / setWidth;
                    const estimatedPillIndex = Math.floor(relativePosition * setLength);
                    const clampedIndex = Math.max(0, Math.min(setLength - 1, estimatedPillIndex));
                    
                    if (relativePosition < (clampedIndex + 0.5) / setLength) {
                        bestPosition = { pillIndex: clampedIndex, position: 'before' };
                    } else {
                        bestPosition = { pillIndex: clampedIndex, position: 'after' };
                    }
                    
                    if (relativePosition > 0.9) {
                        bestPosition = { pillIndex: setLength - 1, position: 'after' };
                    }
                }
                
                if (!bestPosition) {
                    bestPosition = { pillIndex: 0, position: 'before' };
                }
                
                // If user is typing, finish typing first
                if (textInput && textInput.typing) {
                    textInput.finishTyping(true); // Always keep keyboard open on mobile touch
                }
                
                // Clear selection when touching to move cursor
                CursorManager.clearSelection();
                
                CursorManager.setCursorPosition(setIndex, bestPosition.pillIndex, bestPosition.position);
            } else {
                // Touch in empty space - set cursor at end
                if (textInput && textInput.typing) {
                    textInput.finishTyping(true); // Always keep keyboard open on mobile touch
                }
                
                PillSelection.selectNone();
                
                CursorManager.setCursorPosition(tunePillsData.length, 0, 'newset');
            }
            
            e.preventDefault();
        }
        // If touch moved, allow normal scroll behavior (no preventDefault)
        
        containerTouchStart = null;
    });
    
    // Keyboard shortcuts and text input - handled by KeyboardHandler module
    KeyboardHandler.setupKeyboardListeners();
    
    // Container drag and drop event listeners
    DragDrop.setupContainerDragListeners();
    
    // Modal event listeners
    document.getElementById('link-cancel-btn').addEventListener('click', hideLinkModal);
    document.getElementById('link-confirm-btn').addEventListener('click', confirmLink);
    document.getElementById('edit-tune-cancel-btn').addEventListener('click', hideEditModal);
    document.getElementById('edit-tune-save-btn').addEventListener('click', confirmEdit);
}

// Modal control functions
function hideLinkModal() {
    ModalManager.hideModal('link-tune-modal');
    window.currentLinkingPill = null;
}

function hideEditModal() {
    ModalManager.hideModal('edit-tune-modal');
    window.currentEditingPill = null;
}

function confirmLink() {
    const input = document.getElementById('tune-link-input').value.trim();
    if (!input || !window.currentLinkingPill) return;

    // Extract tune ID from URL or use as is
    let tuneId = input;
    const urlMatch = input.match(/thesession\.org\/tunes\/(\d+)/);
    if (urlMatch) {
        tuneId = urlMatch[1];
    }

    if (!/^\d+$/.test(tuneId)) {
        showMessage('Please enter a valid tune ID or thesession.org URL', 'error');
        return;
    }

    undoRedoManager.saveToUndo();

    // Store the user-provided name before linking
    // This will be saved as an alias if it differs from the canonical name
    const userProvidedName = window.currentLinkingPill.tuneName;

    // Update the pill
    window.currentLinkingPill.tuneId = parseInt(tuneId);
    window.currentLinkingPill.tuneName = userProvidedName; // Keep the user's name
    window.currentLinkingPill.state = 'linked';

    PillRenderer.renderTunePills();
    hideLinkModal();

    showMessage('Tune linked successfully!', 'success');
}

function confirmEdit() {
    const newName = document.getElementById('edit-tune-name-input').value.trim();
    if (!newName || !window.currentEditingPill) return;
    
    undoRedoManager.saveToUndo();
    
    const pill = window.currentEditingPill;
    
    // Update the tune name
    pill.tuneName = newName;
    
    // Mark as dirty since we changed the pill
    AutoSaveManager.forceCheckChanges();
    
    // If the tune was linked, unlink it first and re-run matching
    if (pill.state === 'linked') {
        // Unlink the tune
        pill.tuneId = null;
        pill.setting = null;
        pill.tuneType = null;
        pill.state = 'loading';  // Show loading state while re-matching
        
        // Update the pill appearance immediately to show loading state
        PillRenderer.updatePillAppearance(pill);
        
        // Re-run auto-matching with the new name
        autoMatchTune(pill);
    } else {
        // If it was unlinked, still try to match the new name
        pill.state = 'loading';
        PillRenderer.updatePillAppearance(pill);
        autoMatchTune(pill);
    }
    
    hideEditModal();
    showMessage('Tune name updated!', 'success');
}

// Session edit functionality (reused from original)
function setupSessionEditListeners() {
    document.getElementById('edit-date-btn').addEventListener('click', showEditSessionModal);
    document.getElementById('edit-session-cancel-btn').addEventListener('click', hideSessionEditModal);
    document.getElementById('edit-session-save-btn').addEventListener('click', saveSessionInstance);
}

function setupSaveListeners() {
    // Save button click
    document.getElementById('save-session-btn').addEventListener('click', () => {
        // Cancel auto-save timer immediately when manually saving
        AutoSaveManager.autoSaveTimer.stop();
        AutoSaveManager.autoSaveTimer.hideCountdown();
        
        // Perform the save
        AutoSaveManager.saveSession();
    });
    
    // Auto-save checkbox change
    document.getElementById('auto-save-checkbox').addEventListener('change', () => AutoSaveManager.setupAutoSave());
    
    // Auto-save interval change
    document.getElementById('auto-save-interval').addEventListener('change', () => {
        const autoSaveCheckbox = document.getElementById('auto-save-checkbox');
        const intervalSelect = document.getElementById('auto-save-interval');
        
        if (autoSaveCheckbox.checked) {
            // If auto-save is enabled, restart with new interval
            AutoSaveManager.setupAutoSave();
        } else {
            // If auto-save is disabled, just save the interval preference
            AutoSaveManager.saveAutoSavePreference(false, parseInt(intervalSelect.value));
        }
    });
    
    // Cancel auto-save link
    document.getElementById('cancel-auto-save').addEventListener('click', (e) => {
        e.preventDefault();
        AutoSaveManager.cancelAutoSave();
    });
}

function showEditSessionModal() {
    // Populate form data first (page-specific business logic)
    const dateInput = document.getElementById('edit-session-date-input');
    const locationInput = document.getElementById('edit-session-location-input');
    const commentsInput = document.getElementById('edit-session-comments-input');
    const cancelledInput = document.getElementById('edit-session-cancelled-input');
    
    dateInput.value = sessionInstanceData.date;
    locationInput.value = sessionInstanceData.location_override || '';
    commentsInput.value = sessionInstanceData.comments || '';
    cancelledInput.checked = sessionInstanceData.is_cancelled;
    
    // Show modal with generic ModalManager
    ModalManager.showModal('edit-session-instance-modal', {
        autoFocus: false // We'll focus manually
    });
    
    dateInput.focus();
}

function hideSessionEditModal() {
    ModalManager.hideModal('edit-session-instance-modal');
}

function saveSessionInstance() {
    const dateInput = document.getElementById('edit-session-date-input');
    const locationInput = document.getElementById('edit-session-location-input');
    const commentsInput = document.getElementById('edit-session-comments-input');
    const cancelledInput = document.getElementById('edit-session-cancelled-input');
    
    const date = dateInput.value.trim();
    const location = locationInput.value.trim();
    const comments = commentsInput.value.trim();
    const cancelled = cancelledInput.checked;
    
    if (!date) {
        showMessage('Please enter a session date', 'error');
        return;
    }
    
    const requestData = { 
        date: date,
        cancelled: cancelled
    };
    
    if (location) requestData.location = location;
    if (comments) requestData.comments = comments;
    
    fetch(`/api/sessions/${sessionPath}/${sessionDate}/update`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(data.message);
            hideSessionEditModal();
            if (date !== sessionDate) {
                window.location.href = `/sessions/${sessionPath}/${date}/beta`;
            } else {
                window.location.reload();
            }
        } else {
            showMessage(data.message, 'error');
        }
    })
    .catch(error => {
        showMessage('Failed to update session instance', 'error');
        console.error('Error:', error);
    });
}

// Message display function - uses the existing base template flash message system
function showMessage(message, type = 'success') {
    return ModalManager.showMessage(message, type);
}

// Mark complete link event listener (if link exists)
const markCompleteLink = document.getElementById('mark-complete-link');
if (markCompleteLink) {
    markCompleteLink.addEventListener('click', function(event) {
        event.preventDefault();
        markSessionLogComplete();
    });
}

// Mark incomplete link event listener (if link exists)
const markIncompleteLink = document.getElementById('mark-incomplete-link');
if (markIncompleteLink) {
    markIncompleteLink.addEventListener('click', function(event) {
        event.preventDefault();
        markSessionLogIncomplete();
    });
}

function markSessionLogComplete() {
    if (!confirm('Mark this session log as complete? This will switch to view mode and hide the edit button from non-admins.')) {
        return;
    }
    
    fetch(`/api/sessions/${sessionPath}/${sessionDate}/mark_complete`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(data.message);
            // Redirect to normal view after a short delay
            setTimeout(() => {
                window.location.href = `/sessions/${sessionPath}/${sessionDate}`;
            }, 1500);
        } else {
            showMessage(data.message, 'error');
        }
    })
    .catch(error => {
        showMessage('Failed to mark session log complete', 'error');
        console.error('Error:', error);
    });
}

function markSessionLogIncomplete() {
    if (!confirm('Mark this session log as not complete? This will allow all users to edit it again.')) {
        return;
    }
    
    fetch(`/api/sessions/${sessionPath}/${sessionDate}/mark_incomplete`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(data.message);
            // Reload the page to show updated status
            setTimeout(() => {
                window.location.href = `/sessions/${sessionPath}/${sessionDate}/beta`;
            }, 1500);
        } else {
            showMessage(data.message, 'error');
        }
    })
    .catch(error => {
        showMessage('Failed to mark session log as not complete', 'error');
        console.error('Error:', error);
    });
}

/**
 * Handle finishTyping calls from the keyboard handler
 * Always keep keyboard open on mobile when cursor is active
 */
function finishTypingFromKeyboard() {
    const isMobile = CursorManager.isMobileDevice();
    
    // On mobile, always try to keep keyboard open for continued input
    if (isMobile) {
        // Call finishTyping with keepKeyboard=true
        textInput.finishTyping(true);
        
        // Also ensure container stays focused after any DOM updates
        setTimeout(() => {
            const container = document.getElementById('tune-pills-container');
            const hasOpenModal = document.body.classList.contains('modal-open');
            if (container && !hasOpenModal) {
                container.contentEditable = 'true';
                container.inputMode = 'text';
                if (document.activeElement !== container) {
                    container.focus();
                }
            }
        }, 100);
    } else {
        // Desktop behavior - normal finish typing
        textInput.finishTyping(false);
    }
}

/**
 * Wrapper for finishTyping that ensures mobile keyboard stays open after pill creation
 */
function finishTypingWithKeyboardFix(keepKeyboard) {
    const isMobile = CursorManager.isMobileDevice();
    
    // On mobile, always try to keep keyboard open, regardless of the keepKeyboard parameter
    const shouldKeepKeyboard = isMobile ? true : keepKeyboard;
    
    // Call the original finishTyping method
    textInput.finishTyping(shouldKeepKeyboard);
    
    // On mobile, ensure focus is maintained after any DOM updates
    if (isMobile) {
        setTimeout(() => {
            const container = document.getElementById('tune-pills-container');
            const hasOpenModal = document.body.classList.contains('modal-open');
            if (container && document.activeElement !== container && !hasOpenModal) {
                container.contentEditable = 'true';
                container.inputMode = 'text';
                container.focus();
            }
        }, 150); // Wait for DOM updates and original textInput timeout
    }
}

/**
 * Set up mobile keyboard management to ensure keyboard stays visible
 */
function setupMobileKeyboardManagement() {
    if (!CursorManager.isMobileDevice()) {
        return; // Only needed on mobile
    }
    
    const container = document.getElementById('tune-pills-container');
    if (!container) {
        return;
    }
    
    // Monitor for blur events and restore focus if cursor is still active
    container.addEventListener('blur', function() {
        // Small delay to check if we should restore focus
        setTimeout(() => {
            const cursorPosition = CursorManager.getCursorPosition();
            const hasOpenModal = document.body.classList.contains('modal-open');
            if (cursorPosition && !textInput.typing && !hasOpenModal) {
                // Cursor is active but container lost focus - restore it
                container.contentEditable = 'true';
                container.inputMode = 'text';
                container.focus();
            }
        }, 50);
    });
    
    // Monitor for DOM changes that might reset contentEditable
    const observer = new MutationObserver(() => {
        const cursorPosition = CursorManager.getCursorPosition();
        const hasOpenModal = document.body.classList.contains('modal-open');
        if (cursorPosition && container.contentEditable !== 'true' && !hasOpenModal) {
            // Container was reset but cursor is still active
            container.contentEditable = 'true';
            container.inputMode = 'text';
            if (document.activeElement !== container) {
                container.focus();
            }
        }
    });
    
    observer.observe(container, {
        attributes: true,
        attributeFilter: ['contenteditable'],
        childList: true,
        subtree: true
    });
}

/**
 * Synchronize the native browser cursor position with the blue cursor position
 * This prevents the dual-cursor issue on mobile devices
 */
function syncNativeCursorPosition() {
    const container = document.getElementById('tune-pills-container');
    if (!container || container.contentEditable !== 'true') {
        return;
    }
    
    const cursorPosition = CursorManager.getCursorPosition();
    if (!cursorPosition) {
        return;
    }
    
    try {
        // Find the cursor element that represents our current position
        const cursorElement = document.querySelector('.text-cursor');
        if (!cursorElement) {
            return;
        }
        
        // Create a range and set it to the cursor element's position
        const selection = window.getSelection();
        const range = document.createRange();
        
        // Position the native cursor at the same location as our blue cursor
        // We'll place it right before the cursor element
        range.setStartBefore(cursorElement);
        range.setEndBefore(cursorElement);
        
        // Apply the selection to sync the native cursor
        selection.removeAllRanges();
        selection.addRange(range);
        
    } catch (error) {
        // Silently handle any errors in cursor positioning
        // This prevents breaking the editor if there are DOM structure issues
        console.debug('Could not sync native cursor position:', error);
    }
}