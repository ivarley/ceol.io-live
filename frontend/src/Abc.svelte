<script>
  // Renders an incipit ABC string to SVG notation via abcjs (client-side, no
  // server round-trip). Used by the deep-search cards + the tune drawer.
  import abcjs from 'abcjs'

  let { abc = '' } = $props()
  let el

  $effect(() => {
    const cur = abc
    if (!el) return
    if (!cur) { el.replaceChildren(); return }
    try {
      abcjs.renderAbc(el, cur, {
        responsive: 'resize',
        scale: 1,
        paddingtop: 2,
        paddingbottom: 2,
        paddingleft: 0,
        paddingright: 0,
        add_classes: false,
      })
    } catch {
      el.replaceChildren()
    }
  })
</script>

<div class="abc-render" bind:this={el}></div>
