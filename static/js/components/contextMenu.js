/**
 * Context Menu Module
 * Handles the creation and management of context menus for tune pills
 */
class ContextMenu {
    
    /**
     * Remove all context menus and reset chevron states
     * @param {string} [pillId] - Optional pill ID for specific targeting
     */
    static hideContextMenu(pillId) {
        // Remove all context menus and reset chevron states
        document.querySelectorAll('.tune-context-menu').forEach(menu => menu.remove());
        document.querySelectorAll('.chevron.open').forEach(chevron => chevron.classList.remove('open'));
    }
    
    /**
     * Remove match results menu for specific pill
     * @param {string} pillId - The pill ID to hide match results for
     */
    static hideMatchResultsMenu(pillId) {
        const menu = document.querySelector(`.match-results-menu[data-pill-id="${pillId}"]`);
        if (menu) {
            menu.remove();
        }
    }
    
    /**
     * Show context menu for a pill
     * @param {Event} event - The click event that triggered the menu
     * @param {Object} pillData - The pill data object
     */
    static showContextMenu(event, pillData) {
        // Remove existing context menus and reset all chevrons
        ContextMenu.hideContextMenu();
        
        const menu = document.createElement('div');
        menu.className = 'tune-context-menu';
        menu.style.display = 'block';
        menu.dataset.pillId = pillData.id; // Track which pill this menu belongs to
        
        // Find the pill element to match its dimensions and color
        const pillElement = event.target.closest('.tune-pill');
        const rect = pillElement.getBoundingClientRect();
        
        // Set chevron to open state
        const chevron = pillElement.querySelector('.chevron');
        chevron.classList.add('open');
        
        // Position menu
        menu.style.position = 'fixed';
        menu.style.left = rect.left + 'px';
        menu.style.top = (rect.bottom + 5) + 'px';
        
        // For unmatched pills with results or unlinked pills, make menu wider to accommodate content
        if ((pillData.state === 'unmatched' && pillData.matchResults && pillData.matchResults.length > 0) || 
            pillData.state === 'unlinked') {
            menu.style.width = 'auto';
            menu.style.minWidth = Math.max(250, rect.width) + 'px';
            menu.style.maxWidth = Math.min(500, window.innerWidth - rect.left - 20) + 'px';
        } else {
            // Match pill width for other states
            menu.style.width = rect.width + 'px';
            menu.style.minWidth = 'unset';
        }
        
        // Match pill background color based on state
        const computedStyle = window.getComputedStyle(pillElement);
        menu.style.backgroundColor = computedStyle.backgroundColor;
        menu.style.color = computedStyle.color;
        menu.style.borderColor = computedStyle.borderColor;
        
        // Create menu items based on pill state
        if (pillData.state === 'linked') {
            // Linked tune options
            ContextMenu.addMenuItem(menu, 'Dots', () => {
                const url = `https://thesession.org/tunes/${pillData.tuneId}${pillData.setting ? '#setting' + pillData.setting : ''}`;
                window.open(url, '_blank');
                ContextMenu.hideContextMenu();
            });
            
            ContextMenu.addMenuItem(menu, 'Relink', () => {
                ContextMenu.showLinkModal(pillData);
                ContextMenu.hideContextMenu();
            });
        } else if (pillData.state === 'unmatched' && pillData.matchResults && pillData.matchResults.length > 0) {
            // Show match results first if available
            pillData.matchResults.forEach(result => {
                const item = document.createElement('a');
                item.style.display = 'block';
                item.style.padding = '8px 12px';
                item.style.cursor = 'pointer';
                item.style.borderBottom = '1px solid rgba(255,255,255,0.2)';
                
                // Show tune name and type
                const nameSpan = document.createElement('span');
                nameSpan.textContent = result.tune_name;
                nameSpan.style.fontWeight = '500';
                item.appendChild(nameSpan);
                
                if (result.tune_type) {
                    const typeSpan = document.createElement('span');
                    typeSpan.textContent = ` (${result.tune_type})`;
                    typeSpan.style.opacity = '0.8';
                    typeSpan.style.fontSize = '0.9em';
                    item.appendChild(typeSpan);
                }
                
                // Click to select this match
                item.addEventListener('click', () => {
                    // Apply the selected match
                    pillData.tuneId = result.tune_id;
                    pillData.tuneName = result.tune_name;
                    pillData.tuneType = result.tune_type;
                    pillData.state = 'linked';
                    pillData.matchResults = null;
                    
                    // Update the pill appearance
                    PillRenderer.updatePillAppearance(pillData);
                    
                    // Force check for changes (includes timer reset and dirty state)
                    AutoSaveManager.forceCheckChanges();
                    ContextMenu.hideContextMenu();
                });
                
                menu.appendChild(item);
            });
            
            // Add separator
            const separator = document.createElement('div');
            separator.style.borderTop = '1px solid rgba(255,255,255,0.3)';
            separator.style.margin = '4px 0';
            menu.appendChild(separator);
            
            // Add manual link option
            ContextMenu.addMenuItem(menu, 'Manual Link...', () => {
                ContextMenu.showLinkModal(pillData);
                ContextMenu.hideContextMenu();
            });
        } else {
            // Unlinked tune options
            ContextMenu.addMenuItem(menu, 'Link', () => {
                ContextMenu.showLinkModal(pillData);
                ContextMenu.hideContextMenu();
            });
        }
        
        // Common options
        ContextMenu.addMenuItem(menu, 'Edit Text', () => {
            ContextMenu.showEditModal(pillData);
            ContextMenu.hideContextMenu();
        });
        
        if (PillSelection.getSelectionCount() <= 1) {
            ContextMenu.addMenuItem(menu, 'Delete', () => {
                ContextMenu.deletePill(pillData.id);
                ContextMenu.hideContextMenu();
            });
        } else {
            ContextMenu.addMenuItem(menu, `Delete Selected (${PillSelection.getSelectionCount()})`, () => {
                PillSelection.deleteSelectedPills();
                ContextMenu.hideContextMenu();
            });
        }
        
        document.body.appendChild(menu);
        
        // Hide menu when clicking elsewhere or scrolling
        setTimeout(() => {
            const hideMenu = (e) => {
                if (!menu.contains(e.target)) {
                    ContextMenu.hideContextMenu();
                    document.removeEventListener('click', hideMenu);
                    document.removeEventListener('scroll', hideOnScroll, true);
                }
            };
            
            const hideOnScroll = () => {
                ContextMenu.hideContextMenu();
                document.removeEventListener('click', hideMenu);
                document.removeEventListener('scroll', hideOnScroll, true);
            };
            
            document.addEventListener('click', hideMenu);
            // Use capture phase to catch scroll on any element
            document.addEventListener('scroll', hideOnScroll, true);
        }, 0);
    }
    
