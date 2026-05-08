# Azure Multi-modal Compliance Ingestion Engine

> **An AI-powered pipeline that automatically audits YouTube ad content for brand & regulatory compliance — combining video intelligence, RAG, and LLM reasoning on Azure.**

![Architecture](Project2_Langgraph_Architecture.png)

---

## What This Project Does

Brands running ads on YouTube face a real operational problem: manually reviewing every video for regulatory compliance is slow, expensive, and error-prone. This system automates that end-to-end.

Submit a YouTube URL → the pipeline downloads the video, extracts every spoken word and on-screen text via Azure Video Indexer, retrieves the relevant regulatory rules from a vector knowledge base, and sends everything to GPT-4o for a structured compliance audit. The result is a severity-ranked list of violations with a plain-English summary report — in seconds.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Entry Points                                │
│              CLI (main.py)  ·  REST API (FastAPI)                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  Orchestration — LangGraph DAG                      │
│                                                                     │
│   ┌─────────────────────┐         ┌───────────────────────────┐    │
│   │   Node 1: Indexer   │ ──────► │   Node 2: Auditor (RAG)   │    │
│   │                     │         │                           │    │
│   │  • yt-dlp download  │         │  • Embed transcript+OCR   │    │
│   │  • Azure Blob upload│         │  • Similarity search      │    │
│   │  • Azure Video Index│         │    (Azure AI Search)      │    │
│   │  • Extract:         │         │  • GPT-4o compliance audit│    │
│   │    - Transcript     │         │  • Return JSON violations  │    │
│   │    - OCR text       │         │    + severity + report     │    │
│   │    - Metadata       │         │                           │    │
│   └─────────────────────┘         └───────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│               External Intelligence + Observability                 │
│                                                                     │
│  Azure OpenAI (GPT-4o + text-embedding-3-small)                    │
│  Azure Application Insights (traces, logs, metrics)                 │
│  LangSmith (LLM tracing + prompt debugging)                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Workflow Orchestration** | LangGraph (StateGraph DAG) |
| **API Framework** | FastAPI + Uvicorn |
| **LLM** | Azure OpenAI GPT-4o |
| **Embeddings** | Azure OpenAI `text-embedding-3-small` |
| **Vector Store / RAG** | Azure AI Search |
| **Video Intelligence** | Azure Video Indexer (transcript + OCR) |
| **Video Download** | yt-dlp | RapidAPI YT Video downloader
| **Blob Storage** | Azure Blob Storage |
| **Observability** | Azure Monitor OpenTelemetry + LangSmith |
| **Data Validation** | Pydantic v2 |
| **Package Management** | uv |

---

## Key Engineering Decisions

### LangGraph for Workflow Orchestration
The audit pipeline is modeled as a **Directed Acyclic Graph (DAG)** using LangGraph's `StateGraph`. Each node reads from and writes to a shared `VideoAuditState` TypedDict, making state transitions explicit, traceable, and easy to extend. Adding a new audit step (e.g. a frame-level image classifier) is as simple as adding a new node and edge.

### Multi-modal Input → Single Audit Context
Azure Video Indexer extracts **both** the audio transcript and on-screen OCR text. Both are concatenated and fed into the RAG query, meaning the compliance auditor reasons over everything the viewer would hear *and* see — not just the voiceover.

### RAG over a Regulatory Knowledge Base
Compliance rules are chunked, embedded, and indexed into Azure AI Search ahead of time (via `backend/scripts/index_documents.py`). At audit time, the transcript+OCR is used as the query to retrieve the top-3 most relevant rule chunks. This keeps the LLM context focused and the prompt grounded in actual guidelines — not hallucinated rules.

### Structured LLM Output
The auditor node instructs GPT-4o to return a strict JSON schema with `category`, `severity` (`CRITICAL / HIGH / MEDIUM / LOW`), and `description` per violation. A regex-based cleanup handles any accidental markdown fences before JSON parsing, making the pipeline robust to minor model formatting drift.

### End-to-End Observability
Azure Monitor OpenTelemetry is initialized at FastAPI startup and auto-instruments all HTTP requests and exceptions. LangSmith captures every LLM call with its full prompt and response for post-hoc debugging.

---

## Project Structure

```
LLMOPS/
├── backend/
│   ├── data/                        # Regulatory PDFs (knowledge base source)
│   │   ├── youtube-ad-specs.pdf
│   │   └── 1001a-influencer-guide-508_1.pdf
│   ├── scripts/
│   │   └── index_documents.py       # One-time: chunk PDFs → embed → index into Azure AI Search
│   └── src/
│       ├── api/
│       │   ├── server.py            # FastAPI app, /audit and /health endpoints
│       │   └── telemetry.py         # Azure Monitor OpenTelemetry setup
│       ├── graph/
│       │   ├── state.py             # VideoAuditState TypedDict + ComplianceIssue schema
│       │   ├── workflow.py          # LangGraph DAG (START → indexer → auditor → END)
│       │   └── nodes.py             # Node implementations
│       └── services/
│           └── video_indexer.py     # Azure Video Indexer: upload, poll, extract transcript/OCR
├── main.py                          # CLI entry point for local testing
├── pyproject.toml                   # Dependencies
└── uv.lock                          # Locked dependency manifest
```

