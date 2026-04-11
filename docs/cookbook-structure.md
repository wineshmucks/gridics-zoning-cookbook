# Cookbook Structure

Each numbered folder in `cookbook/` represents one business/use-case concept.

## Folder Map

- `01-instant-feasibility-api`: “Can I build this here?” instant feasibility API
- `02-national-adu-eligibility-lead-gen`: National ADU eligibility + ADU-in-a-box lead gen
- `03-developer-site-sourcing`: Developer site-sourcing for specific strategies
- `04-franchise-expansion-intelligence`: Franchise expansion intelligence
- `05-zoning-driven-comps-valuation`: Zoning-driven comps + valuation uplift modeling
- `06-upzoning-radar-alerts`: “Upzoning radar” + entitlement opportunity alerts
- `07-underbuilt-parcel-detection`: Underbuilt parcel detection (redevelopment candidates)
- `08-industrial-conversion-adaptive-reuse`: Industrial conversion/adaptive reuse screener
- `09-retail-siting-special-buffers`: Retail siting + special distance buffer rules
- `10-permit-precheck-automation`: Permit pre-check automation for municipalities
- `11-brokerage-zoning-truth-widget`: Brokerage “zoning truth” widget for listings
- `12-nonconforming-use-risk-screening`: Insurance/risk screening for nonconforming use
- `13-climate-zoning-resilience-buildability`: Climate + zoning retreat/resilience buildability
- `14-infrastructure-utility-load-forecasting`: Infrastructure and utility load forecasting
- `15-housing-policy-capacity-dashboard`: Housing policy dashboards (“capacity vs need”)
- `16-national-zoning-index-benchmarks`: National zoning index / benchmarks
- `17-title-closing-zoning-verification`: Title/closing zoning and use verification
- `18-short-term-rental-legality-engine`: Short-term rental legality engine
- `19-zoning-translator-consumer`: “Zoning translator” for consumers
- `20-lender-compliance-layer`: Compliance layer for lenders
- `21-land-assembly-optimizer`: Land assembly optimizer
- `22-zoning-change-detection-audit-trail`: Zoning change detection + audit trail
- `23-zoning-massing-cost-generator`: Zoning-based massing + construction cost generator
- `24-specialized-data-licensing`: Specialized data licensing

## Standard Starter File

Each track starts with:

- `README.md` containing:
- `Audience`
- `Problem`
- `Example Scope`
- `Inputs`
- `Outputs`
- `Monetization`
- `API/Workflow Sketch`
- `Data Dependencies`
- `Open Questions`

## Templates

- `cookbook/_templates/example-template.md`
- `cookbook/_templates/implementation-checklist.md`

## Runtime Integration

- Unified API runtime: `server/app/main.py`
- Shared composition logic: `common/`
- Agent interface layer: `agent-os/agent_os/`
