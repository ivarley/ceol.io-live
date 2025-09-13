/**
 * Attendance Management JavaScript
 * Handles session attendance functionality including check-in, person search, and instrument management
 */

// Use function constructor for maximum compatibility
function AttendanceManager() {
    this.config = null;
    this.attendees = [];
    this.searchTimeout = null;
    this.instruments = [
        'Fiddle', 'Flute', 'Whistle', 'Accordion', 'Concertina', 'Banjo', 
        'Guitar', 'Bouzouki', 'Mandolin', 'Bodhrán', 'Pipes', 'Harp'
    ];
}

AttendanceManager.prototype.init = function(config) {
    this.config = config;
    window.attendanceManagerInstance = this;
    
    // Check if we're on the beta page
    this.isBetaPage = window.location.pathname.includes('/beta') || 
                     window.TextInput !== undefined || 
                     document.querySelector('#tune-pills-container') !== null;
    
    this.loadAttendance();
    this.setupEventListeners();
    this.initializeQuickCheckin();
    
    // Set up modal input protection for beta page
    if (this.isBetaPage) {
        this.setupBetaPageModalSupport();
    }
};

AttendanceManager.prototype.setupBetaPageModalSupport = function() {
    var self = this;
    console.log('Setting up beta page modal support');
    
    // When modals are shown, prevent the beta page's text input system from interfering
    var modalIds = ['addPersonModal', 'personEditModal'];
    modalIds.forEach(function(modalId) {
        var modal = document.getElementById(modalId);
        if (modal) {
            // Stop text input events from propagating to the beta page handlers
            modal.addEventListener('keydown', function(e) {
                e.stopPropagation();
            });
            modal.addEventListener('keypress', function(e) {
                e.stopPropagation();
            });
            modal.addEventListener('input', function(e) {
                e.stopPropagation();
            });
        }
    });
};

AttendanceManager.prototype.setupEventListeners = function() {
    var self = this;
    var searchInput = document.getElementById('attendee-search');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            clearTimeout(self.searchTimeout);
            self.searchTimeout = setTimeout(function() {
                self.searchPeople(e.target.value);
            }, 300);
        });

        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                self.searchPeople(e.target.value);
            }
        });
    }

    document.addEventListener('click', function(e) {
        var searchResults = document.getElementById('search-results');
        var searchInput = document.getElementById('attendee-search');
        if (searchResults && searchInput && 
            !searchResults.contains(e.target) && 
            !searchInput.contains(e.target)) {
            searchResults.style.display = 'none';
        }
    });
};

AttendanceManager.prototype.initializeQuickCheckin = function() {
    if (this.config.isRegular) {
        this.updateQuickCheckinButton();
    }
};

AttendanceManager.prototype.updateQuickCheckinButton = function() {
    var self = this;
    var btn = document.getElementById('quick-checkin-btn');
    if (!btn) return;

    var currentAttendee = this.attendees.find(function(a) { 
        return a.person_id === self.config.currentUserId; 
    });
    
    if (currentAttendee) {
        switch (currentAttendee.attendance_status) {
            case 'yes':
                btn.innerHTML = '<i class="fas fa-check-circle"></i> Checked In';
                btn.className = 'btn btn-success btn-sm';
                btn.onclick = function() { self.changeMyStatus('maybe'); };
                break;
            case 'maybe':
                btn.innerHTML = '<i class="fas fa-question-circle"></i> Maybe';
                btn.className = 'btn btn-warning btn-sm';
                btn.onclick = function() { self.changeMyStatus('no'); };
                break;
            case 'no':
                btn.innerHTML = '<i class="fas fa-times-circle"></i> Not Coming';
                btn.className = 'btn btn-danger btn-sm';
                btn.onclick = function() { self.changeMyStatus('yes'); };
                break;
        }
    } else {
        btn.innerHTML = '<i class="fas fa-check"></i> Check In';
        btn.className = 'btn btn-success btn-sm';
        btn.onclick = function() { self.quickCheckin(); };
    }
};

