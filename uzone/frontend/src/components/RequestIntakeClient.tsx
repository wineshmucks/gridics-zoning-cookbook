'use client'

import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'

import { buildApiUrl, fetchJsonWithToken, postJsonWithToken } from '../lib/api'
import { ErrorCard, LoadingCard } from './RemoteState'

type FeeItem = {
  code: string
  name: string
  fee_type: string
  amount_cents: number
  applies_to_letter_type: string | null
  applies_to_processing_type: string | null
  applies_to_delivery_method: string | null
}

type FeesResponse = {
  items: FeeItem[]
}

type MeResponse = {
  local_user_id: string | null
}

type DevIdentities = {
  customer_user_id: string | null
}

type CreatedRequest = {
  id: string
  public_id: string
}

type Parcel = {
  id: string
  source_property_id: string
  group_id: string
  apn: string
  address_line1: string
  city: string
  state: string
  postal_code: string
  zoning_code: string
  zoning_name: string
  lot_size_sf: number
  x: number
  y: number
}

type DetailsFormState = {
  letter_type: 'standard' | 'comprehensive'
  processing_type: 'standard' | 'expedited'
  delivery_method: 'email' | 'mail'
  requester_first_name: string
  requester_last_name: string
  requester_email: string
  requester_phone: string
  requester_organization: string
  mailing_street: string
  mailing_city: string
  mailing_state: string
  mailing_postal_code: string
  special_instructions: string
}

const mockParcels: Parcel[] = [
  {
    id: 'parcel-1',
    source_property_id: '123-main',
    group_id: 'block-a-1',
    apn: '123-456-001',
    address_line1: '123 Main Street',
    city: 'Dream Town',
    state: 'CA',
    postal_code: '94103',
    zoning_code: 'R-1',
    zoning_name: 'Single Family Residential',
    lot_size_sf: 6250,
    x: 48,
    y: 42,
  },
  {
    id: 'parcel-2',
    source_property_id: '125-main',
    group_id: 'block-a-2',
    apn: '123-456-002',
    address_line1: '125 Main Street',
    city: 'Dream Town',
    state: 'CA',
    postal_code: '94103',
    zoning_code: 'R-1',
    zoning_name: 'Single Family Residential',
    lot_size_sf: 6150,
    x: 58,
    y: 36,
  },
  {
    id: 'parcel-3',
    source_property_id: '456-oak',
    group_id: 'block-b-1',
    apn: '123-456-003',
    address_line1: '456 Oak Avenue',
    city: 'Dream Town',
    state: 'CA',
    postal_code: '94105',
    zoning_code: 'C-2',
    zoning_name: 'Neighborhood Commercial',
    lot_size_sf: 8200,
    x: 40,
    y: 58,
  },
  {
    id: 'parcel-4',
    source_property_id: '789-pine',
    group_id: 'block-c-1',
    apn: '123-456-004',
    address_line1: '789 Pine Street',
    city: 'Dream Town',
    state: 'CA',
    postal_code: '94107',
    zoning_code: 'R-2',
    zoning_name: 'Two Family Residential',
    lot_size_sf: 7100,
    x: 70,
    y: 30,
  },
  {
    id: 'parcel-5',
    source_property_id: '321-elm',
    group_id: 'block-d-2',
    apn: '123-456-005',
    address_line1: '321 Elm Drive',
    city: 'Dream Town',
    state: 'CA',
    postal_code: '94108',
    zoning_code: 'M-1',
    zoning_name: 'Light Industrial',
    lot_size_sf: 12000,
    x: 32,
    y: 70,
  },
]

function formatCurrency(amountCents: number) {
  return `$${(amountCents / 100).toFixed(2)}`
}

