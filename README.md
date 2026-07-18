# Pragyan Plant Intelligence

**Pragyan Plant Intelligence** is a source-grounded industrial RAG (Retrieval-Augmented Generation) copilot built for the ET AI Hackathon. It acts as an Expert Knowledge Copilot that retrieves evidence from an active engineering corpus, traverses asset/document relationships, and answers operational questions with strict citations. It safely abstains from answering when support is missing, ensuring high reliability for industrial applications.

## 🚀 Features

- **Expert Knowledge Copilot**: Conversational interface grounded entirely in source engineering data (e.g., P&IDs, Work Orders).
- **Hybrid Retrieval System**: Combines MongoDB (Canonical), Qdrant (Semantic Vector Search), and Neo4j (Graph Projection) for robust evidence retrieval.
- **Strict Provenance & Grounding**: LLM answers are strictly cited and backed by retrieved documents, avoiding hallucination on critical plant operations.
- **Safety Boundaries**: Automatically detects and rejects operational commands or out-of-scope compliance questions.
- **Interactive Asset 360 & P&ID Explorer**: View detailed insights for each asset tag and explore relationships visually.
- **Review Workflow**: Dedicated UI for reviewing OCR and AI-proposed data prior to indexing.

## 🛠️ Technology Stack

- **Frontend**: React (Vite), JavaScript, Vanilla CSS
- **Backend**: FastAPI (Python), Uvicorn
- **Databases**:
  - **MongoDB**: Canonical storage (documents, chunks, review queue)
  - **Qdrant**: Local vector database for semantic search
  - **Neo4j**: Graph database for P&ID asset and component relationships
- **AI / LLM**: Locally hosted Ollama (`qwen2.5:1.5b` or `qwen3:8b`) for embeddings and chat generation.

## 🏃‍♂️ Getting Started

### Prerequisites
- Node.js (v18+)
- Python 3.10+
- Docker & Docker Compose
- [Ollama](https://ollama.com/) (running locally)

### 1. Start Database Services (Docker)
Ensure Docker is running, then start Qdrant and Neo4j:
```bash
docker compose -f infra/rag-compose.yml up -d
```

### 2. Setup the Backend
Navigate to the `backend` folder, set up your virtual environment, and start the FastAPI server:
```bash
cd backend
python -m venv .venv-api
.\.venv-api\Scripts\activate  # On Windows
pip install -r requirements.txt
# Update .env with your Neo4j credentials
python -m uvicorn app.main:app --reload
```

### 3. Setup the Frontend
Navigate to the `frontend` folder, install dependencies, and start the Vite dev server:
```bash
cd frontend
npm install
npm run dev
```

### 4. Setup Local LLM
Ensure Ollama is running and pull the required models:
```bash
ollama pull qwen2.5:1.5b
ollama pull mxbai-embed-large
```

## 📜 Project Structure
- `/backend`: FastAPI Python server, services (retrieval, generation, DB clients), and API routes.
- `/frontend`: React web application featuring the Copilot, Asset 360, and Review Queue interfaces.
- `/infra`: Docker compose files for local services.
- `/Data`: Initial corpus, evaluations, and mock engineering records.

## 🏆 Hackathon Context
Developed for the **ET AI Hackathon**. This prototype demonstrates a safe, read-only AI system tailored for critical plant engineering environments, bridging the gap between unstructured PDFs and structured knowledge graphs.
