// Home's rules, tested against the payload rather than the page (spec 052 §B8
// Stage 4, and §B5's "fixture tests for the pure client logic").
//
// These are the decisions a SwiftUI Home screen has to make too — which nights are
// today, whether one is live, what the tally line says, what order the unfinished
// work comes back in. Testing them here, against the same GET /api/home shape the
// app will hold, is what makes it possible to check the two agree later instead of
// discovering they don't on a device.
import { describe, it, expect } from 'vitest'
import {
  todaysSessions,
  sessionStatus,
  statusLabel,
  todaySubtitle,
  tallyLabel,
  sessionInstanceHref,
  weekSubtitle,
  continueItems,
  editedLabel,
  adjustedCounts,
} from '../src/homepage/logic.js'

const night = (over = {}) => ({
  name: 'Mueller Session',
  path: 'austin/mueller',
  session_id: 1,
  session_instance_id: 120,
  date: '2026-09-22',
  start_time: '19:00',
  end_time: '22:00',
  location_name: "BD Riley's Irish Pub",
  log_complete_date: null,
  is_active: false,
  tunes_logged: 0,
  people_here: 0,
  ...over,
})

describe('todaysSessions', () => {
  it('is a subset of the week, not a second list', () => {
    const week = [night({ date: '2026-09-21' }), night({ date: '2026-09-22' })]
    const today = todaysSessions(week, '2026-09-22')
    expect(today).toHaveLength(1)
    // Identity, not a copy: the card and the week row are the same object, so they
    // cannot end up describing the night differently.
    expect(today[0]).toBe(week[1])
  })

  it('returns nothing when the payload has no today (an anonymous or broken load)', () => {
    expect(todaysSessions([night()], null)).toEqual([])
    expect(todaysSessions(null, '2026-09-22')).toEqual([])
  })

  it('keeps every session on the day, which is the festival case', () => {
    const week = [
      night({ session_instance_id: 1 }),
      night({ session_instance_id: 2, name: 'Downtown Session' }),
      night({ session_instance_id: 3, name: 'After hours' }),
    ]
    expect(todaysSessions(week, '2026-09-22')).toHaveLength(3)
  })
})

describe('sessionStatus / statusLabel', () => {
  it('trusts the server flag for liveness', () => {
    // Never a clock comparison here: the instance's timezone is the session's, not
    // the phone's, and `is_active` already accounts for the buffer either side.
    expect(sessionStatus(night({ is_active: true }))).toBe('live')
    expect(statusLabel(night({ is_active: true }))).toBe('Live now')
  })

  it('reads a completed log as finished even if the flag lingers false', () => {
    expect(sessionStatus(night({ log_complete_date: '2026-09-22T23:10:00Z' }))).toBe('finished')
    expect(statusLabel(night({ log_complete_date: '2026-09-22T23:10:00Z' }))).toBe('Finished')
  })

  it('live wins over a completed log, because someone reopened it', () => {
    const s = night({ is_active: true, log_complete_date: '2026-09-22T23:10:00Z' })
    expect(sessionStatus(s)).toBe('live')
  })

  it('announces the start time, and falls back when there is none', () => {
    expect(statusLabel(night())).toBe('Starts 7:00pm')
    expect(statusLabel(night({ start_time: null }))).toBe('Today')
  })
})

describe('todaySubtitle', () => {
  it('counts the room only while the session is live', () => {
    expect(todaySubtitle(night({ is_active: true, people_here: 4 }))).toBe(
      "7:00pm-10:00pm · BD Riley's Irish Pub · 4 people here",
    )
    // Everyone has gone home; "0 people here" would read as a fault, not a fact.
    expect(todaySubtitle(night({ people_here: 0, log_complete_date: 'x' }))).toBe(
      "7:00pm-10:00pm · BD Riley's Irish Pub",
    )
  })

  it('says person, not people, for one', () => {
    expect(todaySubtitle(night({ is_active: true, people_here: 1 }))).toContain('1 person here')
  })

  it('drops the parts it does not have instead of printing empty separators', () => {
    expect(todaySubtitle(night({ start_time: null, end_time: null, location_name: null }))).toBe('')
  })

  it('renders an open-ended night rather than dropping the time', () => {
    // The after-hours session that runs until it stops (the festival case in the seed).
    expect(todaySubtitle(night({ end_time: null }))).toContain('7:00pm - ?')
  })
})

describe('tallyLabel', () => {
  it('says "so far" only while the number can still move', () => {
    expect(tallyLabel(night({ is_active: true, tunes_logged: 18 }))).toBe('18 tunes logged so far')
    expect(tallyLabel(night({ tunes_logged: 18, log_complete_date: 'x' }))).toBe('18 tunes logged')
  })

  it('handles none and one', () => {
    expect(tallyLabel(night({ tunes_logged: 0 }))).toBe('No tunes logged yet')
    expect(tallyLabel(night({ tunes_logged: 1 }))).toBe('1 tune logged')
  })
})

describe('sessionInstanceHref', () => {
  it('points at that night, not at the session', () => {
    expect(sessionInstanceHref(night())).toBe('/sessions/austin/mueller/2026-09-22')
  })

  it('is null rather than a broken link when the payload is short', () => {
    expect(sessionInstanceHref(night({ path: null }))).toBeNull()
    expect(sessionInstanceHref(null)).toBeNull()
  })
})