AttendanceManager.prototype.loadAttendance = function() {
    var self = this;
    console.log('loadAttendance called for session instance:', this.config.sessionInstanceId);
    fetch('/api/session_instance/' + this.config.sessionInstanceId + '/attendees')
        .then(function(response) {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error('Failed to load attendance data');
            }
        })
        .then(function(response) {
            console.log('Attendance API response:', response);
            // Handle different response formats
            if (response.data && response.data.attendees) {
                self.attendees = response.data.attendees;
                self.regulars = response.data.regulars || [];
            } else {
                self.attendees = response.attendees || response.data || [];
                self.regulars = response.regulars || [];
            }
            console.log('Parsed attendees:', self.attendees);
            console.log('Parsed regulars:', self.regulars);
            if (self.attendees.length > 0) {
                console.log('First attendee structure:', self.attendees[0]);
            }
            
            // Debug: show breakdown by status
            var statusBreakdown = {
                yes: self.attendees.filter(function(a) { return (a.attendance || a.attendance_status) === 'yes'; }).length,
                maybe: self.attendees.filter(function(a) { return (a.attendance || a.attendance_status) === 'maybe'; }).length,
                no: self.attendees.filter(function(a) { return (a.attendance || a.attendance_status) === 'no'; }).length,
                other: self.attendees.filter(function(a) { var status = a.attendance || a.attendance_status; return status !== 'yes' && status !== 'maybe' && status !== 'no'; }).length
            };
            console.log('Status breakdown:', statusBreakdown);
            self.renderAttendance();
            self.updateStats();
            self.updateQuickCheckinButton();
        })
        .catch(function(error) {
            console.error('Error loading attendance:', error);
            self.showError('Error loading attendance data');
        });
};

AttendanceManager.prototype.renderAttendance = function() {
    var self = this;
    var container = document.getElementById('attendance-list');
    if (!container) return;

    if (this.attendees.length === 0) {
        container.innerHTML = '<div class="text-center p-3 text-muted">No attendees yet</div>';
        return;
    }

    var sortedAttendees = this.attendees.slice().sort(function(a, b) {
        if (a.is_regular && !b.is_regular) return -1;
        if (!a.is_regular && b.is_regular) return 1;
        var nameA = a.display_name || (a.first_name + ' ' + a.last_name);
        var nameB = b.display_name || (b.first_name + ' ' + b.last_name);
        return nameA.localeCompare(nameB);
    });

    var template = document.getElementById('attendance-item-template');
    container.innerHTML = '';

    sortedAttendees.forEach(function(attendee) {
        var item = template.content.cloneNode(true);
        var itemDiv = item.querySelector('.attendance-item');
        
        itemDiv.dataset.personId = attendee.person_id;
        // Set data-status for CSS styling
        var attendanceStatus = attendee.attendance || attendee.attendance_status;
        itemDiv.dataset.status = attendanceStatus;
        
        var nameDiv = item.querySelector('.person-name');
        console.log('Rendering attendee:', attendee);
        // Use display_name if available, otherwise fall back to first_name + last_name
        var nameText = attendee.display_name || (attendee.first_name + ' ' + attendee.last_name);
        console.log('Name text:', nameText);
        nameDiv.textContent = nameText;
        if (attendee.is_regular) {
            nameDiv.innerHTML = nameText + ' <span class="badge badge-primary badge-sm">Regular</span>';
        }

        var instrumentsDiv = item.querySelector('.person-instruments');
        if (attendee.instruments && attendee.instruments.length > 0) {
            instrumentsDiv.textContent = attendee.instruments.join(', ');
        } else {
            instrumentsDiv.textContent = 'No instruments listed';
        }

        if (self.config.canManage) {
            var statusButtons = item.querySelectorAll('.attendance-status');
            statusButtons.forEach(function(btn) {
                var attendanceStatus = attendee.attendance || attendee.attendance_status;
                if (btn.dataset.status === attendanceStatus) {
                    btn.classList.remove('btn-outline-success', 'btn-outline-warning', 'btn-outline-danger');
                    btn.classList.add(self.getStatusButtonClass(attendanceStatus));
                }
                btn.onclick = function() { 
                    self.updateAttendanceStatus(attendee.person_id, btn.dataset.status); 
                };
            });

            var editBtn = item.querySelector('[onclick*="editPerson"]');
            if (editBtn) {
                editBtn.onclick = function() { self.editPerson(attendee.person_id); };
            }

            var removeBtn = item.querySelector('[onclick*="removePerson"]');
            if (removeBtn) {
                removeBtn.onclick = function() { self.removePerson(attendee.person_id); };
            }
        } else {
            var statusDisplay = item.querySelector('.attendance-status-display');
            if (statusDisplay) {
                var attendanceStatus = attendee.attendance || attendee.attendance_status;
                statusDisplay.innerHTML = self.getStatusDisplay(attendanceStatus);
            }
        }

        container.appendChild(item);
    });
};

