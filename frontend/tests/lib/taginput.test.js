// TagInput (spec 042): the IrishTune-style chip editor — space/enter/comma commit,
// backspace removes the last chip, ✕ removes one, normalize on commit, dedupe.
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import TagInput from '../../src/lib/TagInput.svelte'
import { normalizeTag } from '../../src/tunesheet/logic.js'

const chips = () =>
  [...document.querySelectorAll('.kit-taginput .kit-chip-body')].map((e) => e.textContent.trim())
const field = () => document.querySelector('.kit-taginput-field')

async function type(value) {
  await fireEvent.input(field(), { target: { value } })
}

describe('TagInput', () => {
  it('renders existing tags as chips', () => {
    render(TagInput, { props: { tags: ['practice', 'session'] } })
    expect(chips()).toEqual(['practice', 'session'])
  })

  it('space commits the draft as a normalized chip and clears the input', async () => {
    render(TagInput, { props: { tags: [], normalize: normalizeTag } })
    await type('Session')
    await fireEvent.keyDown(field(), { key: ' ' })
    expect(chips()).toEqual(['session'])
    expect(field().value).toBe('')
  })

  it('enter and comma also commit', async () => {
    render(TagInput, { props: { tags: [], normalize: normalizeTag } })
    await type('reel')
    await fireEvent.keyDown(field(), { key: 'Enter' })
    await type('jig')
    await fireEvent.keyDown(field(), { key: ',' })
    expect(chips()).toEqual(['reel', 'jig'])
  })

  it('ignores duplicates (normalized)', async () => {
    render(TagInput, { props: { tags: ['session'], normalize: normalizeTag } })
    await type('Session')
    await fireEvent.keyDown(field(), { key: 'Enter' })
    expect(chips()).toEqual(['session'])
  })

  it('backspace on an empty input removes the last chip', async () => {
    render(TagInput, { props: { tags: ['a', 'b'], normalize: normalizeTag } })
    await fireEvent.keyDown(field(), { key: 'Backspace' })
    expect(chips()).toEqual(['a'])
  })

  it('backspace with a draft present does NOT remove a chip', async () => {
    render(TagInput, { props: { tags: ['a'], normalize: normalizeTag } })
    await type('x')
    await fireEvent.keyDown(field(), { key: 'Backspace' })
    expect(chips()).toEqual(['a'])
  })

  it('the ✕ removes that chip', async () => {
    render(TagInput, { props: { tags: ['keep', 'drop'], normalize: normalizeTag } })
    const x = [...document.querySelectorAll('.kit-taginput .kit-x')]
    await fireEvent.click(x[1])
    expect(chips()).toEqual(['keep'])
  })

  it('blur commits a pending draft', async () => {
    render(TagInput, { props: { tags: [], normalize: normalizeTag } })
    await type('polka')
    await fireEvent.blur(field())
    expect(chips()).toEqual(['polka'])
  })

  it('disabled: no chip removal, no commit', async () => {
    render(TagInput, { props: { tags: ['x'], disabled: true, normalize: normalizeTag } })
    await fireEvent.keyDown(field(), { key: 'Backspace' })
    expect(chips()).toEqual(['x'])
    // dismiss buttons are not rendered when disabled
    expect(document.querySelectorAll('.kit-taginput .kit-x').length).toBe(0)
  })
})