describe('weekSubtitle', () => {
  it('marks a past night that was never logged', () => {
    const s = night({ date: '2026-09-20' })
    expect(weekSubtitle(s, '2026-09-22')).toContain('not logged')
  })

  it('does not nag about a night that has not happened yet', () => {
    const s = night({ date: '2026-09-24' })
    expect(weekSubtitle(s, '2026-09-22')).not.toContain('not logged')
  })

  it('says logged when it is', () => {
    const s = night({ date: '2026-09-20', log_complete_date: '2026-09-20T23:00:00Z' })
    expect(weekSubtitle(s, '2026-09-22')).toContain('logged')
    expect(weekSubtitle(s, '2026-09-22')).not.toContain('not logged')
  })
})

describe('continueItems', () => {
  const payload = {
    current_year: 2026,
    in_progress_logs: [
      {
        name: 'Mueller Session',
        path: 'austin/mueller',
        session_instance_id: 120,
        date: '2026-09-16',
        last_edit: '2026-09-22T10:00:00Z',
      },
    ],
    in_progress_recordings: [
      {
        recording_id: 7,
        label: 'Mueller Night',
        name: 'Mueller Session',
        path: 'austin/mueller',
        session_instance_id: 90,
        date: '2026-09-09',
        last_edit: '2026-09-22T12:00:00Z',
        placed: 4,
        tune_count: 11,
      },
    ],
  }

  it('merges the two kinds into one list, newest edit first', () => {
    // They were two cards. Interleaving them by edit time is the point of merging:
    // the thing you touched last is the thing you meant to come back to.
    const items = continueItems(payload)
    expect(items.map((i) => i.kind)).toEqual(['recording', 'log'])
  })

  it('keys each item so the two id spaces cannot collide', () => {
    // A recording_id and a session_instance_id are both small integers; keyed on the
    // bare number, a list holding one of each could collide and fail to render.
    const items = continueItems(payload)
    expect(new Set(items.map((i) => i.key)).size).toBe(items.length)
  })

  it('links a log to its night and a recording to the segmenter', () => {
    const items = continueItems(payload)
    const log = items.find((i) => i.kind === 'log')
    const rec = items.find((i) => i.kind === 'recording')
    expect(log.href).toBe('/sessions/austin/mueller/2026-09-16')
    expect(rec.href).toBe('/admin/recordings/7/segment')
    expect(rec.detail).toBe('4 of 11 tunes placed')
  })

  it('falls back to the session name when a recording has no label', () => {
    const items = continueItems({
      ...payload,
      in_progress_logs: [],
      in_progress_recordings: [{ ...payload.in_progress_recordings[0], label: null }],
    })
    expect(items[0].title).toBe('Place tunes on Mueller Session')
  })

  it('is empty, not undefined, when there is nothing to come back to', () => {
    expect(continueItems({})).toEqual([])
    expect(continueItems(null)).toEqual([])
  })
})

describe('editedLabel', () => {
  const now = new Date('2026-09-22T12:00:00Z')

  it('counts in minutes and hours while that is the useful unit', () => {
    expect(editedLabel('2026-09-22T11:58:00Z', 2026, now)).toBe('2 minutes ago')
    expect(editedLabel('2026-09-22T09:00:00Z', 2026, now)).toBe('3 hours ago')
  })

  it('switches to a date once "hours ago" stops meaning anything', () => {
    expect(editedLabel('2026-09-16T12:00:00Z', 2026, now)).toMatch(/Sep 16/)
  })

  it('adds the year only when it is not this one', () => {
    expect(editedLabel('2025-09-16T12:00:00Z', 2026, now)).toMatch(/2025/)
  })

  it('says nothing rather than "Invalid Date"', () => {
    expect(editedLabel(null, 2026, now)).toBe('')
    expect(editedLabel('not a date', 2026, now)).toBe('')
  })
})

describe('adjustedCounts', () => {
  const base = { learning: 5, wantToLearn: 3 }

  it('leaves the server numbers alone when nothing is queued', () => {
    expect(adjustedCounts(base, [], {})).toEqual({ learning: 5, wantToLearn: 3 })
  })

  it('counts an add of a tune not already on the list', () => {
    const ops = [{ ts: 1, type: 'add', tune_id: 99, learn_status: 'learning' }]
    expect(adjustedCounts(base, ops, {})).toEqual({ learning: 6, wantToLearn: 3 })
  })

  it('ignores an add of a tune already on the list', () => {
    const ops = [{ ts: 1, type: 'add', tune_id: 99, learn_status: 'learning' }]
    expect(adjustedCounts(base, ops, { 99: 'learning' })).toEqual(base)
  })

  it('moves a tune between buckets on a status change', () => {
    const ops = [{ ts: 1, type: 'set_status', tune_id: 99, learn_status: 'learning' }]
    expect(adjustedCounts(base, ops, { 99: 'want to learn' })).toEqual({
      learning: 6,
      wantToLearn: 2,
    })
  })

  it('replays in timestamp order, not arrival order', () => {
    // The queue can be handed over out of order; the last write has to win.
    const ops = [
      { ts: 2, type: 'set_status', tune_id: 99, learn_status: 'learned' },
      { ts: 1, type: 'add', tune_id: 99, learn_status: 'learning' },
    ]
    expect(adjustedCounts(base, ops, {})).toEqual({ learning: 5, wantToLearn: 3 })
  })

  it('never shows a negative count', () => {
    const ops = [{ ts: 1, type: 'remove', tune_id: 99 }]
    expect(adjustedCounts({ learning: 0, wantToLearn: 0 }, ops, { 99: 'learning' })).toEqual({
      learning: 0,
      wantToLearn: 0,
    })
  })

  it('does not mutate the caller\'s status map', () => {
    const status = { 99: 'want to learn' }
    adjustedCounts(base, [{ ts: 1, type: 'set_status', tune_id: 99, learn_status: 'learning' }], status)
    expect(status).toEqual({ 99: 'want to learn' })
  })
})
