<script>
  // i18n-converted
  // The certainty meter as the iPhone shows it (spec 061), for the Listen page and a
  // night's logger alike: the clock and the link, then one main state: starting up,
  // no tune playing, figuring out the tune (the candidates, any of which can be
  // tapped, and "None of these"), or sure of it. Under the sure tune are three taps:
  // wrong tune (thumbs down), right tune (thumbs up: a person's check) and next tune
  // (it has ended, listen afresh). Its name opens the tune.
  // What a tap leads to is the page's: it passes the handlers, and `sure` (what goes
  // under the sure tune) and `noTune` (under "No tune playing").
  import { t, formatNumber, tuneTypeName } from '../lib/i18n/index.js'
  import { bar, candidates } from './meter.js'
  import { clock } from './listening.svelte.js'

  let {
    listening,
    night = false, // a night's session is preferred: say which candidates are new to it
    onTapThis = (c) => listening.send(listening.meter.tapThis(c.tune_id)),
    onTapNone = () => listening.send(listening.meter.tapNone()),
    onWrong = () => listening.send(listening.meter.wrongTune()),
    onRight = () => listening.send(listening.meter.rightTune()),
    onChanged = () => listening.send(listening.meter.tuneChanged()),
    onOpen = null, // (tuneId) the sure tune's name was tapped
    sure = null,
    noTune = null,
  } = $props()

  // The Meter is a plain object; the Listening's `version` is bumped after every
  // change to it, so this follows it.
  const view = $derived.by(() => {
    listening.version
    const meter = listening.meter
    const s = meter.state
    const sureId = meter.confirmed
    const mine = s && sureId != null ? (s.top || []).find((c) => c.tune_id === sureId) : null
    return {
      showing: meter.showing,
      state: s,
      rows: s ? candidates(s) : [],
      wasName: meter.wasName,
      changed: meter.mayHaveChanged,
      sureId,
      sureName: meter.confirmedName || (sureId != null ? t('Tune {id}', { id: sureId }) : ''),
      sureType: meter.confirmedType,
      sureNew: !!(mine && mine.outside && night),
      approved: sureId != null && meter.approved === sureId,
    }
  })

  const pct = (p) => formatNumber(p || 0, { style: 'percent', maximumFractionDigits: 0 })
  const tuneName = (c) => c.name || t('Tune {id}', { id: c.tune_id })
</script>

<div class="lp-status">
  <span class="lp-dot" class:is-off={listening.status !== 'live'} aria-hidden="true"></span>
  <span class="lp-num">{clock(listening.clockS)}</span>
  {#if view.state && view.state.tuneness != null}
    <span class="lp-tuneness">{t('sounds like a tune {n}%', { n: Math.round(view.state.tuneness * 100) })}</span>
  {/if}
</div>
<p class="lp-linktext" class:lp-warn={listening.status === 'reconnecting' || listening.status === 'refused'} id="lp-link">{listening.linkText}</p>
{#if listening.error}<p class="lp-error" role="alert">{listening.error}</p>{/if}

<div class="lp-meter" id="lp-meter" data-showing={view.showing}>
  {#if view.showing === 'waiting'}
    <p class="lp-big"><span class="lp-spinner" aria-hidden="true"></span>{t('Starting up…')}</p>
  {:else if view.showing === 'noTune'}
    <p class="lp-big">{t('No tune playing')}</p>
    <p class="lp-sub lp-num">{pct(view.state.none)}</p>
    {@render noTune?.()}
  {:else if view.showing === 'figuring'}
    <p class="lp-big"><span class="lp-spinner" aria-hidden="true"></span>{t('Figuring out the tune…')}</p>
    {#if view.changed && view.wasName}
      <p class="lp-sub">{t('The tune may have changed (was {name}).', { name: view.wasName })}</p>
    {/if}
    <div class="lp-rows" id="lp-candidates">
      {#each view.rows as c (c.tune_id)}
        <button type="button" class="lp-row" class:is-weak={c.weak} class:is-shown={c.tune_id === view.state.shown && !view.changed} onclick={() => onTapThis(c)}>
          <span class="lp-row-text">
            <span class="lp-row-name">{tuneName(c)}</span>
            <span class="lp-row-meta">
              {[tuneTypeName(c.type), c.outside && night ? t('new to this session') : null, pct(c.p)].filter(Boolean).join(' · ')}
            </span>
          </span>
          <span class="lp-bar" role="img" aria-label={t('{n} percent', { n: Math.round(c.p * 100) })}>
            {#each bar(c.p) as cell, i (i)}<span class="lp-cell is-{cell}"></span>{/each}
          </span>
        </button>
      {/each}
    </div>
    <button type="button" class="lp-none" id="lp-none" disabled={!view.rows.length} onclick={onTapNone}>{t('None of these')}</button>
  {:else}
    <div class="lp-sure" id="lp-sure">
      <svg class="lp-check" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="M7.5 12.5l3 3 6-6.5" /></svg>
      <span class="lp-sure-text">
        {#if onOpen}
          <button type="button" class="lp-sure-name lp-sure-open" id="lp-sure-name" onclick={() => onOpen(view.sureId)}>{view.sureName}</button>
        {:else}
          <span class="lp-sure-name" id="lp-sure-name">{view.sureName}</span>
        {/if}
        {#if view.sureType || view.sureNew}
          <span class="lp-row-meta">{[tuneTypeName(view.sureType), view.sureNew ? t('new to this session') : null].filter(Boolean).join(' · ')}</span>
        {/if}
      </span>
    </div>
    <div class="lp-sure-taps">
      <button type="button" id="lp-wrong" title={t('Wrong tune')} aria-label={t('Wrong tune')} onclick={onWrong}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17 14V3H8.3a2 2 0 0 0-1.9 1.4l-2.3 7A2 2 0 0 0 6 14h4.5l-.8 3.6a2 2 0 0 0 2 2.4L17 14zM17 3h3v11h-3" /></svg>
      </button>
      <button type="button" id="lp-right" class:is-on={view.approved} title={t('Right tune')} aria-label={t('Right tune')} aria-pressed={view.approved} onclick={onRight}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10v11h8.7a2 2 0 0 0 1.9-1.4l2.3-7A2 2 0 0 0 18 10h-4.5l.8-3.6a2 2 0 0 0-2-2.4L7 10zM7 21H4V10h3" /></svg>
      </button>
      <button type="button" id="lp-changed" title={t('Next tune')} aria-label={t('Next tune')} onclick={onChanged}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5l10 7-10 7V5zM18 5v14" /></svg>
      </button>
    </div>
    {@render sure?.({ id: view.sureId, name: view.sureName, type: view.sureType })}
  {/if}
</div>

{#if view.state && (view.state.history || []).length}
  <h3 class="kit-group-head">{t('Shown so far')}</h3>
  <div class="lp-history">
    {#each [...view.state.history].reverse() as h (h.from_ms + ':' + h.tune_id)}
      <div class="lp-history-line"><span class="lp-num">{clock(h.from_ms / 1000)}</span> · {h.name || t('Tune {id}', { id: h.tune_id })}</div>
    {/each}
  </div>
{/if}
