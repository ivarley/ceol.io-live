/**
 * Unified Tune Detail Modal
 *
 * Provides consistent tune detail modal UI across all contexts:
 * - my_tunes: Personal tune collection (person_tune table)
 * - session: Session-level tune info (session_tune table)
 * - session_instance: Instance-specific overrides (session_instance_tune table)
 * - admin: Global tune info (tune table)
 */

(function(window) {
    'use strict';

    // Modal state
    let modalShowTime = 0;
    let currentContext = null;
    let currentTuneData = null;
    let currentConfig = null;
    let originalValues = {};
    let isConfigSectionVisible = false;
    let pendingHeardCountRequests = 0;

    // Musical keys list
    const MUSICAL_KEYS = [
        '', 'Amajor', 'Aminor', 'Adorian', 'Amixolydian', 'Bminor', 'Cmajor',
        'Dmajor', 'Dminor', 'Eminor', 'Fmajor', 'Gmajor', 'Dmixolydian',
        'Bmixolydian', 'Edorian', 'Gdorian', 'Gminor', 'Ddorian', 'Cdorian',
        'Fdorian', 'Gmixolydian', 'Emajor', 'Bdorian', 'Emixolydian'
    ];

    /**
     * Initialize the tune detail modal system
     */
    function init() {
        // Set up modal overlay click handler
        const modalOverlay = document.getElementById('tune-detail-modal');
        if (modalOverlay) {
            modalOverlay.addEventListener('click', function(event) {
                const timeSinceShown = Date.now() - modalShowTime;
                if (timeSinceShown < 500) return;

                if (event.target === event.currentTarget && event.target.classList.contains('modal-overlay')) {
                    closeModal();
                }
            });
        }

        // Escape key to close
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                const modal = document.getElementById('tune-detail-modal');
                if (modal && modal.style.display === 'flex') {
                    closeModal();
                }
            }
        });
    }

    /**
     * Show tune detail modal
     * @param {Object} config - Configuration object
     * @param {string} config.context - Context type: 'my_tunes', 'session', 'session_instance', 'admin'
     * @param {number} config.tuneId - The tune ID
     * @param {string} config.apiEndpoint - API endpoint to fetch tune details
     * @param {Function} config.onSave - Callback when save is successful
     * @param {Object} config.additionalData - Additional context-specific data
     */
    function showModal(config) {
        currentContext = config.context;
        currentConfig = config;
        pendingHeardCountRequests = 0; // Reset pending requests counter
        const modal = document.getElementById('tune-detail-modal');
        const modalContent = document.getElementById('tune-detail-content');

        // Update URL with tune parameter
        // For my_tunes context, use person_tune_id; otherwise use tune_id
        const urlParam = (config.context === 'my_tunes' && config.additionalData?.personTuneId)
            ? config.additionalData.personTuneId
            : config.tuneId;
        updateUrlWithTune(urlParam);

        // Show modal with loading state
        displayLoadingState(modalContent, config);
        modal.style.display = 'flex';

        setTimeout(() => {
            modal.classList.add('show');
        }, 10);

        modalShowTime = Date.now();

        // Fetch full tune details
        fetch(config.apiEndpoint)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    currentTuneData = extractTuneData(data, config.context);
                    renderModalContent(modalContent, currentTuneData, config);
                } else {
                    showError(modalContent, data.error || 'Failed to load tune details');
                }
            })
            .catch(error => {
                console.error('Error loading tune details:', error);
                showError(modalContent, 'Failed to load tune details');
            });
    }

    /**
     * Extract tune data from API response based on context
     */
    function extractTuneData(apiResponse, context) {
        let tuneData;

        switch(context) {
            case 'my_tunes':
                tuneData = apiResponse.person_tune || {};
                break;
            case 'session':
            case 'session_instance':
                tuneData = apiResponse.session_tune || {};
                break;
            case 'admin':
                tuneData = apiResponse.tune || {};
                break;
            default:
                tuneData = {};
        }

        return tuneData;
    }

    /**
     * Display loading state while fetching data
     */
    function displayLoadingState(container, config) {
        const tuneName = config.additionalData?.tuneName || 'Loading...';
        const tuneType = config.additionalData?.tuneType || '';

        container.innerHTML = `
            <button class="modal-close-btn" onclick="TuneDetailModal.close()" title="Close">&times;</button>
            <div class="modal-header-section">
                ${tuneType ? `<span class="tune-type-pill">${tuneType}</span>` : ''}
                <h2 class="modal-tune-title">${tuneName}</h2>
            </div>
            <div class="modal-loading">
                <div class="loading-spinner"></div>
                <p>Loading tune details...</p>
            </div>
        `;
    }

    /**
     * Render full modal content
     */
    function renderModalContent(container, tuneData, config) {
        const html = buildModalHTML(tuneData, config);
        container.innerHTML = html;

        // Store original values for dirty checking
        storeOriginalValues(tuneData, config);

        // Set up event listeners
        setupModalEventListeners(config);

        // Initialize configure section state
        isConfigSectionVisible = config.context === 'admin';
        updateConfigSectionVisibility();
    }

    /**
     * Build complete modal HTML
     */
    function buildModalHTML(tuneData, config) {
        const sections = [];

        // Close button
        sections.push(`<button class="modal-close-btn" onclick="TuneDetailModal.close()" title="Close">&times;</button>`);

        // Header section with tune type and title
        sections.push(buildHeaderSection(tuneData, config));

        // Configure section (collapsible except on admin)
        sections.push(buildConfigureSection(tuneData, config));

        // Tunebook status section (not on admin)
        if (config.context !== 'admin') {
            sections.push(buildTunebookStatusSection(tuneData, config));
        }

        // Heard count section (all contexts except admin, if Want To Learn or Learning)
        if (config.context !== 'admin') {
            sections.push(buildHeardCountSection(tuneData, config));
        }

        // ABC notation section (below heard count, above notes)
        sections.push(buildAbcNotationSection(tuneData, config));

        // Notes section (only on my_tunes)
        if (config.context === 'my_tunes') {
            sections.push(buildNotesSection(tuneData, config));
        }

        // Action buttons
        sections.push(buildActionButtons(config));

        // Additional links
        sections.push(buildAdditionalLinks(config));

        // Tabs section (Stats and History)
        sections.push(buildTabsSection(tuneData, config));

        return sections.join('\n');
    }

    /**
     * Build header section with tune type pill and title
     */
    function buildHeaderSection(tuneData, config) {
        const displayName = getDisplayName(tuneData, config);
        const thesessionLink = buildTheSessionLink(tuneData);
        const tuneType = tuneData.tune_type || config.additionalData?.tuneType || '';
        const isClickable = config.context !== 'admin';
        const clickHandler = isClickable ? ' onclick="TuneDetailModal.toggleConfigSection()"' : '';
        const clickableClass = isClickable ? ' modal-tune-title-clickable' : '';

        return `
            <div class="modal-header-section">
                ${tuneType ? `<span class="tune-type-pill">${tuneType}</span>` : ''}
                <h2 class="modal-tune-title${clickableClass}"${clickHandler} ${isClickable ? 'title="Click to configure"' : ''}>
                    ${displayName}
                    ${thesessionLink}
                </h2>
            </div>
        `;
    }

    /**
     * Get display name based on context
     */
    function getDisplayName(tuneData, config) {
        switch(config.context) {
            case 'my_tunes':
                return tuneData.name_alias || tuneData.tune_name || 'Unknown';
            case 'session':
            case 'session_instance':
                return tuneData.alias || tuneData.tune_name || 'Unknown';
            case 'admin':
                return tuneData.name || tuneData.tune_name || 'Unknown';
            default:
                return 'Unknown';
        }
    }

    /**
     * Escape HTML for safe use in attributes
     */
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Build TheSession.org link icon (blue hue)
     */
    function buildTheSessionLink(tuneData) {
        if (!tuneData.tune_id) return '';

        const baseUrl = `https://thesession.org/tunes/${tuneData.tune_id}`;
        let url = baseUrl;

        // Add setting_id if available
        const settingId = tuneData.setting_id || tuneData.setting_override;
        if (settingId) {
            url = `${baseUrl}?setting=${settingId}#setting${settingId}`;
        }

        return `<a href="${url}" target="_blank" class="thesession-link-icon" title="View on TheSession.org" onclick="event.stopPropagation();">🔗</a>`;
    }

    /**
     * Build ABC notation section
     * Displays cached ABC notation if available
     */
    function buildAbcNotationSection(tuneData, config) {
        // Get ABC notation from tuneData
        const abc = tuneData.abc;
        const incipitAbc = tuneData.incipit_abc;

        if (!abc && !incipitAbc) {
            return '';
        }

        // Default to showing incipit if available, otherwise full ABC
        const showIncipit = !!incipitAbc;
        const displayText = showIncipit ? incipitAbc : abc;

        // Replace "!" with newlines for display
        const formattedDisplayText = displayText.replace(/!/g, '\n');

        // Only make it clickable if we have both incipit and full ABC
        const hasToggle = !!(incipitAbc && abc && incipitAbc !== abc);
        const clickHandler = hasToggle ? ' onclick="TuneDetailModal.toggleAbcDisplay()"' : '';
        const clickableClass = hasToggle ? ' abc-notation-clickable' : '';
        const displayClass = showIncipit ? ' abc-notation-incipit' : ' abc-notation-full';
        const titleAttr = hasToggle ? ' title="Click to toggle between incipit and full notation"' : '';

        return `
            <div class="abc-notation-section">
                <pre class="abc-notation-display${clickableClass}${displayClass}"${clickHandler}${titleAttr} data-full-abc="${escapeHtml(abc || '')}" data-incipit-abc="${escapeHtml(incipitAbc || '')}" data-showing-incipit="${showIncipit}">${formattedDisplayText}</pre>
            </div>
        `;
    }

    /**
     * Build configure section
     */
    function buildConfigureSection(tuneData, config) {
        const isAdmin = config.context === 'admin';
        const isMyTunes = config.context === 'my_tunes';
        const isSession = config.context === 'session';
        const isSessionInstance = config.context === 'session_instance';

        const fields = [];

        // Official tune name and ID (always shown in configure section)
        fields.push(`
            <div class="configure-field-group-inline">
                <div class="configure-label">Official Name:</div>
                <div class="configure-value">${tuneData.tune_name || tuneData.name || 'Unknown'}</div>
            </div>
            <div class="configure-field-group-inline">
                <div class="configure-label">Tune ID:</div>
                <div class="configure-value">${tuneData.tune_id || 'Unknown'}</div>
            </div>
        `);

        // Editable fields based on context
        if (isMyTunes) {
            fields.push(`
                <div class="configure-field-group">
                    <label class="configure-label" for="name-alias-input">I call this:</label>
                    <input type="text" id="name-alias-input" class="configure-input"
                           value="${tuneData.name_alias || ''}"
                           placeholder="Enter your name for this tune"
                           oninput="TuneDetailModal.onFieldChange()">
                </div>
                <div class="configure-field-group">
                    <label class="configure-label" for="setting-input">My setting:</label>
                    <div class="input-with-button">
                        <input type="text" id="setting-input" class="configure-input"
                               value="${tuneData.setting_id || ''}"
                               placeholder="e.g., 123 or paste URL"
                               oninput="TuneDetailModal.onSettingInput()">
                        <button type="button" class="fetch-setting-btn" onclick="TuneDetailModal.fetchSetting()" title="Fetch setting from TheSession.org">Fetch</button>
                    </div>
                    <div id="setting-error" class="field-error" style="display: none;"></div>
                </div>
            `);
        } else if (isSession) {
            fields.push(`
                <div class="configure-field-group">
                    <label class="configure-label" for="alias-input">We call this:</label>
                    <input type="text" id="alias-input" class="configure-input"
                           value="${tuneData.alias || ''}"
                           placeholder="Enter session name for this tune"
                           oninput="TuneDetailModal.onFieldChange()">
                </div>
                <div class="configure-field-group">
                    <label class="configure-label" for="setting-input">Our setting:</label>
                    <div class="input-with-button">
                        <input type="text" id="setting-input" class="configure-input"
                               value="${tuneData.setting_id || ''}"
                               placeholder="e.g., 123 or paste URL"
                               oninput="TuneDetailModal.onSettingInput()">
                        <button type="button" class="fetch-setting-btn" onclick="TuneDetailModal.fetchSetting()" title="Fetch setting from TheSession.org">Fetch</button>
                    </div>
                    <div id="setting-error" class="field-error" style="display: none;"></div>
                </div>
                <div class="configure-field-group">
                    <label class="configure-label" for="key-select">We play this in:</label>
                    <select id="key-select" class="configure-select" onchange="TuneDetailModal.onFieldChange()">
                        ${MUSICAL_KEYS.map(key => `
                            <option value="${key}" ${key === (tuneData.key || '') ? 'selected' : ''}>
                                ${key || '(not specified)'}
                            </option>
                        `).join('')}
                    </select>
                </div>
            `);
        } else if (isSessionInstance) {
            fields.push(`
                <div class="configure-field-group">
                    <label class="configure-label" for="alias-input">In this case, we called it:</label>
                    <input type="text" id="alias-input" class="configure-input"
                           value="${tuneData.name || ''}"
                           placeholder="Enter name for this instance"
                           oninput="TuneDetailModal.onFieldChange()">
                </div>
                <div class="configure-field-group">
                    <label class="configure-label" for="setting-input">This time, we played setting:</label>
                    <div class="input-with-button">
                        <input type="text" id="setting-input" class="configure-input"
                               value="${tuneData.setting_override || ''}"
                               placeholder="e.g., 123 or paste URL"
                               oninput="TuneDetailModal.onSettingInput()">
                        <button type="button" class="fetch-setting-btn" onclick="TuneDetailModal.fetchSetting()" title="Fetch setting from TheSession.org">Fetch</button>
                    </div>
                    <div id="setting-error" class="field-error" style="display: none;"></div>
                </div>
                <div class="configure-field-group">
                    <label class="configure-label" for="key-select">This time, we played in:</label>
                    <select id="key-select" class="configure-select" onchange="TuneDetailModal.onFieldChange()">
                        ${MUSICAL_KEYS.map(key => `
                            <option value="${key}" ${key === (tuneData.key_override || '') ? 'selected' : ''}>
                                ${key || '(not specified)'}
                            </option>
                        `).join('')}
                    </select>
                </div>
            `);
        } else if (isAdmin) {
            fields.push(`
                <div class="configure-field-group">
                    <label class="configure-label" for="tune-name-input">Tune Name:</label>
                    <input type="text" id="tune-name-input" class="configure-input"
                           value="${tuneData.name || ''}"
                           placeholder="Enter tune name"
                           oninput="TuneDetailModal.onFieldChange()">
                </div>
            `);
        }

        const displayStyle = isAdmin ? '' : ' style="display: none;"';

        return `
            <div id="configure-section" class="configure-section"${displayStyle}>
                ${fields.join('\n')}
            </div>
        `;
    }

    /**
     * Build tunebook status section
     */
    function buildTunebookStatusSection(tuneData, config) {
        // Only show if user is logged in
        if (!config.additionalData?.isUserLoggedIn) {
            return '';
        }

        // For my_tunes context, the tune is ALWAYS on the list and data is directly on tuneData
        // For other contexts, check person_tune_status
        let onList, learnStatus;

        if (config.context === 'my_tunes') {
            // my_tunes: tune is always on list, data is directly on tuneData
            onList = true;
            learnStatus = tuneData.learn_status || 'want to learn';
        } else {
            // session/session_instance: check person_tune_status
            const status = tuneData.person_tune_status;
            onList = status?.on_list || false;
            learnStatus = status?.learn_status || 'want to learn';
        }

        if (!onList) {
            // Not on list - red state
            return `
                <div class="tunebook-status-section tunebook-status-not-on-list">
                    This tune is not on your list.
                    <button class="tunebook-action-btn" onclick="TuneDetailModal.addToTunebook()">Add</button>
                </div>
            `;
        }

        // On list - color by status
        const statusClass = `tunebook-status-${learnStatus.replace(/ /g, '-')}`;

        return `
            <div class="tunebook-status-section ${statusClass}">
                This tune is on your list as
                <select id="tunebook-status-select" class="tunebook-status-select" onchange="TuneDetailModal.onFieldChange()">
                    <option value="want to learn" ${learnStatus === 'want to learn' ? 'selected' : ''}>Want To Learn</option>
                    <option value="learning" ${learnStatus === 'learning' ? 'selected' : ''}>Learning</option>
                    <option value="learned" ${learnStatus === 'learned' ? 'selected' : ''}>Learned</option>
                </select>
            </div>
        `;
    }

    /**
     * Build heard count section (all contexts except admin, for Want To Learn or Learning status)
     */
    function buildHeardCountSection(tuneData, config) {
        const status = tuneData.person_tune_status?.learn_status || tuneData.learn_status;
        if (!status || status === 'learned') {
            return '';
        }

        // Check if we have a person_tune_id to work with
        let hasPersonTuneId = false;
        if (config.context === 'my_tunes') {
            hasPersonTuneId = !!(tuneData.person_tune_id || config.additionalData?.personTuneId);
        } else {
            hasPersonTuneId = !!tuneData.person_tune_status?.person_tune_id;
        }

        // Don't show the section if we don't have a person_tune_id
        if (!hasPersonTuneId) {
            return '';
        }

        // Get heard_count from the appropriate location based on context
        const heardCount = config.context === 'my_tunes'
            ? (tuneData.heard_count || 0)
            : (tuneData.person_tune_status?.heard_count || 0);
        const plural = heardCount !== 1 ? 's' : '';

        return `
            <div class="heard-count-section">
                <div class="heard-count-label">
                    You've heard this <span id="heard-count-value">${heardCount}</span> time${plural}
                </div>
                <div class="heard-count-controls">
                    <span class="heard-count-spinner" style="display: none;">
                        <svg class="spinner-icon" viewBox="0 0 50 50">
                            <circle class="spinner-path" cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle>
                        </svg>
                    </span>
                    <button class="heard-count-btn heard-count-btn-minus"
                            onclick="TuneDetailModal.decrementHeardCount()"
                            ${heardCount === 0 ? 'disabled' : ''}>−</button>
                    <button class="heard-count-btn heard-count-btn-plus"
                            onclick="TuneDetailModal.incrementHeardCount()">+</button>
                </div>
            </div>
        `;
    }

    /**
     * Build notes section (my_tunes only)
     */
    function buildNotesSection(tuneData, config) {
        return `
            <div class="notes-section">
                <textarea id="notes-textarea" class="notes-textarea"
                          placeholder="Add notes about this tune..."
                          oninput="TuneDetailModal.onFieldChange()">${tuneData.notes || ''}</textarea>
            </div>
        `;
    }

    /**
     * Build action buttons
     */
    function buildActionButtons(config) {
        return `
            <div class="modal-action-buttons">
                <button id="cancel-btn" class="btn-secondary" onclick="TuneDetailModal.close()">Cancel</button>
                <button id="save-btn" class="btn-primary" onclick="TuneDetailModal.save()" disabled>Save</button>
            </div>
        `;
    }

    /**
     * Build additional links below buttons
     */
    function buildAdditionalLinks(config) {
        const links = [];

        if (config.context === 'my_tunes') {
            links.push(`<a href="#" class="remove-link" onclick="TuneDetailModal.removeFromMyTunes(); return false;">Remove From My Tunes</a>`);
        }

        if (config.context !== 'admin') {
            links.push(`<a href="#" onclick="TuneDetailModal.toggleConfigSection(); return false;">Configure This Tune</a>`);
        }

        if (links.length === 0) return '';

        return `
            <div class="modal-additional-links">
                ${links.join('<br>')}
            </div>
        `;
    }

    /**
     * Build tabs section (Stats and History)
     */
    function buildTabsSection(tuneData, config) {
        return `
            <div class="modal-tabs-section">
                <div class="modal-tabs-header">
                    <button class="modal-tab active" data-tab="stats" onclick="TuneDetailModal.switchTab('stats')">Stats</button>
                    <button class="modal-tab" data-tab="history" onclick="TuneDetailModal.switchTab('history')">History</button>
                </div>
                <div class="modal-tabs-content">
                    <div id="stats-tab" class="modal-tab-pane active">
                        ${buildStatsTabContent(tuneData, config)}
                    </div>
                    <div id="history-tab" class="modal-tab-pane">
                        ${buildHistoryTabContent(tuneData, config)}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Build Stats tab content
     */
    function buildStatsTabContent(tuneData, config) {
        const stats = [];

        // TheSession.org popularity
        const tunebookCount = tuneData.tunebook_count || tuneData.tunebook_count_cached || 0;
        const cachedDate = tuneData.tunebook_count_cached_date || '';
        stats.push(`
            <div class="stat-item">
                <div class="stat-label">TheSession.org Popularity:</div>
                <div class="stat-value">
                    <span id="tunebook-count">${tunebookCount}</span>
                    <button class="refresh-btn" onclick="TuneDetailModal.refreshTunebookCount()" title="Refresh">↻</button>
                    ${cachedDate ? `<span class="stat-date">Last Updated: ${cachedDate}</span>` : ''}
                </div>
            </div>
        `);

        // Context-specific stats
        if (config.context === 'my_tunes') {
            stats.push(`
                <div class="stat-item">
                    <div class="stat-label">Times Played At My Sessions:</div>
                    <div class="stat-value">${tuneData.session_play_count || 0}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Times Played Globally:</div>
                    <div class="stat-value">${tuneData.global_play_count || 0}</div>
                </div>
            `);
        } else if (config.context === 'session' || config.context === 'session_instance') {
            stats.push(`
                <div class="stat-item">
                    <div class="stat-label">Times Played At This Session:</div>
                    <div class="stat-value">${tuneData.times_played || 0}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Times Played Globally:</div>
                    <div class="stat-value">${tuneData.global_play_count || 0}</div>
                </div>
            `);
        } else if (config.context === 'admin') {
            stats.push(`
                <div class="stat-item">
                    <div class="stat-label">Times Played Globally:</div>
                    <div class="stat-value">${tuneData.global_play_count || 0}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Number Of Sessions Playing This Tune:</div>
                    <div class="stat-value">${tuneData.session_count || 0}</div>
                </div>
            `);
        }

        return stats.join('\n');
    }

    /**
     * Build History tab content
     */
    function buildHistoryTabContent(tuneData, config) {
        const playInstances = tuneData.play_instances || [];

        if (playInstances.length === 0) {
            return '<div class="no-history">No play history recorded yet.</div>';
        }

        const showFullInstanceName = config.context === 'my_tunes' || config.context === 'admin';

        const items = playInstances.map(instance => {
            const instanceName = buildInstanceName(instance, showFullInstanceName, config);
            const link = buildInstanceLink(instance, tuneData.tune_id, config);
            const position = instance.position_in_set || instance.order_number || '?';
            const settingId = instance.setting_id_override || instance.setting_override || '';

            return `
                <div class="history-item">
                    <div class="history-instance-name"><a href="${link}">${instanceName}</a></div>
                    <div class="history-position">Position in set: #${position}</div>
                    ${settingId ? `<div class="history-setting">Setting: #${settingId}</div>` : ''}
                </div>
            `;
        }).join('\n');

        return `<div class="history-list">${items}</div>`;
    }

    /**
     * Build instance name for history
     */
    function buildInstanceName(instance, showFullName, config) {
        if (showFullName) {
            // Full format: "Session Name - YYYY-MM-DD" or "Session Name - MM/DD - Location"
            return instance.full_name || instance.date || 'Unknown';
        } else {
            // Contextual format (within session): just the date or identifier
            return instance.date || 'Unknown';
        }
    }

    /**
     * Build link to session instance detail with tune parameter
     */
    function buildInstanceLink(instance, tuneId, config) {
        const instanceId = instance.session_instance_id;
        const sessionPath = config.additionalData?.sessionPath || '';

        if (config.context === 'admin') {
            // Need full path - should be in instance data
            return instance.link || '#';
        }

        return `/sessions/${sessionPath}/${instanceId}?tune=${tuneId}`;
    }

    /**
     * Store original values for dirty checking
     */
    function storeOriginalValues(tuneData, config) {
        originalValues = {
            context: config.context
        };

        switch(config.context) {
            case 'my_tunes':
                originalValues.name_alias = tuneData.name_alias || '';
                originalValues.setting_id = tuneData.setting_id || '';
                originalValues.notes = tuneData.notes || '';
                originalValues.learn_status = tuneData.learn_status || 'want to learn';
                break;
            case 'session':
                originalValues.alias = tuneData.alias || '';
                originalValues.setting_id = tuneData.setting_id || '';
                originalValues.key = tuneData.key || '';
                originalValues.learn_status = tuneData.person_tune_status?.learn_status || '';
                break;
            case 'session_instance':
                originalValues.name = tuneData.name || '';
                originalValues.setting_override = tuneData.setting_override || '';
                originalValues.key_override = tuneData.key_override || '';
                originalValues.learn_status = tuneData.person_tune_status?.learn_status || '';
                break;
            case 'admin':
                originalValues.name = tuneData.name || '';
                break;
        }
    }

    /**
     * Set up modal event listeners
     */
    function setupModalEventListeners(config) {
        // Field change detection for enabling Save button
        onFieldChange();
    }

    /**
     * Toggle configure section visibility
     */
    function toggleConfigSection() {
        if (currentContext === 'admin') return; // Always visible on admin

        isConfigSectionVisible = !isConfigSectionVisible;
        updateConfigSectionVisibility();
    }

    /**
     * Update configure section visibility
     */
    function updateConfigSectionVisibility() {
        const section = document.getElementById('configure-section');
        if (section) {
            section.style.display = isConfigSectionVisible ? 'block' : 'none';
        }
    }

    /**
     * Handle field change - enable/disable Save button
     */
    function onFieldChange() {
        const saveBtn = document.getElementById('save-btn');
        if (!saveBtn) return;

        const isDirty = checkIfDirty();
        saveBtn.disabled = !isDirty;
    }

    /**
     * Check if any field has been modified
     */
    function checkIfDirty() {
        // Check tunebook status for all contexts (except admin)
        const statusSelect = document.getElementById('tunebook-status-select');
        const statusChanged = statusSelect && statusSelect.value !== originalValues.learn_status;

        switch(currentContext) {
            case 'my_tunes':
                const nameAliasInput = document.getElementById('name-alias-input');
                const settingInput = document.getElementById('setting-input');
                const notesTextarea = document.getElementById('notes-textarea');

                return statusChanged ||
                       (nameAliasInput && nameAliasInput.value !== originalValues.name_alias) ||
                       (settingInput && extractSettingId(settingInput.value) !== (originalValues.setting_id || null)) ||
                       (notesTextarea && notesTextarea.value !== originalValues.notes);

            case 'session':
                const aliasInput = document.getElementById('alias-input');
                const sessionSettingInput = document.getElementById('setting-input');
                const keySelect = document.getElementById('key-select');

                return statusChanged ||
                       (aliasInput && aliasInput.value !== originalValues.alias) ||
                       (sessionSettingInput && extractSettingId(sessionSettingInput.value) !== (originalValues.setting_id || null)) ||
                       (keySelect && keySelect.value !== originalValues.key);

            case 'session_instance':
                const instanceAliasInput = document.getElementById('alias-input');
                const instanceSettingInput = document.getElementById('setting-input');
                const instanceKeySelect = document.getElementById('key-select');

                return statusChanged ||
                       (instanceAliasInput && instanceAliasInput.value !== originalValues.name) ||
                       (instanceSettingInput && extractSettingId(instanceSettingInput.value) !== (originalValues.setting_override || null)) ||
                       (instanceKeySelect && instanceKeySelect.value !== originalValues.key_override);

            case 'admin':
                const tuneNameInput = document.getElementById('tune-name-input');
                return tuneNameInput && tuneNameInput.value !== originalValues.name;

            default:
                return false;
        }
    }

    /**
     * Handle setting input with validation
     */
    function onSettingInput() {
        const input = document.getElementById('setting-input');
        const errorDiv = document.getElementById('setting-error');
        const saveBtn = document.getElementById('save-btn');

        if (!input || !errorDiv) return;

        const value = input.value.trim();
        if (!value) {
            errorDiv.style.display = 'none';
            input.style.borderColor = '';
            onFieldChange();
            return;
        }

        // Validate the input
        const validation = validateSettingInput(value, currentTuneData.tune_id);

        if (!validation.valid) {
            errorDiv.textContent = validation.error;
            errorDiv.style.display = 'block';
            input.style.borderColor = '#dc3545';
            if (saveBtn) saveBtn.disabled = true;
        } else {
            errorDiv.style.display = 'none';
            input.style.borderColor = '';

            // If we extracted a setting ID from URL, replace with just the number
            if (validation.settingId !== null && value !== validation.settingId.toString()) {
                input.value = validation.settingId.toString();
            }

            onFieldChange();
        }
    }

    /**
     * Validate setting input (number or TheSession.org URL)
     */
    function validateSettingInput(input, expectedTuneId) {
        if (!input) return { valid: true, settingId: null };

        // Check if it's just a number
        if (/^\d+$/.test(input)) {
            return { valid: true, settingId: parseInt(input) };
        }

        // Check if it's a TheSession.org URL
        if (input.includes('thesession.org')) {
            const settingId = extractSettingId(input);
            if (settingId === null) {
                return { valid: false, error: 'Could not extract setting ID from URL' };
            }

            // Validate that tune_id in URL matches current tune
            const tuneIdMatch = input.match(/thesession\.org\/tunes\/(\d+)/);
            if (tuneIdMatch) {
                const urlTuneId = parseInt(tuneIdMatch[1]);
                if (urlTuneId !== expectedTuneId) {
                    // Silently discard - wrong tune
                    return { valid: true, settingId: null };
                }
            }

            return { valid: true, settingId: settingId };
        }

        return { valid: false, error: 'Please enter a number or paste a valid TheSession.org URL' };
    }

    /**
     * Extract setting ID from input (number or URL)
     */
    function extractSettingId(input) {
        if (!input || input.trim() === '') return null;

        const trimmed = input.trim();

        // If it's just a number
        if (/^\d+$/.test(trimmed)) {
            return parseInt(trimmed);
        }

        // Try to extract from URL
        const queryMatch = trimmed.match(/[?&]setting=(\d+)/);
        if (queryMatch) return parseInt(queryMatch[1]);

        const hashMatch = trimmed.match(/#setting(\d+)/);
        if (hashMatch) return parseInt(hashMatch[1]);

        return null;
    }

    /**
     * Switch between tabs
     */
    function switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.modal-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update tab panes
        document.querySelectorAll('.modal-tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === `${tabName}-tab`);
        });
    }

    /**
     * Toggle between incipit and full ABC notation display
     */
    function toggleAbcDisplay() {
        const displayElement = document.querySelector('.abc-notation-display');
        if (!displayElement) return;

        const fullAbc = displayElement.dataset.fullAbc;
        const incipitAbc = displayElement.dataset.incipitAbc;
        const showingIncipit = displayElement.dataset.showingIncipit === 'true';

        // Toggle between incipit and full
        const newShowingIncipit = !showingIncipit;
        const newText = newShowingIncipit ? incipitAbc : fullAbc;

        // Replace "!" with newlines for display
        const formattedText = newText.replace(/!/g, '\n');

        // Update the display
        displayElement.textContent = formattedText;
        displayElement.dataset.showingIncipit = newShowingIncipit.toString();

        // Update classes
        if (newShowingIncipit) {
            displayElement.classList.add('abc-notation-incipit');
            displayElement.classList.remove('abc-notation-full');
        } else {
            displayElement.classList.remove('abc-notation-incipit');
            displayElement.classList.add('abc-notation-full');
        }
    }

    /**
     * Close modal
     */
    function closeModal() {
        const modal = document.getElementById('tune-detail-modal');
        modal.classList.remove('show');
        pendingHeardCountRequests = 0; // Reset pending requests counter

        // Remove tune parameter from URL
        removeUrlTuneParam();

        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }

    /**
     * Update URL with tune parameter
     */
    function updateUrlWithTune(tuneId) {
        // For session context, use path-based URLs; otherwise use query params
        const pathname = window.location.pathname;

        if (pathname.includes('/sessions/') && !pathname.includes('/my-tunes')) {
            // Session context: use path-based URL
            let basePath = pathname;
            // Remove existing tune ID from path if present
            basePath = basePath.replace(/\/tunes\/\d+$/, '');
            // Ensure we're on the tunes tab
            if (!basePath.endsWith('/tunes')) {
                basePath = basePath.replace(/\/(logs|people)$/, '') + '/tunes';
            }
            const newPath = `${basePath}/${tuneId}`;
            window.history.replaceState({}, '', newPath);
        } else {
            // Other contexts: use query params
            const url = new URL(window.location);
            url.searchParams.set('tune', tuneId);
            window.history.replaceState({}, '', url);
        }
    }

    /**
     * Remove tune parameter from URL
     */
    function removeUrlTuneParam() {
        const pathname = window.location.pathname;

        if (pathname.includes('/sessions/') && !pathname.includes('/my-tunes')) {
            // Session context: remove tune ID from path
            let newPath = pathname.replace(/\/tunes\/\d+$/, '/tunes');
            window.history.replaceState({}, '', newPath);
        } else {
            // Other contexts: remove query param
            const url = new URL(window.location);
            url.searchParams.delete('tune');
            window.history.replaceState({}, '', url);
        }
    }

    /**
     * Show error message in modal
     */
    function showError(container, message) {
        container.innerHTML = `
            <button class="modal-close-btn" onclick="TuneDetailModal.close()" title="Close">&times;</button>
            <div class="modal-error">
                <h3>Error</h3>
                <p>${message}</p>
            </div>
        `;
    }

    /**
     * Save changes to the tune
     */
    function save() {
        const saveBtn = document.getElementById('save-btn');
        if (!saveBtn || saveBtn.disabled) return;

        // Disable button and show saving state
        saveBtn.disabled = true;
        const originalText = saveBtn.textContent;
        saveBtn.textContent = 'Saving...';

        // Collect changed values based on context
        const updates = {};
        let apiEndpoint = '';
        let httpMethod = 'PUT';

        // Collect learn_status separately for session/session_instance contexts
        const statusSelect = document.getElementById('tunebook-status-select');
        const learnStatusChanged = statusSelect && statusSelect.value !== originalValues.learn_status;
        let separateLearnStatusUpdate = null;

        switch(currentContext) {
            case 'my_tunes':
                const nameAliasInput = document.getElementById('name-alias-input');
                const settingInput = document.getElementById('setting-input');
                const notesTextarea = document.getElementById('notes-textarea');

                // Only include fields that have changed
                if (nameAliasInput && nameAliasInput.value !== originalValues.name_alias) {
                    updates.name_alias = nameAliasInput.value.trim() || null;
                }
                if (settingInput) {
                    const newSettingId = extractSettingId(settingInput.value);
                    if (newSettingId !== (originalValues.setting_id || null)) {
                        updates.setting_id = newSettingId;
                    }
                }
                if (notesTextarea && notesTextarea.value !== originalValues.notes) {
                    updates.notes = notesTextarea.value.trim() || null;
                }
                if (statusSelect && statusSelect.value !== originalValues.learn_status) {
                    updates.learn_status = statusSelect.value;
                }

                apiEndpoint = `/api/my-tunes/${currentConfig.additionalData.personTuneId}`;
                break;

            case 'session':
                const aliasInput = document.getElementById('alias-input');
                const sessionSettingInput = document.getElementById('setting-input');
                const keySelect = document.getElementById('key-select');

                // Only include fields that have changed
                if (aliasInput && aliasInput.value !== originalValues.alias) {
                    updates.alias = aliasInput.value.trim() || null;
                }
                if (sessionSettingInput) {
                    const newSettingId = extractSettingId(sessionSettingInput.value);
                    if (newSettingId !== (originalValues.setting_id || null)) {
                        updates.setting_id = newSettingId;
                    }
                }
                if (keySelect && keySelect.value !== originalValues.key) {
                    updates.key = keySelect.value || null;
                }

                // learn_status must be updated via separate endpoint for session context
                if (learnStatusChanged) {
                    separateLearnStatusUpdate = {
                        endpoint: `/api/person/tunes/${currentTuneData.tune_id}/status`,
                        data: { learn_status: statusSelect.value }
                    };
                }

                apiEndpoint = `/api/sessions/${currentConfig.additionalData.sessionPath}/tunes/${currentTuneData.tune_id}`;
                break;

            case 'session_instance':
                const instanceNameInput = document.getElementById('alias-input');
                const instanceSettingInput = document.getElementById('setting-input');
                const instanceKeySelect = document.getElementById('key-select');

                // Only include fields that have changed
                if (instanceNameInput && instanceNameInput.value !== originalValues.name) {
                    updates.name = instanceNameInput.value.trim() || null;
                }
                if (instanceSettingInput) {
                    const newSettingId = extractSettingId(instanceSettingInput.value);
                    if (newSettingId !== (originalValues.setting_override || null)) {
                        updates.setting_override = newSettingId;
                    }
                }
                if (instanceKeySelect && instanceKeySelect.value !== originalValues.key_override) {
                    updates.key_override = instanceKeySelect.value || null;
                }

                // learn_status must be updated via separate endpoint for session_instance context
                if (learnStatusChanged) {
                    separateLearnStatusUpdate = {
                        endpoint: `/api/person/tunes/${currentTuneData.tune_id}/status`,
                        data: { learn_status: statusSelect.value }
                    };
                }

                const dateOrId = currentConfig.additionalData.dateOrId;
                apiEndpoint = `/api/sessions/${currentConfig.additionalData.sessionPath}/${dateOrId}/tunes/${currentTuneData.tune_id}`;
                break;

            case 'admin':
                const tuneNameInput = document.getElementById('tune-name-input');
                if (tuneNameInput) updates.name = tuneNameInput.value.trim();

                if (!updates.name) {
                    alert('Tune name cannot be empty');
                    saveBtn.disabled = false;
                    saveBtn.textContent = originalText;
                    return;
                }

                apiEndpoint = `/api/admin/tunes/${currentTuneData.tune_id}`;
                break;
        }

        // Build promise chain - main update first, then learn_status if needed
        let savePromise;

        // Check if there are any updates to send to the main endpoint
        const hasMainUpdates = Object.keys(updates).length > 0;

        if (hasMainUpdates) {
            // Make the main update request
            savePromise = fetch(apiEndpoint, {
                method: httpMethod,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(updates)
            })
            .then(response => response.json());
        } else {
            // No main updates, just return success
            savePromise = Promise.resolve({ success: true, message: 'No changes to save' });
        }

        // If we need to make a separate learn_status update, chain it
        if (separateLearnStatusUpdate) {
            savePromise = savePromise.then(data => {
                if (!data.success) return data; // Don't continue if first update failed

                // Make the learn_status update
                return fetch(separateLearnStatusUpdate.endpoint, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(separateLearnStatusUpdate.data)
                })
                .then(statusResponse => statusResponse.json())
                .then(statusData => {
                    // Return combined success
                    return {
                        success: data.success && statusData.success,
                        error: statusData.error || data.error,
                        message: statusData.message || data.message
                    };
                });
            });
        }

        // Handle the response
        savePromise.then(data => {
            if (data.success) {
                saveBtn.textContent = 'Saved!';
                saveBtn.style.backgroundColor = '#28a745';

                // Update the status section color if status was changed
                const statusSelect = document.getElementById('tunebook-status-select');
                if (statusSelect && updates.learn_status) {
                    const statusSection = document.querySelector('.tunebook-status-section');
                    if (statusSection) {
                        // Remove old status classes
                        statusSection.classList.remove('tunebook-status-want-to-learn', 'tunebook-status-learning', 'tunebook-status-learned');
                        // Add new status class
                        statusSection.classList.add(`tunebook-status-${updates.learn_status.replace(/ /g, '-')}`);
                    }

                    // Update local data
                    if (currentContext === 'my_tunes') {
                        currentTuneData.learn_status = updates.learn_status;
                    } else if (currentTuneData.person_tune_status) {
                        currentTuneData.person_tune_status.learn_status = updates.learn_status;
                    }

                    // Update heard count section visibility if status changed to/from learned
                    const heardCountSection = document.querySelector('.heard-count-section');
                    if (heardCountSection) {
                        if (updates.learn_status === 'learned') {
                            heardCountSection.style.display = 'none';
                        } else {
                            heardCountSection.style.display = 'flex';
                        }
                    }
                }

                // Update original values to reflect saved state
                storeOriginalValues(Object.assign({}, currentTuneData, updates), currentConfig);

                // Remove tune parameter from URL first (before onSave which might reload)
                removeUrlTuneParam();

                // Call onSave callback if provided
                if (currentConfig.onSave && typeof currentConfig.onSave === 'function') {
                    currentConfig.onSave();
                }

                setTimeout(() => {
                    closeModal();
                }, 1000);
            } else {
                saveBtn.textContent = 'Error';
                saveBtn.style.backgroundColor = '#dc3545';
                console.error('Error saving:', data.error || data.message);

                setTimeout(() => {
                    saveBtn.disabled = false;
                    saveBtn.textContent = originalText;
                    saveBtn.style.backgroundColor = '';
                }, 2000);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            saveBtn.textContent = 'Error';
            saveBtn.style.backgroundColor = '#dc3545';

            setTimeout(() => {
                saveBtn.disabled = false;
                saveBtn.textContent = originalText;
                saveBtn.style.backgroundColor = '';
            }, 2000);
        });
    }

    /**
     * Update heard count spinner visibility based on pending requests
     */
    function updateHeardCountSpinner() {
        const spinner = document.querySelector('.heard-count-spinner');
        if (spinner) {
            spinner.style.display = pendingHeardCountRequests > 0 ? 'inline-block' : 'none';
        }
    }

    /**
     * Start a heard count API request (increment pending counter and show spinner)
     */
    function startHeardCountRequest() {
        pendingHeardCountRequests++;
        updateHeardCountSpinner();
    }

    /**
     * End a heard count API request (decrement pending counter and update spinner)
     */
    function endHeardCountRequest() {
        pendingHeardCountRequests = Math.max(0, pendingHeardCountRequests - 1);
        updateHeardCountSpinner();
    }

    /**
     * Increment heard count (all contexts except admin)
     */
    function incrementHeardCount() {
        if (currentContext === 'admin') return;

        const countValueSpan = document.getElementById('heard-count-value');
        const plusBtn = document.querySelector('.heard-count-btn-plus');
        const minusBtn = document.querySelector('.heard-count-btn-minus');

        // Get current count from appropriate location based on context
        let currentCount;
        if (currentContext === 'my_tunes') {
            currentCount = currentTuneData.heard_count || 0;
        } else if (currentTuneData.person_tune_status) {
            currentCount = currentTuneData.person_tune_status.heard_count || 0;
        } else {
            currentCount = 0;
        }

        const newCount = currentCount + 1;

        // Optimistically update UI immediately
        if (countValueSpan) {
            countValueSpan.textContent = newCount;
        }

        // Update local data
        if (currentContext === 'my_tunes') {
            currentTuneData.heard_count = newCount;
        } else if (currentTuneData.person_tune_status) {
            currentTuneData.person_tune_status.heard_count = newCount;
        }

        // Enable minus button since count is now > 0
        if (minusBtn) minusBtn.disabled = false;

        // Update plural text
        const labelDiv = countValueSpan?.parentElement;
        if (labelDiv) {
            const plural = newCount !== 1 ? 's' : '';
            labelDiv.innerHTML = `You've heard this <span id="heard-count-value">${newCount}</span> time${plural}`;
        }

        // Get person_tune_id for API call
        let personTuneId = null;
        if (currentContext === 'my_tunes') {
            personTuneId = currentTuneData.person_tune_id || currentConfig.additionalData?.personTuneId;
        } else if (currentTuneData.person_tune_status?.person_tune_id) {
            personTuneId = currentTuneData.person_tune_status.person_tune_id;
        }

        if (!personTuneId) {
            console.error('Cannot increment: person_tune_id not available');
            // Revert optimistic update
            if (countValueSpan) countValueSpan.textContent = currentCount;
            if (currentContext === 'my_tunes') {
                currentTuneData.heard_count = currentCount;
            } else if (currentTuneData.person_tune_status) {
                currentTuneData.person_tune_status.heard_count = currentCount;
            }
            return;
        }

        // Start tracking API request and show spinner
        startHeardCountRequest();

        // Make async API call
        fetch(`/api/my-tunes/${personTuneId}/heard`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                console.error('Error incrementing heard count:', data.error);
                // Revert optimistic update on error
                if (countValueSpan) countValueSpan.textContent = currentCount;
                if (currentContext === 'my_tunes') {
                    currentTuneData.heard_count = currentCount;
                } else if (currentTuneData.person_tune_status) {
                    currentTuneData.person_tune_status.heard_count = currentCount;
                }
                if (minusBtn) minusBtn.disabled = currentCount === 0;
                // Update plural text back
                if (labelDiv) {
                    const plural = currentCount !== 1 ? 's' : '';
                    labelDiv.innerHTML = `You've heard this <span id="heard-count-value">${currentCount}</span> time${plural}`;
                }
            }
            // End tracking API request and hide spinner if no more pending
            endHeardCountRequest();
        })
        .catch(error => {
            console.error('Error:', error);
            // Revert optimistic update on error
            if (countValueSpan) countValueSpan.textContent = currentCount;
            if (currentContext === 'my_tunes') {
                currentTuneData.heard_count = currentCount;
            } else if (currentTuneData.person_tune_status) {
                currentTuneData.person_tune_status.heard_count = currentCount;
            }
            if (minusBtn) minusBtn.disabled = currentCount === 0;
            // Update plural text back
            if (labelDiv) {
                const plural = currentCount !== 1 ? 's' : '';
                labelDiv.innerHTML = `You've heard this <span id="heard-count-value">${currentCount}</span> time${plural}`;
            }
            // End tracking API request and hide spinner if no more pending
            endHeardCountRequest();
        });
    }

    /**
     * Decrement heard count (all contexts except admin)
     * Uses PUT with PATCH-like semantics - server will decrement from current DB value
     */
    function decrementHeardCount() {
        if (currentContext === 'admin') return;

        // Get current count from appropriate location based on context
        let currentCount;
        if (currentContext === 'my_tunes') {
            currentCount = currentTuneData.heard_count || 0;
        } else if (currentTuneData.person_tune_status) {
            currentCount = currentTuneData.person_tune_status.heard_count || 0;
        } else {
            currentCount = 0;
        }

        if (currentCount === 0) return;

        const countValueSpan = document.getElementById('heard-count-value');
        const minusBtn = document.querySelector('.heard-count-btn-minus');
        const plusBtn = document.querySelector('.heard-count-btn-plus');

        const newCount = Math.max(0, currentCount - 1);

        // Optimistically update UI immediately
        if (countValueSpan) {
            countValueSpan.textContent = newCount;
        }

        // Update local data
        if (currentContext === 'my_tunes') {
            currentTuneData.heard_count = newCount;
        } else if (currentTuneData.person_tune_status) {
            currentTuneData.person_tune_status.heard_count = newCount;
        }

        // Disable minus button if count is now 0
        if (minusBtn) minusBtn.disabled = newCount === 0;

        // Update plural text
        const labelDiv = countValueSpan?.parentElement;
        if (labelDiv) {
            const plural = newCount !== 1 ? 's' : '';
            labelDiv.innerHTML = `You've heard this <span id="heard-count-value">${newCount}</span> time${plural}`;
        }

        // Get person_tune_id for API call
        let personTuneId = null;
        if (currentContext === 'my_tunes') {
            personTuneId = currentTuneData.person_tune_id || currentConfig.additionalData?.personTuneId;
        } else if (currentTuneData.person_tune_status?.person_tune_id) {
            personTuneId = currentTuneData.person_tune_status.person_tune_id;
        }

        if (!personTuneId) {
            console.error('Cannot decrement: person_tune_id not available');
            // Revert optimistic update
            if (countValueSpan) countValueSpan.textContent = currentCount;
            if (currentContext === 'my_tunes') {
                currentTuneData.heard_count = currentCount;
            } else if (currentTuneData.person_tune_status) {
                currentTuneData.person_tune_status.heard_count = currentCount;
            }
            if (minusBtn) minusBtn.disabled = currentCount === 0;
            return;
        }

        // Start tracking API request and show spinner
        startHeardCountRequest();

        // Make async API call to atomically decrement on server
        fetch(`/api/my-tunes/${personTuneId}/heard`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                console.error('Error decrementing heard count:', data.error);
                // Revert optimistic update on error
                if (countValueSpan) countValueSpan.textContent = currentCount;
                if (currentContext === 'my_tunes') {
                    currentTuneData.heard_count = currentCount;
                } else if (currentTuneData.person_tune_status) {
                    currentTuneData.person_tune_status.heard_count = currentCount;
                }
                if (minusBtn) minusBtn.disabled = currentCount === 0;
                // Update plural text back
                if (labelDiv) {
                    const plural = currentCount !== 1 ? 's' : '';
                    labelDiv.innerHTML = `You've heard this <span id="heard-count-value">${currentCount}</span> time${plural}`;
                }
            }
            // End tracking API request and hide spinner if no more pending
            endHeardCountRequest();
        })
        .catch(error => {
            console.error('Error:', error);
            // Revert optimistic update on error
            if (countValueSpan) countValueSpan.textContent = currentCount;
            if (currentContext === 'my_tunes') {
                currentTuneData.heard_count = currentCount;
            } else if (currentTuneData.person_tune_status) {
                currentTuneData.person_tune_status.heard_count = currentCount;
            }
            if (minusBtn) minusBtn.disabled = currentCount === 0;
            // Update plural text back
            if (labelDiv) {
                const plural = currentCount !== 1 ? 's' : '';
                labelDiv.innerHTML = `You've heard this <span id="heard-count-value">${currentCount}</span> time${plural}`;
            }
            // End tracking API request and hide spinner if no more pending
            endHeardCountRequest();
        });
    }

    /**
     * Add tune to user's tunebook
     */
    function addToTunebook() {
        const tuneId = currentTuneData.tune_id;

        fetch('/api/person/tunes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                tune_id: tuneId,
                learn_status: 'want to learn',
                heard_count: 0
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Reload the modal to show updated state
                if (currentConfig && currentConfig.apiEndpoint) {
                    // Re-fetch and render
                    fetch(currentConfig.apiEndpoint)
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                currentTuneData = extractTuneData(data, currentContext);
                                const modalContent = document.getElementById('tune-detail-content');
                                renderModalContent(modalContent, currentTuneData, currentConfig);
                            }
                        });
                }
            } else {
                console.error('Error adding to tunebook:', data.error);
                alert('Failed to add tune to your list');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to add tune to your list');
        });
    }

    /**
     * Update tunebook status (DEPRECATED - now uses save button)
     * This function is no longer used but kept for reference.
     * Status changes now go through the save() function via dirty tracking.
     */
    function updateTunebookStatus() {
        // This function is deprecated - status changes now use the Save button
        console.log('updateTunebookStatus called but is deprecated - use Save button instead');
    }

    /**
     * Remove tune from user's tunebook
     */
    function removeFromMyTunes() {
        if (!confirm('Are you sure you want to remove this tune from your list?')) {
            return;
        }

        const personTuneId = currentConfig.additionalData?.personTuneId;
        if (!personTuneId) {
            alert('Unable to remove tune');
            return;
        }

        fetch(`/api/my-tunes/${personTuneId}`, {
            method: 'DELETE',
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Remove tune parameter from URL first (before onSave which might reload)
                removeUrlTuneParam();

                // Call onSave callback if provided (to refresh the list)
                if (currentConfig.onSave && typeof currentConfig.onSave === 'function') {
                    currentConfig.onSave();
                }
                closeModal();
            } else {
                console.error('Error removing tune:', data.error);
                alert('Failed to remove tune from your list');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to remove tune from your list');
        });
    }

    /**
     * Refresh tunebook count from TheSession.org
     */
    function refreshTunebookCount() {
        const button = document.getElementById('refresh-btn') || event.target;
        const countSpan = document.getElementById('tunebook-count');
        const tuneId = currentTuneData.tune_id;

        if (!button) return;

        // Disable button and show loading state
        button.disabled = true;
        const originalButtonText = button.textContent;
        button.textContent = '⟳';

        let apiEndpoint = '';

        // Determine API endpoint based on context
        if (currentContext === 'admin') {
            apiEndpoint = `/api/admin/tunes/${tuneId}/refresh_tunebook_count`;
        } else if (currentContext === 'session' || currentContext === 'session_instance') {
            apiEndpoint = `/api/sessions/${currentConfig.additionalData.sessionPath}/tunes/${tuneId}/refresh_tunebook_count`;
        } else {
            // For my_tunes, we can still use the session endpoint or add a dedicated one
            apiEndpoint = `/api/admin/tunes/${tuneId}/refresh_tunebook_count`;
        }

        fetch(apiEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const newCount = data.new_count || data.tunebook_count;
                if (countSpan) {
                    countSpan.textContent = newCount;
                }

                // Update local data
                currentTuneData.tunebook_count = newCount;
                currentTuneData.tunebook_count_cached = newCount;

                // Show success feedback
                button.textContent = '✓';
                button.style.backgroundColor = '#28a745';
                button.style.color = 'white';
            } else {
                button.textContent = '✗';
                button.style.backgroundColor = '#dc3545';
                button.style.color = 'white';
                console.error('Error refreshing tunebook count:', data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            button.textContent = '✗';
            button.style.backgroundColor = '#dc3545';
            button.style.color = 'white';
        })
        .finally(() => {
            // Reset button after 2 seconds
            setTimeout(() => {
                button.disabled = false;
                button.textContent = originalButtonText;
                button.style.backgroundColor = '';
                button.style.color = '';
            }, 2000);
        });
    }

    /**
     * Fetch and cache setting from TheSession.org
     */
    function fetchSetting() {
        const settingInput = document.getElementById('setting-input');
        const tuneId = currentTuneData.tune_id;

        if (!settingInput) return;

        // Get setting_id from input (if specified)
        const settingIdValue = settingInput.value.trim();

        // Find the button (it's a sibling of the input)
        const button = event?.target || document.querySelector('.fetch-setting-btn');
        if (!button) return;

        // Disable button and show loading state
        button.disabled = true;
        const originalButtonText = button.textContent;
        button.textContent = '⟳';

        // Build API URL with optional setting_id parameter
        let apiUrl = `/api/tunes/${tuneId}/settings/cache`;
        if (settingIdValue) {
            // Extract setting ID from URL if needed
            const validation = validateSettingInput(settingIdValue, tuneId);
            const settingId = validation.settingId || settingIdValue;
            apiUrl += `?setting_id=${settingId}`;
        }

        fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update current tune data with the ABC notation and incipit
                currentTuneData.abc = data.setting.abc;
                currentTuneData.incipit_abc = data.setting.incipit_abc;

                // Re-render the modal to show the ABC notation
                const modalContent = document.getElementById('tune-detail-content');
                renderModalContent(modalContent, currentTuneData, currentConfig);

                // Show success feedback on button
                const newButton = document.querySelector('.fetch-setting-btn');
                if (newButton) {
                    newButton.textContent = '✓';
                    newButton.style.backgroundColor = '#28a745';
                    newButton.style.color = 'white';

                    setTimeout(() => {
                        newButton.disabled = false;
                        newButton.textContent = originalButtonText;
                        newButton.style.backgroundColor = '';
                        newButton.style.color = '';
                    }, 2000);
                }
            } else {
                button.textContent = '✗';
                button.style.backgroundColor = '#dc3545';
                button.style.color = 'white';
                console.error('Error fetching setting:', data.message);

                setTimeout(() => {
                    button.disabled = false;
                    button.textContent = originalButtonText;
                    button.style.backgroundColor = '';
                    button.style.color = '';
                }, 2000);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            button.textContent = '✗';
            button.style.backgroundColor = '#dc3545';
            button.style.color = 'white';

            setTimeout(() => {
                button.disabled = false;
                button.textContent = originalButtonText;
                button.style.backgroundColor = '';
                button.style.color = '';
            }, 2000);
        });
    }

    /**
     * Get tune ID from URL parameter
     * @returns {number|null} Tune ID if present in URL, null otherwise
     */
    function getTuneIdFromUrl() {
        const pathname = window.location.pathname;

        // For session context, check path-based URL first
        if (pathname.includes('/sessions/') && !pathname.includes('/my-tunes')) {
            const match = pathname.match(/\/tunes\/(\d+)$/);
            if (match) {
                return parseInt(match[1], 10);
            }
        }

        // Fall back to query param for other contexts
        const urlParams = new URLSearchParams(window.location.search);
        const tuneParam = urlParams.get('tune');
        return tuneParam ? parseInt(tuneParam, 10) : null;
    }

    // Public API
    window.TuneDetailModal = {
        init: init,
        show: showModal,
        close: closeModal,
        toggleConfigSection: toggleConfigSection,
        toggleAbcDisplay: toggleAbcDisplay,
        onFieldChange: onFieldChange,
        onSettingInput: onSettingInput,
        switchTab: switchTab,
        save: save,
        incrementHeardCount: incrementHeardCount,
        decrementHeardCount: decrementHeardCount,
        addToTunebook: addToTunebook,
        updateTunebookStatus: updateTunebookStatus,
        removeFromMyTunes: removeFromMyTunes,
        refreshTunebookCount: refreshTunebookCount,
        fetchSetting: fetchSetting,
        getTuneIdFromUrl: getTuneIdFromUrl
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})(window);
