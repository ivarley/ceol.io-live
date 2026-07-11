// SearchField: debounce settles typing into ONE onSearch; clear-× and Escape
// report an empty query immediately.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import SearchField from '../../src/lib/SearchField.svelte'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

async function type(input, value) {
  await fireEvent.input(input, { target: { value } })
}

describe('SearchField', () => {
  it('debounces input: onSearch fires once after the idle window', async () => {
    const onSearch = vi.fn()
    render(SearchField, { props: { onSearch } })
    const input = screen.getByPlaceholderText('Search…')

    await type(input, 'butter')
    expect(onSearch).not.toHaveBeenCalled()
    vi.advanceTimersByTime(299)
    expect(onSearch).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(onSearch).toHaveBeenCalledWith('butter')
  })

  it('keystrokes inside the window reset the timer (no intermediate queries)', async () => {
    const onSearch = vi.fn()
    render(SearchField, { props: { onSearch } })
    const input = screen.getByPlaceholderText('Search…')

    await type(input, 'b')
    vi.advanceTimersByTime(200)
    await type(input, 'bu')
    vi.advanceTimersByTime(200)
    expect(onSearch).not.toHaveBeenCalled()
    vi.advanceTimersByTime(100)
    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(onSearch).toHaveBeenCalledWith('bu')
  })

  it('honors a custom debounce', async () => {
    const onSearch = vi.fn()
    render(SearchField, { props: { onSearch, debounce: 50 } })
    await type(screen.getByPlaceholderText('Search…'), 'x')
    vi.advanceTimersByTime(50)
    expect(onSearch).toHaveBeenCalledWith('x')
  })

  it('clear-× empties the field, fires onSearch("") immediately, and cancels the pending search', async () => {
    const onSearch = vi.fn()
    render(SearchField, { props: { onSearch } })
    const input = screen.getByPlaceholderText('Search…')

    await type(input, 'reel')
    const x = screen.getByLabelText('Clear search')
    expect(x).toHaveClass('kit-x')
    await fireEvent.click(x)
    expect(input.value).toBe('')
    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(onSearch).toHaveBeenCalledWith('')
    vi.advanceTimersByTime(1000) // the debounced 'reel' must never land
    expect(onSearch).toHaveBeenCalledTimes(1)
  })

  it('the × only renders when there is text', async () => {
    render(SearchField, { props: {} })
    expect(screen.queryByLabelText('Clear search')).not.toBeInTheDocument()
    await type(screen.getByPlaceholderText('Search…'), 'a')
    expect(screen.getByLabelText('Clear search')).toBeInTheDocument()
  })

  it('Escape clears like the ×, and is consumed (no Sheet-close leak)', async () => {
    const onSearch = vi.fn()
    render(SearchField, { props: { onSearch } })
    const input = screen.getByPlaceholderText('Search…')

    await type(input, 'jig')
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    input.dispatchEvent(escape)
    await Promise.resolve()
    expect(input.value).toBe('')
    expect(onSearch).toHaveBeenCalledWith('')
    expect(escape.defaultPrevented).toBe(true)
  })

  it('Escape on an empty field does nothing', async () => {
    const onSearch = vi.fn()
    render(SearchField, { props: { onSearch } })
    await fireEvent.keyDown(screen.getByPlaceholderText('Search…'), { key: 'Escape' })
    expect(onSearch).not.toHaveBeenCalled()
  })
})
