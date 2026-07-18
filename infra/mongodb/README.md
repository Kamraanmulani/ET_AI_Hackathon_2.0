# MongoDB Community — Local Setup

## Required: MongoDB Community Server

Pragyan Plant Intelligence uses a local MongoDB Community instance.
No cloud MongoDB is required; all data stays on your machine.

## Install MongoDB Community (if not already installed)

1. Download MongoDB Community 7.x from https://www.mongodb.com/try/download/community
2. Install with default settings (installs as a Windows service).
3. Verify: open a terminal and run `mongod --version`

## Start MongoDB

MongoDB typically starts automatically as a Windows service.
If it is not running:

```powershell
# Start the service
net start MongoDB

# Or start manually (adjust path if needed)
"C:\Program Files\MongoDB\Server\7.0\bin\mongod.exe" --dbpath "C:\data\db"
```

## Verify with MongoDB Compass

Open MongoDB Compass and connect to: `mongodb://localhost:27017`

You should see an empty connection. After running the importer the
`pragyan_ppi` database will appear with these collections:
- documents
- assets
- relationships
- ocr_jobs, ocr_pages, ocr_regions
- work_order_fields, work_order_links
- review_tasks
- audit_events

## Environment

The backend reads `backend/.env` (copy from `backend/.env.example`):

```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=pragyan_ppi
```

## Run the importer

```powershell
cd backend
python importer.py
```

The importer is idempotent — you can run it multiple times safely.

## Qdrant (optional — not yet enabled)

Qdrant will be added in a later phase after OCR text chunks are reviewed.
Do not enable Qdrant until then.
