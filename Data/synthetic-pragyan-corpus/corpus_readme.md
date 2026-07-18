GENERATED SYNTHETIC DEMO DATA - NOT AN OFFICIAL PLANT DOCUMENT

---
document_id: SYN-PRG-README-001
title: Pragyan Synthetic Corpus Guide
document_type: corpus_readme
synthetic: true
generated_for: Pragyan Plant Intelligence Hackathon Prototype
revision: "1.0"
effective_or_event_date: 2025-07-01
owner_role: Reliability Engineer
related_asset_tags: []
related_drawing_ids: []
confidentiality: Internal Demo
review_status: Draft for Human Review
---

# Purpose

This directory defines a fictional, internally consistent document corpus for product demonstration. It supplements but never replaces the supplied Pragyan P&IDs and the separate scanned Maintenance Records / Work Orders PDF.

# Source Boundary

- Files in this directory are synthetic demo data.
- The P&ID PNGs and supplied work-order PDF are separate source files and must not be overwritten, paraphrased as synthetic records, or used to invent content.
- This corpus contains no regulations, legal conclusions, compliance certificates, live operating instructions, emergency procedures, setpoints, chemical recipes, or equipment-control actions.

# Generation Order

1. Batch 0 control files define IDs, dates, links, allowed tags, and vocabulary.
2. Batch 1 creates four SOP excerpts.
3. Batch 2 creates nine inspection reports.
4. Batch 3 creates four near-miss reports.
5. Batch 4 creates seven internal emails.

# Required Validation

Before adding a later document, verify that its document ID, asset tags, drawing IDs, date, and references appear in `manifest.json`, `synthetic_timeline.csv`, and `cross_document_link_map.json`. Every Markdown and email file must begin with the required synthetic warning and include the metadata defined in `data_dictionary.json`.
