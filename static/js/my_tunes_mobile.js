/**
 * Mobile Enhancements for Personal Tune Management
 * Handles swipe gestures, pull-to-refresh, and touch interactions
 */

(function() {
    'use strict';

    // Only initialize on mobile devices
    const isMobile = window.innerWidth <= 768;
    if (!isMobile) return;

    // ============================================
    // PULL-TO-REFRESH FUNCTIONALITY
    // ============================================

    let pullToRefreshEnabled = false;
    let startY = 0;
    let currentY = 0;
    let pulling = false;
    let refreshThreshold = 80;
    let refreshIndicator = null;

    function initPullToRefresh() {
        // DISABLED: Conflicts with horizontal swipe gestures
        return;

        // Only enable on my-tunes list page
        if (!document.querySelector('.my-tunes-container')) return;
        if (!document.querySelector('.tunes-grid')) return;

        pullToRefreshEnabled = true;

        // Create refresh indicator
        refreshIndicator = document.createElement('div');
        refreshIndicator.className = 'pull-to-refresh';
        refreshIndicator.textContent = 'Pull to refresh';
        document.body.appendChild(refreshIndicator);

        // Add touch event listeners
        // Note: touchmove must be non-passive to allow preventDefault
        document.addEventListener('touchstart', handleTouchStart, { passive: true });
        document.addEventListener('touchmove', handleTouchMove, { passive: false });
        document.addEventListener('touchend', handleTouchEnd, { passive: true });
    }

    function handleTouchStart(e) {
        if (!pullToRefreshEnabled) return;
        if (window.scrollY > 0) return;

        startY = e.touches[0].clientY;
        pulling = false;
    }

    function handleTouchMove(e) {
        if (!pullToRefreshEnabled) return;
        if (window.scrollY > 0) return;

        currentY = e.touches[0].clientY;
        const pullDistance = currentY - startY;

        if (pullDistance > 0 && window.scrollY === 0) {
            pulling = true;

            // Only preventDefault if we can (check if cancelable)
            if (e.cancelable) {
                e.preventDefault();
            }

            // Update indicator
            if (pullDistance > refreshThreshold) {
                refreshIndicator.textContent = 'Release to refresh';
                refreshIndicator.style.backgroundColor = 'var(--success, #28a745)';
                refreshIndicator.style.opacity = '1';
            } else {
                refreshIndicator.textContent = 'Pull to refresh';
                refreshIndicator.style.backgroundColor = 'var(--primary)';
                refreshIndicator.style.opacity = '1';
            }

            // Show indicator with pull distance
            const progress = Math.min(pullDistance / refreshThreshold, 1);
            refreshIndicator.style.transform = `translateX(-50%) translateY(${progress * 100 - 100}%)`;
        }
    }

    function handleTouchEnd(e) {
        if (!pullToRefreshEnabled || !pulling) return;

        const pullDistance = currentY - startY;

        if (pullDistance > refreshThreshold) {
            // Trigger refresh
            refreshIndicator.textContent = 'Refreshing...';
            refreshIndicator.classList.add('active');
            
            // Reload tunes
            if (typeof loadTunes === 'function') {
                loadTunes();
            } else {
                location.reload();
            }

            // Hide indicator after delay
            setTimeout(() => {
                refreshIndicator.classList.remove('active');
                refreshIndicator.style.transform = 'translateX(-50%) translateY(-100%)';
            }, 1500);
        } else {
            // Reset indicator
            refreshIndicator.style.transform = 'translateX(-50%) translateY(-100%)';
        }

        pulling = false;
        startY = 0;
        currentY = 0;
    }

    // ============================================
    // SWIPE GESTURE SUPPORT FOR TUNE CARDS
    // ============================================

    let swipeStartX = 0;
    let swipeStartY = 0;
    let swipeEndX = 0;
    let swipeEndY = 0;
    let swipeThreshold = 50;
    let swipeTarget = null;

    function initSwipeGestures() {
        const tuneCards = document.querySelectorAll('.tune-card');
        
        tuneCards.forEach(card => {
            card.addEventListener('touchstart', handleSwipeStart, { passive: true });
            card.addEventListener('touchmove', handleSwipeMove, { passive: true });
            card.addEventListener('touchend', handleSwipeEnd, { passive: true });
        });
    }

    function handleSwipeStart(e) {
        swipeStartX = e.touches[0].clientX;
        swipeStartY = e.touches[0].clientY;
        swipeTarget = e.currentTarget;
    }

    function handleSwipeMove(e) {
        if (!swipeTarget) return;
        
        swipeEndX = e.touches[0].clientX;
        swipeEndY = e.touches[0].clientY;
    }

    function handleSwipeEnd(e) {
        if (!swipeTarget) return;

        const deltaX = swipeEndX - swipeStartX;
        const deltaY = swipeEndY - swipeStartY;

        // Check if horizontal swipe is dominant
        if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > swipeThreshold) {
            if (deltaX > 0) {
                // Swipe right - could add quick action
                handleSwipeRight(swipeTarget);
            } else {
                // Swipe left - could add quick action
                handleSwipeLeft(swipeTarget);
            }
        }

        // Reset
        swipeTarget = null;
        swipeStartX = 0;
        swipeStartY = 0;
        swipeEndX = 0;
        swipeEndY = 0;
    }

    function handleSwipeRight(card) {
        // Optional: Add quick action for swipe right
        // For now, just provide visual feedback
        card.style.transform = 'translateX(10px)';
        setTimeout(() => {
            card.style.transform = '';
        }, 200);
    }

    function handleSwipeLeft(card) {
        // Optional: Add quick action for swipe left
        // For now, just provide visual feedback
        card.style.transform = 'translateX(-10px)';
        setTimeout(() => {
            card.style.transform = '';
        }, 200);
    }

    // ============================================
    // TOUCH FEEDBACK ENHANCEMENTS
    // ============================================

    function initTouchFeedback() {
        // Add haptic feedback for button presses (if supported)
        const buttons = document.querySelectorAll('.btn, .tune-action-btn, .increment-heard-btn');
        
        buttons.forEach(button => {
            button.addEventListener('touchstart', () => {
                // Visual feedback
                button.style.opacity = '0.7';
            }, { passive: true });

            button.addEventListener('touchend', () => {
                button.style.opacity = '';
            }, { passive: true });

            button.addEventListener('touchcancel', () => {
                button.style.opacity = '';
            }, { passive: true });
        });
    }

    // ============================================
    // OPTIMIZE SEARCH INPUT FOR MOBILE
    // ============================================

    function optimizeSearchInput() {
        const searchInput = document.getElementById('search-input');
        if (!searchInput) return;

        // Prevent zoom on focus for iOS
        searchInput.setAttribute('autocomplete', 'off');
        searchInput.setAttribute('autocorrect', 'off');
        searchInput.setAttribute('autocapitalize', 'off');
        searchInput.setAttribute('spellcheck', 'false');

        // Add clear button
        const clearBtn = document.createElement('button');
        clearBtn.className = 'search-clear-btn';
        clearBtn.innerHTML = '×';
        clearBtn.style.cssText = `
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            font-size: 24px;
            color: var(--text-muted);
            cursor: pointer;
            display: none;
            padding: 5px;
            min-width: 44px;
            min-height: 44px;
        `;

        const filterGroup = searchInput.closest('.filter-group');
        if (filterGroup) {
            filterGroup.style.position = 'relative';
            filterGroup.appendChild(clearBtn);

            searchInput.addEventListener('input', () => {
                clearBtn.style.display = searchInput.value ? 'block' : 'none';
            });

            clearBtn.addEventListener('click', () => {
                searchInput.value = '';
                searchInput.dispatchEvent(new Event('input'));
                clearBtn.style.display = 'none';
                searchInput.focus();
            });
        }
    }

    // ============================================
    // OPTIMIZE AUTOCOMPLETE FOR MOBILE
    // ============================================

    function optimizeAutocomplete() {
        const tuneSearchInput = document.getElementById('tune-search');
        if (!tuneSearchInput) return;

        // Prevent zoom on focus for iOS
        tuneSearchInput.setAttribute('autocomplete', 'off');
        tuneSearchInput.setAttribute('autocorrect', 'off');
        tuneSearchInput.setAttribute('autocapitalize', 'off');
        tuneSearchInput.setAttribute('spellcheck', 'false');

        // Optimize autocomplete results for touch
        const autocompleteResults = document.getElementById('autocomplete-results');
        if (autocompleteResults) {
            // Use event delegation for better performance
            autocompleteResults.addEventListener('touchstart', (e) => {
                const item = e.target.closest('.autocomplete-item');
                if (item) {
                    item.style.backgroundColor = 'var(--hover-bg)';
                }
            }, { passive: true });

            autocompleteResults.addEventListener('touchend', (e) => {
                const item = e.target.closest('.autocomplete-item');
                if (item) {
                    setTimeout(() => {
                        item.style.backgroundColor = '';
                    }, 200);
                }
            }, { passive: true });
        }
    }

    // ============================================
    // MODAL OPTIMIZATIONS FOR MOBILE
    // ============================================

    function optimizeModal() {
        const modal = document.getElementById('tune-detail-modal');
        if (!modal) return;

        // Prevent body scroll when modal is open
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.attributeName === 'style') {
                    const isVisible = modal.style.display === 'flex';
                    document.body.style.overflow = isVisible ? 'hidden' : '';
                }
            });
        });

        observer.observe(modal, { attributes: true });

        // Add swipe-down to close gesture
        let modalStartY = 0;
        let modalCurrentY = 0;
        let modalPulling = false;

        const modalDialog = modal.querySelector('.modal-dialog');
        if (modalDialog) {
            modalDialog.addEventListener('touchstart', (e) => {
                modalStartY = e.touches[0].clientY;
                modalPulling = false;
            }, { passive: true });

            modalDialog.addEventListener('touchmove', (e) => {
                modalCurrentY = e.touches[0].clientY;
                const pullDistance = modalCurrentY - modalStartY;

                // Only allow pulling down from the top
                if (pullDistance > 0 && modalDialog.scrollTop === 0) {
                    modalPulling = true;
                    modalDialog.style.transform = `translateY(${pullDistance}px)`;
                }
            }, { passive: true });

            modalDialog.addEventListener('touchend', () => {
                if (modalPulling) {
                    const pullDistance = modalCurrentY - modalStartY;
                    
                    if (pullDistance > 100) {
                        // Close modal
                        if (typeof closeTuneDetailModal === 'function') {
                            closeTuneDetailModal();
                        }
                    }
                    
                    // Reset transform
                    modalDialog.style.transform = '';
                }

                modalPulling = false;
                modalStartY = 0;
                modalCurrentY = 0;
            }, { passive: true });
        }
    }

    // ============================================
    // PERFORMANCE OPTIMIZATIONS
    // ============================================

    function optimizePerformance() {
        // Debounce scroll events
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                // Lazy load images if needed
                lazyLoadImages();
            }, 100);
        }, { passive: true });

        // Optimize filter changes
        const filterInputs = document.querySelectorAll('.filter-input, .filter-select');
        filterInputs.forEach(input => {
            // Add loading indicator during filter operations
            input.addEventListener('change', () => {
                const grid = document.getElementById('tunes-grid');
                if (grid) {
                    grid.style.opacity = '0.6';
                    setTimeout(() => {
                        grid.style.opacity = '';
                    }, 300);
                }
            });
        });
    }

    function lazyLoadImages() {
        // Placeholder for future image lazy loading
        // Currently not needed as we don't have images in tune cards
    }

    // ============================================
    // VIEWPORT HEIGHT FIX FOR MOBILE BROWSERS
    // ============================================

    function fixViewportHeight() {
        // Fix for mobile browsers where 100vh includes address bar
        const setVH = () => {
            const vh = window.innerHeight * 0.01;
            document.documentElement.style.setProperty('--vh', `${vh}px`);
        };

        setVH();
        window.addEventListener('resize', setVH);
        window.addEventListener('orientationchange', setVH);
    }

    // ============================================
    // INITIALIZE ALL MOBILE ENHANCEMENTS
    // ============================================

    function init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        console.log('Initializing mobile enhancements...');

        initPullToRefresh();
        initSwipeGestures();
        initTouchFeedback();
        optimizeSearchInput();
        optimizeAutocomplete();
        optimizeModal();
        optimizePerformance();
        fixViewportHeight();

        // Re-initialize swipe gestures when tunes are reloaded
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.addedNodes.length) {
                    initSwipeGestures();
                    initTouchFeedback();
                }
            });
        });

        const tunesGrid = document.getElementById('tunes-grid');
        if (tunesGrid) {
            observer.observe(tunesGrid, { childList: true });
        }

        console.log('Mobile enhancements initialized');
    }

    // Start initialization
    init();

})();
