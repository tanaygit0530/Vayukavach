const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export default function App() {
  return (
    <main className="min-h-screen grid place-items-center p-6">
      <section className="rounded-card bg-white/90 backdrop-blur-[14px] shadow-card p-10 max-w-md text-center">
        <h1 className="text-3xl font-semibold">VayuKavach</h1>
        <p className="mt-2 text-ink-muted">India&apos;s year-round environmental health shield.</p>
        <p className="mt-6 text-sm text-ink-muted">
          API: <code>{API_BASE}</code>
        </p>
      </section>
    </main>
  )
}
