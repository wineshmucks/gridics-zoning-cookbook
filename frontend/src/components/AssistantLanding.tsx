"use client"

import { type PropertySummary } from '../lib/property-summary'
import { AssistantPropertyCard } from './AssistantPropertyCard'
import PropertySelectionCard from './PropertySelectionCard'
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
  market,
  propertySummary,
  propertySummaryLoading,
  propertySummaryError,
  isPropertySearchOpen,
  onPropertySearchOpenChange,
  onSelectPrompt,
  selectedProperty,
  onSelectProperty,
}: {
  customerName: string
  market?: string | null
  propertySummary: PropertySummary | null
  propertySummaryLoading: boolean
  propertySummaryError: string | null
  isPropertySearchOpen: boolean
  onPropertySearchOpenChange: (nextOpen: boolean) => void
  onSelectPrompt: (prompt: string) => void
  selectedProperty: Feature | null
  onSelectProperty: (feature: Feature) => void
}) {
  const hasSelectedProperty = Boolean(selectedProperty)

  return (
    <div className={`assistant-landing${hasSelectedProperty ? ' assistant-landing-has-property' : ''}`}>
      {!hasSelectedProperty || isPropertySearchOpen ? (
        <>
          {!hasSelectedProperty ? (
            <div className="assistant-landing-header">
              <h1>How can I help with zoning today?</h1>
              <p className="muted">Ask a general zoning question or set a property to get answers specific to that location.</p>
            </div>
          ) : null}

          <PropertySelectionCard
            market={market}
            isOpen={isPropertySearchOpen}
            onOpenChange={onPropertySearchOpenChange}
            onSelectProperty={onSelectProperty}
          />

          {!hasSelectedProperty ? (
            <div className="assistant-landing-note muted">Set a property above to get answers about what you can build, setbacks, units, overlays, and more.</div>
          ) : null}
        </>
      ) : (
        <div className="assistant-selected-property-intro">Ask zoning questions about this property.</div>
      )}

      {selectedProperty && !isPropertySearchOpen ? (
        <AssistantPropertyCard
          selectedProperty={selectedProperty}
          propertySummary={propertySummary}
          propertySummaryLoading={propertySummaryLoading}
          propertySummaryError={propertySummaryError}
          onChange={() => onPropertySearchOpenChange(true)}
        />
      ) : null}

      {/* suggestions removed to match design */}
    </div>
  )
}
