"use client"

import PropertySelector from './PropertySelector'
import React from 'react'

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
  return (
    <div className="assistant-landing">
      <div className="topbar topbar-public">
        <div className="brand">
          <div className="brand-mark brand-mark-has-image" aria-hidden>
            {/* placeholder for city seal/logo */}
            <img src="/public/logos/miami-seal.png" alt="" style={{ width: 40, height: 40, borderRadius: 8 }} />
          </div>
          <div className="brand-copy">
            <div className="brand-title">Zoning Assistant</div>
            <div className="brand-subtitle">City of Miami, FL</div>
          </div>
        </div>

        <div className="topbar-actions">
          <button className="button secondary" type="button" aria-label="Toggle theme">☀️</button>
          <button className="button" type="button" aria-label="Help">?</button>
          <button className="button" type="button">New Chat</button>
          <button className="button secondary" type="button" aria-label="User">
            <img src="/public/logos/avatar-placeholder.png" alt="User" style={{ width: 28, height: 28, borderRadius: 14 }} />
          </button>
        </div>
      </div>

      <div className="assistant-landing-header">
        <h1>How can I help with zoning today?</h1>
        <p className="muted">Ask a general zoning question or set a property to get answers specific to that location.</p>
      </div>

      <div className="assistant-landing-card card">
        <div className="assistant-landing-property-row">
          <div className="assistant-landing-property-label">Set a property (optional)</div>
          <div className="assistant-landing-property-actions">
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
                  <div className="assistant-property-card-address">{selectedProperty.place_name}</div>
                  {/* chips intentionally removed to match design */}
                </div>

                <div className="assistant-property-actions">
                  <button
                    type="button"
                    className="button"
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
                    View on Map
                  </button>
                  <button type="button" className="button secondary" onClick={onClearProperty}>
                    Change
                  </button>
                </div>
              </div>
            ) : (
              <PropertySelector
                placeholder="Start typing an address..."
                onSelect={(f) => onSelectProperty(f)}
              />
            )}
          </div>
        </div>

        <div className="assistant-landing-note muted">Set a property above to get answers about what you can build, setbacks, units, overlays, and more.</div>
      </div>

      {/* suggestions removed to match design */}
    </div>
  )
}