function IntakeFlow({
  getToken,
  actorUserId,
  clerkMode,
  tenantClientId,
  tenantJurisdictionId,
}: {
  getToken: () => Promise<string | null>
  actorUserId: string | null
  clerkMode: boolean
  tenantClientId: string
  tenantJurisdictionId: string | null
}) {
  const searchParams = useSearchParams()
  const detailsRef = useRef<HTMLElement | null>(null)
  const [fees, setFees] = useState<FeesResponse | null>(null)
  const [addressSearch, setAddressSearch] = useState('')
  const [apnSearch, setApnSearch] = useState('')
  const [showLabels, setShowLabels] = useState(true)
  const [satelliteView, setSatelliteView] = useState(false)
  const [selectedParcelIds, setSelectedParcelIds] = useState<string[]>([])
  const [step, setStep] = useState<1 | 2>(1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [createdRequests, setCreatedRequests] = useState<CreatedRequest[]>([])
  const [form, setForm] = useState<DetailsFormState>({
    letter_type:
      searchParams.get('letter_type') === 'comprehensive' ? 'comprehensive' : 'standard',
    processing_type: 'standard',
    delivery_method: 'email',
    requester_first_name: '',
    requester_last_name: '',
    requester_email: '',
    requester_phone: '',
    requester_organization: '',
    mailing_street: '',
    mailing_city: '',
    mailing_state: '',
    mailing_postal_code: '',
    special_instructions: '',
  })

  useEffect(() => {
    let active = true

    fetch(buildApiUrl(`/api/admin/fees?client_id=${encodeURIComponent(tenantClientId)}`), {
      cache: 'no-store',
    })
      .then(async (feeResponse) => {
        if (!active) {
          return
        }
        const feeData = feeResponse.ok ? ((await feeResponse.json()) as FeesResponse) : { items: [] }
        setFees(feeData)
      })
      .catch(() => {
        if (active) {
          setError('Failed to load parcel selection data.')
          setFees({ items: [] })
        }
      })

    return () => {
      active = false
    }
  }, [tenantClientId])

  const selectedParcels = useMemo(
    () => mockParcels.filter((parcel) => selectedParcelIds.includes(parcel.id)),
    [selectedParcelIds],
  )

  const filteredParcels = useMemo(() => {
    return mockParcels.filter((parcel) => {
      const addressOk =
        !addressSearch.trim() ||
        `${parcel.address_line1} ${parcel.city}`.toLowerCase().includes(addressSearch.toLowerCase())
      const apnOk = !apnSearch.trim() || parcel.apn.toLowerCase().includes(apnSearch.toLowerCase())
      return addressOk && apnOk
    })
  }, [addressSearch, apnSearch])

  const baseLetterFee = useMemo(() => {
    const match = fees?.items.find(
      (item) =>
        item.fee_type === 'base' &&
        item.applies_to_letter_type === form.letter_type &&
        !item.applies_to_processing_type &&
        !item.applies_to_delivery_method,
    )
    return match?.amount_cents ?? (form.letter_type === 'standard' ? 12500 : 32500)
  }, [fees?.items, form.letter_type])

  const rushFee = useMemo(() => {
    const match = fees?.items.find(
      (item) =>
        item.fee_type === 'rush' &&
        item.applies_to_processing_type === 'expedited',
    )
    return match?.amount_cents ?? 5000
  }, [fees?.items])

  const mailFee = useMemo(() => {
    const match = fees?.items.find((item) => item.applies_to_delivery_method === 'mail')
    return match?.amount_cents ?? 0
  }, [fees?.items])

  const estimatedTotal = selectedParcels.length * baseLetterFee +
    (form.processing_type === 'expedited' ? selectedParcels.length * rushFee : 0) +
    (form.delivery_method === 'mail' ? selectedParcels.length * mailFee : 0)

  const mailingAddress =
    form.mailing_street || form.mailing_city || form.mailing_state || form.mailing_postal_code
      ? {
          street: form.mailing_street || null,
          city: form.mailing_city || null,
          state: form.mailing_state || null,
          postal_code: form.mailing_postal_code || null,
        }
      : null

  function toggleParcel(parcelId: string) {
    setSelectedParcelIds((current) =>
      current.includes(parcelId) ? current.filter((id) => id !== parcelId) : [...current, parcelId],
    )
  }

  function continueToDetails() {
    setStep(2)
    requestAnimationFrame(() => {
      detailsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  async function submitRequests(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setCreatedRequests([])

    try {
      if (!actorUserId) {
        throw new Error('Sign in before submitting requests.')
      }
      if (!tenantJurisdictionId) {
        throw new Error('No jurisdiction is configured for the selected tenant.')
      }
      if (selectedParcels.length === 0) {
        throw new Error('Select at least one parcel before continuing.')
      }

      const created: CreatedRequest[] = []

      for (const parcel of selectedParcels) {
        const property = await postJsonWithToken<{ id: string }>(
          '/api/properties',
          {
            jurisdiction_id: tenantJurisdictionId,
            source_system: 'parcel_selection',
            source_property_id: parcel.source_property_id,
            group_id: parcel.group_id,
            apn: parcel.apn,
            address_line1: parcel.address_line1,
            address_line2: null,
            city: parcel.city,
            state: parcel.state,
            postal_code: parcel.postal_code,
            latitude: null,
            longitude: null,
          },
          getToken,
        )
        if (!property?.id) {
          throw new Error(`Property creation failed for ${parcel.address_line1}.`)
        }

        const snapshot = await postJsonWithToken<{ id: string }>(
          `/api/properties/${property.id}/snapshots`,
          {
            property_id: property.id,
            captured_by_user_id: clerkMode ? null : actorUserId,
            capture_reason: 'parcel_selection',
            address: `${parcel.address_line1}, ${parcel.city}, ${parcel.state} ${parcel.postal_code}`,
            apn: parcel.apn,
            group_id: parcel.group_id,
            zoning_code: parcel.zoning_code,
            zoning_name: parcel.zoning_name,
            lot_size_sf: parcel.lot_size_sf,
            permitted_uses_json: null,
            restrictions_json: null,
            overlays_json: null,
            raw_source_payload_json: {
              source_property_id: parcel.source_property_id,
              selection_mode: 'map',
            },
            source_payload_hash: null,
          },
          getToken,
        )
        if (!snapshot?.id) {
          throw new Error(`Property snapshot creation failed for ${parcel.address_line1}.`)
        }

        const request = await postJsonWithToken<CreatedRequest>(
          '/api/requests',
          {
            jurisdiction_id: tenantJurisdictionId,
            requester_user_id: actorUserId,
            property_id: property.id,
            property_snapshot_id: snapshot.id,
            letter_type: form.letter_type,
            processing_type: form.processing_type,
            delivery_method: form.delivery_method,
            requester_first_name: form.requester_first_name.trim(),
            requester_last_name: form.requester_last_name.trim(),
            requester_email: form.requester_email.trim(),
            requester_phone: form.requester_phone.trim() || null,
            requester_organization: form.requester_organization.trim() || null,
            mailing_address_json: mailingAddress,
            special_instructions: form.special_instructions.trim() || null,
          },
          getToken,
        )
        if (!request?.id) {
          throw new Error(`Request creation failed for ${parcel.address_line1}.`)
        }
        created.push(request)
      }

      setCreatedRequests(created)
      setSelectedParcelIds([])
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'Request creation failed.')
    } finally {
      setBusy(false)
    }
  }

  if (error && !fees) {
    return <ErrorCard title="Select Property" message={error} />
  }
  if (!fees) {
    return <LoadingCard title="Select Property" />
  }

  return (
    <div className="request-flow">
      <section className="progress-section">
        <div className="home-container">
          <div className="progress-steps">
            {[
              ['1', 'Select Property', 'Choose parcels for verification'],
              ['2', 'Account', 'Sign in or create account'],
              ['3', 'Request Details', 'Complete request form'],
              ['4', 'Payment', 'Review and pay'],
            ].map(([index, title, subtitle], itemIndex) => {
              const active = step === 1 ? itemIndex === 0 : itemIndex === 1
              return (
                <div key={title} className="progress-step-wrap">
                  <div className={`progress-step ${active ? 'is-active' : 'is-muted'}`}>
                    <div className="progress-step-number">{index}</div>
                    <div>
                      <p>{title}</p>
                      <span>{subtitle}</span>
                    </div>
                  </div>
                  {itemIndex < 3 ? <div className="progress-line" /> : null}
                </div>
              )
            })}
          </div>
        </div>
      </section>

      <section className="request-section">
        <div className="home-container">
          {error ? <p className="form-error">{error}</p> : null}
          {createdRequests.length > 0 ? (
            <div className="success-banner">
              Created {createdRequests.length} request{createdRequests.length > 1 ? 's' : ''}:{' '}
              {createdRequests.map((request, index) => (
                <span key={request.id}>
                  {index > 0 ? ', ' : ''}
                  <Link href={`/requests/${request.public_id}`}>{request.public_id}</Link>
                </span>
              ))}
              . Continue in <Link href="/account/requests">Account Requests</Link>.
            </div>
          ) : null}

          <div className="request-layout">
            <div className="map-column">
              <div className="selection-card">
                <div className="selection-card-header">
                  <h2>Select Property on Map</h2>
                  <p>Search by address or parcel number, then click on the map to select</p>
                </div>

                <div className="selection-toolbar">
                  <div className="search-row">
                    <label className="search-field">
                      <span>Address search</span>
                      <input
                        value={addressSearch}
                        onChange={(event) => setAddressSearch(event.target.value)}
                        placeholder="Search by address (e.g., 123 Main Street)"
                      />
                    </label>
                    <label className="search-field">
                      <span>APN search</span>
                      <input
                        value={apnSearch}
                        onChange={(event) => setApnSearch(event.target.value)}
                        placeholder="Search by APN (e.g., 123-456-789)"
                      />
                    </label>
                    <button className="button search-button" type="button">
                      Search
                    </button>
                  </div>

                  <div className="map-options">
                    <label>
                      <input
                        type="checkbox"
                        checked={satelliteView}
                        onChange={(event) => setSatelliteView(event.target.checked)}
                      />
                      Satellite View
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={showLabels}
                        onChange={(event) => setShowLabels(event.target.checked)}
                      />
                      Show Labels
                    </label>
                    <button className="ghost-link" type="button">
                      Use My Location
                    </button>
                  </div>
                </div>

                <div className={`parcel-map ${satelliteView ? 'is-satellite' : ''}`}>
                  <div className="parcel-map-grid" />
                  {filteredParcels.map((parcel) => {
                    const selected = selectedParcelIds.includes(parcel.id)
                    return (
                      <button
                        key={parcel.id}
                        className={`parcel-marker ${selected ? 'is-selected' : ''}`}
                        style={{ left: `${parcel.x}%`, top: `${parcel.y}%` }}
                        onClick={() => toggleParcel(parcel.id)}
                        type="button"
                      >
                        {showLabels ? <span>{parcel.address_line1}</span> : null}
                      </button>
                    )
                  })}
                </div>

                <div className="map-footer">
                  <div className="map-legend">
                    <span className="legend-item">
                      <i className="legend-dot legend-selected" />
                      Selected Parcel
                    </span>
                    <span className="legend-item">
                      <i className="legend-dot legend-available" />
                      Available Parcel
                    </span>
                  </div>
                  <div className="button-row">
                    <button className="secondary button map-footer-button" type="button">
                      Fullscreen
                    </button>
                    <button className="secondary button map-footer-button" type="button">
                      Print Map
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div className="selection-side">
              <div className="selection-panel">
                <div className="selection-panel-header">
                  <h3>Selected Properties</h3>
                  <p>
                    <strong>{selectedParcels.length}</strong> parcels selected
                  </p>
                </div>

                <div className="selected-list">
                  {selectedParcels.length === 0 ? (
                    <div className="selection-empty">
                      <div className="selection-empty-icon">⌖</div>
                      <p>No properties selected yet</p>
                      <span>Click on the map to select parcels</span>
                    </div>
                  ) : (
                    selectedParcels.map((parcel) => (
                      <div key={parcel.id} className="selected-parcel-card">
                        <div className="selected-parcel-head">
                          <div>
                            <p>{parcel.address_line1}</p>
                            <span>APN: {parcel.apn}</span>
                            <span>Zoning: {parcel.zoning_code}</span>
                          </div>
                          <button
                            className="remove-parcel"
                            onClick={() => toggleParcel(parcel.id)}
                            type="button"
                          >
                            ×
                          </button>
                        </div>
                        <div className="selected-parcel-fee">
                          <span>
                            {form.letter_type === 'standard'
                              ? 'Standard Letter'
                              : 'Comprehensive Letter'}
                          </span>
                          <strong>{formatCurrency(baseLetterFee)}</strong>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                <div className="selection-panel-footer">
                  <div className="selection-total">
                    <span>Estimated Total</span>
                    <strong>{formatCurrency(estimatedTotal || 0)}</strong>
                  </div>
                  <button
                    className={`continue-button ${selectedParcels.length === 0 ? 'is-disabled' : ''}`}
                    disabled={selectedParcels.length === 0}
                    onClick={continueToDetails}
                    type="button"
                  >
                    Continue to Account
                  </button>
                  <p>You&apos;ll review pricing details in the next step</p>
                </div>
              </div>

              <div className="selection-tips">
                <h4>Selection Tips</h4>
                <ul>
                  <li>Click parcels on the map to select them</li>
                  <li>You can select multiple properties at once</li>
                  <li>Use search to quickly find specific addresses</li>
                  <li>Each property requires a separate letter fee</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section ref={detailsRef} className="request-section request-details-section">
        <div className="home-container">
          <div className="card">
            <div className="stack-header">
              <div>
                <h2 className="section-title">Account and Request Details</h2>
                <p className="subtitle" style={{ marginBottom: 0, fontSize: 16 }}>
                  Complete the request for {selectedParcels.length || 0} selected parcel
                  {selectedParcels.length === 1 ? '' : 's'}.
                </p>
              </div>
              <Link className="button secondary" href="/account/requests">
                View account queue
              </Link>
            </div>

            <form className="intake-form" onSubmit={submitRequests}>
              <section className="form-section">
                <h2>Letter options</h2>
                <div className="form-grid">
                  <label>
                    Letter type
                    <select
                      value={form.letter_type}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          letter_type: event.target.value as DetailsFormState['letter_type'],
                        }))
                      }
                    >
                      <option value="standard">Standard</option>
                      <option value="comprehensive">Comprehensive</option>
                    </select>
                  </label>
                  <label>
                    Processing
                    <select
                      value={form.processing_type}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          processing_type: event.target.value as DetailsFormState['processing_type'],
                        }))
                      }
                    >
                      <option value="standard">Standard</option>
                      <option value="expedited">Expedited</option>
                    </select>
                  </label>
                  <label>
                    Delivery method
                    <select
                      value={form.delivery_method}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          delivery_method: event.target.value as DetailsFormState['delivery_method'],
                        }))
                      }
                    >
                      <option value="email">Email</option>
                      <option value="mail">Mail</option>
                    </select>
                  </label>
                </div>
              </section>

              <section className="form-section">
                <h2>Requester information</h2>
                <div className="form-grid">
                  <label>
                    First name
                    <input
                      required
                      value={form.requester_first_name}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, requester_first_name: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Last name
                    <input
                      required
                      value={form.requester_last_name}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, requester_last_name: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Email
                    <input
                      required
                      type="email"
                      value={form.requester_email}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, requester_email: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Phone
                    <input
                      value={form.requester_phone}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, requester_phone: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Organization
                    <input
                      value={form.requester_organization}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          requester_organization: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
              </section>

              <section className="form-section">
                <h2>Mailing and notes</h2>
                <div className="form-grid">
                  <label>
                    Mailing street
                    <input
                      value={form.mailing_street}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, mailing_street: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Mailing city
                    <input
                      value={form.mailing_city}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, mailing_city: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Mailing state
                    <input
                      value={form.mailing_state}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, mailing_state: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Mailing postal code
                    <input
                      value={form.mailing_postal_code}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, mailing_postal_code: event.target.value }))
                      }
                    />
                  </label>
                  <label className="full-span">
                    Special instructions
                    <textarea
                      rows={5}
                      value={form.special_instructions}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, special_instructions: event.target.value }))
                      }
                    />
                  </label>
                </div>
              </section>

              <div className="button-row">
                <button
                  className="button"
                  type="submit"
                  disabled={busy || selectedParcels.length === 0 || !actorUserId}
                >
                  {busy ? 'Creating requests...' : 'Create requests'}
                </button>
                <button className="button secondary" onClick={() => setStep(1)} type="button">
                  Back to parcel selection
                </button>
              </div>
            </form>
          </div>
        </div>
      </section>
    </div>
  )
}

