// "Find the tunes automatically" (spec 053): the segmenter's panel for a
// night with nothing logged, showing the listening service's job as it goes.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, waitFor, fireEvent } from '@testing-library/svelte'
import FindTunes from '../src/segmenterpage/FindTunes.svelte'

const reply = (body, status = 200) => ({ ok: status < 400, status, json: async () => body })
const job = (over = {}) => ({
  listen_job_id: 5, status: 'queued', phase: null, progress: null, heard_ms: 0, total_ms: 600000,
  waited_s: 12, running_s: 0, paused_s: 0, jobs_ahead: 1, result: null, error: null, ...over,
})

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('finding the tunes', () => {
  it('shows nothing to anyone the job API turns away', async () => {
    global.fetch = vi.fn(async () => reply({ success: false, error: 'no' }, 403))
    const { container } = render(FindTunes, { props: { recordingId: 7, tunesCount: 0 } })
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    expect(container.querySelector('.ft')).toBeNull()
  })

  it('asks nothing on a logged night with nothing of the listener to check', () => {
    global.fetch = vi.fn()
    render(FindTunes, { props: { recordingId: 7, tunesCount: 12, listenCount: 0 } })
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('queues a job and shows it waiting', async () => {
    global.fetch = vi.fn(async (url, init) =>
      init?.method === 'POST' ? reply({ success: true, job: job() }, 201) : reply({ success: true, job: null }))
    const { getByText } = render(FindTunes, { props: { recordingId: 7, tunesCount: 0 } })
    await waitFor(() => expect(getByText('Find the tunes automatically')).toBeTruthy())
    await fireEvent.click(getByText('Find the tunes automatically'))
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/recordings/7/find-tunes', expect.objectContaining({ method: 'POST' })))
    await waitFor(() => expect(getByText(/Waiting to start/)).toBeTruthy())
    expect(getByText(/1 job ahead/)).toBeTruthy()
  })

  it('shows how far it has got, when live listening has paused it, and reloads the log when done', async () => {
    const states = [
      job({ status: 'running', phase: 'listening', heard_ms: 300000, running_s: 75 }),
      job({ status: 'paused', phase: 'listening', heard_ms: 320000, running_s: 80, paused_s: 40 }),
      job({ status: 'done', running_s: 200, paused_s: 40, result: { logged: 23, sets: 11, need_check: 1 } }),
    ]
    let i = 0
    global.fetch = vi.fn(async () => reply({ success: true, job: states[Math.min(i++, states.length - 1)] }))
    const onfound = vi.fn()
    const { getByText, container } = render(FindTunes, { props: { recordingId: 7, tunesCount: 0, onfound } })
    await waitFor(() => expect(getByText(/Finding the tunes: listening/)).toBeTruthy())
    expect(container.querySelector('.ft-bar div').style.width).toBe('50%')
    await vi.advanceTimersByTimeAsync(5000)
    await waitFor(() => expect(getByText(/Paused while a night is being listened to live/)).toBeTruthy())
    await vi.advanceTimersByTimeAsync(5000)
    await waitFor(() => expect(onfound).toHaveBeenCalled())
  })

  it('says why it failed, and tries again', async () => {
    global.fetch = vi.fn(async (url, init) =>
      init?.method === 'POST'
        ? reply({ success: true, job: job() }, 201)
        : reply({ success: true, job: job({ status: 'failed', error: 'could not fetch the recording' }) }))
    const { getByText } = render(FindTunes, { props: { recordingId: 7, tunesCount: 0 } })
    await waitFor(() => expect(getByText(/could not fetch the recording/)).toBeTruthy())
    await fireEvent.click(getByText('Try again'))
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/listen-jobs/5/retry', expect.objectContaining({ method: 'POST' })))
  })
})

describe('the phone bar', () => {
  // On a phone the panel waits behind the ⋯ button; a job in flight still shows,
  // as a thin bar over the mark row that opens the panel.
  it('shows a running job as a thin bar that opens the panel', async () => {
    global.fetch = vi.fn(async () => reply({ success: true, job: job({ status: 'running', phase: 'listening', heard_ms: 150000 }) }))
    const onopen = vi.fn()
    const { container } = render(FindTunes, { props: { recordingId: 7, tunesCount: 4, listenCount: 4, variant: 'bar', onopen } })
    await waitFor(() => expect(container.querySelector('.ft-thin')).toBeTruthy())
    expect(container.querySelector('.ft')).toBeNull() // not the panel
    expect(container.querySelector('.ft-thin .ft-bar span').style.width).toBe('25%')
    expect(container.querySelector('.ft-thin').getAttribute('aria-label')).toBe('Finding the tunes: listening 25%')
    await fireEvent.click(container.querySelector('.ft-thin'))
    expect(onopen).toHaveBeenCalled()
  })

  it('shows nothing once the job is done', async () => {
    global.fetch = vi.fn(async () => reply({ success: true, job: job({ status: 'done', result: { logged: 4, sets: 2 } }) }))
    const { container } = render(FindTunes, { props: { recordingId: 7, tunesCount: 4, listenCount: 4, variant: 'bar' } })
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    expect(container.querySelector('.ft-thin')).toBeNull()
  })
})