---

## Data Flow

```
1. Input          YouTube video URL
                        │
2. Download       yt-dlp → temp_audit_video.mp4
                        │
3. Index          Upload to Azure Blob → Azure Video Indexer
                  Poll until processing complete
                  Extract: transcript (speech-to-text) + OCR (on-screen text)
                        │
4. Retrieve       Embed transcript+OCR → query Azure AI Search
                  Return top-3 relevant regulatory rule chunks
                        │
5. Audit          System prompt (rules) + user message (transcript+OCR+metadata)
                  → GPT-4o → structured JSON response
                        │
6. Output         {
                    "compliance_result": [
                      {
                        "category": "Disclosure",
                        "severity": "HIGH",
                        "description": "Sponsored content not disclosed within first 30 seconds..."
                      }
                    ],
                    "status": "FAIL",
                    "final_report": "The video contains 1 high-severity disclosure violation..."
                  }
```

---

## API Reference

### `POST /audit`

Triggers a full compliance audit for a YouTube video.

**Request**
```json
{
  "video_url": "https://youtu.be/dT7S75eYhcQ"
}
```

**Response**
```json
{
  "session_id": "3f1a2b4c-...",
  "video_id": "vid_3f1a2b4c",
  "status": "FAIL",
  "final_report": "The ad contains two violations: an undisclosed sponsorship and an unsubstantiated performance claim. Immediate remediation is recommended before further distribution.",
  "compliance_results": [
    {
      "category": "Disclosure",
      "severity": "HIGH",
      "description": "Sponsorship not disclosed within the first 30 seconds as required by FTC guidelines."
    },
    {
      "category": "Claim Validation",
      "severity": "MEDIUM",
      "description": "On-screen text claims '10x faster results' without supporting evidence cited."
    }
  ]
}
```

### `GET /health`

```json
{ "status": "Healthy", "service": "Brand Compliance AI" }
```

---

## Setup & Running

### Prerequisites
- Python 3.14+
- [`uv`](https://github.com/astral-sh/uv) package manager
- Azure subscription with: OpenAI, Video Indexer, AI Search, Blob Storage, Application Insights

### 1. Clone & install dependencies

```bash
git clone <repo-url>
cd LLMOPS
uv sync
```

### 2. Configure environment variables

Create a `.env` file at the project root:

```env
# Azure OpenAI
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# Azure AI Search (Vector Store)
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_API_KEY=
AZURE_SEARCH_INDEX_NAME=

# Azure Video Indexer
AZURE_VI_NAME=
AZURE_VI_LOCATION=
AZURE_VI_ACCOUNT_ID=
AZURE_SUBSCRIPTION_ID=
AZURE_RESOURCE_GROUP=

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_TENANT_ID=

# Observability
APPLICATIONINSIGHTS_CONNECTION_STRING=

# LangSmith (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=brand-compliance
```

### 3. Build the knowledge base (one-time)

```bash
uv run python backend/scripts/index_documents.py
```

This chunks the regulatory PDFs in `backend/data/`, embeds them with `text-embedding-3-small`, and uploads to Azure AI Search.

### 4a. Run via CLI

```bash
uv run python main.py
```

### 4b. Run the API server

```bash
uv run uvicorn backend.src.api.server:app --reload
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Compliance Knowledge Base

The RAG knowledge base is built from two authoritative sources:

| Document | Coverage |
|---|---|
| `youtube-ad-specs.pdf` | YouTube ad format requirements, video specs, content policies |
| `1001a-influencer-guide-508_1.pdf` | FTC influencer marketing guidelines, disclosure requirements |

To extend coverage, drop additional PDFs into `backend/data/` and re-run the indexing script.

---

## Severity Framework

| Level | Meaning |
|---|---|
| `CRITICAL` | Legal or regulatory breach — immediate action required |
| `HIGH` | Significant violation likely to result in penalty or harm |
| `MEDIUM` | Clear rule breach with limited impact |
| `LOW` | Minor or technical deviation from guidelines |

---

## Future Roadmap

- [ ] Frame-level visual analysis (logo placement, prohibited imagery detection)
- [ ] Support for non-YouTube sources (direct upload, Vimeo, TikTok)
- [ ] Async audit queue with Redis + status polling endpoint
- [ ] Streamlit dashboard for audit history and violation trends
- [ ] CI/CD pipeline with GitHub Actions + Azure Container Registry
- [ ] Multi-language transcript support

---

## Author

Built by **Robin Singh** · [GitHub](https://github.com/Robin-singh24)
