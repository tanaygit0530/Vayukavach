import clsx from 'clsx'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Bell, CheckCircle2, Mail, MessageSquare, Phone } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'

import { Card } from '../components/ui/Card'
import {
  ApiError,
  apiGet,
  apiPost,
  type AlertChannels,
  type AlertSubscribeReply,
  type AlertVerifyReply,
} from '../lib/api'
import { useDistricts } from '../lib/queries'
import { useShell } from '../lib/shell'

type Channel = 'whatsapp' | 'sms' | 'email'
type Lang = 'en' | 'hi' | 'mr'

const CHANNELS: { id: Channel; label: string; icon: typeof Mail; field: string; placeholder: string }[] = [
  { id: 'whatsapp', label: 'WhatsApp', icon: MessageSquare, field: 'WhatsApp number', placeholder: '98765 43210' },
  { id: 'sms', label: 'SMS', icon: Phone, field: 'Mobile number', placeholder: '98765 43210' },
  { id: 'email', label: 'Email', icon: Mail, field: 'Email address', placeholder: 'you@example.com' },
]

const TRIGGERS = [
  'Every morning at 7 AM: today’s AQI with advice, heat level and safer work hours',
  'Instantly when air turns Very poor or Severe (again only after it improves to Moderate)',
  'Instantly when heat reaches Danger or Extreme (at most once per hot day)',
  'No instant alerts between 10 PM and 6 AM',
]

function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 429) return 'Too many tries. Please wait and try again later.'
    return err.message
  }
  return 'Something went wrong. Please try again.'
}

