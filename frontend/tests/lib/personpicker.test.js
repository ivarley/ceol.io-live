// PersonPicker (spec 034): the one find-or-add-a-person flow.
//
// The behaviour worth pinning is the TIERING and the archived rule, because both encode
// decisions that are easy to "simplify" back into bugs:
//
//   * archived people are hidden from the default list but MUST surface when you type.
//     Drop that and a member back for one night is invisible in the picker, so whoever's
//     logging creates a duplicate person for her.
//   * there is no global person search — the picker's universe is the roster it is handed.
//   * starter mode commits and closes; attendance mode stays open for several check-ins.
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import PersonPicker from '../../src/lib/PersonPicker.svelte'

const roster = [
  { person_id: 1, display_name: 'Andy Byrne', attending: true, archived: false, relationship: 'member' },
  { person_id: 2, display_name: 'Sarah Murphy', attending: false, archived: false, relationship: 'member' },
  { person_id: 3, display_name: 'Saratha Quinn', attending: false, archived: false, relationship: 'visitor' },
  { person_id: 4, display_name: 'Maura Gone', attending: false, archived: true, relationship: 'member' },
]

const mount = (props = {}) =>
  render(PersonPicker, {
    props: { open: true, people: roster, scope: 'instance', mode: 'attendance', ...props },
  })

const typeQuery = async (text) => {
  await fireEvent.input(screen.getByPlaceholderText(/Filter/i), { target: { value: text } })
}

describe('PersonPicker tiers', () => {
  it('splits the instance roster into "checked in" and "not checked in"', () => {
    mount()
    expect(screen.getByText('Checked in')).toBeInTheDocument()
    expect(screen.getByText('Not checked in')).toBeInTheDocument()
    expect(screen.getByText('Andy Byrne')).toBeInTheDocument()
    expect(screen.getByText('Sarah Murphy')).toBeInTheDocument()
  })

  it('hides archived people from the DEFAULT list', () => {
    mount()
    expect(screen.queryByText('Maura Gone')).not.toBeInTheDocument()
  })

  it('but surfaces them once you type — archived means hidden, never unfindable', async () => {
    mount()
    await typeQuery('Maura')
    expect(screen.getByText('Maura Gone')).toBeInTheDocument()
    expect(screen.getByText('Archived')).toBeInTheDocument()
  })

  it('shows an archived person under "Checked in" once they are checked in', () => {
    // The bug this guards: you find archived Maura by typing, tap her, she IS checked in --
    // and then vanishes, because the default list hides archived people. The write worked but
    // the UI swallowed her, so it read as a no-op.
    //
    // `archived` means "not currently around". Being checked in is direct evidence to the
    // contrary, so attending MUST win over archived.
    const checkedInMaura = roster.map((p) =>
      p.person_id === 4 ? { ...p, attending: true } : p
    )
    mount({ people: checkedInMaura }) // note: no search query — this is the DEFAULT list

    expect(screen.getByText('Maura Gone')).toBeInTheDocument()
    expect(screen.getByText('Checked in')).toBeInTheDocument()
    // ...and she is NOT filed under the Archived heading while she's standing in the room.
    expect(screen.queryByText('Archived')).not.toBeInTheDocument()
  })

  it('filters locally across both tiers (no fetch — there is no global search)', async () => {
    mount()
    await typeQuery('Sar')
    expect(screen.getByText('Sarah Murphy')).toBeInTheDocument()
    expect(screen.getByText('Saratha Quinn')).toBeInTheDocument()
    expect(screen.queryByText('Andy Byrne')).not.toBeInTheDocument()
  })

  it('session scope is one flat list with no check-in tiers', () => {
    mount({ scope: 'session' })
    expect(screen.queryByText('Checked in')).not.toBeInTheDocument()
    expect(screen.getByText('Sarah Murphy')).toBeInTheDocument()
  })
})

describe('PersonPicker selection', () => {
  it('starter mode commits and closes', async () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    mount({ mode: 'starter', onSelect, onClose })

    await fireEvent.click(screen.getByText('Sarah Murphy'))

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ person_id: 2 }))
    expect(onClose).toHaveBeenCalled()
  })

  it('closes SYNCHRONOUSLY after onSelect — hosts must not read their own state afterwards', async () => {
    // Regression guard for a race that silently half-completed the flow: the host awaited a
    // check-in inside onSelect, and by the time it resolved the picker had already closed and
    // nulled the host's "which set am I attributing" state -- so the person got checked in but
    // the set was never credited. The picker is allowed to close first; the CONTRACT is that
    // onSelect is fire-and-forget, so hosts must capture what they need BEFORE awaiting.
    // See pickPerson()/createPerson() in the logger, which snapshot pickerSet up front.
    const order = []
    let resolveSelect
    const onSelect = vi.fn(() => {
      order.push('select')
      return new Promise((r) => (resolveSelect = r)) // still pending when close() runs
    })
    const onClose = vi.fn(() => order.push('close'))
    mount({ mode: 'starter', onSelect, onClose })

    await fireEvent.click(screen.getByText('Sarah Murphy'))

    expect(order).toEqual(['select', 'close'])
    resolveSelect?.()
  })

  it('attendance mode stays open — you are checking several people in', async () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    mount({ mode: 'attendance', onSelect, onClose })

    await fireEvent.click(screen.getByText('Sarah Murphy'))

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ person_id: 2 }))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('offers "Clear" only in starter mode, and only when a starter is set', () => {
    mount({ mode: 'starter', currentStarterName: 'Andy B' })
    expect(screen.getByText('— Clear —')).toBeInTheDocument()
  })

  it('has no Clear row when no starter is set', () => {
    mount({ mode: 'starter', currentStarterName: null })
    expect(screen.queryByText('— Clear —')).not.toBeInTheDocument()
  })
})

describe('PersonPicker create', () => {
  it('offers to add whoever you typed when nobody matches', async () => {
    mount()
    await typeQuery('James Quinn')
    expect(screen.getByText(/No one here by that name/i)).toBeInTheDocument()
    expect(screen.getByText('James Quinn')).toBeInTheDocument() // inside the ＋ Add button
  })

  it('pre-splits the typed text into first and last name', async () => {
    mount()
    await typeQuery('James Quinn')
    await fireEvent.click(screen.getByRole('button', { name: /Add James Quinn/i }))

    expect(screen.getByPlaceholderText('First name')).toHaveValue('James')
    expect(screen.getByPlaceholderText('Last name')).toHaveValue('Quinn')
  })

  it('emits the new person, email included (the only cross-session identity key)', async () => {
    const onCreate = vi.fn()
    mount({ onCreate })
    await typeQuery('James Quinn')
    await fireEvent.click(screen.getByRole('button', { name: /Add James Quinn/i }))
    await fireEvent.input(screen.getByPlaceholderText('name@example.com'), {
      target: { value: 'james@example.com' },
    })
    await fireEvent.click(screen.getByRole('button', { name: 'Add person' }))

    expect(onCreate).toHaveBeenCalledWith({
      first_name: 'James',
      last_name: 'Quinn',
      email: 'james@example.com',
      instruments: [],
    })
  })
})