AttendanceManager.prototype.getStatusButtonClass = function(status) {
    switch (status) {
        case 'yes': return 'btn-success';
        case 'maybe': return 'btn-warning';
        case 'no': return 'btn-danger';
        default: return 'btn-secondary';
    }
};

AttendanceManager.prototype.getStatusDisplay = function(status) {
    switch (status) {
        case 'yes': return '<span class="text-success"><i class="fas fa-check"></i> Yes</span>';
        case 'maybe': return '<span class="text-warning"><i class="fas fa-question"></i> Maybe</span>';
        case 'no': return '<span class="text-danger"><i class="fas fa-times"></i> No</span>';
        default: return '<span class="text-muted">Unknown</span>';
    }
};

AttendanceManager.prototype.updateStats = function() {
    var yesCount = this.attendees.filter(function(a) { return (a.attendance || a.attendance_status) === 'yes'; }).length;
    var maybeCount = this.attendees.filter(function(a) { return (a.attendance || a.attendance_status) === 'maybe'; }).length;
    var noCount = this.attendees.filter(function(a) { return (a.attendance || a.attendance_status) === 'no'; }).length;
    var totalCount = this.attendees.length;

    document.getElementById('yes-count').textContent = yesCount;
    document.getElementById('maybe-count').textContent = maybeCount;
    document.getElementById('no-count').textContent = noCount;
    document.getElementById('total-count').textContent = totalCount;
};

AttendanceManager.prototype.quickCheckin = function() {
    var self = this;
    fetch('/api/session_instance/' + this.config.sessionInstanceId + '/attendees/checkin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ attendance_status: 'yes' })
    })
    .then(function(response) {
        if (response.ok) {
            return response.json();
        } else {
            return response.json().then(function(error) {
                throw new Error(error.error || 'Failed to check in');
            });
        }
    })
    .then(function() {
        self.loadAttendance();
        self.showSuccess('Checked in successfully!');
    })
    .catch(function(error) {
        console.error('Error checking in:', error);
        self.showError(error.message || 'Error checking in');
    });
};

AttendanceManager.prototype.changeMyStatus = function(newStatus) {
    var self = this;
    fetch('/api/session_instance/' + this.config.sessionInstanceId + '/attendees/checkin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ attendance_status: newStatus })
    })
    .then(function(response) {
        if (response.ok) {
            return response.json();
        } else {
            return response.json().then(function(error) {
                throw new Error(error.error || 'Failed to update status');
            });
        }
    })
    .then(function() {
        self.loadAttendance();
        self.showSuccess('Status updated!');
    })
    .catch(function(error) {
        console.error('Error updating status:', error);
        self.showError(error.message || 'Error updating status');
    });
};

