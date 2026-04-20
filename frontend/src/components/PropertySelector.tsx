"use client"

import { useEffect, useState, useRef } from "react"

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
}

export default function PropertySelector({ placeholder, onSelect, initial }: Props) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<Feature[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const timeoutRef = useRef<number | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const MAPBOX_TOKEN = (process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "").trim()

  useEffect(() => {
    if (!query || query.trim().length < 2) {
      setResults([])
      return
    }

    setLoading(true)
    if (timeoutRef.current) {
      window.clearTimeout(timeoutRef.current)
    }
    // debounce
    timeoutRef.current = window.setTimeout(async () => {
      try {
        const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(
          query,
        )}.json?access_token=${encodeURIComponent(MAPBOX_TOKEN)}&autocomplete=true&limit=6&types=address,place,poi&language=en`
        const resp = await fetch(url)
        if (!resp.ok) {
          setResults([])
          setLoading(false)
          return
        }
        const body = await resp.json()
        const features = Array.isArray(body.features) ? body.features : []
        setResults(features)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 220)

    return () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current)
      }
    }
  }, [query, MAPBOX_TOKEN])

  useEffect(() => {
    if (initial) {
      setQuery(initial.place_name || initial.text || "")
    }
  }, [initial])

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
          className="button secondary"
          onClick={() => {
            if (query && query.length > 0) {
              setQuery("")
              setResults([])
              setIsOpen(false)
            } else {
              setIsOpen(true)
              if (inputRef.current) inputRef.current.focus()
            }
          }}
        >
          {query && query.length > 0 ? 'Clear' : 'Set Property'}
        </button>
      </div>

      {isOpen ? (
        <div className="property-selector-results card">
          {loading ? <div className="muted">Searching…</div> : null}
          {!loading && results.length === 0 ? (
            <div className="muted">No results</div>
          ) : (
            results.map((feature: Feature) => (
              <button
                key={feature.id}
                type="button"
                className="property-selector-result"
                onClick={() => {
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