    /**
     * Show match results menu for a pill during typing
     * @param {Object} pill - The pill data object with match results
     */
    static showMatchResultsMenu(pill) {
        // Remove any existing match results menu for this pill
        ContextMenu.hideMatchResultsMenu(pill.id);
        
        if (!pill.matchResults || pill.matchResults.length === 0) {
            return;
        }
        
        // Find the pill element
        const pillElement = document.querySelector(`[data-pill-id="${pill.id}"]`);
        if (!pillElement) {
            console.error(`Could not find pill element for ID: ${pill.id}`);
            return;
        }
        
        const menu = document.createElement('div');
        menu.className = 'tune-context-menu match-results-menu';
        menu.style.display = 'block';
        menu.dataset.pillId = pill.id;
        
        const rect = pillElement.getBoundingClientRect();
        
        // Position menu below the pill
        menu.style.position = 'fixed';
        menu.style.left = rect.left + 'px';
        menu.style.top = (rect.bottom + 5) + 'px';
        menu.style.width = 'auto';
        menu.style.minWidth = Math.max(200, rect.width) + 'px';
        menu.style.maxWidth = Math.min(600, window.innerWidth - rect.left - 20) + 'px';
        
        // Use a neutral background for the menu
        menu.style.backgroundColor = 'white';
        menu.style.color = '#212529';
        menu.style.border = '1px solid #dee2e6';
        menu.style.borderRadius = '4px';
        menu.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
        
        // Add match results as menu items
        pill.matchResults.forEach(result => {
            const item = document.createElement('a');
            item.style.display = 'block';
            item.style.padding = '8px 12px';
            item.style.cursor = 'pointer';
            item.style.borderBottom = '1px solid #f0f0f0';
            item.style.color = '#212529';
            item.style.textDecoration = 'none';
            
            // Show tune name and type
            const nameSpan = document.createElement('span');
            nameSpan.textContent = result.tune_name;
            nameSpan.style.fontWeight = '500';
            item.appendChild(nameSpan);
            
            if (result.tune_type) {
                const typeSpan = document.createElement('span');
                typeSpan.textContent = ` (${result.tune_type})`;
                typeSpan.style.color = '#6c757d';
                typeSpan.style.fontSize = '0.9em';
                item.appendChild(typeSpan);
            }
            
            // Hover effect
            item.addEventListener('mouseenter', () => {
                item.style.backgroundColor = '#f8f9fa';
            });
            item.addEventListener('mouseleave', () => {
                item.style.backgroundColor = 'transparent';
            });
            
            // Click to select this match
            item.addEventListener('click', () => {
                // Apply the selected match
                pill.tuneId = result.tune_id;
                pill.tuneName = result.tune_name;
                pill.tuneType = result.tune_type;
                pill.state = 'linked';
                pill.matchResults = null;
                
                // Update the pill appearance
                PillRenderer.updatePillAppearance(pill);
                
                // Force check for changes (includes timer reset and dirty state)
                AutoSaveManager.forceCheckChanges();
                
                // Hide the menu
                ContextMenu.hideMatchResultsMenu(pill.id);
                
                // If we're still typing, maintain typing state
                if (window.textInput && window.textInput.typing) {
                    // Move cursor after this pill
                    const pillPosition = window.findPillPosition(pill.id);
                    if (pillPosition) {
                        CursorManager.setCursorPosition(pillPosition.setIndex, pillPosition.pillIndex, 'after');
                    }
                }
            });
            
            menu.appendChild(item);
        });
        
        document.body.appendChild(menu);
        
        // Hide menu when clicking elsewhere or scrolling
        setTimeout(() => {
            const hideMenu = (e) => {
                if (!menu.contains(e.target)) {
                    ContextMenu.hideMatchResultsMenu(pill.id);
                    document.removeEventListener('click', hideMenu);
                    document.removeEventListener('scroll', hideOnScroll, true);
                }
            };
            
            const hideOnScroll = () => {
                ContextMenu.hideMatchResultsMenu(pill.id);
                document.removeEventListener('click', hideMenu);
                document.removeEventListener('scroll', hideOnScroll, true);
            };
            
            document.addEventListener('click', hideMenu);
            // Use capture phase to catch scroll on any element
            document.addEventListener('scroll', hideOnScroll, true);
        }, 0);
    }
    
