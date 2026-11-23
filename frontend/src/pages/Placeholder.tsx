import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'

export function Placeholder({ title, phase, note }: { title: string; phase: number; note: string }) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="sr-only">{title}</h1>
      <Card title={title} subtitle={`Built in Phase ${phase}`}>
        <EmptyState message={note} />
      </Card>
    </div>
  )
}
