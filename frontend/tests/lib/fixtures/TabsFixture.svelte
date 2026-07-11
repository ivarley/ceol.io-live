<script>
  // Test harness: a reactive pane snippet (raw snippets don't re-render on
  // active-id changes, so the Tabs test needs a real component wrapper).
  import Tabs from '../../../src/lib/Tabs.svelte'

  let { tabs, initial = undefined, onValueChange = () => {}, navigate = false, onNavigate = undefined, styled = true, tabClass = '', listClass = '' } = $props()
  let value = $state(initial)
  export function getValue() {
    return value
  }
</script>

<Tabs {tabs} bind:value {onValueChange} {navigate} {styled} {...(onNavigate ? { onNavigate } : {})} {tabClass} {listClass}>
  {#snippet children(active)}
    <div data-testid="pane">pane:{active}</div>
  {/snippet}
</Tabs>