AttendanceManager.prototype.updateAttendanceStatus = function(personId, status) {
    if (!this.config.canManage) return;

    // Optimistic update: Update UI immediately
    this.updateAttendeeStatusOptimistic(personId, status);
    this.updateStatusCountsOptimistic();

    var self = this;
    fetch('/api/session_instance/' + this.config.sessionInstanceId + '/attendees/checkin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ person_id: personId, attendance: status })
    })
    .then(function(response) {
        if (response.ok) {
            return response.json();
        } else {
            return response.json().then(function(error) {
                throw new Error(error.error || 'Failed to update attendance');
            });
        }
    })
    .then(function() {
        // Success - optimistic update was correct
        self.showSuccess('Attendance updated');
    })
    .catch(function(error) {
        console.error('Error updating attendance:', error);
        // Revert optimistic update on error by reloading from server
        self.loadAttendance();
        self.showError(error.message || 'Error updating attendance');
    });
};

AttendanceManager.prototype.searchPeople = function(query) {
    var self = this;
    if (!query) {
        var searchInput = document.getElementById('attendee-search');
        if (searchInput) {
            query = searchInput.value.trim();
        }
    }

    if (!query || query.length < 2) {
        var searchResults = document.getElementById('search-results');
        if (searchResults) {
            searchResults.style.display = 'none';
        }
        return;
    }

    fetch('/api/session/' + this.config.sessionId + '/people/search?q=' + encodeURIComponent(query))
        .then(function(response) {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error('Search failed');
            }
        })
        .then(function(data) {
            self.displaySearchResults(data.people || []);
        })
        .catch(function(error) {
            console.error('Error searching people:', error);
            self.showError('Search error');
        });
};

AttendanceManager.prototype.displaySearchResults = function(people) {
    var resultsDiv = document.getElementById('search-results');
    if (!resultsDiv) return;

    if (people.length === 0) {
        resultsDiv.innerHTML = '<div class="search-result-item text-muted">No people found</div>';
        resultsDiv.style.display = 'block';
        return;
    }

    var html = people.map(function(person) {
        var instruments = person.instruments && person.instruments.length > 0 ? 
            person.instruments.join(', ') : 'No instruments';
        return '<div class="search-result-item" onclick="window.AttendanceManager.addExistingPerson(' + person.person_id + ')">' +
               '<div class="person-name">' + person.first_name + ' ' + person.last_name + '</div>' +
               '<div class="person-instruments text-muted small">' + instruments + '</div>' +
               '</div>';
    }).join('');

    resultsDiv.innerHTML = html;
    resultsDiv.style.display = 'block';
};

AttendanceManager.prototype.addExistingPerson = function(personId) {
    var self = this;
    var payload = { person_id: personId, attendance: 'yes' };
    console.log('Sending checkin payload:', payload);
    
    fetch('/api/session_instance/' + this.config.sessionInstanceId + '/attendees/checkin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(function(response) {
        if (response.ok) {
            return response.json();
        } else {
            return response.json().then(function(error) {
                console.error('API Error Response:', error);
                throw new Error(error.error || error.message || 'Failed to add person');
            });
        }
    })
    .then(function() {
        console.log('Refreshing attendance list...');
        self.loadAttendance();
        var searchInput = document.getElementById('attendee-search');
        var searchResults = document.getElementById('search-results');
        if (searchInput) searchInput.value = '';
        if (searchResults) searchResults.style.display = 'none';
        self.showSuccess('Person added to attendance');
    })
    .catch(function(error) {
        console.error('Error adding person:', error);
        self.showError(error.message || 'Error adding person');
    });
};

