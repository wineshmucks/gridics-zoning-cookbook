'use client'

import { useEffect, useMemo, useState, useTransition } from 'react'

import type { AdminFeeStructureItem, AdminFeeStructurePayload } from '../app/admin/actions'
import { fetchAdminFeeStructureAction, saveAdminFeeStructureAction } from '../app/admin/actions'
import { AdminSectionTitle } from './AdminSectionTitle'

type EditableFeeItem = AdminFeeStructureItem & {
  description: string
  metadata_json: Record<string, string | number | boolean | null>
}

const SECTION_ORDER: Array<EditableFeeItem['category']> = [
  'base_fees',
  'expedited_fees',
  'additional_services',
  'general',
]

const SECTION_LABELS: Record<EditableFeeItem['category'], string> = {
  base_fees: 'Base Fees',
  expedited_fees: 'Expedited Fees',
  additional_services: 'Additional Services',
  general: 'Other Fees',
}

const SECTION_TABS: Array<{
  key: EditableFeeItem['category'] | 'fee_history'
  label: string
}> = [
  { key: 'base_fees', label: 'Standard Fees' },
  { key: 'expedited_fees', label: 'Expedited Fees' },
  { key: 'additional_services', label: 'Additional Services' },
  { key: 'fee_history', label: 'Fee History' },
]

function formatCurrency(amountCents: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amountCents / 100)
}

function moneyToCents(value: string) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < 0) {
    return 0
  }
  return Math.round(parsed * 100)
}

function centsToMoney(value: number) {
  return (value / 100).toFixed(2)
}

function normalizePayload(payload: AdminFeeStructurePayload): AdminFeeStructurePayload {
  return {
    ...payload,
    items: payload.items
      .slice()
      .sort((left, right) => left.display_order - right.display_order || left.name.localeCompare(right.name)),
  }
}

function toEditableItem(item: AdminFeeStructureItem): EditableFeeItem {
  return {
    ...item,
    description: item.description || '',
    metadata_json: { ...(item.metadata_json || {}) },
  }
}

function getStringMeta(item: EditableFeeItem, key: string, fallback = '') {
  const value = item.metadata_json[key]
  return typeof value === 'string' ? value : fallback
}

function getNumberMeta(item: EditableFeeItem, key: string, fallback = 0) {
  const value = item.metadata_json[key]
  return typeof value === 'number' ? value : fallback
}

