<script>
  // i18n-converted
  // The Add Session Instance sheet — kit Sheet chrome (spec 035: Cancel top-left,
  // scrim/Escape cancel, commit in the footer so a failed POST keeps it open).
  // Opening prefills from GET next_instance_suggestion; adding POSTs add_instance
  // and redirects to the new instance in edit mode.
  // isFestival re-frames one field: `location` is stored as session_instance.location_override,
  // which at a festival is the log's NAME, not an exception to the usual venue — several
  // sessions share the date, so it's the only thing telling them apart afterwards.
  let { sessionPath, locationName, isFestival = false } = $props()

  let visible = $state(false)
  let date = $state('')
  let startTime = $state('')
  let endTime = $state('')
  let location = $state('')
  let comments = $state('')
  let adding = $state(false)
  let suggesting = $state(false)
  let suggestError = $state(false)

  import { Sheet, toast, LoadError, t } from '../lib/index.js'

  export async function open() {
    // Defaults while we fetch the suggestion.
    date = new Date().toISOString().split('T')[0]
    startTime = ''
    endTime = ''
    location = ''
    comments = ''
    adding = false
    visible = true
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
      date = data.date || date
      startTime = data.start_time || ''
      endTime = data.end_time || ''
    } catch (error) {
      console.error('Failed to get next session suggestion:', error)
      suggestError = true
    } finally {
      suggesting = false
    }
  }

  export function close() {
    visible = false
  }

  function addSessionInstance() {
    if (adding) return
    const dateVal = date.trim()
    if (!dateVal) {
      toast(t('Please enter a session date'), 'error')
      return
    }

    const requestData = { date: dateVal }
    if (startTime.trim()) requestData.start_time = startTime.trim()
    if (endTime.trim()) requestData.end_time = endTime.trim()
    if (location.trim()) requestData.location = location.trim()
    if (comments.trim()) requestData.comments = comments.trim()

    adding = true
    fetch(`/api/sessions/${sessionPath}/add_instance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestData),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          // No toast (spec 052 §B4): the next line navigates to the instance that was
          // just created, so the confirmation was a banner shown for one frame over a
          // page on its way out.
          // Stays "Adding…" through the redirect — the page is about to change.
          close()
          // Redirect to the new session instance in edit mode; the id-based URL
          // is unambiguous when several instances share a date.
          const instanceId = data.session_instance_id || dateVal
          window.location.href = `/sessions/${sessionPath}/${instanceId}?edit=true`
        } else {
          adding = false
          toast(data.message || t("Couldn't add the session. Try again."), 'error')
        }
      })
      .catch((error) => {
        adding = false
        console.error('Error adding session instance:', error)
        toast(t("Couldn't add the session. Check your connection and try again."), 'error')
      })
  }
</script>

<Sheet bind:open={visible} title={t('Add Session Instance')}>
  <!-- .modal-body keeps the page's label/input styling; the chrome is the Sheet's -->
  <div class="modal-body">
    {#if suggestError}
      <LoadError
        inline
        id="add-instance-suggest-error"
        message={t("Couldn't look up the next usual date, so this is today. Check it before adding.")}
        onRetry={suggest}
        retrying={suggesting} />
    {/if}
    <label for="session-date-input">{t('Session Date:')}</label>
    <input
      type="date"
      id="session-date-input"
      required
      bind:value={date}
      onkeydown={(e) => {
        if (e.key === 'Enter' && visible) addSessionInstance()
      }} />

    <div style="margin-top: 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
      <div>
        <label for="session-start-time-input">{t('Start Time:')}</label>
        <input type="time" id="session-start-time-input" bind:value={startTime} />
      </div>
      <div>
        <label for="session-end-time-input">{t('End Time:')}</label>
        <input type="time" id="session-end-time-input" bind:value={endTime} />
      </div>
    </div>

    <label for="session-location-input" style="margin-top: 16px;">{isFestival ? t('Name:') : t('Location:')}</label>
    <input
      type="text"
      id="session-location-input"
      placeholder={isFestival ? t('e.g. Advanced Session @ Jim Bowie') : t('The usual: {location}', { location: locationName })}
      bind:value={location} />
    {#if isFestival}
      <small class="add-instance-hint">
        {t("Several sessions share a day at a festival, so the date alone won't tell them apart. This is what the log is called everywhere it's listed.")}
      </small>
    {/if}

    <label for="session-comments-input" style="margin-top: 16px;">{t('Comments:')}</label>
    <textarea
      id="session-comments-input"
      placeholder={t('Notes about this session')}
      rows="3"
      style="resize: vertical;"
      bind:value={comments}></textarea>
  </div>
  {#snippet footer()}
    <div style="text-align: right;">
      <button type="button" class="selection-btn primary" id="add-session-confirm-btn" onclick={addSessionInstance} disabled={adding}>{adding ? t('Adding…') : t('Add Session')}</button>
    </div>
  {/snippet}
</Sheet>

<style>
  /* Sits directly under the Name input, so it reads as that field's caption. */
  .add-instance-hint {
    display: block;
    margin-top: 6px;
    color: var(--text-muted, #9a9aa3);
    font-size: 12px;
    line-height: 1.4;
  }
</style>
