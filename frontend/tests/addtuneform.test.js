// The preview-footer add form (My Tunes pane): defaults, the instrument roll-up's
// override semantics (auto follows base / manual starts untracked / snap-back),
// the on-list hand-off branch, and the error path keeping the form alive.
import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/svelte'
import AddTuneForm from '../src/mytunes/AddTuneForm.svelte'
import { ServerError } from '../src/lib/index.js'

const INSTRUMENTS = [
  { instrument: 'Fiddle', is_auto: true },
  { instrument: 'Flute', is_auto: false },
]

describe('AddTuneForm', () => {
  it('submits the defaults: want to learn, no notes, no overrides', async () => {
    const onSubmit = vi.fn().mockResolvedValue()
    const { container } = render(AddTuneForm, { instruments: INSTRUMENTS, onSubmit })
    await fireEvent.click(container.querySelector('.mt-submit'))
    expect(onSubmit).toHaveBeenCalledWith({ status: 'want to learn', notes: '', overrides: [] })
  })

  it('submits the alias and key only once each is opened and given', async () => {
    // Opened and left blank: no alias.
    const blank = vi.fn().mockResolvedValue()
    const first = render(AddTuneForm, { instruments: [], onSubmit: blank })
    await fireEvent.click(first.getByText('I call this something else'))
    await fireEvent.click(first.container.querySelector('.mt-submit'))
    expect(blank).toHaveBeenCalledWith({ status: 'want to learn', notes: '', overrides: [] })
    first.unmount()
    // Given: both ride along, the alias trimmed.
    const onSubmit = vi.fn().mockResolvedValue()
    const { container, getByText } = render(AddTuneForm, { instruments: [], onSubmit })
    await fireEvent.click(getByText('I call this something else'))
    await fireEvent.input(container.querySelector('.mt-alias'), { target: { value: '  The Jig I Know ' } })
    await fireEvent.click(getByText('I play this in a different key'))
    await fireEvent.change(container.querySelector('.mt-key'), { target: { value: 'Gmajor' } })
    await fireEvent.click(container.querySelector('.mt-submit'))
    expect(onSubmit).toHaveBeenCalledWith({
      status: 'want to learn', notes: '', overrides: [], alias: 'The Jig I Know', key: 'Gmajor',
    })
  })

  it('submits the chosen status and typed note', async () => {
    const onSubmit = vi.fn().mockResolvedValue()
    const { container } = render(AddTuneForm, { instruments: [], onSubmit })
    await fireEvent.click(container.querySelector('[data-status="learned"]'))
    await fireEvent.click(container.querySelector('.mt-note-toggle'))
    await fireEvent.input(container.querySelector('.mt-notes'), { target: { value: '  b part is tricky ' } })
    await fireEvent.click(container.querySelector('.mt-submit'))
    expect(onSubmit).toHaveBeenCalledWith({ status: 'learned', notes: 'b part is tricky', overrides: [] })
  })

  it('roll-up override rules: manual pick is an override, auto snap-back to base is not', async () => {
    const onSubmit = vi.fn().mockResolvedValue()
    const { container } = render(AddTuneForm, { instruments: INSTRUMENTS, onSubmit })
    await fireEvent.click(container.querySelector('.mt-expand'))
    const blocks = container.querySelectorAll('.tsc-inst-block')
    // Fiddle (auto): pick 'learning' = override; Flute (manual): pick 'learned' = override.
    await fireEvent.click(blocks[0].querySelector('[data-status="learning"]'))
    await fireEvent.click(blocks[1].querySelector('[data-status="learned"]'))
    // Fiddle back to the base status = follow base again (no override stored).
    await fireEvent.click(blocks[0].querySelector('[data-status="want to learn"]'))
    await fireEvent.click(container.querySelector('.mt-submit'))
    expect(onSubmit).toHaveBeenCalledWith({
      status: 'want to learn',
      notes: '',
      overrides: [{ instrument: 'Flute', status: 'learned' }],
    })
  })

  it('single-instrument people get no roll-up expander', () => {
    const { container } = render(AddTuneForm, {
      instruments: [{ instrument: 'Fiddle', is_auto: true }],
      onSubmit: vi.fn(),
    })
    expect(container.querySelector('.mt-expand')).toBeNull()
  })

  it('on-list tune renders the on-list panel instead of the form', async () => {
    const onShowExisting = vi.fn()
    const { container } = render(AddTuneForm, {
      onList: true,
      existing: { person_tune_id: 9, on_list: true, learn_status: 'learned', setting_id: 5, heard_count: 0 },
      onSubmit: vi.fn(),
      onShowExisting,
    })
    expect(container.querySelector('.mt-submit')).toBeNull()
    const head = container.querySelector('.mt-onlist-head')
    expect(head.textContent).toContain('Already on your list')
    // The status is part of the answer to "what do I already have on this tune?"
    expect(container.querySelector('.mt-onlist-status').textContent).toBe('Learned')
    await fireEvent.click(head)
    expect(onShowExisting).toHaveBeenCalled()
  })

  it('on-list: no setting was pointed at, so nothing to update', () => {
    const { container } = render(AddTuneForm, {
      onList: true,
      existing: { person_tune_id: 9, on_list: true, learn_status: 'learning', setting_id: 5, heard_count: 2 },
      onSubmit: vi.fn(),
    })
    expect(container.querySelector('.mt-onlist-ask')).toBeNull()
    const labels = [...container.querySelectorAll('.mt-onlist-actions .pv-action')].map((b) => b.textContent.trim())
    expect(labels).toEqual(['I Heard It Again (2)', 'Cancel'])
  })

  it('a failed submit shows the error and keeps the form usable', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new ServerError('You are offline.'))
    const { container } = render(AddTuneForm, { instruments: [], onSubmit })
    await fireEvent.click(container.querySelector('.mt-submit'))
    await waitFor(() => {
      expect(container.querySelector('.mt-error').textContent).toBe('You are offline.')
    })
    const submit = container.querySelector('.mt-submit')
    expect(submit.disabled).toBe(false)
  })

  it('a network failure shows a human sentence, never the raw error text', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const onSubmit = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    const { container } = render(AddTuneForm, { instruments: [], onSubmit })
    await fireEvent.click(container.querySelector('.mt-submit'))
    await waitFor(() => {
      expect(container.querySelector('.mt-error').textContent).toBe(
        "Couldn't add the tune. Check your connection and try again."
      )
    })
  })
})
