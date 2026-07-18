# Work-Order OCR Benchmark

**Source:** `work-orders-001`  
**Source file:** `Data/Maintenance Records  Work Orders/Maintenance Records  Work Orders.pdf`  
**Baseline:** 5 scanned pages; embedded text layer is empty; OCR has not run.

## Required Outputs Per Page

- Raw OCR text.
- Text bounding boxes or crop coordinates.
- OCR confidence per detected region.
- Engine and configuration version.
- Page duration and total job duration.
- Review state: `pending_review`, `verified`, `rejected`, or `unreadable`.

## Candidate Fields

Extract only if readable. Do not create placeholder values.

| Field | Validation |
| --- | --- |
| Work-order ID | Preserve exact source string and page region |
| Date | Preserve original text plus normalised date only after review |
| Asset tag | Match against `pid_asset_registry.json`; unmatched tags remain proposed |
| Symptom / finding | Preserve source wording; do not diagnose or paraphrase as fact |
| Action taken | Preserve source wording; do not turn it into an instruction |
| Status / owner | Extract only if visible and readable |

## Performance Targets

- API returns an extraction job state immediately; it does not wait for OCR.
- Repeated source/configuration uses a cache instead of rerunning OCR.
- Measure the actual development-machine baseline before setting a final timing threshold.
- Retry only unreadable or low-confidence regions at higher resolution.

## Acceptance Checks

1. Every candidate field opens its original page/region.
2. No field is marked `verified` before reviewer confirmation.
3. A work-order-to-asset link is `verified` only when the asset tag/source evidence match is reviewable.
4. A failed or timed-out OCR job leaves the original PDF browseable and reports a safe error state.