AttendanceManager.prototype.showAddPersonModal = function() {
    // Temporarily disable beta page text input if present
    if (this.isBetaPage && window.TextInput) {
        this.originalTextInputTyping = window.TextInput.prototype.handleTextInput;
        window.TextInput.prototype.handleTextInput = function() {
            // Disable text input handling while modal is open
            return;
        };
    }
    
    // Check if ModalManager is available
    if (typeof ModalManager !== 'undefined') {
        var result = ModalManager.showModal('addPersonModal');
        
        // Ensure modal is properly visible - add Bootstrap modal classes
        if (result) {
            result.classList.add('show');
            result.style.display = 'block';
            result.removeAttribute('aria-hidden');
            
            // Add backdrop
            var backdrop = document.createElement('div');
            backdrop.className = 'modal-backdrop fade show';
            backdrop.id = 'modal-backdrop-' + Date.now();
            document.body.appendChild(backdrop);
            
            // Store backdrop reference for cleanup
            result.setAttribute('data-backdrop-id', backdrop.id);
        }
    } else {
        // Fallback: show modal directly with CSS
        var modal = document.getElementById('addPersonModal');
        if (modal) {
            modal.style.display = 'flex';
            modal.classList.add('show');
        }
    }
};

AttendanceManager.prototype.closeModal = function(modalId) {
    // Restore beta page text input if it was disabled
    if (this.isBetaPage && this.originalTextInputTyping && window.TextInput) {
        window.TextInput.prototype.handleTextInput = this.originalTextInputTyping;
        this.originalTextInputTyping = null;
    }
    
    var modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('show');
        modal.setAttribute('aria-hidden', 'true');
        
        // Remove backdrop
        var backdropId = modal.getAttribute('data-backdrop-id');
        if (backdropId) {
            var backdrop = document.getElementById(backdropId);
            if (backdrop) {
                backdrop.remove();
            }
            modal.removeAttribute('data-backdrop-id');
        }
    }
};

AttendanceManager.prototype.createPerson = function() {
    var self = this;
    var form = document.getElementById('person-add-form');
    var formData = new FormData(form);
    
    var instruments = [];
    var checkboxes = document.querySelectorAll('#add-instruments-container input[type="checkbox"]:checked');
    for (var i = 0; i < checkboxes.length; i++) {
        instruments.push(checkboxes[i].value);
    }

    var customInstrument = document.getElementById('add-new-instrument');
    if (customInstrument && customInstrument.value.trim()) {
        instruments.push(customInstrument.value.trim());
    }

    var personData = {
        first_name: formData.get('first_name'),
        last_name: formData.get('last_name'),
        email: formData.get('email'),
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
    
    var attendanceStatus = formData.get('attendance_status') || 'yes';

    // Debug logging
    console.log('Creating person with data:', personData);
    console.log('Instruments array:', instruments);

    // Create temporary person for optimistic update
    var tempPerson = {
        person_id: 'temp_' + Date.now(), // Temporary ID
        first_name: personData.first_name,
        last_name: personData.last_name,
        display_name: personData.first_name + ' ' + personData.last_name,
        instruments: instruments,
        attendance: attendanceStatus,
        is_admin: false,
        is_regular: false
    };

    // Optimistic update: Add person to UI immediately
    this.addPersonToUIOptimistic(tempPerson);

    fetch('/api/person', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(personData)
    })
    .then(function(response) {
        console.log('API Response status:', response.status);
        if (response.ok) {
            return response.json();
        } else {
            return response.json().then(function(error) {
                console.log('API Error response:', error);
                throw new Error(error.error || 'Failed to create person');
            });
        }
    })
    .then(function(result) {
        console.log('Person creation result:', result);
        var personId = result.data && result.data.person_id ? result.data.person_id : result.person_id;
        console.log('Extracted person ID:', personId);
        
        // Replace temporary person with real person ID
        self.replaceTemporaryPerson(tempPerson.person_id, personId);
        
        // Add person to attendance with chosen status
        var payload = { person_id: personId, attendance: attendanceStatus };
        console.log('Checking in new person with payload:', payload);
        
        return fetch('/api/session_instance/' + self.config.sessionInstanceId + '/attendees/checkin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(function(response) {
            if (response.ok) {
                return response.json();
            } else {
                return response.json().then(function(error) {
                    console.error('API Error Response:', error);
                    throw new Error(error.error || 'Failed to add person to attendance');
                });
            }
        });
    })
    .then(function() {
        self.closeModal('addPersonModal');
        form.reset();
        var checkboxes = document.querySelectorAll('#add-instruments-container input[type="checkbox"]');
        for (var i = 0; i < checkboxes.length; i++) {
            checkboxes[i].checked = false;
        }
        if (customInstrument) customInstrument.value = '';
        
        self.showSuccess('New person created and added to attendance');
    })
    .catch(function(error) {
        console.error('Error creating person:', error);
        // Remove optimistic update on error
        self.removePersonFromUIOptimistic(tempPerson.person_id);
        self.showError(error.message || 'Error creating person');
    });
};