export function AlertsPage() {
  const { place } = useShell()
  const districts = useDistricts()
  const city = districts.data?.find((d) => d.id === place)?.name ?? place
  const [channel, setChannel] = useState<Channel>('whatsapp')
  const [address, setAddress] = useState('')
  const [lang, setLang] = useState<Lang>('en')
  const [daily, setDaily] = useState(true)
  const [instant, setInstant] = useState(true)
  const [pending, setPending] = useState<AlertSubscribeReply | null>(null)
  const [code, setCode] = useState('')
  const [done, setDone] = useState<AlertVerifyReply | null>(null)
  const [resendIn, setResendIn] = useState(0)

  const channels = useQuery({
    queryKey: ['alert-channels'],
    queryFn: () => apiGet<AlertChannels>('/alerts/channels'),
    staleTime: 5 * 60_000,
  })
  const preview = useQuery({
    queryKey: ['alert-preview', place, lang],
    queryFn: () => apiGet<{ text: string; note: string }>('/alerts/preview', { place, language: lang }),
    staleTime: 10 * 60_000,
  })

  const subscribe = useMutation({
    mutationFn: () =>
      apiPost<AlertSubscribeReply>('/alerts/subscribe', { channel, address, place, language: lang, daily, instant }),
    onSuccess: (r) => {
      setPending(r)
      setCode('')
      setResendIn(60)
    },
  })
  const verify = useMutation({
    mutationFn: () => apiPost<AlertVerifyReply>('/alerts/verify', { id: pending!.id, code }),
    onSuccess: setDone,
  })

  useEffect(() => {
    if (resendIn <= 0) return
    const t = setTimeout(() => setResendIn((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [resendIn])

  const ready = channels.data?.[channel] ?? false
  const meta = CHANNELS.find((c) => c.id === channel)!
  const start = (e: FormEvent) => {
    e.preventDefault()
    subscribe.mutate()
  }
  const confirm = (e: FormEvent) => {
    e.preventDefault()
    verify.mutate()
  }
  const reset = () => {
    setPending(null)
    setDone(null)
    subscribe.reset()
    verify.reset()
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="glass-card inline-flex min-h-touch w-fit items-center gap-2 rounded-full px-4 text-[15px] font-medium">
        <Bell aria-hidden className="h-4 w-4" /> Alerts for {city}
      </h1>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[1fr_380px]">
        <Card title="Get air and heat alerts" subtitle="WhatsApp, SMS or email. Confirm with a 6-digit code; stop any time with the link in every message.">
          {done ? (
            <div role="status" className="flex items-start gap-3 rounded-[20px] bg-emerald-50 p-4 text-[14px] ring-1 ring-emerald-200">
              <CheckCircle2 aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-aqi-good" />
              <div>
                <p className="font-medium">You’re subscribed.</p>
                <p className="mt-1 text-ink-muted">
                  {CHANNELS.find((c) => c.id === done.channel)?.label} to {done.sent_to} for {done.place}:{' '}
                  {[done.daily && 'daily 7 AM summary', done.instant && 'instant alerts'].filter(Boolean).join(' and ')}.
                </p>
                <button type="button" onClick={reset} className="focus-ring mt-3 min-h-touch rounded-full bg-white px-4 text-[13px] ring-1 ring-slate-200">
                  Add another
                </button>
              </div>
            </div>
          ) : pending ? (
            pending.status === 'already_subscribed' ? (
              <div role="status" className="rounded-[20px] bg-slate-50 p-4 text-[14px] ring-1 ring-slate-200">
                <p>{pending.sent_to} already gets alerts for {city}. To change them, use the stop link in any alert, then sign up again.</p>
                <button type="button" onClick={reset} className="focus-ring mt-3 min-h-touch rounded-full bg-white px-4 text-[13px] ring-1 ring-slate-200">
                  Back
                </button>
              </div>
            ) : (
              <form onSubmit={confirm} className="space-y-4">
                <p className="text-[14px]">
                  We sent a 6-digit code to <span className="font-medium">{pending.sent_to}</span>. It expires in 15 minutes.
                </p>
                <label className="block">
                  <span className="mb-1 block text-[13px] text-ink-muted">Code</span>
                  <input
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    className="focus-ring min-h-touch w-40 rounded-full border border-slate-200 bg-white px-4 text-[18px] tracking-[0.3em]"
                  />
                </label>
                {verify.isError && <p role="alert" className="text-[13px] text-stale">{errorText(verify.error)}</p>}
                <div className="flex flex-wrap items-center gap-2">
                  <button type="submit" disabled={code.length !== 6 || verify.isPending} className="focus-ring min-h-touch rounded-full bg-ink px-5 text-[14px] text-white disabled:opacity-40">
                    Confirm
                  </button>
                  <button
                    type="button"
                    disabled={resendIn > 0 || subscribe.isPending}
                    onClick={() => subscribe.mutate()}
                    className="focus-ring min-h-touch rounded-full px-4 text-[13px] text-ink-muted disabled:opacity-50"
                  >
                    {resendIn > 0 ? `Send again in ${resendIn}s` : 'Send again'}
                  </button>
                  <button type="button" onClick={reset} className="focus-ring min-h-touch rounded-full px-4 text-[13px] text-ink-muted">
                    Change details
                  </button>
                </div>
              </form>
            )
          ) : (
            <form onSubmit={start} className="space-y-5">
              <fieldset>
                <legend className="mb-2 text-[13px] text-ink-muted">Send alerts by</legend>
                <div className="flex flex-wrap gap-2">
                  {CHANNELS.map((c) => {
                    const on = channels.data?.[c.id]
                    return (
                      <label
                        key={c.id}
                        className={clsx(
                          'focus-within:ring-2 focus-within:ring-accent inline-flex min-h-touch cursor-pointer items-center gap-2 rounded-full px-4 text-[14px] ring-1',
                          channel === c.id ? 'bg-ink text-white ring-ink' : 'bg-white ring-slate-200',
                        )}
                      >
                        <input type="radio" name="channel" value={c.id} checked={channel === c.id} onChange={() => setChannel(c.id)} className="sr-only" />
                        <c.icon aria-hidden className="h-4 w-4" />
                        {c.label}
                        {channels.data && !on && <span className="text-[11px] opacity-70">(not set up)</span>}
                      </label>
                    )
                  })}
                </div>
              </fieldset>

              {channel === 'whatsapp' && channels.data?.whatsapp_join && (
                <p className="rounded-[16px] bg-amber-50 px-4 py-3 text-[13px] ring-1 ring-amber-200">
                  First, on WhatsApp send <span className="font-medium">{channels.data.whatsapp_join}</span> to{' '}
                  <span className="font-medium">{channels.data.whatsapp_number}</span> (Twilio test number). Then enter your number below.
                </p>
              )}

              <div className="grid gap-4 sm:grid-cols-[1fr_180px]">
                <label className="block">
                  <span className="mb-1 block text-[13px] text-ink-muted">{meta.field}</span>
                  <input
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    type={channel === 'email' ? 'email' : 'tel'}
                    autoComplete={channel === 'email' ? 'email' : 'tel'}
                    placeholder={meta.placeholder}
                    required
                    maxLength={254}
                    className="focus-ring min-h-touch w-full rounded-full border border-slate-200 bg-white px-4 text-[14px] placeholder:text-ink-muted"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-[13px] text-ink-muted">Language</span>
                  <select value={lang} onChange={(e) => setLang(e.target.value as Lang)} className="focus-ring min-h-touch w-full rounded-full border border-slate-200 bg-white px-4 text-[14px]">
                    <option value="en">English</option>
                    <option value="hi">हिंदी</option>
                    <option value="mr">मराठी</option>
                  </select>
                </label>
              </div>

              <fieldset className="space-y-2 text-[14px]">
                <legend className="mb-2 text-[13px] text-ink-muted">What to send</legend>
                <label className="flex min-h-touch items-center gap-3">
                  <input type="checkbox" checked={daily} onChange={(e) => setDaily(e.target.checked)} className="h-5 w-5 accent-[#17212b]" />
                  Daily summary at 7 AM
                </label>
                <label className="flex min-h-touch items-center gap-3">
                  <input type="checkbox" checked={instant} onChange={(e) => setInstant(e.target.checked)} className="h-5 w-5 accent-[#17212b]" />
                  Instant alerts (Very poor or Severe air, Danger heat)
                </label>
              </fieldset>

              {subscribe.isError && <p role="alert" className="text-[13px] text-stale">{errorText(subscribe.error)}</p>}
              {channels.data && !ready && (
                <p className="text-[13px] text-stale">{meta.label} alerts are not set up on this server yet. Try another channel.</p>
              )}
              <button
                type="submit"
                disabled={!ready || !address.trim() || !(daily || instant) || subscribe.isPending}
                className="focus-ring min-h-touch rounded-full bg-ink px-5 text-[14px] text-white disabled:opacity-40"
              >
                {subscribe.isPending ? 'Sending…' : 'Send code'}
              </button>
              <p className="text-[11px] text-ink-muted">
                Your {channel === 'email' ? 'email address' : 'number'} is used only to send these alerts and is deleted when you stop them.
                SMS and WhatsApp are sent through Twilio, email through our mail server.
              </p>
            </form>
          )}
        </Card>

        <div className="flex flex-col gap-4">
          <Card title="Sample morning message" subtitle={preview.data?.note} as="article">
            {preview.isLoading && <p className="text-[13px] text-ink-muted">Loading the latest data…</p>}
            {preview.isError && <p className="text-[13px] text-stale">Preview unavailable right now.</p>}
            {preview.data && (
              <pre className="whitespace-pre-wrap rounded-[16px] bg-slate-50 p-4 font-sans text-[13px] leading-relaxed ring-1 ring-slate-200">
                {preview.data.text}
              </pre>
            )}
          </Card>
          <Card title="When you’ll hear from us" as="article">
            <ul className="list-disc space-y-2 pl-5 text-[13px]">
              {TRIGGERS.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}
