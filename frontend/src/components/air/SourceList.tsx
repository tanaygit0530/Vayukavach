import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'

/** Sector shares of PM2.5. Data arrives in Phase 9 (IITM DSS for Delhi, studies elsewhere). */
export function SourceList() {
  return (
    <Card title="Pollution Sources" subtitle="Share of today's PM2.5 by sector">
      <EmptyState
        message="No source data for this city yet"
        detail="Delhi will use IITM's Decision Support System; other cities, published source-apportionment studies with their year."
      />
    </Card>
  )
}
