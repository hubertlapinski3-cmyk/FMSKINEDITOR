// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import AppUpdate from './AppUpdate'

const invoke = vi.fn()
vi.mock('@tauri-apps/api/core', () => ({ invoke: (...a: unknown[]) => invoke(...a) }))
vi.mock('@tauri-apps/api/app', () => ({ getVersion: async () => '0.1.1' }))

afterEach(() => { cleanup(); invoke.mockReset(); delete (window as any).__TAURI_INTERNALS__ })

describe('App updates', () => {
  it('outside the installed app it says so and offers nothing', () => {
    render(<AppUpdate say={() => {}} />)
    expect(screen.getByText(/work in the installed FM Skin Studio/)).toBeTruthy()
    expect(screen.queryByText('Check for updates')).toBeNull()
  })

  it('shows the running version, reports up to date, and offers an install when a newer version exists', async () => {
    ;(window as any).__TAURI_INTERNALS__ = {}
    invoke.mockResolvedValueOnce(null).mockResolvedValueOnce({ version: '0.1.2', current: '0.1.1', notes: 'Fixes', date: null })
    render(<AppUpdate say={() => {}} />)
    expect(await screen.findByText(/FM Skin Studio 0.1.1/)).toBeTruthy()
    fireEvent.click(screen.getByText('Check for updates'))
    expect(await screen.findByText(/up to date/)).toBeTruthy()
    fireEvent.click(screen.getByText('Check for updates'))
    expect(await screen.findByText('0.1.2')).toBeTruthy()
    expect(screen.getByText('Install and restart')).toBeTruthy()
    expect(screen.getByText('Fixes')).toBeTruthy()
    expect(invoke).toHaveBeenCalledWith('app_update_check')
  })

  it('install asks the shell, and a refusal (game running) is shown as text and the button comes back', async () => {
    ;(window as any).__TAURI_INTERNALS__ = {}
    invoke.mockResolvedValueOnce({ version: '0.1.2', current: '0.1.1' }).mockRejectedValueOnce('FM27 is running: close the game before updating')
    render(<AppUpdate say={() => {}} />)
    fireEvent.click(screen.getByText('Check for updates'))
    fireEvent.click(await screen.findByText('Install and restart'))
    expect(await screen.findByText(/close the game before updating/)).toBeTruthy()
    await waitFor(() => expect((screen.getByText('Install and restart') as HTMLButtonElement).disabled).toBe(false))
    expect(invoke).toHaveBeenCalledWith('app_update_install')
  })

  it('a failed check is shown as text', async () => {
    ;(window as any).__TAURI_INTERNALS__ = {}
    invoke.mockRejectedValueOnce('could not fetch a valid release JSON from the remote')
    render(<AppUpdate say={() => {}} />)
    fireEvent.click(screen.getByText('Check for updates'))
    expect(await screen.findByText(/could not fetch a valid release JSON/)).toBeTruthy()
  })
})
