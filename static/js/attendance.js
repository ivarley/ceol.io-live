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
    this.loadAttendance();
    this.setupEventListeners();
    this.initializeQuickCheckin();
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
        self.loadAttendance();
    })
    .catch(function(error) {
        console.error('Error updating attendance:', error);
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
    
    var attendanceStatus = formData.get('attendance_status') || 'yes';

    // Debug logging
    console.log('Creating person with data:', personData);
    console.log('Instruments array:', instruments);

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
        
        // Refresh attendance list to show the new person
        self.loadAttendance();
        
        self.showSuccess('New person created and added to attendance');
    })
    .catch(function(error) {
        console.error('Error creating person:', error);
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

AttendanceManager.prototype.showSuccess = function(message) {
    console.log('Success:', message);
    var messageContainer = document.getElementById('message-container');
    if (messageContainer) {
        messageContainer.innerHTML = '<div class="message success"><p>' + message + '</p></div>';
        setTimeout(function() { 
            messageContainer.innerHTML = ''; 
        }, 3000);
    }
};

AttendanceManager.prototype.showError = function(message) {
    console.error('Error:', message);
    var messageContainer = document.getElementById('message-container');
    if (messageContainer) {
        messageContainer.innerHTML = '<div class="message error"><p>' + message + '</p></div>';
        setTimeout(function() { 
            messageContainer.innerHTML = ''; 
        }, 5000);
    }
};

// Constructor is available globally for initialization
window.AttendanceManager = AttendanceManager;

// Global instance variable
window.attendanceManagerInstance = null;