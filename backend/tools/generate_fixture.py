import openpyxl
from pathlib import Path
import json

BACKEND_DIR = Path(__file__).parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "Data"
FIXTURES_DIR = DATA_DIR / "fixtures"

def generate_xlsx():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    filepath = FIXTURES_DIR / "PRG-MNT-WO-REGISTER-001.xlsx"
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Work Orders"
    
    headers = ["Work Order ID", "Asset Tag", "Record Date", "Record Type", "Status", "Source Document ID", "Notes"]
    ws.append(headers)
    
    # Approved canonical tags and IDs from R1 requirements
    # 'ETP-601', 'P-601', 'AIT-601', 'AAH-601', 'LIC-601', 'LV-601', 'XV-603'
    # Documents: pid-005-etp
    # Let's insert a couple of rows
    ws.append(["WO-2023-001", "ETP-601", "2023-10-15", "Maintenance", "Completed", "pid-005-etp", "Synthetic fixture note for ETP-601"])
    ws.append(["WO-2023-002", "P-601", "2023-10-16", "Inspection", "Pending", "pid-005-etp", "Synthetic fixture note for P-601"])
    
    wb.save(filepath)
    print(f"Created fixture at {filepath}")
    
    # Now update active_document_manifest.json
    manifest_path = DATA_DIR / "manifests" / "active_document_manifest.json"
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
        
    import hashlib
    sha256 = hashlib.sha256(open(filepath, "rb").read()).hexdigest()
    
    # Check if already in manifest
    exists = any(s["source_id"] == "wo-register-fixture-001" for s in manifest["sources"])
    if not exists:
        manifest["sources"].append({
            "source_id": "wo-register-fixture-001",
            "path": "Data/fixtures/PRG-MNT-WO-REGISTER-001.xlsx",
            "document_type": "spreadsheet",
            "provenance": "synthetic_demo",
            "sha256": sha256
        })
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print("Updated manifest.")

if __name__ == "__main__":
    generate_xlsx()
