"use client"

import { useEffect, useState, useRef } from "react"
import { getMapboxCoordinates } from '../lib/property-summary'

type Feature = {
  id: string
  place_name: string
  text: string
  center?: number[]
  [key: string]: any
}

type Props = {
  placeholder?: string
  onSelect: (feature: Feature) => void
  initial?: Feature | null
  // optional restrictions
  city?: string
  state?: string
  // bbox: [minLng, minLat, maxLng, maxLat]
  bbox?: number[]
}

const MIN_AUTOCOMPLETE_LENGTH = 3

export default function PropertySelector({ placeholder, onSelect, initial, city, state, bbox }: Props) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<Feature[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timeoutRef = useRef<number | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const MAPBOX_TOKEN = (process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "").replace(/^"|"$/g, '').trim()

  const q = query?.trim() || ''

  useEffect(() => {
    // Search after more than 2 characters have been entered.
    if (q.length < MIN_AUTOCOMPLETE_LENGTH) {
      setResults([])
      setError(null)
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    if (timeoutRef.current) {
      window.clearTimeout(timeoutRef.current)
    }
    // debounce
    timeoutRef.current = window.setTimeout(async () => {
      try {
        if (!MAPBOX_TOKEN) {
          console.warn('Mapbox token not configured (NEXT_PUBLIC_MAPBOX_TOKEN)')
          setResults([])
          setError('Mapbox token is not configured.')
          setLoading(false)
          return
        }

        let url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(
          q,
        )}.json?access_token=${encodeURIComponent(MAPBOX_TOKEN)}&autocomplete=true&limit=6&types=address,place,poi&language=en`
        // if bbox provided, add it to restrict results
        if (Array.isArray(bbox) && bbox.length === 4) {
          url += `&bbox=${bbox[0]},${bbox[1]},${bbox[2]},${bbox[3]}`
        }
        const resp = await fetch(url)
        if (!resp.ok) {
          let message = `Mapbox request failed (${resp.status}).`
          try {
            const body = (await resp.json()) as { message?: string }
            if (body?.message) {
              message = `Mapbox request failed (${resp.status}): ${body.message}`
            }
          } catch {
            // Keep the status-only message if Mapbox did not return JSON.
          }
          console.warn(message)
          setResults([])
          setError(message)
          setLoading(false)
          return
        }
        const body = await resp.json()
        const features = Array.isArray(body.features) ? body.features : []
        // if city/state restrictions provided, filter results
        let filtered = features
        if (city || state) {
          const cityLower = (city || '').toLowerCase()
          const stateLower = (state || '').toLowerCase()
          filtered = features.filter((f: Feature) => {
            const pn = (f.place_name || '').toLowerCase()
            if (city && state) {
              // prefer exact inclusion
              if (pn.includes(`${cityLower}`) && pn.includes(`${stateLower}`)) return true
            }
            if (city && pn.includes(cityLower)) return true
            if (state && pn.includes(stateLower)) return true

            // check context array entries from Mapbox
            if (Array.isArray((f as any).context)) {
              for (const c of (f as any).context) {
                const txt = (c.text || c.id || '').toString().toLowerCase()
                if (city && txt === cityLower) return true
                if (state && (txt === stateLower || (c.short_code || '').toString().toLowerCase().endsWith(stateLower))) return true
              }
            }

            return false
          })
        }
        setResults(filtered)
      } catch {
        setResults([])
        setError('Unable to reach Mapbox.')
      } finally {
        setLoading(false)
      }
    }, 220)

    return () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current)
      }
    }
  }, [query, MAPBOX_TOKEN, city, state, bbox])

  useEffect(() => {
    if (initial) {
      setQuery(initial.place_name || initial.text || "")
    }
  }, [initial])

  useEffect(() => {
    inputRef.current?.focus()
    setIsOpen(true)
  }, [])

  return (
    <div className="property-selector">
      <div className="property-selector-input">
        <input
          ref={inputRef}
          type="search"
          aria-label="Search address"
          placeholder={placeholder || 'Start typing an address...'}
          value={query}
          onFocus={() => setIsOpen(true)}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button
          type="button"
          className="property-selector-clear-button"
          aria-label={query ? 'Clear address search' : 'Focus address search'}
          onClick={() => {
            if (query && query.length > 0) {
              setQuery("")
              setResults([])
              setError(null)
              setIsOpen(true)
              if (inputRef.current) inputRef.current.focus()
            } else {
              setIsOpen(true)
              if (inputRef.current) inputRef.current.focus()
            }
          }}
        >
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {isOpen && q.length > 0 ? (
        <div className="property-selector-results card">
          {q.length < MIN_AUTOCOMPLETE_LENGTH ? (
            <div className="muted">Type at least 3 characters to search</div>
          ) : error ? (
            <div className="muted">{error}</div>
          ) : loading ? (
            <div className="muted">Searching…</div>
          ) : !loading && results.length === 0 ? (
            <div className="muted">No results</div>
          ) : (
            results.map((feature: Feature) => (
              <button
                key={feature.id}
                type="button"
                className="property-selector-result"
                onClick={() => {
                  const { lng, lat } = getMapboxCoordinates(feature)
                  console.log('[Mapbox] selected property', {
                    address: feature.place_name,
                    lng,
                    lat,
                    center: feature.center || null,
                  })
                  onSelect(feature)
                  setIsOpen(false)
                }}
              >
                <div className="property-selector-result-line">{feature.place_name}</div>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  )
}
