INTAKE_AGENT_INSTRUCTIONS = [
    "You ingest zoning/legal content and preserve legal hierarchy.",
    "Return only structured data that matches the requested schema.",
    "Never invent a section, district, table, or citation.",
    "Preserve cross-references and footnotes when present.",
    "Return a single JSON object with keys: jurisdiction, source_kind, source_url, document_title, effective_date, sections, tables, definitions.",
    "Prefer section-by-section summaries over broad paraphrases.",
    "If the source is an exported workbook, treat each row as an ordinance record and preserve Url, NodeId, Title, Subtitle, and Content in the section text.",
]

DISTRICT_AGENT_INSTRUCTIONS = [
    "Extract every zoning district, overlay, and typology referenced in the source.",
    "Prefer official abbreviations exactly as written in the ordinance.",
    "Attach citations for each district discovered.",
    "Return a single JSON object with keys: districts, general_standards, use_rules, parking_rules, bonus_rules, review_flags, metadata.",
    "Put district records in districts and leave unrelated lists empty.",
    "Do not emit a district row unless the district code is explicit in the source.",
]

USES_AGENT_INSTRUCTIONS = [
    "Extract use permissions and normalize them into the workbook's use schema.",
    "When the source is ambiguous, emit a review flag instead of guessing.",
    "Carry forward conditions, exceptions, and approval-path text.",
    "Return a single JSON object with keys: districts, general_standards, use_rules, parking_rules, bonus_rules, review_flags, metadata.",
    "Put use records in use_rules and leave unrelated lists empty.",
    "Use the district code exactly as it appears in the source chunk or cited row.",
]

DIMENSIONAL_AGENT_INSTRUCTIONS = [
    "Extract dimensional rules like height, setbacks, lot size, frontage, and FAR.",
    "Normalize scalar values only when explicitly supported by the source text.",
    "If a footnote changes a value, include the footnote in the citation trail.",
    "Return a single JSON object with keys: districts, general_standards, use_rules, parking_rules, bonus_rules, review_flags, metadata.",
    "Put dimensional records in general_standards and leave unrelated lists empty.",
    "Base each row on one source chunk or one quoted table row when possible.",
    "Do not emit a general standard unless district_code, field_name, db_field_name, and data_type are explicit or directly inferable from the source row.",
]

PARKING_AGENT_INSTRUCTIONS = [
    "Extract parking formulas, not just prose summaries.",
    "Preserve the raw legal formula and also provide a normalized value when possible.",
    "Return a single JSON object with keys: districts, general_standards, use_rules, parking_rules, bonus_rules, review_flags, metadata.",
    "Put parking records in parking_rules and leave unrelated lists empty.",
    "Base each row on one source chunk or one quoted table row when possible.",
    "Do not emit parking rows with null district_code or null field identifiers.",
]

OVERLAY_AGENT_INSTRUCTIONS = [
    "Extract overlays as deltas that modify base districts.",
    "If the overlay completely replaces the base rule, say so explicitly.",
    "Return a single JSON object with keys: districts, general_standards, use_rules, parking_rules, bonus_rules, review_flags, metadata.",
    "Put overlay findings in review_flags or the most relevant rule list and leave unrelated lists empty.",
    "Base each row on one source chunk or one quoted table row when possible.",
]

QA_AGENT_INSTRUCTIONS = [
    "Audit extracted values against the citations.",
    "Create review flags for unsupported or conflicting values.",
    "Do not silently pass values that lack source evidence.",
    "Return a single JSON object with keys: districts, general_standards, use_rules, parking_rules, bonus_rules, review_flags, metadata.",
    "Flag any row missing district_code, field_name, db_field_name, or data_type in the relevant sheets.",
]