function FeeCard({
  item,
  onChange,
}: {
  item: EditableFeeItem
  onChange: (item: EditableFeeItem) => void
}) {
  function update(partial: Partial<EditableFeeItem>) {
    onChange({ ...item, ...partial })
  }

  function updateMeta(key: string, value: string | number | boolean | null) {
    onChange({
      ...item,
      metadata_json: {
        ...item.metadata_json,
        [key]: value,
      },
    })
  }

  return (
    <article className={`card fee-structure-card${item.is_active ? '' : ' is-muted'}`}>
      <div className="fee-structure-card-head">
        <div>
          <h3 className="admin-section-title">{item.name}</h3>
          <p className="admin-copy">
            {item.applies_to_letter_type
              ? `Applies to ${item.applies_to_letter_type} letters`
              : item.applies_to_processing_type
                ? `Applies to ${item.applies_to_processing_type} processing`
                : item.applies_to_delivery_method
                  ? `Applies to ${item.applies_to_delivery_method} delivery`
                  : 'Available as a configurable fee item'}
          </p>
        </div>
        <label className="fee-toggle">
          <span>{item.is_active ? 'Enabled' : 'Disabled'}</span>
          <input
            type="checkbox"
            checked={item.is_active}
            onChange={(event) => update({ is_active: event.target.checked })}
          />
        </label>
      </div>

      <div className="fee-structure-grid">
        <label className="field">
          Fee name
          <input value={item.name} onChange={(event) => update({ name: event.target.value })} />
        </label>
        <label className="field">
          Amount
          <input
            type="number"
            min="0"
            step="0.01"
            value={centsToMoney(item.amount_cents)}
            onChange={(event) => update({ amount_cents: moneyToCents(event.target.value) })}
          />
        </label>
        <label className="field full-span">
          Description
          <textarea
            rows={2}
            value={item.description}
            onChange={(event) => update({ description: event.target.value })}
          />
        </label>

        {(item.code === 'standard_letter' || item.code === 'comprehensive_letter') && (
          <>
            <label className="field">
              Processing time
              <input
                value={getStringMeta(item, 'processing_time_label')}
                onChange={(event) => updateMeta('processing_time_label', event.target.value)}
              />
            </label>
            <label className="field">
              Tax label
              <input
                value={getStringMeta(item, 'tax_label')}
                onChange={(event) => updateMeta('tax_label', event.target.value)}
              />
            </label>
          </>
        )}

        {item.code === 'rush_processing' && (
          <>
            <label className="field">
              Processing time
              <input
                value={getStringMeta(item, 'processing_time_label')}
                onChange={(event) => updateMeta('processing_time_label', event.target.value)}
              />
            </label>
            <label className="field">
              Availability
              <input
                value={getStringMeta(item, 'availability_label')}
                onChange={(event) => updateMeta('availability_label', event.target.value)}
              />
            </label>
          </>
        )}

        {item.code === 'certified_copy' && (
          <>
            <label className="field">
              Max quantity
              <input
                type="number"
                min="0"
                value={String(getNumberMeta(item, 'max_quantity', 0))}
                onChange={(event) => updateMeta('max_quantity', Number(event.target.value || 0))}
              />
            </label>
            <label className="field">
              Bulk discount label
              <input
                value={getStringMeta(item, 'bulk_discount_label')}
                onChange={(event) => updateMeta('bulk_discount_label', event.target.value)}
              />
            </label>
          </>
        )}

        {item.code === 'physical_mail_delivery' && (
          <>
            <label className="field">
              Delivery method
              <input
                value={getStringMeta(item, 'delivery_method_label')}
                onChange={(event) => updateMeta('delivery_method_label', event.target.value)}
              />
            </label>
            <label className="field">
              International fee
              <input
                type="number"
                min="0"
                step="0.01"
                value={centsToMoney(getNumberMeta(item, 'international_amount_cents', 0))}
                onChange={(event) =>
                  updateMeta('international_amount_cents', moneyToCents(event.target.value))
                }
              />
            </label>
          </>
        )}
      </div>
    </article>
  )
}

