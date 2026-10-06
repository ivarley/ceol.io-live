// Spec 057: the live logger's activity line in English is people.js's, unchanged,
// and in Irish is built from the catalog.
import { describe, it, expect, afterEach } from 'vitest'
import { activityText } from '../src/people.js'
import { activityLine } from '../src/livelabels.js'

const actor = { person_id: 2, name: 'Sarah' }
const OPS = [
  { op_type: 'add_tune', record: { name: 'The Kesh' } },
  { op_type: 'corroborate', record: { tune_id: 12 } },
  { op_type: 'change_tune', record: {} },
  { op_type: 'remove_tune', record: { name: 'The Kesh' } },
  { op_type: 'move_tunes', moved_ids: [1, 2, 3] },
  { op_type: 'remove_tunes', records: [1] },
  { op_type: 'restore_tunes', records: [1, 2] },
  { op_type: 'set_break', removed: true },
  { op_type: 'set_break' },
  { op_type: 'attribute_set_starter', person: { display_name: 'Ian' } },
  { op_type: 'attribute_set_starter' },
  { op_type: 'set_confidence', record: { name: 'The Kesh' } },
  { op_type: 'attendance_add', person: { display_name: 'Ian' } },
  { op_type: 'attendance_create_person' },
  { op_type: 'attendance_remove', person: { display_name: 'Ian' } },
  { op_type: 'edit_notes' },
  { op_type: 'set_date', date: '2026-10-23', previous_date: '2026-10-22', session_date: 'Oct 23' },
  { op_type: 'set_date', start_time: '20:00:00', previous_start_time: '19:00:00', end_time: '22:00:00', previous_end_time: '22:00:00' },
  { op_type: 'set_date' },
  { op_type: 'set_name', instance_name: 'Late' },
  { op_type: 'set_name' },
]

afterEach(() => {
  delete window.__CEOL_LANG__
})

describe('activityLine', () => {
  it('is people.js activityText in English, for every op', () => {
    for (const op of OPS) {
      const d = { ...op, actor }
      expect(activityLine(d, 1, true)).toBe(activityText(d, 1, true))
    }
  })

  it('is Irish, verb first, in Irish', () => {
    window.__CEOL_LANG__ = 'ga'
    expect(activityLine({ op_type: 'add_tune', record: { name: 'The Kesh' }, actor }, 1, true)).toBe('Chuir Sarah The Kesh leis')
    expect(activityLine({ op_type: 'move_tunes', moved_ids: [1, 2, 3, 4, 5, 6, 7], actor }, 1, true)).toBe('Bhog Sarah 7 bhfonn')
  })

  it('still skips your own changes while you edit', () => {
    window.__CEOL_LANG__ = 'ga'
    expect(activityLine({ op_type: 'add_tune', record: {}, actor: { person_id: 1, name: 'Me' } }, 1, false)).toBe(null)
  })
})
