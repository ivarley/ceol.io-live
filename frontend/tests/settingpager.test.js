// The settings pager (the engine behind the tune drawer's staff and the setting
// chooser): the held settings at once, thesession.org's list only when asked, a step
// past the end that waits for it, and the notation drawn ahead in the size in view.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushSync } from 'svelte'

vi.mock('../src/client.js', () => ({
  tunePreview: vi.fn(),
  thesessionPreview: vi.fn(),
  settingImage: vi.fn(),
  renderRemoteAbc: vi.fn(),
}))

import { tunePreview, thesessionPreview, settingImage, renderRemoteAbc } from '../src/client.js'
import { createSettingPager } from '../src/tunesheet/settingpager.svelte.js'

const local = (id, incipit = null) => ({ setting_id: id, key: 'Dmajor', abc: `abc-${id}`, incipit_abc: `inc-${id}`, incipit_image: incipit })
const remote = (id) => ({ setting_id: id, key: 'Gmajor', abc: `abc-${id}`, incipit_abc: `inc-${id}` })
const tick = async () => {
  await Promise.resolve()
  await Promise.resolve()
  flushSync()
}

// A promise whose settling the test controls.
function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

beforeEach(() => {
  vi.clearAllMocks()
  settingImage.mockImplementation((_, id, kind) => Promise.resolve(`IMG-${id}-${kind}`))
  renderRemoteAbc.mockImplementation((_, key) => Promise.resolve(`R-${key}`))
})