export function AdminFeeStructureClient({
  initialPayload,
}: {
  initialPayload: AdminFeeStructurePayload
}) {
  const normalizedInitial = useMemo(() => normalizePayload(initialPayload), [initialPayload])
  const [payload, setPayload] = useState(normalizedInitial)
  const [scheduleName, setScheduleName] = useState(normalizedInitial.schedule.name)
  const [items, setItems] = useState<EditableFeeItem[]>(normalizedInitial.items.map(toEditableItem))
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activePanel, setActivePanel] = useState<'summary' | 'calculator' | null>(null)
  const [activeTab, setActiveTab] = useState<EditableFeeItem['category'] | 'fee_history'>('base_fees')
  const [isPending, startTransition] = useTransition()

  useEffect(() => {
    const nextPayload = normalizePayload(initialPayload)
    setPayload(nextPayload)
    setScheduleName(nextPayload.schedule.name)
    setItems(nextPayload.items.map(toEditableItem))
  }, [initialPayload])

  const groupedItems = useMemo(() => {
    return SECTION_ORDER.map((category) => ({
      category,
      label: SECTION_LABELS[category],
      items: items.filter((item) => item.category === category),
    })).filter((group) => group.items.length > 0)
  }, [items])
  const selectedGroup = groupedItems.find((group) => group.category === activeTab) || groupedItems[0] || null

  const activeItems = useMemo(() => items.filter((item) => item.is_active), [items])
  const standardFee = activeItems.find((item) => item.code === 'standard_letter')?.amount_cents || 0
  const comprehensiveFee =
    activeItems.find((item) => item.code === 'comprehensive_letter')?.amount_cents || 0
  const rushFee = activeItems.find((item) => item.code === 'rush_processing')?.amount_cents || 0
  const copyFee = activeItems.find((item) => item.code === 'certified_copy')?.amount_cents || 0
  const mailFee = activeItems.find((item) => item.code === 'physical_mail_delivery')?.amount_cents || 0
  const mailItem = items.find((item) => item.code === 'physical_mail_delivery') || null
  const internationalMailFee = mailItem ? getNumberMeta(mailItem, 'international_amount_cents', 0) : 0

  const summaryExamples = useMemo(
    () => ({
      standardMail: standardFee + mailFee,
      rushCopyMail: standardFee + rushFee + copyFee + mailFee,
      comprehensiveRushMail: comprehensiveFee + rushFee + mailFee,
    }),
    [comprehensiveFee, copyFee, mailFee, rushFee, standardFee],
  )

  const [calculatorLetterType, setCalculatorLetterType] = useState<'standard' | 'comprehensive'>('standard')
  const [calculatorProcessing, setCalculatorProcessing] = useState<'standard' | 'expedited'>('standard')
  const [calculatorCopies, setCalculatorCopies] = useState(0)
  const [calculatorDelivery, setCalculatorDelivery] = useState<'digital' | 'mail' | 'international'>('digital')

  const calculatorBase = calculatorLetterType === 'standard' ? standardFee : comprehensiveFee
  const calculatorRush = calculatorProcessing === 'expedited' ? rushFee : 0
  const calculatorCopiesTotal = calculatorCopies * copyFee
  const calculatorDeliveryFee =
    calculatorDelivery === 'mail' ? mailFee : calculatorDelivery === 'international' ? internationalMailFee : 0
  const calculatorTotal = calculatorBase + calculatorRush + calculatorCopiesTotal + calculatorDeliveryFee
  const feeHistoryEntries = useMemo(() => {
    return items
      .slice()
      .sort(
        (left, right) =>
          new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime() ||
          left.display_order - right.display_order,
      )
      .map((item) => ({
        code: item.code,
        name: item.name,
        updatedAt: item.updated_at,
        amount: formatCurrency(item.amount_cents),
        status: item.is_active ? 'Active' : 'Disabled',
      }))
  }, [items])

  async function refreshFeeStructure(successMessage?: string) {
    const nextPayload = normalizePayload(await fetchAdminFeeStructureAction())
    setPayload(nextPayload)
    setScheduleName(nextPayload.schedule.name)
    setItems(nextPayload.items.map(toEditableItem))
    setMessage(successMessage || null)
  }

  function updateItem(nextItem: EditableFeeItem) {
    setItems((current) => current.map((item) => (item.code === nextItem.code ? nextItem : item)))
  }

  return (
    <section className="admin-sections">
      <div className="card admin-section-detail fee-structure-hero">
        <div className="fee-structure-topbar">
          <div className="fee-structure-heading">
            <AdminSectionTitle icon="fee-structure" title="Fee Structure Management">
              <p className="fee-structure-subtitle">
                Define and manage fees for different services and request types
              </p>
            </AdminSectionTitle>
          </div>
          <div className="fee-structure-actions">
            <button type="button" className="button secondary fee-header-button">
              Export Fees
            </button>
            <button
              type="button"
              className="button fee-header-button"
              disabled={isPending}
              onClick={() => {
                setError(null)
                setMessage(null)
                startTransition(async () => {
                  try {
                    const result = await saveAdminFeeStructureAction({
                      name: scheduleName.trim(),
                      items: items.map((item) => ({
                        code: item.code,
                        name: item.name.trim(),
                        category: item.category,
                        fee_type: item.fee_type,
                        description: item.description.trim(),
                        amount_cents: item.amount_cents,
                        currency: item.currency,
                        applies_to_letter_type: item.applies_to_letter_type,
                        applies_to_processing_type: item.applies_to_processing_type,
                        applies_to_delivery_method: item.applies_to_delivery_method,
                        tax_mode: item.tax_mode,
                        charge_unit: item.charge_unit,
                        display_order: item.display_order,
                        is_active: item.is_active,
                        metadata_json: item.metadata_json,
                      })),
                    })
                    await refreshFeeStructure(result.success)
                  } catch (nextError) {
                    setError(nextError instanceof Error ? nextError.message : 'Unable to save fees.')
                  }
                })
              }}
            >
              {isPending ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>

        {message ? <div className="success-banner">{message}</div> : null}
        {error ? <p className="form-error">{error}</p> : null}

        <div className="fee-structure-toolbar">
          <label className="field">
            Active schedule name
            <input value={scheduleName} onChange={(event) => setScheduleName(event.target.value)} />
          </label>
          <div className="fee-structure-toolbar-note">
            <span className="pill">{activeItems.length} active fees</span>
            <span className="pill">Jurisdiction scoped</span>
            <button
              type="button"
              className={`button secondary fee-utility-toggle${activePanel === 'summary' ? ' is-active' : ''}`}
              onClick={() => setActivePanel((current) => (current === 'summary' ? null : 'summary'))}
            >
              Fee Summary
            </button>
            <button
              type="button"
              className={`button secondary fee-utility-toggle${activePanel === 'calculator' ? ' is-active' : ''}`}
              onClick={() => setActivePanel((current) => (current === 'calculator' ? null : 'calculator'))}
            >
              Calculator
            </button>
          </div>
        </div>
      </div>

      {activePanel === 'summary' ? (
        <div className="fee-modal-overlay" onClick={() => setActivePanel(null)}>
          <div
            className="card fee-utility-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fee-summary-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="stack-header fee-modal-header">
              <div>
                <h2 id="fee-summary-title" className="admin-section-title">
                  Fee Summary
                </h2>
                <p className="admin-copy">Quick reference for the active public-facing fees.</p>
              </div>
              <button
                type="button"
                className="fee-modal-close"
                aria-label="Close fee summary"
                onClick={() => setActivePanel(null)}
              >
                ×
              </button>
            </div>
            <div className="fee-summary-list">
              {activeItems.map((item) => (
                <div key={item.code} className="fee-summary-row">
                  <div>
                    <strong>{item.name}</strong>
                    <span>
                      {getStringMeta(item, 'processing_time_label') ||
                        getStringMeta(item, 'summary_label') ||
                        item.category.replaceAll('_', ' ')}
                    </span>
                  </div>
                  <strong>{formatCurrency(item.amount_cents)}</strong>
                </div>
              ))}
            </div>
            <div className="fee-summary-totals">
              <div>
                <span>Standard + Mail</span>
                <strong>{formatCurrency(summaryExamples.standardMail)}</strong>
              </div>
              <div>
                <span>Rush + Copy + Mail</span>
                <strong>{formatCurrency(summaryExamples.rushCopyMail)}</strong>
              </div>
              <div>
                <span>Comprehensive + Rush + Mail</span>
                <strong>{formatCurrency(summaryExamples.comprehensiveRushMail)}</strong>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {activePanel === 'calculator' ? (
        <div className="fee-modal-overlay" onClick={() => setActivePanel(null)}>
          <div
            className="card fee-utility-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fee-calculator-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="stack-header fee-modal-header">
              <div>
                <h2 id="fee-calculator-title" className="admin-section-title">
                  Fee Calculator
                </h2>
                <p className="admin-copy">
                  Preview how the current setup totals common request combinations.
                </p>
              </div>
              <button
                type="button"
                className="fee-modal-close"
                aria-label="Close fee calculator"
                onClick={() => setActivePanel(null)}
              >
                ×
              </button>
            </div>

            <div className="fee-calculator-grid">
              <label className="field">
                Letter type
                <select
                  value={calculatorLetterType}
                  onChange={(event) =>
                    setCalculatorLetterType(event.target.value as 'standard' | 'comprehensive')
                  }
                >
                  <option value="standard">Standard</option>
                  <option value="comprehensive">Comprehensive</option>
                </select>
              </label>
              <label className="field">
                Processing
                <select
                  value={calculatorProcessing}
                  onChange={(event) =>
                    setCalculatorProcessing(event.target.value as 'standard' | 'expedited')
                  }
                >
                  <option value="standard">Standard</option>
                  <option value="expedited">Rush</option>
                </select>
              </label>
              <label className="field">
                Certified copies
                <input
                  type="number"
                  min="0"
                  value={String(calculatorCopies)}
                  onChange={(event) => setCalculatorCopies(Number(event.target.value || 0))}
                />
              </label>
              <label className="field">
                Delivery
                <select
                  value={calculatorDelivery}
                  onChange={(event) =>
                    setCalculatorDelivery(event.target.value as 'digital' | 'mail' | 'international')
                  }
                >
                  <option value="digital">Digital only</option>
                  <option value="mail">Physical mail</option>
                  <option value="international">International mail</option>
                </select>
              </label>
            </div>

            <div className="fee-calculator-total">
              <div>
                <span>Base fee</span>
                <strong>{formatCurrency(calculatorBase)}</strong>
              </div>
              <div>
                <span>Rush fee</span>
                <strong>{formatCurrency(calculatorRush)}</strong>
              </div>
              <div>
                <span>Certified copies</span>
                <strong>{formatCurrency(calculatorCopiesTotal)}</strong>
              </div>
              <div>
                <span>Delivery fee</span>
                <strong>{formatCurrency(calculatorDeliveryFee)}</strong>
              </div>
              <div className="is-total">
                <span>Total amount</span>
                <strong>{formatCurrency(calculatorTotal)}</strong>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="fee-structure-layout">
        <div className="fee-structure-editor-stack">
          <div className="fee-tab-bar" role="tablist" aria-label="Fee structure sections">
            {SECTION_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.key}
                className={`fee-tab${activeTab === tab.key ? ' is-active' : ''}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === 'fee_history' ? (
            <section className="fee-structure-section">
              <div className="stack-header fee-section-header">
                <div>
                  <h2 className="admin-section-title">Fee History</h2>
                  <p className="admin-copy">
                    Recent updates for the current active fee schedule.
                  </p>
                </div>
                <span className="pill">{feeHistoryEntries.length} entries</span>
              </div>

              <div className="card fee-history-card">
                <div className="fee-history-list">
                  {feeHistoryEntries.map((entry) => (
                    <div key={entry.code} className="fee-history-row">
                      <div className="fee-history-main">
                        <strong>{entry.name}</strong>
                        <span>{new Date(entry.updatedAt).toLocaleDateString('en-US')}</span>
                      </div>
                      <div className="fee-history-meta">
                        <span>{entry.amount}</span>
                        <span className="pill">{entry.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          ) : selectedGroup ? (
            <section key={selectedGroup.category} className="fee-structure-section">
              <div className="stack-header fee-section-header">
                <div>
                  <h2 className="admin-section-title">{selectedGroup.label}</h2>
                  <p className="admin-copy">
                    Configure the fee items currently available in this part of the request flow.
                  </p>
                </div>
                <span className="pill">{selectedGroup.items.length} fees</span>
              </div>
              <div className="fee-structure-card-stack">
                {selectedGroup.items.map((item) => (
                  <FeeCard key={item.code} item={item} onChange={updateItem} />
                ))}
              </div>
            </section>
          ) : null}

          <p className="fee-structure-footer-note">
            Changes apply to the active jurisdiction fee schedule for {payload.client.city_name}.
          </p>
        </div>
      </div>
    </section>
  )
}
