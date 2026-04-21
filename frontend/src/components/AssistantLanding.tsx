"use client"

import {
  buildPropertySummaryChips,
  buildPropertySummaryUrl,
  getMapboxCoordinates,
  type MapboxFeature,
  type PropertySummary,
} from '../lib/property-summary'
import PropertySelector from './PropertySelector'
import React, { useEffect, useState } from 'react'

const SUGGESTED_PROMPTS = [
  'What can I build on this lot?',
  'What are the setback requirements?',
  'Is an ADU allowed here?',
  'What parking is required?',
  'Explain this zoning district',
  'What overlays apply?',
]

type Feature = {
  id: string
  place_name: string
  text: string
  center?: number[]
  [key: string]: any
}

export default function AssistantLanding({
  customerName,
  onSelectPrompt,
  selectedProperty,
  onSelectProperty,
  onClearProperty,
}: {
  customerName: string
  onSelectPrompt: (prompt: string) => void
  selectedProperty: Feature | null
  onSelectProperty: (feature: Feature) => void
  onClearProperty: () => void
}) {
  const MAPBOX_TOKEN = (process.env.NEXT_PUBLIC_MAPBOX_TOKEN || '').replace(/^"|"$/g, '')
  const [isPropertySearchOpen, setIsPropertySearchOpen] = useState(false)
  const [propertySummary, setPropertySummary] = useState<PropertySummary | null>(null)
  const [propertySummaryLoading, setPropertySummaryLoading] = useState(false)
  const [propertySummaryError, setPropertySummaryError] = useState<string | null>(null)

  function buildStaticMapUrl(center?: number[] | undefined) {
    if (!center || center.length < 2 || !MAPBOX_TOKEN) return null
    const [lng, lat] = center
    const marker = `pin-s+2563eb(${lng},${lat})`
    const zoom = 15
    const size = '320x120@2x'
    return `https://api.mapbox.com/styles/v1/mapbox/streets-v11/static/${encodeURIComponent(marker)}/${lng},${lat},${zoom},0,0/${size}?access_token=${encodeURIComponent(
      MAPBOX_TOKEN,
    )}`
  }

  const mapImageUrl = selectedProperty ? buildStaticMapUrl(selectedProperty.center) : null

  useEffect(() => {
    if (!selectedProperty?.center || selectedProperty.center.length < 2) {
      setPropertySummary(null)
      setPropertySummaryLoading(false)
      setPropertySummaryError(null)
      return
    }

    const { lng, lat } = getMapboxCoordinates(selectedProperty)
    console.log('[Mapbox] selected property coordinates', {
      address: selectedProperty.place_name,
      lng,
      lat,
      center: selectedProperty.center,
    })

    const controller = new AbortController()
    const summaryUrl = buildPropertySummaryUrl(selectedProperty as MapboxFeature)
    if (!summaryUrl) return

    setPropertySummaryLoading(true)
    setPropertySummaryError(null)
    fetch(summaryUrl, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          let message = `Gridics summary request failed (${response.status}).`
          try {
            const body = (await response.json()) as { detail?: string }
            if (body?.detail) message = body.detail
          } catch {
            // Keep the status-only message when the API does not return JSON.
          }
          throw new Error(message)
        }
        return response.json() as Promise<PropertySummary>
      })
      .then((summary) => {
        console.log('[Gridics] property card API response', {
          url: summaryUrl,
          summary,
        })
        console.log('[Gridics] property summary', summary)
        setPropertySummary(summary)
      })
      .catch((error) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        const message = error instanceof Error ? error.message : 'Unable to load Gridics property summary.'
        console.warn('[Gridics] property summary failed', message)
        setPropertySummary(null)
        setPropertySummaryError(message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setPropertySummaryLoading(false)
      })

    return () => controller.abort()
  }, [selectedProperty])

  const propertyChips = buildPropertySummaryChips(propertySummary)
  const hasSelectedProperty = Boolean(selectedProperty)

  return (
    <div className={`assistant-landing${hasSelectedProperty ? ' assistant-landing-has-property' : ''}`}>
      {!hasSelectedProperty ? (
        <>
          <div className="assistant-landing-header">
            <h1>How can I help with zoning today?</h1>
            <p className="muted">Ask a general zoning question or set a property to get answers specific to that location.</p>
          </div>

          <div
            className="assistant-landing-card card"
            role={!isPropertySearchOpen ? 'button' : undefined}
            tabIndex={!isPropertySearchOpen ? 0 : undefined}
            onClick={() => {
              if (!isPropertySearchOpen) {
                setIsPropertySearchOpen(true)
              }
            }}
            onKeyDown={(event) => {
              if (!isPropertySearchOpen && (event.key === 'Enter' || event.key === ' ')) {
                event.preventDefault()
                setIsPropertySearchOpen(true)
              }
            }}
          >
            <div className={`assistant-landing-property-row${isPropertySearchOpen ? ' is-searching' : ''}`}>
              <div className="assistant-landing-property-copy">
                <div className="assistant-landing-property-icon" aria-hidden="true" />
                <div>
                  <div className="assistant-landing-property-label">Set a property (optional)</div>
                  <div className="assistant-landing-property-description">
                    Enter an address to get location-specific answers
                  </div>
                </div>
                {isPropertySearchOpen ? (
                  <button
                    type="button"
                    className="assistant-property-search-cancel"
                    onClick={() => setIsPropertySearchOpen(false)}
                  >
                    Cancel
                  </button>
                ) : null}
              </div>
              <div className="assistant-landing-property-actions">
                {!isPropertySearchOpen ? (
                  <button
                    type="button"
                    className="button secondary assistant-set-property-button"
                    onClick={() => setIsPropertySearchOpen(true)}
                  >
                    <span className="assistant-set-property-button-icon" aria-hidden="true" />
                    Set Property
                  </button>
                ) : (
                  <div className="assistant-property-search-panel">
                    <PropertySelector
                      placeholder="Start typing an address..."
                      onSelect={(f) => {
                        const { lng, lat } = getMapboxCoordinates(f)
                        console.log('[Mapbox] address selected for assistant context', {
                          address: f.place_name,
                          lng,
                          lat,
                          center: f.center || null,
                        })
                        onSelectProperty(f)
                        setIsPropertySearchOpen(false)
                      }}
                      city="Miami"
                      state="FL"
                    />
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="assistant-landing-note muted">Set a property above to get answers about what you can build, setbacks, units, overlays, and more.</div>
        </>
      ) : (
        <div className="assistant-selected-property-intro">Ask zoning questions about this property.</div>
      )}

      {selectedProperty ? (
        <div className="assistant-property-card">
          <div className="assistant-property-thumb">
            {mapImageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={mapImageUrl} alt={`Map of ${selectedProperty.place_name}`} loading="lazy" />
            ) : (
              <div className="assistant-property-thumb-placeholder" />
            )}
            {mapImageUrl ? <div className="assistant-property-thumb-marker" aria-hidden="true" /> : null}
          </div>

          <div className="assistant-property-content">
            <div className="assistant-property-title-row">
              <span className="assistant-property-location-icon" aria-hidden="true" />
              <div className="assistant-property-card-address">{propertySummary?.address || selectedProperty.place_name}</div>
              <button
                type="button"
                className="assistant-property-change-link"
                onClick={() => {
                  onClearProperty()
                  setIsPropertySearchOpen(true)
                }}
              >
                Change
              </button>
            </div>
            {propertySummaryLoading ? (
              <div className="assistant-property-summary-status">Loading Gridics parcel summary...</div>
            ) : propertyChips.length > 0 ? (
              <div className="assistant-property-chips" aria-label="Gridics parcel summary">
                {propertyChips.slice(0, 5).map((chip) => (
                  <span key={chip} className="assistant-property-chip">{chip}</span>
                ))}
              </div>
            ) : propertySummaryError ? (
              <div className="assistant-property-summary-status">Gridics summary unavailable</div>
            ) : null}
          </div>

          <div className="assistant-property-actions">
            <button
              type="button"
              className="button secondary assistant-property-map-button"
              onClick={() => {
                if (selectedProperty.center && selectedProperty.center.length >= 2) {
                  const [lng, lat] = selectedProperty.center
                  window.open(`https://www.google.com/maps/search/?api=1&query=${lat},${lng}`, '_blank')
                } else {
                  window.open(`https://www.google.com/maps/search/${encodeURIComponent(
                    selectedProperty.place_name,
                  )}`, '_blank')
                }
              }}
            >
              <span className="assistant-property-map-icon" aria-hidden="true" />
              View on Map
            </button>
          </div>
        </div>
      ) : null}

      {/* suggestions removed to match design */}
    </div>
  )
}
