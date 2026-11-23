import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { EstimatedBadge, StaleBadge } from '../components/ui/Badges'
import { EmptyState } from '../components/ui/EmptyState'
import { MetricBubble } from '../components/ui/MetricBubble'
import { updatedAgo } from '../lib/format'

describe('component states', () => {
  it('MetricBubble: loading, no data, estimated, stale', () => {
    const { rerender } = render(<MetricBubble value="249" label="AQI" loading />)
    expect(screen.getByText('Loading AQI')).toBeInTheDocument()
    rerender(<MetricBubble value={null} label="AQI" />)
    expect(screen.getByText('No reading for this hour')).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
    rerender(<MetricBubble value={null} label="AQI" error />)
    expect(screen.getByText(/Couldn’t load/)).toBeInTheDocument()
    expect(screen.queryByText('No reading for this hour')).not.toBeInTheDocument()
    rerender(<MetricBubble value="133" label="AQI" estimated />)
    expect(screen.getByText('Estimated')).toBeInTheDocument()
    rerender(<MetricBubble value="133" label="AQI" stale />)
    expect(screen.getByText('Stale')).toBeInTheDocument()
  })

  it('StaleBadge appears only when stale', () => {
    const iso = new Date(Date.now() - 3 * 3600_000).toISOString()
    const { rerender, container } = render(<StaleBadge updatedAt={iso} stale={false} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<StaleBadge updatedAt={iso} stale />)
    expect(screen.getByRole('status')).toHaveTextContent('Updated 3 h ago')
  })

  it('EstimatedBadge and EmptyState wording', () => {
    render(
      <>
        <EstimatedBadge />
        <EmptyState />
      </>,
    )
    expect(screen.getByText('Estimated')).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('No reading for this hour')
  })

  it('updatedAgo wording', () => {
    const now = new Date('2026-11-23T12:00:00Z')
    expect(updatedAgo('2026-11-23T11:59:30Z', now)).toBe('Updated just now')
    expect(updatedAgo('2026-11-23T11:35:00Z', now)).toBe('Updated 25 min ago')
    expect(updatedAgo('2026-11-23T09:00:00Z', now)).toBe('Updated 3 h ago')
    expect(updatedAgo(null, now)).toBeNull()
  })
})
