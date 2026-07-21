# ARCHITECTURE.md

# CampusBrain AI — System Architecture

## Architecture Philosophy

CampusBrain AI follows:

* Clean Architecture
* Domain-Driven Design (lightweight)
* SOLID Principles
* Modular Monolith (v1)
* API First
* Docker First
* Cloud Native Ready

The architecture should allow future migration to microservices without rewriting business logic.

---

# High-Level Architecture

```
                Browser
                    │
                    ▼
           React + TypeScript
                    │
             REST API / SSE
                    │
                    ▼
              FastAPI Backend
                    │
      ┌─────────────┼──────────────┐
      │             │              │
      ▼             ▼              ▼
 PostgreSQL      Qdrant         Redis
      │
      ▼
    MinIO
      │
      ▼
PyMuPDF / Unstructured / PaddleOCR
      │
      ▼
 Embeddings (BGE-M3)
      │
      ▼
      Ollama
```

---

# Backend Layers

```
API Layer
↓

Service Layer
↓

Repository Layer
↓

Infrastructure Layer
↓

Database
```

Responsibilities

API

* Request validation
* Authentication
* Response formatting

Service

* Business logic

Repository

* Database operations

Infrastructure

* Qdrant
* MinIO
* Redis
* Ollama

---

# Core Modules

* Authentication
* Users
* Organizations
* Collections
* Documents
* Storage
* Chunking
* Embeddings
* Retrieval
* Reranking
* LLM
* Chat
* Analytics
* Evaluation
* Workers

---

# Data Flow

Upload

↓

Validation

↓

MinIO

↓

Extraction

↓

OCR

↓

Chunking

↓

Embeddings

↓

Qdrant

↓

Question

↓

Embedding

↓

Hybrid Retrieval

↓

Re-ranking

↓

LLM

↓

Answer

↓

Citation

---

# Multi-Tenancy

Every resource belongs to:

organization_id

All queries must be scoped by organization_id.

No cross-organization access.

---

# Design Principles

* Business logic never inside API routes.
* Services never call other services directly without interfaces.
* Repositories never contain business logic.
* Configuration comes from environment variables.
* Every external dependency is abstracted behind an interface.

---

# Error Handling

Use a unified error model.

* ValidationError
* AuthenticationError
* AuthorizationError
* NotFoundError
* ConflictError
* InternalServerError

---

# Logging

Log:

* Request ID
* User ID
* Organization ID
* Latency
* Retrieval time
* LLM time
* Errors

---

# Security

* JWT
* bcrypt
* HTTPS
* File validation
* MIME validation
* Prompt injection mitigation
* Rate limiting
* Secrets via environment variables

---

# Scalability Goals

Current

1 College

↓

Future

1000+ Organizations

↓

Millions of vectors

↓

Horizontal scaling without architectural changes.
