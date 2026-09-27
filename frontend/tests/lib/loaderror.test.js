// LoadError: a failed load says so where the content would be, with a Retry.
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import { fireEvent } from '@testing-library/dom'
import LoadError from '../../src/lib/LoadError.svelte'

describe('LoadError', () => {
  it('says what could not be loaded, as an alert', () => {
    render(LoadError, { props: { what: 'the logs' } })
    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't load the logs.")
  })

  it('message overrides the sentence', () => {
    render(LoadError, { props: { message: "Couldn't filter by that tune." } })
    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't filter by that tune.")
  })

  it('Retry re-runs the fetch', async () => {
    const onRetry = vi.fn()
    render(LoadError, { props: { what: 'stats', onRetry } })
    await fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('no Retry button without onRetry; busy while retrying', async () => {
    const { rerender } = render(LoadError, { props: { what: 'stats' } })
    expect(screen.queryByRole('button')).toBeNull()
    await rerender({ what: 'stats', onRetry: () => {}, retrying: true })
    expect(screen.getByRole('button', { name: 'Retrying…' })).toBeDisabled()
  })

  it('inline variant and attribute passthrough', () => {
    render(LoadError, { props: { what: 'x', inline: true, id: 'le', class: 'extra' } })
    const el = document.getElementById('le')
    expect(el).toHaveClass('kit-load-error', 'inline', 'extra')
  })
})
