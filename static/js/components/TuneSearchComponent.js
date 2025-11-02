/**
 * TuneSearchComponent - Reusable tune search with autocomplete
 *
 * Provides local database search with TheSession.org fallback,
 * keyboard navigation, and configurable callbacks.
 *
 * @example
 * const search = new TuneSearchComponent({
 *   searchInputId: 'tune-search',
 *   autocompleteResultsId: 'autocomplete-results',
 *   onTuneSelected: (tune) => {
 *     console.log('Selected:', tune);
 *   }
 * });
 */
class TuneSearchComponent {
    constructor(config = {}) {
        // Configuration
        this.config = {
            searchInputId: 'tune-search',
            autocompleteResultsId: 'autocomplete-results',
            hiddenInputId: 'selected-tune-id',
            searchPlaceholder: 'Start typing a tune name...',
            noResultsMessage: 'No tunes found',
            showTunebookCount: true,
            tunebookCountStyle: 'badge', // 'badge' or 'text'
            enableTheSessionSearch: true,
            enableTuneIdPaste: true,
            minSearchLength: 2,
            debounceMs: 300,
            onTuneSelected: null, // Callback: function(tuneData)
            onSearchStart: null, // Callback: function(query)
            onSearchComplete: null, // Callback: function(results, query)
            ...config
        };

        // State
        this.searchTimeout = null;
        this.selectedTuneId = null;
        this.selectedIndex = -1;
        this.searchResults = [];
        this.lastSearchQuery = '';
        this.isSearchingTheSession = false;

        // DOM elements
        this.searchInput = document.getElementById(this.config.searchInputId);
        this.autocompleteResults = document.getElementById(this.config.autocompleteResultsId);
        this.hiddenInput = this.config.hiddenInputId ?
            document.getElementById(this.config.hiddenInputId) : null;

        if (!this.searchInput || !this.autocompleteResults) {
            console.error('TuneSearchComponent: Required elements not found');
            return;
        }

        this.init();
    }

