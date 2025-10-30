/**
 * Session Instance Detail Modal
 *
 * Provides a slide-in modal for viewing and managing session instance details
 * from the admin interface.
 */

const SessionInstanceModal = {
    currentInstanceId: null,
    currentSessionPath: null,
    currentDate: null,
    currentInstance: null,
    deleteConfirmShown: false,

    /**
     * Show the modal with session instance details
     * @param {number} sessionInstanceId - The ID of the session instance
     * @param {string} sessionPath - The session path (e.g., "austin/mueller")
     * @param {string} date - The date of the instance (YYYY-MM-DD)
     */
    show(sessionInstanceId, sessionPath, date) {
        this.currentInstanceId = sessionInstanceId;
        this.currentSessionPath = sessionPath;
        this.currentDate = date;
        this.deleteConfirmShown = false;

        const modal = document.getElementById('instance-detail-modal');
        const modalContent = document.getElementById('instance-modal-content');

        if (!modal || !modalContent) {
            console.error('Modal elements not found');
            return;
        }

        // Show loading state
        modalContent.innerHTML = `
            <div class="instance-modal-loading">
                <div class="instance-loading-spinner"></div>
                <p>Loading instance details...</p>
            </div>
        `;

        // Show modal with animation
        modal.style.display = 'flex';
        setTimeout(() => {
            modal.classList.add('show');
        }, 10);

        // Fetch instance details from the logs endpoint
        this.fetchInstanceDetails(sessionPath, sessionInstanceId);
    },

    /**
     * Fetch instance details from the server
     */
    fetchInstanceDetails(sessionPath, sessionInstanceId) {
        fetch(`/api/admin/sessions/${sessionPath}/logs`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to fetch session logs');
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }

                // Find the specific instance in the logs
                const instance = data.logs.find(log => log.session_instance_id === sessionInstanceId);

                if (!instance) {
                    throw new Error('Session instance not found');
                }

                this.renderModalContent(instance);
            })
            .catch(error => {
                console.error('Error fetching instance details:', error);
                this.showError(error.message);
            });
    },

    /**
     * Render the modal content with instance details
     */
    renderModalContent(instance) {
        const modalContent = document.getElementById('instance-modal-content');

        if (!modalContent) return;

        // Store instance data for later use
        this.currentInstance = instance;

        // Format date for display
        const date = new Date(instance.date);
        const dateStr = date.toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });

        // Format time range
        let timeRange = 'Time not specified';
        if (instance.start_time && instance.end_time) {
            timeRange = `${instance.start_time} - ${instance.end_time}`;
        } else if (instance.start_time) {
            timeRange = `From ${instance.start_time}`;
        }

        // Status badge
        const statusClass = instance.is_cancelled ? 'instance-status-cancelled' : 'instance-status-held';
        const statusText = instance.is_cancelled ? 'Cancelled' : 'Held';

        // Comments
        const comments = instance.comments && instance.comments.trim()
            ? instance.comments
            : null;

        modalContent.innerHTML = `
            <button class="instance-modal-close-btn" onclick="SessionInstanceModal.close()" title="Close">&times;</button>

            <div class="instance-modal-header">
                <h2 class="instance-modal-title">${dateStr}</h2>
                <div class="instance-modal-subtitle">${this.currentSessionPath}</div>
            </div>

            <div class="instance-info-section">
                <div class="instance-info-row">
                    <span class="instance-info-label">Time:</span>
                    <span class="instance-info-value">${timeRange}</span>
                </div>
                <div class="instance-info-row">
                    <span class="instance-info-label">Status:</span>
                    <span class="instance-status-badge ${statusClass}">${statusText}</span>
                </div>
                <div class="instance-info-row">
                    <span class="instance-info-label">Tunes Played:</span>
                    <span class="instance-info-value">
                        <a href="/sessions/${this.currentSessionPath}/${instance.date}" target="_blank">
                            ${instance.tune_count} tune${instance.tune_count !== 1 ? 's' : ''}
                        </a>
                    </span>
                </div>
                <div class="instance-info-row">
                    <span class="instance-info-label">Attendance:</span>
                    <span class="instance-info-value">${instance.attendance_count} player${instance.attendance_count !== 1 ? 's' : ''}</span>
                </div>
            </div>

            ${comments ? `
                <div class="instance-comments-section">
                    <div class="instance-comments-label">Comments:</div>
                    <div class="instance-comments-value">${this.escapeHtml(comments)}</div>
                </div>
            ` : ''}

            <div class="instance-modal-actions">
                <a href="/sessions/${this.currentSessionPath}/${instance.date}"
                   class="instance-action-btn instance-action-btn-primary"
                   target="_blank">
                    View Full Log
                </a>
                <a href="/sessions/${this.currentSessionPath}/${instance.date}?mode=edit"
                   class="instance-action-btn instance-action-btn-secondary">
                    Edit Log
                </a>
                <button class="instance-action-btn instance-action-btn-danger"
                        onclick="SessionInstanceModal.showDeleteConfirmation()">
                    Delete This Instance
                </button>
            </div>

            <div id="delete-confirmation" style="display: none;"></div>
        `;

        // Setup swipe-to-close for mobile
        this.setupSwipeToClose();
    },

    /**
     * Show delete confirmation UI
     */
    showDeleteConfirmation() {
        if (this.deleteConfirmShown) return;

        this.deleteConfirmShown = true;
        const confirmDiv = document.getElementById('delete-confirmation');

        if (!confirmDiv || !this.currentInstance) return;

        // Get instance details for warning message
        const tuneCount = this.currentInstance.tune_count;
        const attendanceCount = this.currentInstance.attendance_count;
        const tuneLabel = tuneCount === 1 ? 'tune' : 'tunes';
        const playerLabel = attendanceCount === 1 ? 'player' : 'players';

        confirmDiv.innerHTML = `
            <div class="instance-delete-confirm">
                <div class="instance-delete-confirm-title">⚠️ Confirm Deletion</div>
                <div class="instance-delete-confirm-text">
                    Are you sure you want to delete this session instance?<br>
                    This will remove:<br>
                    • ${tuneCount} ${tuneLabel}<br>
                    • ${attendanceCount} ${playerLabel}
                    <br><br>
                    <strong>This action cannot be undone.</strong>
                </div>
                <div class="instance-delete-confirm-actions">
                    <button class="instance-delete-confirm-btn instance-delete-cancel-btn"
                            onclick="SessionInstanceModal.hideDeleteConfirmation()">
                        Cancel
                    </button>
                    <button class="instance-delete-confirm-btn instance-delete-execute-btn"
                            onclick="SessionInstanceModal.executeDelete()">
                        Yes, Delete Instance
                    </button>
                </div>
            </div>
        `;

        confirmDiv.style.display = 'block';

        // Scroll to confirmation
        confirmDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    },

    /**
     * Hide delete confirmation UI
     */
    hideDeleteConfirmation() {
        this.deleteConfirmShown = false;
        const confirmDiv = document.getElementById('delete-confirmation');
        if (confirmDiv) {
            confirmDiv.style.display = 'none';
        }
    },

    /**
     * Execute the deletion
     */
    executeDelete() {
        const modalContent = document.getElementById('instance-modal-content');

        // Show loading state
        modalContent.innerHTML = `
            <div class="instance-modal-loading">
                <div class="instance-loading-spinner"></div>
                <p>Deleting instance...</p>
            </div>
        `;

        // Call delete API
        fetch(`/api/sessions/${this.currentSessionPath}/${this.currentDate}/delete`, {
            method: 'DELETE'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to delete session instance');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Show success message
                if (typeof showMessage === 'function') {
                    showMessage(data.message || 'Session instance deleted successfully', 'success');
                }

                // Close modal
                this.close();

                // Refresh the logs table
                if (typeof loadLogsContent === 'function') {
                    loadLogsContent();
                }
            } else {
                throw new Error(data.message || 'Failed to delete session instance');
            }
        })
        .catch(error => {
            console.error('Error deleting instance:', error);
            this.showError(error.message);
        });
    },

    /**
     * Show error state in modal
     */
    showError(message) {
        const modalContent = document.getElementById('instance-modal-content');

        if (!modalContent) return;

        modalContent.innerHTML = `
            <button class="instance-modal-close-btn" onclick="SessionInstanceModal.close()" title="Close">&times;</button>
            <div class="modal-error">
                <h3>Error</h3>
                <p>${this.escapeHtml(message)}</p>
                <button class="instance-action-btn instance-action-btn-primary"
                        onclick="SessionInstanceModal.close()">
                    Close
                </button>
            </div>
        `;
    },

    /**
     * Close the modal
     */
    close() {
        const modal = document.getElementById('instance-detail-modal');

        if (!modal) return;

        // Remove show class to trigger slide-out animation
        modal.classList.remove('show');

        // Wait for animation to complete before hiding
        setTimeout(() => {
            modal.style.display = 'none';
            this.currentInstanceId = null;
            this.currentSessionPath = null;
            this.currentDate = null;
            this.currentInstance = null;
            this.deleteConfirmShown = false;
        }, 300);
    },

    /**
     * Setup swipe-to-close gesture for mobile
     */
    setupSwipeToClose() {
        const modalDialog = document.querySelector('.instance-modal-dialog');

        if (!modalDialog) return;

        let touchStartX = 0;
        let touchStartY = 0;
        let touchStartTime = 0;
        let isSwiping = false;

        modalDialog.addEventListener('touchstart', (e) => {
            // Don't intercept touches on buttons or links
            const target = e.target;
            if (target.tagName === 'BUTTON' || target.tagName === 'A') {
                return;
            }

            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            touchStartTime = Date.now();
            isSwiping = false;
        }, { passive: true });

        modalDialog.addEventListener('touchmove', (e) => {
            if (!touchStartX) return;

            const target = e.target;
            if (target.tagName === 'BUTTON' || target.tagName === 'A') {
                return;
            }

            const touchCurrentX = e.touches[0].clientX;
            const touchCurrentY = e.touches[0].clientY;
            const deltaX = touchCurrentX - touchStartX;
            const deltaY = touchCurrentY - touchStartY;

            // Detect horizontal swipe (more horizontal than vertical)
            if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 10) {
                isSwiping = true;
            }
        }, { passive: true });

        modalDialog.addEventListener('touchend', (e) => {
            if (!touchStartX || !isSwiping) {
                touchStartX = 0;
                touchStartY = 0;
                return;
            }

            const target = e.target;
            if (target.tagName === 'BUTTON' || target.tagName === 'A') {
                touchStartX = 0;
                touchStartY = 0;
                isSwiping = false;
                return;
            }

            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;

            // Swipe right: deltaX > 0 and significant horizontal movement
            if (deltaX > 50 && Math.abs(deltaX) > Math.abs(deltaY) * 2) {
                // Swipe right detected - close modal
                this.close();
            }

            touchStartX = 0;
            touchStartY = 0;
            isSwiping = false;
        }, { passive: true });
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Close modal when clicking outside of it
document.addEventListener('click', function(e) {
    const modal = document.getElementById('instance-detail-modal');
    if (modal && e.target === modal) {
        SessionInstanceModal.close();
    }
});