describe('createSettingPager', () => {
  it('lists the held settings at once, opens on the current one, and leaves thesession.org alone', async () => {
    tunePreview.mockResolvedValue({ success: true, settings: [local(10, 'INC-10'), local(20), local(30)] })
    const p = createSettingPager({ tuneId: 1, currentSettingId: 20 })
    expect(p.loading).toBe(true)
    await p.load()
    expect(p.loading).toBe(false)
    expect(p.count).toBe(3)
    expect(p.idx).toBe(1)
    expect(p.isCurrent).toBe(true)
    expect(thesessionPreview).not.toHaveBeenCalled()
    // The preview's own incipit is in the registry without a render.
    expect(p.image(10, 'incipit')).toBe('INC-10')
  })

  it('draws ahead in the size in view: the one showing, then the next, the one before, the one after next', async () => {
    tunePreview.mockResolvedValue({ success: true, settings: [local(10), local(20), local(30), local(40), local(50)] })
    const p = createSettingPager({ tuneId: 1, currentSettingId: 20, kind: 'incipit' })
    await p.load()
    await tick()
    await tick()
    await tick()
    expect(settingImage.mock.calls.map(([, id, kind]) => `${id}:${kind}`)).toEqual(['20:incipit', '30:incipit', '10:incipit', '40:incipit'])
    expect(p.image(20)).toBe('IMG-20-incipit')
    expect(p.image(50)).toBeUndefined()
    // Looking at the whole tune now: the same four, full size.
    p.setSize('full')
    await tick()
    await tick()
    await tick()
    expect(settingImage.mock.calls.slice(4).map(([, id, kind]) => `${id}:${kind}`)).toEqual(['20:full', '30:full', '10:full', '40:full'])
  })

  it('a step asks thesession.org once, merges its settings in order, and renders the remote ones ephemerally', async () => {
    tunePreview.mockResolvedValue({ success: true, settings: [local(20)] })
    thesessionPreview.mockResolvedValue({ success: true, settings: [remote(10), remote(20), remote(30)] })
    const p = createSettingPager({ tuneId: 7, tuneType: 'reel', currentSettingId: 20 })
    await p.load()
    expect(p.count).toBe(1)
    p.step(1) // nothing past the end yet: the step waits for the list
    expect(thesessionPreview).toHaveBeenCalledTimes(1)
    expect(thesessionPreview).toHaveBeenCalledWith({}, 7, true)
    await tick()
    await tick()
    expect(p.settings.map((s) => s.setting_id)).toEqual([10, 20, 30])
    expect(p.settings.map((s) => !!s.remote)).toEqual([true, false, true])
    // The pending step landed on the setting after the one that was showing.
    expect(p.setting.setting_id).toBe(30)
    expect(p.touched).toBe(true) // the user did page; the list was just late
    await tick()
    expect(renderRemoteAbc).toHaveBeenCalledWith({}, 'ts:7:30:incipit', { abc: 'abc-30', key: 'Gmajor', tune_type: 'reel', kind: 'incipit' })
    p.step(1)
    p.step(1)
    expect(thesessionPreview).toHaveBeenCalledTimes(1) // once per load
  })

  it('a hand-paged position survives the backfill; the current setting is found when it only just arrived', async () => {
    tunePreview.mockResolvedValue({ success: true, settings: [local(10), local(30)] })
    const d = deferred()
    thesessionPreview.mockReturnValue(d.promise)
    const p = createSettingPager({ tuneId: 2, currentSettingId: 20 })
    await p.load()
    expect(p.idx).toBe(0) // 20 isn't held yet
    p.step(1) // by hand, to 30
    expect(p.setting.setting_id).toBe(30)
    expect(p.touched).toBe(true)
    d.resolve({ success: true, settings: [remote(10), remote(20), remote(30)] })
    await tick()
    expect(p.setting.setting_id).toBe(30) // stayed where the hand put it
    expect(p.isCurrent).toBe(false)

    // Untouched, the pager re-centres on the current setting once it arrives.
    tunePreview.mockResolvedValue({ success: true, settings: [local(10), local(30)] })
    thesessionPreview.mockResolvedValue({ success: true, settings: [remote(10), remote(20), remote(30)] })
    const q = createSettingPager({ tuneId: 3, currentSettingId: 20 })
    await q.load()
    q.ensureBackfill()
    await tick()
    expect(q.setting.setting_id).toBe(20)
    expect(q.isCurrent).toBe(true)
  })

  it('offline or thesession.org down, the held settings stand; a failed load says so', async () => {
    tunePreview.mockResolvedValue({ success: true, settings: [local(10), local(20)] })
    thesessionPreview.mockRejectedValue(new Error('down'))
    const p = createSettingPager({ tuneId: 4, currentSettingId: 10 })
    await p.load()
    p.step(1)
    p.step(1) // past the end, waits
    await tick()
    expect(p.backfilling).toBe(false)
    expect(p.count).toBe(2)
    expect(p.setting.setting_id).toBe(20)

    tunePreview.mockRejectedValue(new Error('no'))
    const q = createSettingPager({ tuneId: 5 })
    await q.load()
    expect(q.failed).toBe(true)
    expect(q.loading).toBe(false)
  })

  it('signed out, thesession.org is never asked: the held settings are the list', async () => {
    tunePreview.mockResolvedValue({ success: true, settings: [local(10), local(20)] })
    const p = createSettingPager({ tuneId: 8, currentSettingId: 10, canBackfill: false })
    await p.load()
    p.ensureBackfill()
    p.step(1)
    p.step(1)
    expect(thesessionPreview).not.toHaveBeenCalled()
    expect(p.backfilling).toBe(false)
    expect(p.setting.setting_id).toBe(20)
  })

  it('jumpTo, setCurrent and dispose', async () => {
    tunePreview.mockResolvedValue({ success: true, settings: [local(10), local(20), local(30)] })
    const p = createSettingPager({ tuneId: 6, currentSettingId: 10 })
    await p.load()
    expect(p.jumpTo(30)).toBe(true)
    expect(p.setting.setting_id).toBe(30)
    expect(p.jumpTo(99)).toBe(false)
    expect(p.isCurrent).toBe(false)
    p.setCurrent(30)
    expect(p.isCurrent).toBe(true)
    expect(p.current).toBe(30)
    // Disposed: a late backfill lands on nothing.
    const d = deferred()
    thesessionPreview.mockReturnValue(d.promise)
    p.ensureBackfill()
    p.dispose()
    d.resolve({ success: true, settings: [remote(10), remote(20), remote(30), remote(40)] })
    await tick()
    expect(p.count).toBe(3)
  })
})
