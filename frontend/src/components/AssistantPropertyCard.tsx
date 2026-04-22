"use client"

import { useEffect, useMemo, useRef, useState } from 'react'

import { buildPropertySummaryChips, getMapboxCoordinates, type MapboxFeature, type PropertySummary } from '../lib/property-summary'

export type AssistantPropertyCardFeature = MapboxFeature & {
  id: string
  place_name: string
  text: string
  center?: number[]
  standardized_address?: string
}

type Props = {
  selectedProperty: AssistantPropertyCardFeature
  onChange: () => void
  className?: string
  propertySummary: PropertySummary | null
  propertySummaryLoading: boolean
  propertySummaryError: string | null
}

function buildStaticMapUrl(center?: number[] | undefined, token = '') {
  if (!center || center.length < 2 || !token) return null
  const [lng, lat] = center
  const marker = `pin-s+2563eb(${lng},${lat})`
  const zoom = 15
  const size = '320x120@2x'
  return `https://api.mapbox.com/styles/v1/mapbox/streets-v11/static/${encodeURIComponent(marker)}/${lng},${lat},${zoom},0,0/${size}?access_token=${encodeURIComponent(
    token,
  )}`
}

export function AssistantPropertyCard({
  selectedProperty,
  onChange,
  className,
  propertySummary,
  propertySummaryLoading,
  propertySummaryError,
}: Props) {
  const MAPBOX_TOKEN = (process.env.NEXT_PUBLIC_MAPBOX_TOKEN || '').replace(/^"|"$/g, '')
  const [isExpanded, setIsExpanded] = useState(false)
  const [hiddenChipCount, setHiddenChipCount] = useState(0)
  const chipRailRef = useRef<HTMLDivElement | null>(null)

  const propertyChips = useMemo(() => buildPropertySummaryChips(propertySummary), [propertySummary])
  const mapImageUrl = buildStaticMapUrl(selectedProperty.center, MAPBOX_TOKEN)
  const displayAddress = selectedProperty.standardized_address || selectedProperty.place_name

  useEffect(() => {
    setIsExpanded(false)
  }, [selectedProperty.id])

  useEffect(() => {
    const rail = chipRailRef.current
    if (!rail) {
      setHiddenChipCount(0)
      return
    }

    const updateOverflow = () => {
      const chipNodes = Array.from(rail.querySelectorAll<HTMLElement>('[data-chip-index]'))
      if (!chipNodes.length || isExpanded) {
        setHiddenChipCount(0)
        return
      }

      const visibleWidth = rail.clientWidth
      let visibleCount = chipNodes.length

      for (let index = 0; index < chipNodes.length; index += 1) {
        const chip = chipNodes[index]
        const chipRightEdge = chip.offsetLeft + chip.offsetWidth
        if (chipRightEdge > visibleWidth + 1) {
          visibleCount = index
          break
        }
      }

      setHiddenChipCount(Math.max(0, chipNodes.length - visibleCount))
    }

    updateOverflow()

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateOverflow)
      return () => {
        window.removeEventListener('resize', updateOverflow)
      }
    }

    const observer = new ResizeObserver(updateOverflow)
    observer.observe(rail)

    return () => {
      observer.disconnect()
    }
  }, [propertyChips, isExpanded])

  return (
    <div className={className ? `assistant-property-card ${className}` : 'assistant-property-card'}>
      <div className="assistant-property-thumb">
        {mapImageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={mapImageUrl} alt={`Map of ${displayAddress}`} loading="lazy" />
        ) : (
          <div className="assistant-property-thumb-placeholder" />
        )}
        {mapImageUrl ? <div className="assistant-property-thumb-marker" aria-hidden="true" /> : null}
      </div>

      <div className="assistant-property-content">
        <div className="assistant-property-title-row">
          <span className="assistant-property-location-icon" aria-hidden="true" />
          <div className="assistant-property-card-address">{displayAddress}</div>
          <button type="button" className="assistant-property-change-link" onClick={onChange}>
            Change
          </button>
        </div>
        {propertySummaryLoading ? (
          <div className="assistant-property-summary-status">Loading Gridics parcel summary...</div>
        ) : propertySummaryError ? (
          <div className="assistant-property-summary-status">Gridics summary unavailable</div>
        ) : propertyChips.length ? (
          <div className="assistant-property-summary-row">
            <div
              ref={chipRailRef}
              className={`assistant-property-chip-rail${isExpanded ? ' is-expanded' : ''}`}
              aria-label="Gridics parcel summary"
            >
              {propertyChips.map((chip, index) => (
                <span
                  data-chip-index={index}
                  key={`${chip}-${index}`}
                  className={`assistant-property-chip${chip.startsWith('Zoning:') ? ' assistant-property-chip-primary' : ''}`}
                >
                  {chip}
                </span>
              ))}
            </div>
            {isExpanded ? (
              <button
                type="button"
                className="assistant-property-chip-expand"
                onClick={() => setIsExpanded(false)}
                aria-expanded="true"
                aria-label="Show less zoning details"
              >
                Show less
              </button>
            ) : hiddenChipCount > 0 ? (
              <button
                type="button"
                className="assistant-property-chip-expand"
                onClick={() => setIsExpanded((current) => !current)}
                aria-expanded={isExpanded}
                aria-label={`${hiddenChipCount} more zoning detail${hiddenChipCount === 1 ? '' : 's'}`}
              >
                +{hiddenChipCount}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="assistant-property-actions">
        <button
          type="button"
          className="button secondary assistant-property-map-button"
          onClick={() => {
            if (selectedProperty.center && selectedProperty.center.length >= 2) {
              const { lng, lat } = getMapboxCoordinates(selectedProperty)
              window.open(`https://www.google.com/maps/search/?api=1&query=${lat},${lng}`, '_blank')
            } else {
              window.open(`https://www.google.com/maps/search/${encodeURIComponent(displayAddress)}`, '_blank')
            }
          }}
        >
          <span className="assistant-property-map-icon" aria-hidden="true" />
          View on Map
        </button>
      </div>
    </div>
  )
}
