# ROADMAP.md

# CampusBrain AI Development Roadmap

## Phase 0 — Planning

Learn

* What is RAG?
* Why embeddings?
* Why vector databases?
* Project architecture
* Folder structure

Deliverables

* PRD
* Architecture
* Coding Standards
* Git repository

---

## Phase 1 — Project Foundation

Learn

* Docker
* Docker Compose
* Git workflow
* Environment variables

Build

* React app
* FastAPI app
* PostgreSQL
* Qdrant
* Redis
* MinIO
* Ollama

Deliverable

Everything starts with:

docker compose up

---

## Phase 2 — Backend APIs

Learn

* FastAPI
* REST APIs
* Pydantic
* Dependency Injection

Build

* Health endpoint
* Auth endpoints
* User endpoints

---

## Phase 3 — Database

Learn

* SQLAlchemy
* Alembic
* Relationships
* Indexing

Build

* Users
* Organizations
* Documents
* Collections

---

## Phase 4 — Storage

Learn

* Object Storage
* MinIO

Build

* File upload
* Metadata storage

---

## Phase 5 — Document Processing

Learn

* PyMuPDF
* OCR
* Metadata extraction

Build

* PDF extraction
* DOCX extraction
* CSV parsing

---

## Phase 6 — Chunking

Learn

* Recursive chunking
* Semantic chunking
* Chunk overlap

Experiment with chunk sizes and evaluate quality.

---

## Phase 7 — Embeddings

Learn

* Embedding models
* Similarity search

Build

* BGE-M3 embedding pipeline

---

## Phase 8 — Vector Database

Learn

* Qdrant
* HNSW
* Metadata filtering

Build

* Store vectors
* Retrieve vectors

---

## Phase 9 — Retrieval

Implement

* Semantic Search
* BM25
* Hybrid Search

---

## Phase 10 — Re-ranking

Implement

* BGE reranker

Compare retrieval quality before and after reranking.

---

## Phase 11 — LLM

Integrate

* Ollama
* Qwen 3

Build

Prompt pipeline.

---

## Phase 12 — Complete RAG

Connect all components.

Measure latency.

Verify citations.

---

## Phase 13 — Chat

Implement

* Memory
* History
* Streaming responses

---

## Phase 14 — Frontend

Build

* Dashboard
* Chat UI
* Upload UI
* Admin Panel

---

## Phase 15 — Evaluation

Integrate

* RAGAS
* Langfuse

Measure

* Faithfulness
* Recall
* Precision

---

## Phase 16 — Production

Implement

* Docker Compose Production
* Nginx
* CI/CD
* Monitoring
* Logging

---

## Definition of Done

A phase is complete only if:

* Feature works
* Tests pass
* Documentation updated
* Architecture reviewed
* Git commit created
* You can explain how it works without reading the code
