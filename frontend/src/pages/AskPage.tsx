import clsx from 'clsx'
import { useMutation } from '@tanstack/react-query'
import { Bot, Check, MessageCircle, SendHorizontal, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'

import { Card } from '../components/ui/Card'
import { ApiError, apiPost, type ChatReply } from '../lib/api'
import { useDistricts } from '../lib/queries'
import { useShell } from '../lib/shell'

type Lang = 'auto' | 'en' | 'hi' | 'mr'

interface Turn {
  id: number
  role: 'user' | 'bot'
  text: string
  reply?: ChatReply
  error?: boolean
}

const SUGGESTIONS: Record<'en' | 'hi' | 'mr', string[]> = {
  en: [
    'What is the AQI right now, and can I trust it?',
    'Is it safe to go for a run tomorrow morning?',
    'Why is the official AQI different from your estimate?',
    'Find me a cleaner place for a day trip',
  ],
  hi: ['आज हवा कैसी है?', 'क्या कल सुबह दौड़ना सुरक्षित है?', 'आज गर्मी का खतरा कितना है?'],
  mr: ['आज हवेची गुणवत्ता कशी आहे?', 'आज उष्णता किती आहे?', 'स्टेशनचा डेटा पूर्ण आहे का?'],
}

const CAN = [
  'Current and past AQI for covered cities',
  'Whether official data is complete, and the shadow AQI',
  'AQI and heat forecasts, heat risk and safe work hours',
  'Cleaner or cooler places, and official precautions',
]
const CANNOT = ['Medical diagnosis (it will suggest a doctor; call 108 for heatstroke)', 'Anything outside air quality, heat and this app', 'Numbers it has no data for: it says so instead of guessing']

const LABEL_TEXT = { measured: 'Measured', estimated: 'Estimated' } as const

function SourceChips({ reply }: { reply: ChatReply }) {
  if (!reply.sources.length) return null
  return (
    <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Sources">
      {reply.sources.map((s, i) => (
        <li
          key={i}
          className={clsx(
            'rounded-full px-2.5 py-1 text-[11px]',
            s.label === 'estimated' ? 'border border-dashed border-ink-muted/60' : 'border border-ink-muted/40',
          )}
        >
          <span className="font-medium">{s.source}</span>
          {s.time && <span className="text-ink-muted"> · {s.time}</span>}
          {s.label && <span className="text-ink-muted"> · {LABEL_TEXT[s.label]}</span>}
        </li>
      ))}
    </ul>
  )
}

export function AskPage() {
  const { place } = useShell()
  const districts = useDistricts()
  const city = districts.data?.find((d) => d.id === place)?.name ?? place
  const [lang, setLang] = useState<Lang>('auto')
  const [text, setText] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const nextId = useRef(1)
  const endRef = useRef<HTMLDivElement>(null)

  const ask = useMutation({
    mutationFn: (message: string) =>
      apiPost<ChatReply>('/chat', { message, place, language: lang === 'auto' ? null : lang }),
    onSuccess: (reply) =>
      setTurns((t) => [...t, { id: nextId.current++, role: 'bot', text: reply.answer, reply }]),
    onError: (err) =>
      setTurns((t) => [
        ...t,
        {
          id: nextId.current++,
          role: 'bot',
          error: true,
          text:
            err instanceof ApiError && err.status === 429
              ? 'Too many questions. Please wait a minute.'
              : 'Ask VayuKavach is unavailable right now. Please try again shortly.',
        },
      ]),
  })

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' })
  }, [turns, ask.isPending])

  const send = (message: string) => {
    const m = message.trim()
    if (!m || ask.isPending) return
    setTurns((t) => [...t, { id: nextId.current++, role: 'user', text: m }])
    setText('')
    ask.mutate(m)
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    send(text)
  }

  const suggestions = SUGGESTIONS[lang === 'auto' ? 'en' : lang]
  const last = turns[turns.length - 1]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[15px] font-medium">
          <MessageCircle aria-hidden className="h-4 w-4" /> Ask VayuKavach
        </h1>
        <label className="glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[13px]">
          <span className="text-ink-muted">Language</span>
          <select
            value={lang}
            onChange={(e) => setLang(e.target.value as Lang)}
            className="focus-ring rounded-md bg-transparent font-medium"
          >
            <option value="auto">Auto</option>
            <option value="en">English</option>
            <option value="hi">हिंदी</option>
            <option value="mr">मराठी</option>
          </select>
        </label>
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[1fr_320px]">
        <section aria-label="Conversation" className="glass-card flex min-h-[560px] flex-col p-5">
          <div className="flex-1 space-y-4 overflow-y-auto pr-1" role="log" aria-live="polite" aria-relevant="additions">
            {turns.length === 0 && (
              // empty conversation: a centred welcome with the suggestions, instead of a blank panel
              <div className="flex h-full min-h-[380px] flex-col items-center justify-center px-4 text-center">
                <span className="grid h-14 w-14 place-items-center rounded-full bg-accent/10">
                  <Bot aria-hidden className="h-7 w-7 text-accent" />
                </span>
                <h2 className="mt-4 text-[20px] font-medium">Ask about air or heat in {city}</h2>
                <p className="mt-2 max-w-[520px] text-[14px] text-ink-muted">
                  Answers use VayuKavach's own data only, with the source, time and whether each number is
                  measured or estimated.
                </p>
                <div className="mt-6 grid w-full max-w-[640px] gap-2 sm:grid-cols-2" aria-label="Suggested questions">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => send(s)}
                      disabled={ask.isPending}
                      className="focus-ring min-h-touch rounded-2xl border border-slate-200 bg-white/70 px-4 py-3 text-left text-[13px] hover:bg-white disabled:opacity-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {turns.map((t) =>
              t.role === 'user' ? (
                <div key={t.id} className="flex justify-end">
                  <p className="max-w-[80%] rounded-[20px] rounded-br-md bg-ink px-4 py-2.5 text-[14px] text-white">{t.text}</p>
                </div>
              ) : (
                <div key={t.id} className="flex items-start gap-2">
                  <Bot aria-hidden className="mt-2 h-5 w-5 shrink-0 text-accent" />
                  <div
                    className={clsx(
                      'max-w-[85%] rounded-[20px] rounded-bl-md px-4 py-2.5 text-[14px]',
                      t.reply?.refused || t.error ? 'bg-amber-50 text-stale ring-1 ring-amber-200' : 'bg-white ring-1 ring-slate-200',
                    )}
                    data-testid={t.reply?.refused ? 'refusal' : undefined}
                  >
                    <p className="whitespace-pre-line leading-relaxed">{t.text}</p>
                    {t.reply && <SourceChips reply={t.reply} />}
                  </div>
                </div>
              ),
            )}
            {ask.isPending && (
              <p className="flex items-center gap-2 text-[13px] text-ink-muted">
                <Bot aria-hidden className="h-5 w-5 text-accent" /> Looking up VayuKavach data…
              </p>
            )}
            <div ref={endRef} />
          </div>

          {turns.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2" aria-label="Suggested questions">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => send(s)}
                disabled={ask.isPending}
                className="focus-ring min-h-[36px] rounded-full bg-slate-100 px-3 text-[12px] hover:bg-slate-200 disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>
          )}

          <form onSubmit={onSubmit} className="mt-3 flex items-center gap-2">
            <label className="flex-1">
              <span className="sr-only">Your question</span>
              <input
                value={text}
                onChange={(e) => setText(e.target.value)}
                maxLength={500}
                placeholder={`Ask about air or heat in ${city}…`}
                className="focus-ring min-h-touch w-full rounded-full border border-slate-200 bg-white px-4 text-[14px] placeholder:text-ink-muted"
              />
            </label>
            <button
              type="submit"
              disabled={!text.trim() || ask.isPending}
              aria-label="Send question"
              className="focus-ring grid h-[44px] w-[44px] place-items-center rounded-full bg-ink text-white disabled:opacity-40"
            >
              <SendHorizontal aria-hidden className="h-4 w-4" />
            </button>
          </form>
          {last?.reply && last.reply.engine !== 'scope' && (
            <p className="mt-2 text-[11px] text-ink-muted">
              Answered from VayuKavach data{last.reply.engine === 'rules' ? ' (template answer)' : ` · ${last.reply.engine === 'gemini' ? 'Gemini' : 'local model'}`}
            </p>
          )}
        </section>

        <Card title="What I can answer" as="article">
          <ul className="space-y-2 text-[13px]">
            {CAN.map((c) => (
              <li key={c} className="flex gap-2">
                <Check aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                {c}
              </li>
            ))}
          </ul>
          <h3 className="mb-2 mt-5 text-[14px] font-medium">What I won't do</h3>
          <ul className="space-y-2 text-[13px]">
            {CANNOT.map((c) => (
              <li key={c} className="flex gap-2">
                <X aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-stale" />
                {c}
              </li>
            ))}
          </ul>
          <p className="mt-5 text-[11px] text-ink-muted">
            Replies in English, हिंदी or मराठी. Questions are logged without personal details to improve answers.
          </p>
        </Card>
      </div>
    </div>
  )
}
