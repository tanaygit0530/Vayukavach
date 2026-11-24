import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { AppShell } from '../components/shell/AppShell'
import { AlertsPage } from '../pages/AlertsPage'
import { mockApi } from './render'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

function renderAlerts(opts: { sms?: boolean; verify?: (code: string) => Response } = {}) {
  const base = mockApi()
  const posts: { path: string; body: Record<string, unknown> }[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    if (url.pathname.endsWith('/alerts/channels'))
      return json({ email: true, sms: opts.sms ?? true, whatsapp: true, whatsapp_join: 'join blue-sky',
        whatsapp_number: '+14155238886' }) // prettier-ignore
    if (url.pathname.endsWith('/alerts/preview'))
      return json({ text: `VayuKavach · Delhi\nAir: AQI 310 (Very poor) [${url.searchParams.get('language')}]`, note: 'Example' })
    if (init?.method === 'POST') {
      const body = JSON.parse(String(init.body))
      posts.push({ path: url.pathname, body })
      if (url.pathname.endsWith('/alerts/subscribe'))
        return json({ id: 7, status: 'code_sent', sent_to: '+91******3210' })
      if (url.pathname.endsWith('/alerts/verify'))
        return opts.verify?.(body.code) ??
          json({ verified: true, channel: 'whatsapp', sent_to: '+91******3210', place: 'Delhi', daily: true, instant: true }) // prettier-ignore
    }
    return base(input)
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/alerts?place=delhi']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="alerts" element={<AlertsPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return posts
}

describe('Alerts', () => {
  it('signs up on WhatsApp with a code and confirms', async () => {
    const user = userEvent.setup()
    const posts = renderAlerts()
    expect(await screen.findByText('join blue-sky')).toBeInTheDocument()
    await user.type(screen.getByLabelText('WhatsApp number'), '98765 43210')
    await user.selectOptions(screen.getByLabelText('Language'), 'hi')
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    expect(await screen.findByText('+91******3210')).toBeInTheDocument()
    expect(posts[0].body).toEqual({ channel: 'whatsapp', address: '98765 43210', place: 'delhi', language: 'hi',
      daily: true, instant: true }) // prettier-ignore
    expect(screen.getByRole('button', { name: /Send again in/ })).toBeDisabled()
    await user.type(screen.getByLabelText('Code'), '12a3456')
    await user.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(await screen.findByText('You’re subscribed.')).toBeInTheDocument()
    expect(posts[1].body).toEqual({ id: 7, code: '123456' })
  })

  it('shows the server reason for a wrong code', async () => {
    const user = userEvent.setup()
    renderAlerts({ verify: () => json({ detail: { code: 'wrong_code', message: 'That code is not right' } }, 400) })
    await user.type(await screen.findByLabelText('WhatsApp number'), '9876543210')
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    await user.type(await screen.findByLabelText('Code'), '000000')
    await user.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('That code is not right')
  })

  it('marks channels that are not set up and previews the message in the chosen language', async () => {
    const user = userEvent.setup()
    renderAlerts({ sms: false })
    await user.click(await screen.findByRole('radio', { name: /SMS/ }))
    expect(await screen.findByText(/SMS alerts are not set up/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send code' })).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('Language'), 'mr')
    expect(await screen.findByText(/\[mr\]/)).toBeInTheDocument()
  })
})
