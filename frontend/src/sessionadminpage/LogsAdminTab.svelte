<script>
  // i18n-converted
  // Logs tab: session instance history table (row click opens the bundled
  // InstanceSheet — the Svelte port of the old static/js/session_instance_modal.js),
  // ?instance= deep link auto-open, and the Add Session Instance sheet
  // (suggestion-prefilled).
  let { sessionPath, locationName, load } = $props()

  import { Sheet, toast, Chip, LoadError, t, formatDate } from '../lib/index.js'
  import InstanceSheet from './InstanceSheet.svelte'
  import { parseLocalDate } from '../shared/parse.js'

  let instanceSheet = $state(null) // bind:this of the bundled InstanceSheet

  let logs = $state(null) // null until loaded
  let loadError = $state(null)
  let started = false

  let reloading = $state(false)

  // A failure renders LoadError (with Retry) in place of the table.
  function loadLogsContent() {
    reloading = true
    return fetch(`/api/admin/sessions/${sessionPath}/logs`)
      .then((response) => response.json())
      .then((data) => {
        if (data.error || !data.logs) throw new Error(data.error || 'logs load failed')
        loadError = null
        logs = data.logs

        // Check if we should auto-open a specific instance sheet
        const urlParams = new URLSearchParams(window.location.search)
        const instanceId = urlParams.get('instance')
        if (instanceId) {
          // Find the log with this instance ID to get the date
          const log = data.logs.find((l) => l.session_instance_id == instanceId)
          if (log && instanceSheet) {
            instanceSheet.show(parseInt(instanceId), sessionPath, log.date)
          }
          // Clear the querystring so refreshing doesn't re-open
          window.history.replaceState({}, '', window.location.pathname)
        }
      })
      .catch((error) => {
        console.error('Error loading session logs:', error)
        loadError = 'failed'
      })
      .finally(() => {
        reloading = false
      })
  }

  $effect(() => {
    if (load && !started) {
      started = true
      loadLogsContent()
    }
  })

  const fmtDate = (dateStr) => {
    const date = parseLocalDate(dateStr)
    return {
      main: formatDate(date, { month: 'short', day: 'numeric', year: 'numeric' }),
      weekday: formatDate(date, { weekday: 'long' }),
    }
  }

  function openInstance(log) {
    instanceSheet?.show(log.session_instance_id, sessionPath, log.date)
  }

  // --- Add Session Instance sheet -------------------------------------------------
  let addModalOpen = $state(false)
  let dateValue = $state('')
  let startTimeValue = $state('')
  let endTimeValue = $state('')
  let locationValue = $state('')
  let commentsValue = $state('')
  let adding = $state(false)
  let suggesting = $state(false)
  let suggestError = $state(false)

  async function showAddSessionModal() {
    // Set defaults while we fetch the suggestion
    dateValue = new Date().toISOString().split('T')[0]
    startTimeValue = ''
    endTimeValue = ''
    locationValue = ''
    commentsValue = ''

    adding = false
    addModalOpen = true
    await suggest()
  }

  // Prefill the next usual date/times. A failure keeps today's date but says so,
  // so a default isn't mistaken for the session's next night.
  async function suggest() {
    suggesting = true
    suggestError = false
    try {
      const response = await fetch(`/api/sessions/${sessionPath}/next_instance_suggestion`)
      const data = await response.json()
      if (!data.success) throw new Error(data.message || 'next_instance_suggestion failed')
      dateValue = data.date || dateValue
      startTimeValue = data.start_time || ''
      endTimeValue = data.end_time || ''
    } catch (error) {
      console.error('Failed to get next session suggestion:', error)
      suggestError = true
    } finally {
      suggesting = false
    }
  }

  function hideAddSessionModal() {
    addModalOpen = false
  }

  function addSessionInstance() {
    if (adding) return
    const date = dateValue.trim()
    const startTime = startTimeValue.trim()
    const endTime = endTimeValue.trim()
    const location = locationValue.trim()
    const comments = commentsValue.trim()

    if (!date) {
      toast(t('Please enter a session date'), 'error')
      return
    }

    // Prepare request data (optional fields only when provided)
    const requestData = { date: date }
    if (startTime) requestData.start_time = startTime
    if (endTime) requestData.end_time = endTime
    if (location) requestData.location = location
    if (comments) requestData.comments = comments

    adding = true
    fetch(`/api/sessions/${sessionPath}/add_instance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestData),
    })
      .then((response) => response.json())
      .then((data) => {
        adding = false
        if (data.success) {
          toast(data.message, 'success')
          hideAddSessionModal()
          // Reload the logs content to show the new instance
          loadLogsContent()
        } else {
          toast(data.message || t("Couldn't add the session instance. Try again."), 'error')
        }
      })
      .catch((error) => {
        adding = false
        console.error('Error adding session instance:', error)
        toast(t("Couldn't add the session instance. Check your connection and try again."), 'error')
      })
  }
</script>

<section class="docs-section">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
    <h2 class="section-heading" style="margin-bottom: 0;">{t('Session Instance History')}</h2>
    <button type="button" class="btn btn-primary" id="add-session-instance-btn" onclick={showAddSessionModal}>
      {t('Add Session Instance')}
    </button>
  </div>
  <div id="logs-content">
    {#if loadError}
      <LoadError id="logs-load-error" message={t("Couldn't load the session history.")} onRetry={loadLogsContent} retrying={reloading} />
    {:else if !logs}
      <p class="text-muted">{t('Loading session history...')}</p>
    {:else if logs.length === 0}
      <div class="alert alert-info">{t('No session instances found.')}</div>
    {:else}
      <div class="table-responsive">
        <table class="table table-striped table-hover" id="logs-table">
          <thead>
            <tr>
              <th>{t('Date')}</th>
              <th class="text-center">{t('Tunes')}</th>
              <th class="text-center">{t('Players')}</th>
              <th class="text-center">{t('Status')}</th>
            </tr>
          </thead>
          <tbody>
            {#each logs as log (log.session_instance_id)}
              <tr
                class="log-row"
                style="cursor: pointer;"
                data-instance-id={log.session_instance_id}
                data-date={log.date}
                onclick={() => openInstance(log)}>
                <td class="log-date">
                  <strong>{fmtDate(log.date).main}</strong>
                  <br />
                  <small class="text-muted">{fmtDate(log.date).weekday}</small>
                </td>
                <td class="log-tunes text-center">{log.tune_count}</td>
                <td class="log-attendance text-center">{log.attendance_count}</td>
                <td class="log-status text-center">
                  {#if log.is_cancelled}<Chip label={t('Cancelled')} styled={false} chipClass="badge bg-danger" />{:else}<Chip label={t('Held')} styled={false} chipClass="badge bg-success" />{/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</section>

<!-- Add Session Instance Sheet (commit lives in the footer so a failed POST
     keeps the form open, like the legacy modal) -->
<Sheet bind:open={addModalOpen} title={t('Add Session Instance')}>
  {#if suggestError}
    <LoadError
      inline
      id="add-instance-suggest-error"
      message={t("Couldn't look up the next usual date, so this is today. Check it before adding.")}
      onRetry={suggest}
      retrying={suggesting} />
  {/if}
  <div class="mb-3">
    <label for="session-date-input" class="form-label">{t('Session Date:')}</label>
    <input type="date" id="session-date-input" class="form-control" bind:value={dateValue} required />
  </div>

  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
    <div class="mb-3">
      <label for="session-start-time-input" class="form-label">{t('Start Time:')}</label>
      <input type="time" id="session-start-time-input" class="form-control" bind:value={startTimeValue} />
    </div>
    <div class="mb-3">
      <label for="session-end-time-input" class="form-label">{t('End Time:')}</label>
      <input type="time" id="session-end-time-input" class="form-control" bind:value={endTimeValue} />
    </div>
  </div>

  <div class="mb-3">
    <label for="session-location-input" class="form-label">{t('Location:')}</label>
    <input type="text" id="session-location-input" class="form-control" placeholder={t('The usual: {location}', { location: locationName })} bind:value={locationValue} />
  </div>

  <div class="mb-3">
    <label for="session-comments-input" class="form-label">{t('Comments:')}</label>
    <textarea id="session-comments-input" class="form-control" placeholder={t('Notes about this session')} rows="3" style="resize: vertical;" bind:value={commentsValue}></textarea>
  </div>
  {#snippet footer()}
    <div style="text-align: right;">
      <button type="button" class="btn btn-primary" id="add-session-confirm-btn" onclick={addSessionInstance} disabled={adding}>{adding ? t('Adding…') : t('Add Session')}</button>
    </div>
  {/snippet}
</Sheet>

<!-- Session instance detail (bundled port of the old vanilla SessionInstanceModal) -->
<InstanceSheet bind:this={instanceSheet} onDeleted={loadLogsContent} />
