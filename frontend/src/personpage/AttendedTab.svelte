<script>
  // Attended tab: lazy-loaded attendance history table (fetched once, on the
  // first activation of the tab — the `load` prop flips true and stays true).
  let { personId, load } = $props()

  let loading = $state(true)
  let records = $state(null) // null = not yet loaded / failed
  let error = $state(false)
  let started = false

  $effect(() => {
    if (load && !started) {
      started = true
      fetch(`/api/person/${personId}/attended`)
        .then((response) => response.json())
        .then((data) => {
          loading = false
          if (data.success && data.attendance.length > 0) {
            records = data.attendance
          } else {
            records = []
          }
        })
        .catch((err) => {
          loading = false
          error = true
          console.error('Error:', err)
        })
    }
  })

  const statusFor = (attendance) => {
    if (attendance === 'yes') return { cls: 'text-success', label: '✓ Yes' }
    if (attendance === 'maybe') return { cls: 'text-warning', label: '? Maybe' }
    if (attendance === 'no') return { cls: 'text-danger', label: '✗ No' }
    return { cls: 'text-muted', label: '- Unknown' }
  }
</script>

<div class="mt-3">
  <div id="attended-loading" class="text-center" style:display={loading ? '' : 'none'}>
    <span class="loading-spinner" style="display: inline-block; width: 16px; height: 16px; border: 2px solid var(--border-color); border-top: 2px solid var(--primary); border-radius: 50%; animation: spin 1s linear infinite;"></span>
    <span style="margin-left: 8px;">Loading attendance history...</span>
  </div>
  <div id="attended-content">
    {#if error}
      <div class="alert alert-danger" role="alert">Error loading attendance data.</div>
    {:else if records && records.length > 0}
      <div class="table-responsive">
        <table class="table table-striped">
          <thead>
            <tr>
              <th>Session Name</th>
              <th>Instance Date</th>
              <th>Attended</th>
            </tr>
          </thead>
          <tbody>
            {#each records as record, i (i)}
              <tr>
                <td>{record.session_name}</td>
                <td>{record.instance_date}</td>
                <td><span class={statusFor(record.attendance).cls}>{statusFor(record.attendance).label}</span></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else if records}
      <div class="alert alert-info" role="alert">No attendance records found.</div>
    {/if}
  </div>
</div>
