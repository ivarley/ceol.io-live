/**
 * Attendance Management TypeScript
 * Handles session attendance functionality including check-in, person search, and instrument management
 */

// Type definitions
interface AttendanceConfig {
    sessionInstanceId: number;
    sessionId: number;
    sessionPath: string;
    currentUserId?: number;
    isRegular?: boolean;
    canManage: boolean;
}

interface Person {
    person_id: number | string;
    first_name: string;
    last_name: string;
    email?: string;
    display_name?: string;
    instruments: string[];
    attendance?: AttendanceStatus;
    attendance_status?: AttendanceStatus;
    is_regular?: boolean;
    is_admin?: boolean;
    comment?: string;
}

interface Attendee extends Person {
    attendance: AttendanceStatus;
}

type AttendanceStatus = 'yes' | 'maybe' | 'no';

interface APIResponse<T = any> {
    data?: T;
    error?: string;
    message?: string;
}

interface AttendanceResponse {
    attendees?: Attendee[];
    regulars?: Person[];
}

declare global {
    interface Window {
        AttendanceManager: typeof AttendanceManager;
        attendanceManagerInstance: AttendanceManager | null;
        TextInput?: {
            prototype: {
                handleTextInput: () => void;
            };
        };
        ModalManager?: {
            showModal: (modalId: string) => HTMLElement | null;
            showMessage: (message: string, type: string) => void;
        };
    }
}

class AttendanceManager {
    private config: AttendanceConfig | null = null;
    private attendees: Attendee[] = [];
    private sessionPeople: Person[] = [];  // All searchable people associated with this session
    private regulars: Person[] = [];
    private currentSearchQuery = '';
    private searchTimeout: number | null = null;
    private currentFilter = ''; // Empty string means no filter (show all)
    private readonly instruments = [
        'Banjo', 'Bodhrán', 'Bouzouki', 'Button Accordion', 'Concertina', 'Fiddle',
        'Flute', 'Guitar', 'Harp', 'Mandolin', 'Piano', 'Piano Accordion', 'Tin Whistle', 'Uilleann Pipes'
    ];
    
    // Beta page compatibility
    private isBetaPage = false;
    private originalTextInputTyping: (() => void) | null = null;

    init(config: AttendanceConfig): void {
        this.config = config;
        window.attendanceManagerInstance = this;
        
        // Check if we're on the beta page
        this.isBetaPage = window.location.pathname.includes('/beta') || 
                         window.TextInput !== undefined || 
                         document.querySelector('#tune-pills-container') !== null;
        
        this.loadAttendance();
        this.loadSessionPeople();
        this.setupEventListeners();
        this.setupFilterListeners();
        this.initializeQuickCheckin();
        
        // Set up modal input protection for beta page
        if (this.isBetaPage) {
            this.setupBetaPageModalSupport();
        }
    }

    private setupBetaPageModalSupport(): void {
        // When modals are shown, prevent the beta page's text input system from interfering
        const modalIds = ['addPersonModal', 'personEditModal'];
        modalIds.forEach(modalId => {
            const modal = document.getElementById(modalId);
            if (modal) {
                // Stop text input events from propagating to the beta page handlers
                modal.addEventListener('keydown', (e) => {
                    e.stopPropagation();
                });
                modal.addEventListener('keypress', (e) => {
                    e.stopPropagation();
                });
                modal.addEventListener('input', (e) => {
                    e.stopPropagation();
                });
            }
        });
    }