AttendanceManager.prototype.refreshAttendance = function() {
    this.loadAttendance();
    this.showSuccess('Attendance refreshed');
};

AttendanceManager.prototype.editPerson = function(personId) {
    console.log('Edit person not yet implemented:', personId);
};

AttendanceManager.prototype.addNewInstrument = function() {
    var input = document.getElementById('add-new-instrument');
    if (!input || !input.value.trim()) return;
    
    var instrumentName = input.value.trim();
    var container = document.getElementById('add-instruments-container');
    if (!container) return;
    
    // Create new checkbox for the instrument
    var checkDiv = document.createElement('div');
    checkDiv.className = 'form-check';
    
    var checkbox = document.createElement('input');
    checkbox.className = 'form-check-input';
    checkbox.type = 'checkbox';
    checkbox.value = instrumentName;
    checkbox.checked = true;
    checkbox.id = 'inst-' + instrumentName.toLowerCase().replace(/\s+/g, '-');
    
    var label = document.createElement('label');
    label.className = 'form-check-label';
    label.setAttribute('for', checkbox.id);
    label.textContent = instrumentName;
    
    checkDiv.appendChild(checkbox);
    checkDiv.appendChild(label);
    container.appendChild(checkDiv);
    
    input.value = '';
};

AttendanceManager.prototype.removePerson = function(personId) {
    if (!confirm('Mark this person as not attending?')) return;
    
    // Set their status to "no" instead of removing them entirely
    this.updateAttendanceStatus(personId, 'no');
};

// Optimistic UI Update Helpers
AttendanceManager.prototype.updateAttendeeStatusOptimistic = function(personId, newStatus) {
    // Update in-memory data
    for (var i = 0; i < this.attendees.length; i++) {
        if (this.attendees[i].person_id == personId) {
            this.attendees[i].attendance = newStatus;
            break;
        }
    }
    
    // Update UI
    var attendanceItem = document.querySelector('.attendance-item[data-person-id="' + personId + '"]');
    if (attendanceItem) {
        // Update data attribute
        attendanceItem.setAttribute('data-status', newStatus);
        
        // Update button states
        var buttons = attendanceItem.querySelectorAll('.attendance-status');
        buttons.forEach(function(btn) {
            var btnStatus = btn.dataset.status;
            btn.classList.remove('btn-success', 'btn-warning', 'btn-danger');
            if (btnStatus === newStatus) {
                // Active state
                if (newStatus === 'yes') btn.classList.add('btn-success');
                else if (newStatus === 'maybe') btn.classList.add('btn-warning');
                else if (newStatus === 'no') btn.classList.add('btn-danger');
            } else {
                // Inactive state
                if (btnStatus === 'yes') btn.classList.add('btn-outline-success');
                else if (btnStatus === 'maybe') btn.classList.add('btn-outline-warning');
                else if (btnStatus === 'no') btn.classList.add('btn-outline-danger');
            }
        });
    }
};

