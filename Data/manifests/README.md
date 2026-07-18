# Pragyan Prototype Source Manifests

These files define the Phase 1 source-of-truth layer for Pragyan Plant Intelligence.

- `source_manifest.json` records the six immutable input sources and their SHA-256 hashes.
- `active_document_manifest.json` inventories every active P&ID, work-order, SOP, inspection, incident, and email source. It records provenance and hashes without altering the original six-source baseline.
- `pid_asset_registry.json` contains manually reviewed seed tags from the five P&IDs.
- `pid_relationships.json` contains reviewed process/context relationships from the drawings.
- `ocr_benchmark.md` defines what the scanned work-order OCR pipeline must measure before it produces proposed records.

The P&ID PNGs and work-order PDF remain unchanged. Any later OCR output, crops, embeddings, or proposed links must point back to these source IDs and hashes.

All documents outside `Data/P&IDs` and `Data/Maintenance Records  Work Orders` are simulated demo records. The application must enforce this provenance label from `active_document_manifest.json`, including for PDF text layers where the notice cannot be extracted reliably.