    /**
     * Add a menu item to a context menu
     * @param {Element} menu - The menu element to add the item to
     * @param {string} text - The text for the menu item
     * @param {Function} callback - The callback function when clicked
     */
    static addMenuItem(menu, text, callback) {
        const item = document.createElement('a');
        item.textContent = text;
        item.addEventListener('click', callback);
        menu.appendChild(item);
    }
    
    /**
     * Show link modal for a pill
     * @param {Object} pillData - The pill data object
     */
    static showLinkModal(pillData) {
        const inputValue = pillData.tuneId ? `https://thesession.org/tunes/${pillData.tuneId}` : '';
        ModalManager.showModalWithInput('link-tune-modal', '#tune-link-input', inputValue, false);
        // Store current pill for linking (backward compatibility)
        window.currentLinkingPill = pillData;
    }
    
    /**
     * Show edit modal for a pill
     * @param {Object} pillData - The pill data object
     */
    static showEditModal(pillData) {
        ModalManager.showModalWithInput('edit-tune-modal', '#edit-tune-name-input', pillData.tuneName, true);
        // Store current pill for editing (backward compatibility)
        window.currentEditingPill = pillData;
    }
    
    /**
     * Delete a pill by ID
     * @param {string} pillId - The ID of the pill to delete
     */
    static deletePill(pillId) {
        // Find and remove the pill
        const tunePillsData = StateManager.getTunePillsData();
        for (let setIndex = 0; setIndex < tunePillsData.length; setIndex++) {
            const pillIndex = tunePillsData[setIndex].findIndex(p => p.id === pillId);
            if (pillIndex !== -1) {
                undoRedoManager.saveToUndo();
                tunePillsData[setIndex].splice(pillIndex, 1);
                
                // Remove empty sets
                if (tunePillsData[setIndex].length === 0) {
                    tunePillsData.splice(setIndex, 1);
                }
                
                // Update StateManager with the modified data
                StateManager.setTunePillsData(tunePillsData);
                
                PillRenderer.renderTunePills();
                break;
            }
        }
    }
}

// Export the ContextMenu class for use in other modules
window.ContextMenu = ContextMenu;