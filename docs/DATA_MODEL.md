# Data Model MVP

## Vault file layers

The vault uses a layered storage model:

- `/srv/hermes-medical/data/raw` — immutable originals exactly as received from the user. A ZIP stays a ZIP; a PDF stays a PDF.
- `/srv/hermes-medical/data/extracted/<document_id>/files` — one-time materialized working copy for fast access. ZIP members are flattened into short safe filenames; non-ZIP originals are copied here too.
- `/srv/hermes-medical/data/extracted/<document_id>/manifest.json` — machine-readable link from working files back to the raw source path and SHA-256.
- `/srv/hermes-medical/data/extracted_text` — future text/OCR output for search and summaries.
- `/srv/hermes-medical/data/db/medical.sqlite` — SQLite metadata, timeline, and body parameters.

Medical data directories are outside the Git repository and must not be committed.

## documents

One row per original file received from Telegram.

Key fields:

- id
- telegram_user_id
- telegram_message_id
- original_filename
- stored_path
- sha256
- mime_type
- document_type
- document_date
- user_comment
- document_role
- role_note
- processing_status

### Document role metadata

`documents.document_role` is the operational classification used to keep
doctor-facing summaries from mixing source results with noisy supporting papers.
It does not change the immutable source file and it must not be used to delete
or hide originals.

Current role values:

- `clinical_source` — primary clinical source: lab result, imaging conclusion,
  endoscopy report, ECG/functional result, specialist examination, or other
  clinically meaningful conclusion.
- `treatment_order` — prescription or medication/treatment order.
- `referral_order` — referral/order for a future test or procedure; useful for
  planning, but not itself a result.
- `administrative_supporting` — contract, payment/order confirmation,
  registration paper, certificate, or other administrative proof.
- `supporting_context` — screenshot/photo/context item that helps explain the
  care pathway but does not replace an official result or referral.
- `auxiliary_context` — wellness/fitness/background data that may be useful as
  context but is not a clinical diagnosis.
- `patient_self_report` — patient-provided facts without an attached verifying
  clinical document.
- `container_bundle` — technical archive/container kept as original source when
  its clinically relevant members are represented as separate document rows.

`documents.role_note` stores a short human-readable reason for the assigned
role. Reports should group or filter by `document_role`: clinical sources first,
then treatment/referral orders, then administrative/supporting/context records,
with patient self-reports clearly separated.

## timeline_items

One row per extracted or user-entered medical event.

Key fields:

- id
- document_id
- event_date
- event_type
- title
- body
- source_quote
- confidence
- verified_by_user

A timeline item answers: what happened at this point in time. A single composite
source document can have many timeline items that all point to the same
`document_id`.

## body_parameters

One row per time-linked body-state parameter.

This is the structured layer for measurable or observable facts that should be
available by time slice, not only as free text.

Key fields:

- id
- document_id
- timeline_item_id
- observed_at
- parameter_group
- parameter_name
- parameter_code
- value_text
- value_numeric
- unit
- reference_range
- note
- body_site
- method
- source_quote
- confidence
- verified_by_user

Representation rules:

- `observed_at` is the date or timestamp of the body-state slice.
- `document_id` links the parameter to the immutable source when available.
- `timeline_item_id` links the parameter to the event slice when available.
- `value_numeric` stores the machine-comparable number when the value is numeric.
- `value_text` stores exact text for ranges, qualitative findings, or composite values.
- `unit` and `reference_range` must be preserved when present.
- `source_quote` should contain a short source-grounded excerpt.
- `confidence` must remain conservative for OCR or AI-extracted values.

The search index includes this table with scope `body_parameter`, so queries for
a parameter name, value, unit, body site, group, note, or source quote can find
the structured parameter and its linked source.

## Patient self-reports

Self-reports are first-class source records for patient-provided information that is clinically relevant but not independently verified by an attached medical document.

Examples:

- medication intake as actually performed by the patient;
- allergies, suspected allergies, and later uncertainty corrections;
- symptoms, side effects, home measurements, subjective status updates;
- practical decisions made while awaiting a doctor visit.

Representation:

- `documents.document_type` should start with `самоотчёт пациента:` followed by the topic.
- `documents.document_role` should be `patient_self_report`.
- `documents.user_comment` and `timeline_items.body` should start with `Со слов пациента:`.
- `timeline_items.confidence` should not imply external verification unless a clinician/source document confirms it.
- Uncertainty must be stored explicitly in the text, e.g. `вероятно`, `точный препарат не подтверждён`, `примерно`, `пациент не помнит`.
- Later corrections should be added as new self-report documents; older timeline wording may be softened so summaries do not preserve an overstated claim.

Self-reports do not replace source medical documents. They are a patient-reported layer for chronology, doctor preparation, and safety flags that need cautious wording.