function ClerkRequestIntake({
  tenantClientId,
  tenantJurisdictionId,
}: {
  tenantClientId: string
  tenantJurisdictionId: string | null
}) {
  const { getToken, isSignedIn } = useAuth()
  const [localUserId, setLocalUserId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function run() {
      if (!isSignedIn) {
        if (active) {
          setLoading(false)
        }
        return
      }
      const me = await fetchJsonWithToken<MeResponse>('/api/auth/me', async () =>
        isSignedIn ? getToken() : null,
      )
      if (!active) {
        return
      }
      if (!me?.local_user_id) {
        setError('Unable to resolve the signed-in Clerk user in the backend.')
      } else {
        setLocalUserId(me.local_user_id)
      }
      setLoading(false)
    }

    run().catch(() => {
      if (active) {
        setError('Failed to load Clerk identity.')
        setLoading(false)
      }
    })

    return () => {
      active = false
    }
  }, [getToken, isSignedIn])

  if (!isSignedIn) {
    return (
      <ErrorCard
        title="Select Property"
        message="Sign in with Clerk before submitting zoning verification requests."
      />
    )
  }
  if (loading) {
    return <LoadingCard title="Select Property" />
  }
  if (error) {
    return <ErrorCard title="Select Property" message={error} />
  }

  return (
    <IntakeFlow
      getToken={async () => (isSignedIn ? getToken() : null)}
      actorUserId={localUserId}
      clerkMode
      tenantClientId={tenantClientId}
      tenantJurisdictionId={tenantJurisdictionId}
    />
  )
}