AttendanceManager.prototype.updateStatusCountsOptimistic = function() {
    // Count statuses from current attendees array
    var counts = { yes: 0, maybe: 0, no: 0, total: 0 };
    
    for (var i = 0; i < this.attendees.length; i++) {
        var status = this.attendees[i].attendance;
        if (counts[status] !== undefined) {
            counts[status]++;
        }
        counts.total++;
    }
    
    // Update UI
    var yesCount = document.getElementById('yes-count');
    var maybeCount = document.getElementById('maybe-count');
    var noCount = document.getElementById('no-count');
    var totalCount = document.getElementById('total-count');
    
    if (yesCount) yesCount.textContent = counts.yes;
    if (maybeCount) maybeCount.textContent = counts.maybe;
    if (noCount) noCount.textContent = counts.no;
    if (totalCount) totalCount.textContent = counts.total;
};

AttendanceManager.prototype.addPersonToUIOptimistic = function(person) {
    // Add to in-memory data
    this.attendees.push(person);
    
    // Add to UI using existing render function
    var listContainer = document.getElementById('attendance-list');
    if (listContainer) {
        var attendeeHTML = this.renderAttendeeItem(person);
        var tempDiv = document.createElement('div');
        tempDiv.innerHTML = attendeeHTML;
        var attendeeElement = tempDiv.firstElementChild;
        
        // Add a visual indicator that this is pending
        attendeeElement.style.opacity = '0.7';
        attendeeElement.style.border = '2px dashed var(--warning, #ffc107)';
        
        listContainer.appendChild(attendeeElement);
        this.setupAttendeeEvents(attendeeElement, person);
    }
    
    // Update counts
    this.updateStatusCountsOptimistic();
};

AttendanceManager.prototype.removePersonFromUIOptimistic = function(personId) {
    // Remove from in-memory data
    this.attendees = this.attendees.filter(function(attendee) {
        return attendee.person_id !== personId;
    });
    
    // Remove from UI
    var attendeeElement = document.querySelector('.attendance-item[data-person-id="' + personId + '"]');
    if (attendeeElement) {
        attendeeElement.remove();
    }
    
    // Update counts
    this.updateStatusCountsOptimistic();
};

AttendanceManager.prototype.replaceTemporaryPerson = function(tempId, realId) {
    // Update in-memory data
    for (var i = 0; i < this.attendees.length; i++) {
        if (this.attendees[i].person_id == tempId) {
            this.attendees[i].person_id = realId;
            break;
        }
    }
    
    // Update UI element
    var attendeeElement = document.querySelector('.attendance-item[data-person-id="' + tempId + '"]');
    if (attendeeElement) {
        // Update data attribute
        attendeeElement.setAttribute('data-person-id', realId);
        
        // Remove pending visual indicators
        attendeeElement.style.opacity = '';
        attendeeElement.style.border = '';
        
        // Update button onclick handlers with real ID
        var buttons = attendeeElement.querySelectorAll('.attendance-status');
        var self = this;
        buttons.forEach(function(btn) {
            btn.onclick = function() { 
                self.updateAttendanceStatus(realId, btn.dataset.status); 
            };
        });
        
        var editBtn = attendeeElement.querySelector('[onclick*="editPerson"]');
        if (editBtn) {
            editBtn.onclick = function() { 
                self.editPerson(realId); 
            };
        }
        
        var removeBtn = attendeeElement.querySelector('[onclick*="removePerson"]');
        if (removeBtn) {
            removeBtn.onclick = function() { 
                self.removePerson(realId); 
            };
        }
    }
};

