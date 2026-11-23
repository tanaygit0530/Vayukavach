import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { STORAGE_KEY } from '../lib/place'
import { mockApi, renderApp } from './render'

const location = () => screen.getByTestId('location').textContent

describe('app shell', () => {
  beforeEach(() => {
    mockApi()
  })

  it('defaults to Delhi and puts the place in the URL', async () => {
    renderApp('/')
    await waitFor(() => expect(location()).toBe('/air?place=delhi'))
    expect(await screen.findByRole('button', { name: /current place: delhi, delhi/i })).toBeInTheDocument()
  })

  it('switches tabs and keeps the place', async () => {
    const user = userEvent.setup()
    renderApp('/air?place=mumbai')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    await user.click(within(nav).getByRole('link', { name: 'Temperature' }))
    expect(location()).toBe('/temperature?place=mumbai')
    expect(within(nav).getByRole('link', { name: 'Temperature' })).toHaveAttribute('aria-current', 'page')
    await user.click(within(nav).getByRole('link', { name: 'Heat' }))
    expect(location()).toBe('/heat?place=mumbai')
  })

  it('opens Places only from the location button and closes on X, Escape and outside click', async () => {
    const user = userEvent.setup()
    renderApp('/air?place=delhi')
    const button = await screen.findByRole('button', { name: /change place/i })
    const dialog = screen.getByRole('dialog', { hidden: true })
    expect(button).toHaveAttribute('aria-expanded', 'false')

    await user.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('searchbox', { name: /search a city/i })).toHaveFocus()
    await user.click(within(dialog).getByRole('button', { name: 'Close places' }))
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(button).toHaveFocus()

    await user.click(button)
    await user.keyboard('{Escape}')
    expect(button).toHaveAttribute('aria-expanded', 'false')

    await user.click(button)
    await user.click(screen.getByTestId('drawer-backdrop'))
    expect(button).toHaveAttribute('aria-expanded', 'false')
  })

  it('choosing a city updates the URL and survives a refresh', async () => {
    const user = userEvent.setup()
    const first = renderApp('/air?place=delhi')
    await user.click(await screen.findByRole('button', { name: /change place/i }))
    const dialog = screen.getByRole('dialog')
    await user.click(await within(dialog).findByRole('button', { name: /shimla/i }))
    expect(location()).toBe('/air?place=shimla')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('shimla')
    expect(screen.getByRole('button', { name: /change place/i })).toHaveAttribute('aria-expanded', 'false')

    first.unmount() // "refresh": a new app with no ?place= in the URL
    renderApp('/temperature')
    await waitFor(() => expect(location()).toBe('/temperature?place=shimla'))
    expect(await screen.findByRole('button', { name: /current place: shimla/i })).toBeInTheDocument()
  })

  it('search marks places that are not covered yet', async () => {
    const user = userEvent.setup()
    renderApp('/air?place=delhi')
    await user.click(await screen.findByRole('button', { name: /change place/i }))
    await user.type(screen.getByRole('searchbox'), 'mum')
    const results = await screen.findByRole('region', { name: 'Search results' })
    const leh = await within(results).findByRole('button', { name: /leh/i })
    expect(leh).toBeDisabled()
    expect(leh).toHaveTextContent('Not covered yet')
    await user.click(within(results).getByRole('button', { name: /navi mumbai/i }))
    expect(location()).toBe('/air?place=mumbai')
  })

  it('every icon button has an accessible name', async () => {
    renderApp('/air?place=delhi')
    await screen.findByRole('button', { name: /change place/i })
    for (const el of screen.getAllByRole('link')) expect(el).toHaveAccessibleName()
    for (const el of screen.getAllByRole('button', { hidden: true })) expect(el).toHaveAccessibleName()
  })
})
