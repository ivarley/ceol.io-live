<script>
  // The language Ceol is in, for the person whose /me this is (spec 057). Saves at once
  // through PUT /api/me/profile, then reloads: the page's own server-rendered text is in
  // the old language until it is fetched again.
  import { Seg, t, LANGUAGE_NAMES } from '../lib/index.js'
  import { toast } from '../lib/index.js'

  let { language = 'en', reload = () => window.location.reload() } = $props()
  let saving = $state(false)

  async function choose(code) {
    if (code === language || saving) return
    saving = true
    try {
      const resp = await fetch('/api/me/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: code }),
      })
      if (!resp.ok) throw new Error(String(resp.status))
      reload()
    } catch {
      saving = false
      toast(t("Couldn't change the language. Try again."), 'error')
    }
  }
</script>

<h3 class="kit-group-head">{t('Language')}</h3>
<div class="kit-group">
  <div class="kit-field">
    <Seg
      options={[{ id: 'en', label: LANGUAGE_NAMES.en }, { id: 'ga', label: LANGUAGE_NAMES.ga }]}
      value={language}
      onSelect={choose}
      idAttr="data-language" />
  </div>
</div>
<p class="kit-field-help">{t("The language Ceol's screens and emails are in.")}</p>
