"use client"

import { getMapboxCoordinates } from '../lib/property-summary'
import PropertySelector from './PropertySelector'
import React from 'react'

type Feature = {
  id: string
  place_name: string
  text: string
  center?: number[]
  standardized_address?: string
  [key: string]: any
}

type Props = {
  market?: string | null
  isOpen: boolean
  onOpenChange: (nextOpen: boolean) => void
  onSelectProperty: (feature: Feature) => void
}

export default function PropertySelectionCard({
  market,
  isOpen,
  onOpenChange,
  onSelectProperty,
}: Props) {
  const marketHint = market?.trim() ? `Searching within ${market.trim()}` : null

  return (
    <div
      className="assistant-landing-card card"
      role={!isOpen ? 'button' : undefined}
      tabIndex={!isOpen ? 0 : undefined}
      onClick={() => {
        if (!isOpen) {
          onOpenChange(true)
        }
      }}
      onKeyDown={(event) => {
        if (!isOpen && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault()
          onOpenChange(true)
        }
      }}
    >
      <div className={`assistant-landing-property-row${isOpen ? ' is-searching' : ''}`}>
        <div className="assistant-landing-property-copy">
          <div className="assistant-landing-property-icon" aria-hidden="true" />
          <div>
            <div className="assistant-landing-property-label">Set a property (optional)</div>
            <div className="assistant-landing-property-description">
              Enter an address to get location-specific answers
            </div>
          </div>
          {isOpen ? (
            <button
              type="button"
              className="assistant-property-search-cancel"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </button>
          ) : null}
        </div>
        <div className="assistant-landing-property-actions">
          {!isOpen ? (
            <button
              type="button"
              className="button secondary assistant-set-property-button"
              onClick={() => onOpenChange(true)}
            >
              <span className="assistant-set-property-button-icon" aria-hidden="true" />
              Set Property
            </button>
          ) : (
            <div className="assistant-property-search-panel">
              {marketHint ? <div className="assistant-property-search-hint">{marketHint}</div> : null}
              <PropertySelector
                placeholder="Start typing an address..."
                market={market}
                onSelect={(feature) => {
                  const standardizedAddress = feature.place_name || feature.text || ''
                  const { lng, lat } = getMapboxCoordinates(feature)
                  console.log('[Mapbox] address selected for assistant context', {
                    address: standardizedAddress,
                    lng,
                    lat,
                    center: feature.center || null,
                  })
                  onSelectProperty({
                    ...feature,
                    standardized_address: standardizedAddress,
                  })
                  onOpenChange(false)
                }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