function LocalRequestIntake({
  tenantClientId,
  tenantJurisdictionId,
}: {
  tenantClientId: string
  tenantJurisdictionId: string | null
}) {
  const [localUserId, setLocalUserId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    fetch(buildApiUrl('/api/dev/identities'), { cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : null))
      .then((data: DevIdentities | null) => {
        if (!active) {
          return
        }
        setLocalUserId(data?.customer_user_id || null)
        if (!data?.customer_user_id) {
          setError('No local customer identity is available.')
        }
        setLoading(false)
      })
      .catch(() => {
        if (active) {
          setError('Failed to load local requester identity.')
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [])

  if (loading) {
    return <LoadingCard title="Select Property" />
  }
  if (error) {
    return <ErrorCard title="Select Property" message={error} />
  }

  return (
    <IntakeFlow
      getToken={async () => null}
      actorUserId={localUserId}
      clerkMode={false}
      tenantClientId={tenantClientId}
      tenantJurisdictionId={tenantJurisdictionId}
    />
  )
}

export function RequestIntakeClient({
  clerkEnabled,
  tenantClientId,
  tenantJurisdictionId,
}: {
  clerkEnabled: boolean
  tenantClientId: string
  tenantJurisdictionId: string | null
}) {
  return clerkEnabled ? (
    <ClerkRequestIntake tenantClientId={tenantClientId} tenantJurisdictionId={tenantJurisdictionId} />
  ) : (
    <LocalRequestIntake tenantClientId={tenantClientId} tenantJurisdictionId={tenantJurisdictionId} />
  )
}