AttendanceManager.prototype.renderAttendeeItem = function(attendee) {
    var template = document.getElementById('attendance-item-template');
    if (!template) {
        console.error('attendance-item-template not found');
        return '';
    }
    
    var item = template.content.cloneNode(true);
    var itemDiv = item.querySelector('.attendance-item');
    
    itemDiv.dataset.personId = attendee.person_id;
    var attendanceStatus = attendee.attendance || attendee.attendance_status;
    itemDiv.dataset.status = attendanceStatus;
    
    var nameDiv = item.querySelector('.person-name');
    var nameText = attendee.display_name || (attendee.first_name + ' ' + attendee.last_name);
    nameDiv.textContent = nameText;
    
    var instrumentsDiv = item.querySelector('.person-instruments');
    if (instrumentsDiv) {
        var instrumentsText = attendee.instruments && attendee.instruments.length > 0 ? 
            attendee.instruments.join(', ') : 'No instruments';
        instrumentsDiv.textContent = instrumentsText;
    }
    
    return item.firstElementChild.outerHTML;
};

AttendanceManager.prototype.setupAttendeeEvents = function(attendeeElement, attendee) {
    var self = this;
    var personId = attendee.person_id;
    
    // Set up status buttons
    var buttons = attendeeElement.querySelectorAll('.attendance-status');
    buttons.forEach(function(btn) {
        var btnStatus = btn.dataset.status;
        var attendanceStatus = attendee.attendance || attendee.attendance_status;
        
        // Set initial button state
        btn.classList.remove('btn-success', 'btn-warning', 'btn-danger', 'btn-outline-success', 'btn-outline-warning', 'btn-outline-danger');
        if (btnStatus === attendanceStatus) {
            // Active state
            if (attendanceStatus === 'yes') btn.classList.add('btn-success');
            else if (attendanceStatus === 'maybe') btn.classList.add('btn-warning');
            else if (attendanceStatus === 'no') btn.classList.add('btn-danger');
        } else {
            // Inactive state
            if (btnStatus === 'yes') btn.classList.add('btn-outline-success');
            else if (btnStatus === 'maybe') btn.classList.add('btn-outline-warning');
            else if (btnStatus === 'no') btn.classList.add('btn-outline-danger');
        }
        
        btn.onclick = function() { 
            self.updateAttendanceStatus(personId, btn.dataset.status); 
        };
    });
    
    // Set up edit button
    var editBtn = attendeeElement.querySelector('[onclick*="editPerson"]');
    if (editBtn) {
        editBtn.onclick = function() { 
            self.editPerson(personId); 
        };
    }
    
    // Set up remove button
    var removeBtn = attendeeElement.querySelector('[onclick*="removePerson"]');
    if (removeBtn) {
        removeBtn.onclick = function() { 
            self.removePerson(personId); 
        };
    }
};

AttendanceManager.prototype.showSuccess = function(message) {
    console.log('Success:', message);
    // Use ModalManager if available (beta page)
    if (typeof ModalManager !== 'undefined' && ModalManager.showMessage) {
        ModalManager.showMessage(message, 'success');
    } else {
        // Fallback to basic message display
        this.showBasicMessage(message, 'success');
    }
};

AttendanceManager.prototype.showError = function(message) {
    console.error('Error:', message);
    // Use ModalManager if available (beta page)
    if (typeof ModalManager !== 'undefined' && ModalManager.showMessage) {
        ModalManager.showMessage(message, 'error');
    } else {
        // Fallback to basic message display
        this.showBasicMessage(message, 'error');
    }
};

AttendanceManager.prototype.showBasicMessage = function(message, type) {
    // Create a simple toast-style message
    var messageDiv = document.createElement('div');
    messageDiv.className = 'attendance-message attendance-message-' + type;
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
    setTimeout(function() {
        messageDiv.style.transition = 'all 0.3s ease';
        messageDiv.style.opacity = '1';
        messageDiv.style.transform = 'translateY(0)';
    }, 10);
    
    // Fade out and remove
    setTimeout(function() {
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(-20px)';
        setTimeout(function() {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        }, 300);
    }, type === 'error' ? 5000 : 3000);
};

// Constructor is available globally for initialization
window.AttendanceManager = AttendanceManager;

// Global instance variable
window.attendanceManagerInstance = null;