    private setupEventListeners(): void {
        const searchInput = document.getElementById('attendee-search') as HTMLInputElement;
        if (searchInput) {
            searchInput.addEventListener('focus', () => {
                // Reset filter when search box gets focus
                this.resetFilter();
            });
            
            searchInput.addEventListener('input', (e) => {
                // Use instant search with preloaded data
                this.performInstantSearch((e.target as HTMLInputElement).value);
            });

            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === 'Return' || e.key === 'Tab') {
                    e.preventDefault();
                    this.handleSearchKeyAction((e.target as HTMLInputElement).value);
                }
            });
        }

        document.addEventListener('click', (e) => {
            const searchResults = document.getElementById('search-results');
            const searchInput = document.getElementById('attendee-search');
            if (searchResults && searchInput && 
                !searchResults.contains(e.target as Node) && 
                !searchInput.contains(e.target as Node)) {
                searchResults.style.display = 'none';
            }
        });
    }

    private setupFilterListeners(): void {
        // Add click handlers to filter badges
        const filterBadges = document.querySelectorAll('.attendance-filter-badge') as NodeListOf<HTMLElement>;
        filterBadges.forEach(badge => {
            badge.addEventListener('click', (e) => {
                e.preventDefault();
                const filter = badge.dataset.filter || '';
                this.applyFilter(filter);
            });
        });
        
        // Set up tab change listener to reset filter
        const tabs = document.querySelectorAll('[data-toggle="tab"]');
        tabs.forEach(tab => {
            tab.addEventListener('shown.bs.tab', (e) => {
                // Reset filter when switching tabs
                const target = e.target as HTMLElement;
                if (target.getAttribute('href') !== '#attendance-panel') {
                    this.resetFilter();
                }
            });
        });
    }

    private applyFilter(filter: string): void {
        // If clicking the same filter that's already active, turn it off
        if (this.currentFilter === filter && filter !== '') {
            this.currentFilter = '';
        } else {
            this.currentFilter = filter;
        }
        
        // Update badge visual states
        this.updateFilterBadgeStates();
        
        // Filter the attendance list
        this.filterAttendanceList();
    }

    private resetFilter(): void {
        if (this.currentFilter !== '') {
            this.currentFilter = '';
            this.updateFilterBadgeStates();
            this.filterAttendanceList();
        }
    }

    private updateFilterBadgeStates(): void {
        const filterBadges = document.querySelectorAll('.attendance-filter-badge') as NodeListOf<HTMLElement>;
        filterBadges.forEach(badge => {
            if (badge.dataset.filter === this.currentFilter) {
                // Active filter badge - add visual indication
                badge.style.opacity = '1';
                badge.style.transform = 'scale(1.05)';
                badge.style.fontWeight = 'bold';
            } else {
                // Inactive filter badge
                badge.style.opacity = '0.7';
                badge.style.transform = 'scale(1)';
                badge.style.fontWeight = 'normal';
            }
        });
    }

    private filterAttendanceList(): void {
        const attendanceItems = document.querySelectorAll('.attendance-item') as NodeListOf<HTMLElement>;
        
        attendanceItems.forEach(item => {
            const itemStatus = item.dataset.status || '';
            const shouldShow = this.currentFilter === '' || itemStatus === this.currentFilter;
            
            if (shouldShow) {
                item.style.display = '';
                item.classList.remove('filtered-out', 'dimmed');
            } else {
                item.style.display = 'none';
                item.classList.add('filtered-out');
            }
        });
    }

    private handleStatusChangeFiltering(personId: number | string, newStatus: AttendanceStatus): void {
        // Only handle special behavior if we have an active filter
        if (this.currentFilter === '') {
            return; // No filter active, normal behavior
        }
        
        const attendeeElement = document.querySelector(`.attendance-item[data-person-id="${personId}"]`) as HTMLElement;
        if (!attendeeElement) {
            return;
        }
        
        // If the new status doesn't match the current filter, show as dimmed instead of hiding
        if (newStatus !== this.currentFilter) {
            attendeeElement.style.display = ''; // Show the element
            attendeeElement.classList.add('dimmed'); // But show it as dimmed
            attendeeElement.classList.remove('filtered-out');
        } else {
            // Status now matches filter, show normally
            attendeeElement.style.display = '';
            attendeeElement.classList.remove('dimmed', 'filtered-out');
        }
    }

    private initializeQuickCheckin(): void {
        if (this.config?.isRegular) {
            this.updateQuickCheckinButton();
        }
    }

    private updateQuickCheckinButton(): void {
        const btn = document.getElementById('quick-checkin-btn') as HTMLButtonElement;
        if (!btn || !this.config) return;

        const currentAttendee = this.attendees.find(a => 
            a.person_id === this.config!.currentUserId
        );
        
        if (currentAttendee) {
            switch (currentAttendee.attendance_status || currentAttendee.attendance) {
                case 'yes':
                    btn.innerHTML = '<i class="fas fa-check-circle"></i> Checked In';
                    btn.className = 'btn btn-success btn-sm';
                    btn.onclick = () => this.changeMyStatus('maybe');
                    break;
                case 'maybe':
                    btn.innerHTML = '<i class="fas fa-question-circle"></i> Maybe';
                    btn.className = 'btn btn-warning btn-sm';
                    btn.onclick = () => this.changeMyStatus('no');
                    break;
                case 'no':
                    btn.innerHTML = '<i class="fas fa-times-circle"></i> Not Coming';
                    btn.className = 'btn btn-danger btn-sm';
                    btn.onclick = () => this.changeMyStatus('yes');
                    break;
            }
        } else {
            btn.innerHTML = '<i class="fas fa-check"></i> Check In';
            btn.className = 'btn btn-success btn-sm';
            btn.onclick = () => this.quickCheckin();
        }
    }

    private async loadAttendance(): Promise<void> {
        if (!this.config) return;
        
        try {
            const response = await fetch(`/api/session_instance/${this.config.sessionInstanceId}/attendees`);
            if (!response.ok) {
                throw new Error('Failed to load attendance data');
            }
            
            const result = await response.json() as APIResponse<AttendanceResponse>;
            
            // Handle different response formats
            if (result.data && (result.data.attendees || result.data.regulars)) {
                // Combine regulars and attendees into a single array for rendering
                const regulars = result.data.regulars || [];
                const attendees = result.data.attendees || [];
                this.attendees = [...regulars, ...attendees] as Attendee[];
                this.regulars = regulars;
            } else {
                // Handle direct response format
                const directResult = result as any;
                this.attendees = (directResult.attendees || directResult.data || []) as Attendee[];
                this.regulars = directResult.regulars || [];
            }
            
            this.renderAttendance();
            this.updateStats();
            this.updateQuickCheckinButton();
        } catch (error) {
            this.showError('Error loading attendance data');
        }
    }

    private async loadSessionPeople(): Promise<void> {
        if (!this.config) return;

        try {
            // Load ALL people associated with this session for instant search functionality
            const response = await fetch(`/api/session/${this.config.sessionId}/people/session-people`);
            if (!response.ok) {
                throw new Error('Failed to load session people data');
            }

            const result = await response.json() as APIResponse<Person[]>;
            this.sessionPeople = result.data || [];  // Contains all searchable people
        } catch (error) {
            // Don't show error to user since this is just for optimization
            this.sessionPeople = [];
        }
    }

    private renderAttendance(): void {
        const container = document.getElementById('attendance-list');
        if (!container) return;

        if (this.attendees.length === 0) {
            container.innerHTML = '<div class="text-center p-3 text-muted">No attendees yet</div>';
            return;
        }

        const sortedAttendees = [...this.attendees].sort((a, b) => {
            // Sort everyone together alphabetically, no special treatment for regulars
            const nameA = a.display_name || (a.first_name + ' ' + a.last_name);
            const nameB = b.display_name || (b.first_name + ' ' + b.last_name);
            return nameA.localeCompare(nameB, undefined, { sensitivity: 'base' });
        });

        const template = document.getElementById('attendance-item-template') as HTMLTemplateElement;
        container.innerHTML = '';

        sortedAttendees.forEach(attendee => {
            const item = template.content.cloneNode(true) as DocumentFragment;
            const itemDiv = item.querySelector('.attendance-item') as HTMLElement;
            
            itemDiv.dataset.personId = String(attendee.person_id);
            // Set data-status for CSS styling
            const attendanceStatus = attendee.attendance || attendee.attendance_status!;
            itemDiv.dataset.status = attendanceStatus;
            
            const nameDiv = item.querySelector('.person-name') as HTMLElement;
            // Use display_name if available, otherwise fall back to first_name + last_name
            const nameText = attendee.display_name || (attendee.first_name + ' ' + attendee.last_name);
            nameDiv.textContent = nameText;

            const instrumentsDiv = item.querySelector('.person-instruments') as HTMLElement;
            if (attendee.instruments && attendee.instruments.length > 0) {
                instrumentsDiv.textContent = attendee.instruments.join(', ');
            } else {
                instrumentsDiv.textContent = 'No instruments listed';
            }

            if (this.config!.canManage) {
                // Set up dropdown for status selection
                const statusSelect = item.querySelector('.attendance-status-select') as HTMLSelectElement;
                if (statusSelect) {
                    const attendanceStatus = attendee.attendance || attendee.attendance_status!;
                    statusSelect.value = attendanceStatus;
                    this.updateDropdownStyle(statusSelect, attendanceStatus);

                    statusSelect.onchange = () => {
                        const selectedValue = statusSelect.value;
                        if (selectedValue === 'remove') {
                            this.removePersonFromSession(attendee.person_id);
                            // Reset dropdown to previous value since remove is an action, not a status
                            statusSelect.value = attendanceStatus;
                            this.updateDropdownStyle(statusSelect, attendanceStatus);
                        } else {
                            this.updateAttendanceStatus(attendee.person_id, selectedValue as AttendanceStatus);
                            this.updateDropdownStyle(statusSelect, selectedValue);
                        }
                    };
                }

                // Set up clickable name for editing
                const editLink = item.querySelector('.person-edit-link') as HTMLAnchorElement;
                if (editLink) {
                    editLink.href = `/admin/sessions/${this.config!.sessionPath}/players/${attendee.person_id}?from=attendance&instance_id=${this.config!.sessionInstanceId}`;
                }
            } else {
                const statusDisplay = item.querySelector('.attendance-status-display') as HTMLElement;
                if (statusDisplay) {
                    const attendanceStatus = attendee.attendance || attendee.attendance_status!;
                    statusDisplay.innerHTML = this.getStatusDisplay(attendanceStatus);
                }
            }

            container.appendChild(item);
        });
    }


    private getStatusDisplay(status: AttendanceStatus): string {
        switch (status) {
            case 'yes': return '<span class="text-success"><i class="fas fa-check"></i> Yes</span>';
            case 'maybe': return '<span class="text-warning"><i class="fas fa-question"></i> Maybe</span>';
            case 'no': return '<span class="text-danger"><i class="fas fa-times"></i> No</span>';
            default: return '<span class="text-muted">Unknown</span>';
        }
    }

    private updateDropdownStyle(selectElement: HTMLSelectElement, status: string): void {
        // Remove all status classes
        selectElement.classList.remove('dropdown-status-yes', 'dropdown-status-maybe', 'dropdown-status-no');

        // Add appropriate status class
        switch (status) {
            case 'yes':
                selectElement.classList.add('dropdown-status-yes');
                break;
            case 'maybe':
                selectElement.classList.add('dropdown-status-maybe');
                break;
            case 'no':
                selectElement.classList.add('dropdown-status-no');
                break;
        }
    }

    private updateStats(): void {
        const yesCount = this.attendees.filter(a => (a.attendance || a.attendance_status) === 'yes').length;
        const maybeCount = this.attendees.filter(a => (a.attendance || a.attendance_status) === 'maybe').length;
        const noCount = this.attendees.filter(a => (a.attendance || a.attendance_status) === 'no').length;
        const totalCount = this.attendees.length;

        const updateElement = (id: string, value: number) => {
            const element = document.getElementById(id);
            if (element) element.textContent = String(value);
        };

        updateElement('yes-count', yesCount);
        updateElement('maybe-count', maybeCount);
        updateElement('no-count', noCount);
        updateElement('total-count', totalCount);
    }

    private async quickCheckin(): Promise<void> {
        if (!this.config) return;
        
        try {
            const response = await fetch(`/api/session_instance/${this.config.sessionInstanceId}/attendees/checkin`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ attendance_status: 'yes' })
            });
            
            if (!response.ok) {
                const error = await response.json() as APIResponse;
                throw new Error(error.error || 'Failed to check in');
            }
            
            await this.loadAttendance();
            this.showSuccess('Checked in successfully!');
        } catch (error) {
            this.showError((error as Error).message || 'Error checking in');
        }
    }

    private async changeMyStatus(newStatus: AttendanceStatus): Promise<void> {
        if (!this.config) return;
        
        try {
            const response = await fetch(`/api/session_instance/${this.config.sessionInstanceId}/attendees/checkin`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ attendance_status: newStatus })
            });
            
            if (!response.ok) {
                const error = await response.json() as APIResponse;
                throw new Error(error.error || 'Failed to update status');
            }
            
            await this.loadAttendance();
            this.showSuccess('Status updated!');
        } catch (error) {
            this.showError((error as Error).message || 'Error updating status');
        }
    }

    private async updateAttendanceStatus(personId: number | string, status: AttendanceStatus): Promise<void> {
        if (!this.config?.canManage) return;

        // Optimistic update: Update UI immediately
        this.updateAttendeeStatusOptimistic(personId, status);
        this.updateStatusCountsOptimistic();
        
        // Handle filtering behavior when status changes
        this.handleStatusChangeFiltering(personId, status);

        try {
            const response = await fetch(`/api/session_instance/${this.config.sessionInstanceId}/attendees/checkin`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ person_id: personId, attendance: status })
            });
            
            if (!response.ok) {
                const error = await response.json() as APIResponse;
                throw new Error(error.error || 'Failed to update attendance');
            }
            
            // Success - optimistic update was correct
            this.showSuccess('Attendance updated');
        } catch (error) {
            // Revert optimistic update on error by reloading from server
            await this.loadAttendance();
            this.showError((error as Error).message || 'Error updating attendance');
        }
    }

    private async searchPeople(query?: string): Promise<void> {
        if (!this.config) return;
        
        if (!query) {
            const searchInput = document.getElementById('attendee-search') as HTMLInputElement;
            if (searchInput) {
                query = searchInput.value.trim();
            }
        }

        if (!query || query.length < 2) {
            const searchResults = document.getElementById('search-results');
            if (searchResults) {
                searchResults.style.display = 'none';
            }
            return;
        }

        try {
            const response = await fetch(`/api/session/${this.config.sessionId}/people/search?q=${encodeURIComponent(query)}`);
            if (!response.ok) {
                throw new Error('Search failed');
            }
            
            const data = await response.json() as APIResponse<Person[]>;
            this.displaySearchResults(data.data || [], query);
        } catch (error) {
            this.showError('Search error');
        }
    }

    private displaySearchResults(people: Person[], query?: string): void {
        const resultsDiv = document.getElementById('search-results');
        if (!resultsDiv) return;

        if (people.length === 0 && query) {
            const addPersonDiv = document.createElement('div');
            addPersonDiv.className = 'search-result-item add-person-result';
            addPersonDiv.dataset.personName = query;
            addPersonDiv.innerHTML = `<div class="person-name text-primary"><i class="fas fa-plus"></i> Add a new person "${query}"</div>`;
            addPersonDiv.onclick = () => {
                window.attendanceManagerInstance?.showAddPersonModalWithName(addPersonDiv.dataset.personName!);
            };
            
            resultsDiv.innerHTML = '';
            resultsDiv.appendChild(addPersonDiv);
            resultsDiv.style.display = 'block';
            return;
        } else if (people.length === 0) {
            resultsDiv.style.display = 'none';
            return;
        }

        const html = people.map(person => {
            const instruments = person.instruments && person.instruments.length > 0 ? 
                person.instruments.join(', ') : 'No instruments';
            return `<div class="search-result-item" onclick="window.attendanceManagerInstance?.addExistingPerson(${person.person_id})">` +
                   `<div class="person-name">${person.first_name} ${person.last_name}</div>` +
                   `<div class="person-instruments text-muted small">${instruments}</div>` +
                   `</div>`;
        }).join('');

        resultsDiv.innerHTML = html;
        resultsDiv.style.display = 'block';
    }

    addExistingPerson(personId: number): void {
        if (!this.config) return;
        
        // Find the person data from the search results or create minimal data
        const personData = this.getPersonDataForOptimisticAdd(personId);
        if (!personData) {
            return;
        }
        
        // Optimistic update: Add person to UI immediately
        this.addPersonOptimistic(personData);
        this.updateStatusCountsOptimistic();
        
        // Clear search UI
        const searchInput = document.getElementById('attendee-search') as HTMLInputElement;
        const searchResults = document.getElementById('search-results');
        if (searchInput) searchInput.value = '';
        if (searchResults) searchResults.style.display = 'none';
        
        const payload = { person_id: personId, attendance: 'yes' };
        
        fetch(`/api/session_instance/${this.config.sessionInstanceId}/attendees/checkin`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(async response => {
            if (response.ok) {
                return response.json();
            } else {
                const error = await response.json() as APIResponse;
                throw new Error(error.error || error.message || 'Failed to add person');
            }
        })
        .then(() => {
            // Success - optimistic update was correct
            this.showSuccess('Person added to attendance');
        })
        .catch(async (error) => {
            // Revert optimistic update on error by reloading from server
            await this.loadAttendance();
            this.showError((error as Error).message || 'Error adding person');
        });
    }

    // Helper function to get person data for optimistic add
    private getPersonDataForOptimisticAdd(personId: number): Attendee | null {
        // Try to find the person data from the search results first
        const searchResults = document.getElementById('search-results');
        if (searchResults) {
            const searchItems = searchResults.querySelectorAll('.search-result-item');
            for (let i = 0; i < searchItems.length; i++) {
                const item = searchItems[i] as HTMLElement;
                const onclick = item.getAttribute('onclick');
                if (onclick && onclick.includes(`(${personId})`)) {
                    const nameElement = item.querySelector('.person-name');
                    const instrumentsElement = item.querySelector('.person-instruments');
                    if (nameElement) {
                        const fullName = nameElement.textContent!.trim();
                        const nameParts = fullName.split(' ');
                        const firstName = nameParts[0] || '';
                        const lastName = nameParts.slice(1).join(' ') || '';
                        let instruments: string[] = [];
                        if (instrumentsElement) {
                            const instrumentText = instrumentsElement.textContent!.trim();
                            if (instrumentText && instrumentText !== 'No instruments') {
                                instruments = instrumentText.split(', ');
                            }
                        }
                        return {
                            person_id: personId,
                            first_name: firstName,
                            last_name: lastName,
                            display_name: fullName,
                            attendance: 'yes',
                            instruments: instruments,
                            is_regular: false, // Default to false since we're adding them
                            is_admin: false,
                            comment: ''
                        };
                    }
                }
            }
        }
        return null;
    }

    // Helper function to add person to UI optimistically
    private addPersonOptimistic(personData: Attendee): void {
        // Find the correct alphabetical position to insert the new person
        const displayName = personData.display_name || (personData.first_name + ' ' + personData.last_name);
        let insertIndex = this.attendees.length;
        
        for (let i = 0; i < this.attendees.length; i++) {
            const attendee = this.attendees[i];
            if (!attendee) continue;
            const existingName = attendee.display_name || (attendee.first_name + ' ' + attendee.last_name);
            if (displayName.localeCompare(existingName, undefined, { sensitivity: 'base' }) < 0) {
                insertIndex = i;
                break;
            }
        }
        
        // Insert at the correct position
        this.attendees.splice(insertIndex, 0, personData);
        
        // Add to UI
        this.renderAttendance();
    }

    showAddPersonModal(): void {
        // Temporarily disable beta page text input if present
        if (this.isBetaPage && window.TextInput) {
            this.originalTextInputTyping = window.TextInput.prototype.handleTextInput;
            window.TextInput.prototype.handleTextInput = function() {
                // Disable text input handling while modal is open
                return;
            };
        }
        
        // Check if ModalManager is available
        if (window.ModalManager) {
            const result = window.ModalManager.showModal('addPersonModal');
            
            // Ensure modal is properly visible - add Bootstrap modal classes
            if (result) {
                result.classList.add('show');
                result.style.display = 'block';
                result.removeAttribute('aria-hidden');
                
                // Add backdrop
                const backdrop = document.createElement('div');
                backdrop.className = 'modal-backdrop fade show';
                backdrop.id = 'modal-backdrop-' + Date.now();
                document.body.appendChild(backdrop);
                
                // Store backdrop reference for cleanup
                result.setAttribute('data-backdrop-id', backdrop.id);
            }
        } else {
            // Fallback: show modal directly with CSS
            const modal = document.getElementById('addPersonModal');
            if (modal) {
                modal.style.display = 'flex';
                modal.classList.add('show');
            }
        }
    }

    closeModal(modalId: string): void {
        // Restore beta page text input if it was disabled
        if (this.isBetaPage && this.originalTextInputTyping && window.TextInput) {
            window.TextInput.prototype.handleTextInput = this.originalTextInputTyping;
            this.originalTextInputTyping = null;
        }
        
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
            modal.classList.remove('show', 'fade');
            modal.setAttribute('aria-hidden', 'true');
            
            // Remove backdrop
            const backdropId = modal.getAttribute('data-backdrop-id');
            if (backdropId) {
                const backdrop = document.getElementById(backdropId);
                if (backdrop) {
                    backdrop.remove();
                }
                modal.removeAttribute('data-backdrop-id');
            }
            
            // Also remove any remaining backdrops (fallback cleanup)
            const remainingBackdrops = document.querySelectorAll('.modal-backdrop');
            remainingBackdrops.forEach(backdrop => backdrop.remove());
            
            // Remove modal-open class from body
            document.body.classList.remove('modal-open');
            
            // Reset body styles that Bootstrap may have set
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';
        }
    }

    async createPerson(): Promise<void> {
        if (!this.config) return;
        
        const form = document.getElementById('person-add-form') as HTMLFormElement;
        const formData = new FormData(form);
        
        const instruments: string[] = [];
        const checkboxes = document.querySelectorAll('#add-instruments-container input[type="checkbox"]:checked') as NodeListOf<HTMLInputElement>;
        checkboxes.forEach(checkbox => {
            instruments.push(checkbox.value);
        });

        const customInstrument = document.getElementById('add-new-instrument') as HTMLInputElement;
        if (customInstrument && customInstrument.value.trim()) {
            instruments.push(customInstrument.value.trim());
        }

        const personData = {
            first_name: formData.get('first_name') as string,
            last_name: formData.get('last_name') as string,
            email: formData.get('email') as string,
            instruments: instruments
        };
        
        // Validate form data
        if (!personData.first_name || !personData.first_name.trim()) {
            this.showError('First name is required');
            return;
        }
        
        if (!personData.last_name || !personData.last_name.trim()) {
            this.showError('Last name is required');
            return;
        }
        
        const attendanceStatus = (formData.get('attendance_status') as AttendanceStatus) || 'yes';

        // Close modal immediately after validation
        this.closeModal('addPersonModal');
        if (form) form.reset();
        const checkboxes2 = document.querySelectorAll('#add-instruments-container input[type="checkbox"]') as NodeListOf<HTMLInputElement>;
        checkboxes2.forEach(checkbox => {
            checkbox.checked = false;
        });
        if (customInstrument) customInstrument.value = '';
        
        // Show initial toast message
        const displayName = personData.first_name + ' ' + personData.last_name;
        this.showSuccess('Adding ' + displayName + '...');

        // Create temporary person for optimistic update
        const tempPerson: Attendee = {
            person_id: 'temp_' + Date.now(), // Temporary ID
            first_name: personData.first_name,
            last_name: personData.last_name,
            display_name: displayName,
            instruments: instruments,
            attendance: attendanceStatus,
            is_admin: false,
            is_regular: false
        };

        // Optimistic update: Add person to UI immediately
        this.addPersonToUIOptimistic(tempPerson);

        try {
            const response = await fetch('/api/person', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(personData)
            });
            
            if (!response.ok) {
                const error = await response.json() as APIResponse;
                throw new Error(error.error || 'Failed to create person');
            }
            
            const result = await response.json() as APIResponse<Person>;
            const personId = result.data?.person_id ?? (result as any).person_id;
            
            // Replace temporary person with real person ID
            this.replaceTemporaryPerson(tempPerson.person_id, personId);
            
            // Add person to attendance with chosen status
            const payload = { person_id: personId, attendance: attendanceStatus };
            
            const checkinResponse = await fetch(`/api/session_instance/${this.config.sessionInstanceId}/attendees/checkin`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (!checkinResponse.ok) {
                const error = await checkinResponse.json() as APIResponse;
                throw new Error(error.error || 'Failed to add person to attendance');
            }
            
            // Clear search box
            const searchInput = document.getElementById('attendee-search') as HTMLInputElement;
            const searchResults = document.getElementById('search-results');
            if (searchInput) searchInput.value = '';
            if (searchResults) searchResults.style.display = 'none';
            
            this.showSuccess(tempPerson.display_name + ' added successfully');
        } catch (error) {
            // Remove optimistic update on error
            this.removePersonFromUIOptimistic(tempPerson.person_id);
            this.showError((error as Error).message || 'Error creating person');
        }
    }

    refreshAttendance(): void {
        this.loadAttendance();
        this.showSuccess('Attendance refreshed');
    }

    editPerson(personId: number | string): void {
        // Edit person not yet implemented
    }

    addNewInstrument(): void {
        const input = document.getElementById('add-new-instrument') as HTMLInputElement;
        if (!input || !input.value.trim()) return;
        
        const instrumentName = input.value.trim();
        const container = document.getElementById('add-instruments-container');
        if (!container) return;
        
        // Create new checkbox for the instrument
        const checkDiv = document.createElement('div');
        checkDiv.className = 'form-check';
        
        const checkbox = document.createElement('input');
        checkbox.className = 'form-check-input';
        checkbox.type = 'checkbox';
        checkbox.value = instrumentName;
        checkbox.checked = true;
        checkbox.id = 'inst-' + instrumentName.toLowerCase().replace(/\s+/g, '-');
        
        const label = document.createElement('label');
        label.className = 'form-check-label';
        label.setAttribute('for', checkbox.id);
        label.textContent = instrumentName;
        
        checkDiv.appendChild(checkbox);
        checkDiv.appendChild(label);
        container.appendChild(checkDiv);
        
        input.value = '';
    }

    removePerson(personId: number | string): void {
        if (!confirm('Mark this person as not attending?')) return;

        // Set their status to "no" instead of removing them entirely
        this.updateAttendanceStatus(personId, 'no');
    }

    async removePersonFromSession(personId: number | string): Promise<void> {
        if (!this.config) return;

        if (!confirm('Remove this person from this session instance? This will not affect their general session membership.')) {
            return;
        }

        // Optimistically remove from UI
        this.removePersonFromUIOptimistic(personId);

        try {
            const response = await fetch(`/api/session_instance/${this.config.sessionInstanceId}/attendees/${personId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to remove person from session');
            }

            this.showSuccess('Person removed from session instance');
        } catch (error) {
            // Reload attendance on error to restore accurate state
            await this.loadAttendance();
            this.showError((error as Error).message || 'Error removing person from session');
        }
    }

    // Optimistic UI Update Helpers
    private performInstantSearch(query: string): void {
        if (!query || query.length < 1) {
            const searchResults = document.getElementById('search-results');
            if (searchResults) {
                searchResults.style.display = 'none';
            }
            return;
        }
        
        // Filter out people who are already in attendance
        const currentAttendeeIds = new Set<number | string>();
        this.attendees.forEach(attendee => {
            currentAttendeeIds.add(attendee.person_id);
        });
        
        // Filter all searchable people (regulars and non-regulars) based on search query
        const searchPattern = query.toLowerCase();
        const matchedPeople: Person[] = [];

        this.sessionPeople.forEach(person => {
            // Skip if person is already attending
            if (currentAttendeeIds.has(person.person_id)) {
                return;
            }
            
            // Check if person matches search query
            const fullName = person.display_name || (person.first_name + ' ' + person.last_name);
            if (fullName.toLowerCase().includes(searchPattern) ||
                person.first_name.toLowerCase().includes(searchPattern) ||
                person.last_name.toLowerCase().includes(searchPattern)) {
                matchedPeople.push(person);
            }
        });
        
        this.currentSearchQuery = query;
        this.displaySearchResults(matchedPeople, query);
    }

    private handleSearchKeyAction(query: string): void {
        const searchResults = document.getElementById('search-results');
        
        if (searchResults && searchResults.style.display !== 'none') {
            const firstResult = searchResults.querySelector('.search-result-item') as HTMLElement;
            if (firstResult) {
                // Add the first search result (could be existing person or "Add new person")
                firstResult.click();
                return;
            }
        }
        
        // No search results, open the Add Person modal with name pre-populated
        if (query && query.trim()) {
            this.showAddPersonModalWithName(query.trim());
        }
    }

    showAddPersonModalWithName(name: string): void {
        const nameParts = name.split(' ');
        const firstName = nameParts[0] || '';
        const lastName = nameParts.slice(1).join(' ') || '';
        
        // Show the modal
        this.showAddPersonModal();
        
        // Pre-populate the name fields with correct IDs
        setTimeout(() => {
            const firstNameInput = document.getElementById('add-first-name') as HTMLInputElement;
            const lastNameInput = document.getElementById('add-last-name') as HTMLInputElement;
            const emailInput = document.getElementById('add-email') as HTMLInputElement;
            
            if (firstNameInput) {
                firstNameInput.value = firstName;
            }
            if (lastNameInput) {
                lastNameInput.value = lastName;
            }
            
            // Focus on the next unfilled field
            if (!firstName && firstNameInput) {
                // No first name provided, focus on first name field
                firstNameInput.focus();
            } else if (!lastName && lastNameInput) {
                // First name filled but no last name, focus on last name field
                lastNameInput.focus();
            } else if (emailInput) {
                // Both names filled, focus on email field
                emailInput.focus();
            }
        }, 150); // Slightly longer delay to ensure modal is fully rendered
    }

    private updateAttendeeStatusOptimistic(personId: number | string, newStatus: AttendanceStatus): void {
        // Update in-memory data
        const attendee = this.attendees.find(a => a.person_id == personId);
        if (attendee) {
            attendee.attendance = newStatus;
        }

        // Update UI
        const attendanceItem = document.querySelector(`.attendance-item[data-person-id="${personId}"]`) as HTMLElement;
        if (attendanceItem) {
            // Update data attribute
            attendanceItem.setAttribute('data-status', newStatus);

            // Update dropdown value and styling
            const statusSelect = attendanceItem.querySelector('.attendance-status-select') as HTMLSelectElement;
            if (statusSelect) {
                statusSelect.value = newStatus;
                this.updateDropdownStyle(statusSelect, newStatus);
            }
        }
    }

    private updateStatusCountsOptimistic(): void {
        // Count statuses from current attendees array
        const counts = { yes: 0, maybe: 0, no: 0, total: 0 };

        this.attendees.forEach(attendee => {
            const status = attendee.attendance;
            if (status && counts.hasOwnProperty(status)) {
                (counts as any)[status]++;
            }
            counts.total++;
        });

        // Update UI
        const updateElement = (id: string, value: number) => {
            const element = document.getElementById(id);
            if (element) element.textContent = String(value);
        };

        updateElement('yes-count', counts.yes);
        updateElement('maybe-count', counts.maybe);
        updateElement('no-count', counts.no);
        updateElement('total-count', counts.total);
    }

    private addPersonToUIOptimistic(person: Attendee): void {
        // Find the correct alphabetical position to insert the new person
        const displayName = person.display_name || (person.first_name + ' ' + person.last_name);
        let insertIndex = this.attendees.length;
        
        for (let i = 0; i < this.attendees.length; i++) {
            const attendee = this.attendees[i];
            if (!attendee) continue;
            const existingName = attendee.display_name || (attendee.first_name + ' ' + attendee.last_name);
            if (displayName.localeCompare(existingName, undefined, { sensitivity: 'base' }) < 0) {
                insertIndex = i;
                break;
            }
        }
        
        // Insert at the correct position in memory
        this.attendees.splice(insertIndex, 0, person);
        
        // Add to UI using existing render function
        const listContainer = document.getElementById('attendance-list');
        if (listContainer) {
            const attendeeHTML = this.renderAttendeeItem(person);
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = attendeeHTML;
            const attendeeElement = tempDiv.firstElementChild as HTMLElement;
            if (!attendeeElement) return;
            
            // Add a visual indicator that this is pending
            attendeeElement.style.opacity = '0.7';
            attendeeElement.style.border = '2px dashed var(--warning, #ffc107)';
            
            // Find the correct DOM position to insert the element
            const existingItems = listContainer.querySelectorAll('.attendance-item');
            if (insertIndex < existingItems.length) {
                const referenceElement = existingItems[insertIndex];
                if (referenceElement) {
                    listContainer.insertBefore(attendeeElement, referenceElement);
                } else {
                    listContainer.appendChild(attendeeElement);
                }
            } else {
                listContainer.appendChild(attendeeElement);
            }
            
            this.setupAttendeeEvents(attendeeElement, person);
        }
        
        // Update counts
        this.updateStatusCountsOptimistic();
    }

    private removePersonFromUIOptimistic(personId: number | string): void {
        // Remove from in-memory data
        this.attendees = this.attendees.filter(attendee => attendee.person_id !== personId);
        
        // Remove from UI
        const attendeeElement = document.querySelector(`.attendance-item[data-person-id="${personId}"]`);
        if (attendeeElement) {
            attendeeElement.remove();
        }
        
        // Update counts
        this.updateStatusCountsOptimistic();
    }

    private replaceTemporaryPerson(tempId: number | string, realId: number | string): void {
        // Update in-memory data
        const attendee = this.attendees.find(a => a.person_id == tempId);
        if (attendee) {
            attendee.person_id = realId;
        }
        
        // Update UI element
        const attendeeElement = document.querySelector(`.attendance-item[data-person-id="${tempId}"]`) as HTMLElement;
        if (attendeeElement) {
            // Update data attribute
            attendeeElement.setAttribute('data-person-id', String(realId));
            
            // Remove pending visual indicators
            attendeeElement.style.opacity = '';
            attendeeElement.style.border = '';
            
            // Update dropdown handler with real ID
            const statusSelect = attendeeElement.querySelector('.attendance-status-select') as HTMLSelectElement;
            if (statusSelect) {
                const attendanceStatus = attendee?.attendance || 'yes';
                statusSelect.onchange = () => {
                    const selectedValue = statusSelect.value;
                    if (selectedValue === 'remove') {
                        this.removePersonFromSession(realId);
                        statusSelect.value = attendanceStatus;
                        this.updateDropdownStyle(statusSelect, attendanceStatus);
                    } else {
                        this.updateAttendanceStatus(realId, selectedValue as AttendanceStatus);
                        this.updateDropdownStyle(statusSelect, selectedValue);
                    }
                };
            }

            // Update edit link with real ID
            const editBtn = attendeeElement.querySelector('.person-edit-link') as HTMLAnchorElement;
            if (editBtn && this.config) {
                editBtn.href = `/admin/sessions/${this.config.sessionPath}/players/${realId}?from=attendance&instance_id=${this.config.sessionInstanceId}`;
            }
        }
    }

    private renderAttendeeItem(attendee: Attendee): string {
        const template = document.getElementById('attendance-item-template') as HTMLTemplateElement;
        if (!template) {
            return '';
        }
        
        const item = template.content.cloneNode(true) as DocumentFragment;
        const itemDiv = item.querySelector('.attendance-item') as HTMLElement;
        
        itemDiv.dataset.personId = String(attendee.person_id);
        const attendanceStatus = attendee.attendance || attendee.attendance_status!;
        itemDiv.dataset.status = attendanceStatus;
        
        const nameDiv = item.querySelector('.person-name') as HTMLElement;
        const nameText = attendee.display_name || (attendee.first_name + ' ' + attendee.last_name);
        nameDiv.textContent = nameText;
        
        const instrumentsDiv = item.querySelector('.person-instruments') as HTMLElement;
        if (instrumentsDiv) {
            const instrumentsText = attendee.instruments && attendee.instruments.length > 0 ? 
                attendee.instruments.join(', ') : 'No instruments';
            instrumentsDiv.textContent = instrumentsText;
        }
        
        return itemDiv.outerHTML;
    }

    private setupAttendeeEvents(attendeeElement: HTMLElement, attendee: Attendee): void {
        const personId = attendee.person_id;
        
        // Set up status dropdown
        const statusSelect = attendeeElement.querySelector('.attendance-status-select') as HTMLSelectElement;
        if (statusSelect) {
            const attendanceStatus = attendee.attendance || attendee.attendance_status!;
            statusSelect.value = attendanceStatus;
            this.updateDropdownStyle(statusSelect, attendanceStatus);

            statusSelect.onchange = () => {
                const selectedValue = statusSelect.value;
                if (selectedValue === 'remove') {
                    this.removePersonFromSession(personId);
                    // Reset dropdown to previous value since remove is an action, not a status
                    statusSelect.value = attendanceStatus;
                    this.updateDropdownStyle(statusSelect, attendanceStatus);
                } else {
                    this.updateAttendanceStatus(personId, selectedValue as AttendanceStatus);
                    this.updateDropdownStyle(statusSelect, selectedValue);
                }
            };
        }
        
        // Set up edit button
        const editBtn = attendeeElement.querySelector('.person-edit-link') as HTMLAnchorElement;
        if (editBtn && this.config) {
            editBtn.href = `/admin/sessions/${this.config.sessionPath}/players/${personId}?from=attendance&instance_id=${this.config.sessionInstanceId}`;
        }
        
        // Set up remove button
        const removeBtn = attendeeElement.querySelector('.person-remove-btn') as HTMLButtonElement;
        if (removeBtn) {
            removeBtn.onclick = () => {
                this.removePersonFromSession(personId);
            };
        }
    }

    private showSuccess(message: string): void {
        // Use ModalManager if available (beta page)
        if (window.ModalManager?.showMessage) {
            window.ModalManager.showMessage(message, 'success');
        } else {
            // Fallback to basic message display
            this.showBasicMessage(message, 'success');
        }
    }

    private showError(message: string): void {
        // Use ModalManager if available (beta page)
        if (window.ModalManager?.showMessage) {
            window.ModalManager.showMessage(message, 'error');
        } else {
            // Fallback to basic message display
            this.showBasicMessage(message, 'error');
        }
    }

    private showBasicMessage(message: string, type: 'success' | 'error'): void {
        // Create a simple toast-style message
        const messageDiv = document.createElement('div');
        messageDiv.className = `attendance-message attendance-message-${type}`;
        messageDiv.textContent = message;
        messageDiv.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; ' +
            'padding: 12px 20px; border-radius: 4px; font-weight: 500; ' +
            'color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.15); ' +
            'max-width: 300px; word-wrap: break-word;';
        
        if (type === 'success') {
            messageDiv.style.backgroundColor = '#28a745';
        } else if (type === 'error') {
            messageDiv.style.backgroundColor = '#dc3545';
        }
        
        document.body.appendChild(messageDiv);
        
        // Fade in
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(-20px)';
        setTimeout(() => {
            messageDiv.style.transition = 'all 0.3s ease';
            messageDiv.style.opacity = '1';
            messageDiv.style.transform = 'translateY(0)';
        }, 10);
        
        // Fade out and remove
        setTimeout(() => {
            messageDiv.style.opacity = '0';
            messageDiv.style.transform = 'translateY(-20px)';
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 300);
        }, type === 'error' ? 5000 : 3000);
    }
}

// Make AttendanceManager available globally
window.AttendanceManager = AttendanceManager;
window.attendanceManagerInstance = null;