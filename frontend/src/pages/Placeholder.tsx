import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'

export function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="sr-only">{title}</h1>
      <Card title={title} subtitle="Not built yet">
        <EmptyState message={note} />
      </Card>
    </div>
  )
}
