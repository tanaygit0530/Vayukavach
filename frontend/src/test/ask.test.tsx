import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { AppShell } from '../components/shell/AppShell'
import { AskPage } from '../pages/AskPage'
import { mockApi } from './render'

type Body = { message: string; place: string; language: string | null }

function renderAsk(reply: (b: Body) => Response) {
  const base = mockApi()
  const sent: Body[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    if (url.pathname.endsWith('/chat')) {
      const b = JSON.parse(String(init?.body)) as Body
      sent.push(b)
      return reply(b)
    }
    return base(input)
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/ask?place=delhi']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="ask" element={<AskPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return sent
}

const ANSWER = {
  answer: 'Delhi AQI today is 312 (Very poor).',
  sources: [{ source: 'CPCB', time: '2026-11-24 14:00 IST', label: 'measured', tool: 'get_aqi' }],
  refused: false,
  language: 'en',
  engine: 'gemini',
}

describe('Ask VayuKavach', () => {
  it('sends the question with the place and shows the answer with source chips', async () => {
    const user = userEvent.setup()
    const sent = renderAsk(() => new Response(JSON.stringify(ANSWER)))
    await user.type(screen.getByLabelText('Your question'), 'What is the AQI?')
    await user.click(screen.getByRole('button', { name: 'Send question' }))
    expect(await screen.findByText(ANSWER.answer)).toBeInTheDocument()
    expect(screen.getByText('What is the AQI?')).toBeInTheDocument()
    const chips = screen.getByRole('list', { name: 'Sources' })
    expect(within(chips).getByText('CPCB')).toBeInTheDocument()
    expect(within(chips).getByText(/Measured/)).toBeInTheDocument()
    expect(sent[0]).toEqual({ message: 'What is the AQI?', place: 'delhi', language: null })
  })

  it('shows refusals in the amber bubble and sends the chosen language', async () => {
    const user = userEvent.setup()
    const sent = renderAsk(() =>
      new Response(JSON.stringify({ answer: 'मैं केवल हवा और गर्मी के बारे में बता सकता हूँ।', sources: [],
        refused: true, language: 'hi', engine: 'scope' })), // prettier-ignore
    )
    await user.selectOptions(screen.getByRole('combobox'), 'hi')
    await user.click(screen.getByRole('button', { name: 'आज हवा कैसी है?' }))
    expect(await screen.findByTestId('refusal')).toHaveTextContent('मैं केवल')
    expect(sent[0].language).toBe('hi')
  })

  it('explains rate limits and outages instead of failing silently', async () => {
    const user = userEvent.setup()
    renderAsk(() => new Response(JSON.stringify({ detail: 'slow down' }), { status: 429 }))
    await user.type(screen.getByLabelText('Your question'), 'AQI?')
    await user.click(screen.getByRole('button', { name: 'Send question' }))
    expect(await screen.findByText(/Too many questions/)).toBeInTheDocument()
  })
})
