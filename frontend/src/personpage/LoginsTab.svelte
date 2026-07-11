<script>
  // Logins tab (only rendered when the person has a user account): lazy-loaded
  // login history table.
  let { personId, load } = $props()

  let loading = $state(true)
  let logins = $state(null)
  let debug = $state(null)
  let error = $state(false)
  let started = false

  $effect(() => {
    if (load && !started) {
      started = true
      fetch(`/api/person/${personId}/logins`)
        .then((response) => response.json())
        .then((data) => {
          loading = false
          if (data.success && data.logins.length > 0) {
            logins = data.logins
          } else {
            logins = []
            debug = data.debug || null
          }
        })
        .catch((err) => {
          loading = false
          error = true
          console.error('Error:', err)
        })
    }
  })

  const eventClass = (eventType) =>
    eventType === 'LOGIN_SUCCESS' ? 'text-success' : eventType === 'LOGIN_FAILURE' ? 'text-danger' : 'text-muted'
</script>

<div class="mt-3">
  <div id="logins-loading" class="text-center" style:display={loading ? '' : 'none'}>
    <span class="loading-spinner" style="display: inline-block; width: 16px; height: 16px; border: 2px solid var(--border-color); border-top: 2px solid var(--primary); border-radius: 50%; animation: spin 1s linear infinite;"></span>
    <span style="margin-left: 8px;">Loading login history...</span>
  </div>
  <div id="logins-content">
    {#if error}
      <div class="alert alert-danger" role="alert">Error loading login history.</div>
    {:else if logins && logins.length > 0}
      <div class="table-responsive">
        <table class="table table-striped">
          <thead>
            <tr>
              <th>Time</th>
              <th>Event</th>
              <th>IP Address</th>
              <th>User Agent</th>
            </tr>
          </thead>
          <tbody>
            {#each logins as record, i (i)}
              <tr>
                <td>{record.login_time}</td>
                <td><span class={eventClass(record.event_type)}>{record.event_type}</span></td>
                <td>{record.ip_address}</td>
                <td style="font-size: 0.8em; max-width: 200px; overflow: hidden; text-overflow: ellipsis;">{record.user_agent}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else if logins}
      <div class="alert alert-info" role="alert">
        No login history found.{#if debug}<br /><small>Debug: {debug}</small>{/if}
      </div>
    {/if}
  </div>
</div>