    init() {
        // Setup event listeners
        this.searchInput.addEventListener('input', (e) => this.handleSearchInput(e));
        this.searchInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        this.searchInput.addEventListener('blur', (e) => this.handleBlur(e));

        // Close autocomplete when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest(`#${this.config.searchInputId}`) &&
                !e.target.closest(`#${this.config.autocompleteResultsId}`)) {
                this.hideAutocomplete();
            }
        });

        // Auto-search from query parameter if present
        this.checkForAutoSearch();
    }

    checkForAutoSearch() {
        const params = new URLSearchParams(window.location.search);
        if (params.has('q')) {
            const query = params.get('q').trim();
            if (query) {
                this.searchInput.value = query;
                this.searchTunes(query);
            }
        }
    }

    handleSearchInput(e) {
        const query = e.target.value.trim();

        // Clear selection when user types
        if (this.selectedTuneId) {
            this.clearSelection();
        }

        // Clear previous timeout
        clearTimeout(this.searchTimeout);

        if (query.length < this.config.minSearchLength) {
            this.hideAutocomplete();
            return;
        }

        // Debounce search
        this.searchTimeout = setTimeout(() => {
            this.searchTunes(query);
        }, this.config.debounceMs);
    }

    handleKeyDown(e) {
        if (!this.autocompleteResults.classList.contains('show')) {
            return;
        }

        const items = this.autocompleteResults.querySelectorAll('.autocomplete-item');

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.selectedIndex = Math.min(this.selectedIndex + 1, items.length - 1);
            this.updateSelection(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
            this.updateSelection(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (this.selectedIndex >= 0 && this.selectedIndex < this.searchResults.length) {
                this.selectTune(this.searchResults[this.selectedIndex]);
            }
        } else if (e.key === 'Escape') {
            this.hideAutocomplete();
        }
    }

    handleBlur(e) {
        // Delay to allow click events on autocomplete items
        setTimeout(() => {
            if (!document.activeElement ||
                (!document.activeElement.closest(`#${this.config.searchInputId}`) &&
                 !document.activeElement.closest(`#${this.config.autocompleteResultsId}`))) {
                this.hideAutocomplete();
            }
        }, 200);
    }

    updateSelection(items) {
        items.forEach((item, index) => {
            if (index === this.selectedIndex) {
                item.classList.add('selected');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('selected');
            }
        });
    }

    searchTunes(query) {
        this.showAutocompleteLoading();
        this.lastSearchQuery = query;
        this.isSearchingTheSession = false;

        if (this.config.onSearchStart) {
            this.config.onSearchStart(query);
        }

        // Check if the query is a tune ID or URL
        if (this.config.enableTuneIdPaste) {
            const tuneId = this.extractTuneId(query);
            if (tuneId) {
                this.searchByTuneId(tuneId);
                return;
            }
        }

        // Regular text search
        fetch(`/api/tunes/search?q=${encodeURIComponent(query)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to search local database');
                }
                return response.json();
            })
            .then(data => {
                this.searchResults = data.tunes || [];
                this.displayResults(this.searchResults, query);

                if (this.config.onSearchComplete) {
                    this.config.onSearchComplete(this.searchResults, query);
                }
            })
            .catch(error => {
                console.error('Search error:', error);
                this.showError('Error searching tunes. Please try again.');
            });
    }

    searchByTuneId(tuneId) {
        // Search for this specific tune ID in local database first
        fetch(`/api/tunes/search?q=${tuneId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to search local database');
                }
                return response.json();
            })
            .then(data => {
                // Check if we found the exact tune ID
                const exactMatch = (data.tunes || []).find(t => t.tune_id === tuneId);
                if (exactMatch) {
                    // Found it locally - show just this tune
                    this.searchResults = [exactMatch];
                    this.displayResults(this.searchResults, this.lastSearchQuery);
                } else {
                    // Not found locally - fetch from TheSession.org API directly
                    this.fetchTuneFromTheSession(tuneId);
                }
            })
            .catch(error => {
                console.error('Local search error:', error);
                // Fall back to TheSession.org API
                this.fetchTuneFromTheSession(tuneId);
            });
    }

    fetchTuneFromTheSession(tuneId) {
        if (!this.config.enableTheSessionSearch) {
            this.showError('Tune not found in local database');
            return;
        }

        this.showAutocompleteLoading();
        this.isSearchingTheSession = true;

        const url = `https://thesession.org/tunes/${tuneId}?format=json`;

        fetch(url)
            .then(response => {
                if (!response.ok) {
                    if (response.status === 404) {
                        throw new Error('Tune not found on TheSession.org');
                    }
                    throw new Error('Failed to fetch from TheSession.org');
                }
                return response.json();
            })
            .then(data => {
                // TheSession.org API returns a single tune object
                const tune = {
                    tune_id: data.id,
                    name: data.name,
                    tune_type: this.normalizeTuneType(data.type),
                    tunebook_count: data.tunebooks || 0,
                    isFromTheSession: true
                };
                this.searchResults = [tune];
                this.displayResults(this.searchResults, this.lastSearchQuery);

                // Auto-select the tune since it's the only result
                this.selectTune(tune);
            })
            .catch(error => {
                console.error('TheSession.org API error:', error);
                this.showError(error.message);
            });
    }

    searchTheSession(query) {
        if (!this.config.enableTheSessionSearch) {
            return;
        }

        this.showAutocompleteLoading();
        this.isSearchingTheSession = true;
        this.lastSearchQuery = query;

        const url = `https://thesession.org/tunes/search?q=${encodeURIComponent(query)}&format=json`;

        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to fetch from TheSession.org');
                }
                return response.json();
            })
            .then(data => {
                // Transform TheSession.org results to match our format
                const tunes = (data.tunes || []).map(tune => ({
                    tune_id: tune.id,
                    name: tune.name,
                    tune_type: this.normalizeTuneType(tune.type),
                    tunebook_count: tune.tunebooks || 0,
                    isFromTheSession: true
                }));
                this.searchResults = tunes;
                this.displayResults(this.searchResults, query);

                if (this.config.onSearchComplete) {
                    this.config.onSearchComplete(this.searchResults, query);
                }
            })
            .catch(error => {
                console.error('TheSession.org search error:', error);
                this.showError('Error searching TheSession.org. Please try again.');
            });
    }

    displayResults(tunes, query) {
        if (tunes.length === 0 && !this.isSearchingTheSession && this.config.enableTheSessionSearch) {
            const searchQuery = query || this.lastSearchQuery;
            this.autocompleteResults.innerHTML = `
                <div class="no-results clickable" data-search-query="${this.escapeHtml(searchQuery)}">
                    ${this.config.noResultsMessage}; click to search TheSession.org
                </div>
            `;
            this.autocompleteResults.classList.add('show');

            // Add click event listener to the no-results div
            const noResultsDiv = this.autocompleteResults.querySelector('.no-results.clickable');
            if (noResultsDiv) {
                noResultsDiv.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const queryToSearch = noResultsDiv.dataset.searchQuery;
                    // Show loading immediately
                    this.showAutocompleteLoading();
                    // Use setTimeout to ensure DOM update happens before async call
                    setTimeout(() => {
                        this.isSearchingTheSession = true;
                        this.lastSearchQuery = queryToSearch;
                        const url = `https://thesession.org/tunes/search?q=${encodeURIComponent(queryToSearch)}&format=json`;

                        fetch(url)
                            .then(response => {
                                if (!response.ok) {
                                    throw new Error('Failed to fetch from TheSession.org');
                                }
                                return response.json();
                            })
                            .then(data => {
                                const tunes = (data.tunes || []).map(tune => ({
                                    tune_id: tune.id,
                                    name: tune.name,
                                    tune_type: this.normalizeTuneType(tune.type),
                                    tunebook_count: tune.tunebooks || 0,
                                    isFromTheSession: true
                                }));
                                this.searchResults = tunes;
                                this.displayResults(this.searchResults, queryToSearch);

                                if (this.config.onSearchComplete) {
                                    this.config.onSearchComplete(this.searchResults, queryToSearch);
                                }
                            })
                            .catch(error => {
                                console.error('TheSession.org search error:', error);
                                this.showError('Error searching TheSession.org. Please try again.');
                            });
                    }, 0);
                });
            }
            return;
        }

        if (tunes.length === 0) {
            const message = this.isSearchingTheSession ?
                'No tunes found on TheSession.org either. Try a different search term.' :
                this.config.noResultsMessage;
            this.autocompleteResults.innerHTML = `<div class="no-results">${message}</div>`;
            this.autocompleteResults.classList.add('show');
            return;
        }

        const html = tunes.map((tune, index) => {
            const tunebookDisplay = this.getTunebookDisplay(tune);
            return `
                <div class="autocomplete-item" data-index="${index}" onclick="tuneSearch.selectTuneByIndex(${index})">
                    <span class="tune-name">
                        ${tune.isFromTheSession || this.isSearchingTheSession ? '<span class="thesession-badge">TheSession</span>' : ''}
                        ${this.escapeHtml(tune.name)}
                    </span>
                    <div class="tune-meta">
                        ${tune.tune_type ? `<span class="tune-type">${this.escapeHtml(tune.tune_type)}</span>` : ''}
                        ${tunebookDisplay}
                    </div>
                </div>
            `;
        }).join('');

        this.autocompleteResults.innerHTML = html;
        this.autocompleteResults.classList.add('show');
        this.selectedIndex = -1;
    }

    getTunebookDisplay(tune) {
        if (!this.config.showTunebookCount || !tune.tunebook_count) {
            return '';
        }

        if (this.config.tunebookCountStyle === 'badge') {
            return `<span class="tune-count-badge">${tune.tunebook_count}</span>`;
        } else {
            return `${tune.tunebook_count} tunebook${tune.tunebook_count !== 1 ? 's' : ''}`;
        }
    }

    selectTuneByIndex(index) {
        if (index >= 0 && index < this.searchResults.length) {
            this.selectTune(this.searchResults[index]);
        }
    }

    selectTune(tune) {
        this.selectedTuneId = tune.tune_id;

        if (this.hiddenInput) {
            this.hiddenInput.value = tune.tune_id;
        }

        this.searchInput.value = tune.name;

        // Store tune details if from TheSession.org for later insertion
        if (tune.isFromTheSession || this.isSearchingTheSession) {
            this.searchInput.dataset.theSessionTune = JSON.stringify({
                tune_id: tune.tune_id,
                name: tune.name,
                tune_type: tune.tune_type,
                tunebook_count: tune.tunebook_count
            });
        } else {
            delete this.searchInput.dataset.theSessionTune;
        }

        this.hideAutocomplete();

        // Call callback if provided
        if (this.config.onTuneSelected) {
            this.config.onTuneSelected({
                ...tune,
                isFromTheSession: tune.isFromTheSession || this.isSearchingTheSession
            });
        }
    }

    clearSelection() {
        this.selectedTuneId = null;
        if (this.hiddenInput) {
            this.hiddenInput.value = '';
        }
        delete this.searchInput.dataset.theSessionTune;
    }

    showAutocompleteLoading() {
        this.autocompleteResults.innerHTML = '<div class="loading-indicator"><div class="loading-spinner"></div>Searching...</div>';
        this.autocompleteResults.classList.add('show');
        this.selectedIndex = -1;
    }

    hideAutocomplete() {
        this.autocompleteResults.classList.remove('show');
        this.selectedIndex = -1;
    }

    showError(message) {
        this.autocompleteResults.innerHTML = `
            <div class="no-results">
                ${this.escapeHtml(message)}
            </div>
        `;
        this.autocompleteResults.classList.add('show');
    }

    // Utility functions

    extractTuneId(input) {
        if (!input) return null;

        const trimmed = input.trim();

        // If it's already just a number, return it
        if (/^\d+$/.test(trimmed)) {
            return parseInt(trimmed);
        }

        // Try to extract from URL: https://thesession.org/tunes/123
        const urlMatch = trimmed.match(/thesession\.org\/tunes\/(\d+)/i);
        if (urlMatch) {
            return parseInt(urlMatch[1]);
        }

        return null;
    }

    normalizeTuneType(type) {
        if (!type) return null;

        // Map TheSession.org tune types to our database format
        const typeMap = {
            'jig': 'Jig',
            'reel': 'Reel',
            'slip jig': 'Slip Jig',
            'hop jig': 'Hop Jig',
            'hornpipe': 'Hornpipe',
            'polka': 'Polka',
            'set dance': 'Set Dance',
            'slide': 'Slide',
            'waltz': 'Waltz',
            'barndance': 'Barndance',
            'strathspey': 'Strathspey',
            'three-two': 'Three-Two',
            'mazurka': 'Mazurka',
            'march': 'March',
            'air': 'Air'
        };

        return typeMap[type.toLowerCase()] || null;
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Public API methods

    getValue() {
        return this.searchInput.value;
    }

    getSelectedTuneId() {
        return this.selectedTuneId;
    }

    getSelectedTune() {
        if (this.selectedIndex >= 0 && this.selectedIndex < this.searchResults.length) {
            return this.searchResults[this.selectedIndex];
        }
        return null;
    }

    isFromTheSession() {
        return !!this.searchInput.dataset.theSessionTune;
    }

    getTheSessionTuneData() {
        if (this.searchInput.dataset.theSessionTune) {
            return JSON.parse(this.searchInput.dataset.theSessionTune);
        }
        return null;
    }

    reset() {
        this.searchInput.value = '';
        this.clearSelection();
        this.hideAutocomplete();
        this.searchResults = [];
        this.lastSearchQuery = '';
        this.isSearchingTheSession = false;
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TuneSearchComponent;
}
