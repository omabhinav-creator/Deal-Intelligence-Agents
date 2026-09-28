# 🎯 Deal Intelligence Overlay — AI Sales Co-Pilot Powered by Hindsight

> Built for **HackwithHyderabad 3.0** | Category: **Sales & Revenue / Deal Intelligence**

[![Hindsight Memory](https://img.shields.io/badge/Memory_Layer-Hindsight_v1.0-blueviolet)](https://hindsight.vectorize.io/)
[![LLM Engine](https://img.shields.io/badge/LLM-Groq_Qwen3_32B-orange)](https://groq.com/)
[![Stack](https://img.shields.io/badge/Tech_Stack-MERN_%2B_Python-brightgreen)]()
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 📌 Overview

**Deal Intelligence Overlay** is a real-time browser extension overlay designed to eliminate lost context in long B2B sales cycles. By embedding directly over CRMs (Salesforce, HubSpot) and video meeting software (Google Meet, Zoom Web), it provides sales reps with live, context-aware memory briefs, objection handling tactics, and competitive battlecards.

Unlike stateless chatbots that treat every conversation as new, our agent uses **Hindsight persistent memory** to remember every stakeholder concern, competitor mention, pricing dispute, and agreed follow-up across months of deal interactions.

---

## 🔥 Key Features

- **🌐 Real-Time HUD Overlay:** Injected floating UI that sits above your CRM and meeting software without disrupting workflow.
- **🧠 Persistent Deal Memory (Hindsight):** Automatically indexes transcripts, call notes, and emails to track deal progression over time.
- **🛡️ Objection & Battlecard Recall:** Detects competitor mentions or objections in real time and recalls past winning tactics that closed similar deals.
- **👤 Stakeholder Dynamics Tracking:** Tracks individual buyer personas, roles, preferences, and promised deliverables across complex enterprise buying committees.
- **⚡ Automated Post-Call Synthesis:** Summarizes key decisions, updates Hindsight memory, and drafts hyper-personalized follow-up emails in seconds.

---

## 🏗️ Architecture & Tech Stack
┌────────────────────────────────────────────────────────┐
│   Chrome Extension (React + Shadow DOM Overlay UI)     │
└───────────┬────────────────────────────────────────────┘
│ API Calls / Webhooks
▼
┌────────────────────────────────────────────────────────┐
│     Node.js / Express Backend (API Gateway & Auth)     │
└───────────┬────────────────────────────────────────────┘
│ Async AI Processing
▼
┌────────────────────────────────────────────────────────┐
│    Python / FastAPI Microservice (Groq Orchestration)  │
└────────────────────────────────────┬───────────────────┘
│ Memory Queries                     │ Store State
▼                                    ▼
┌───────────────────────┐  ┌─────────────────────────────┐
│ Hindsight Memory Bank │  │     MongoDB Atlas DB        │
└───────────────────────┘  └─────────────────────────────┘

- **Frontend:** React.js, Tailwind CSS, Chrome Extension V3 Manifest, Web Speech API
- **Backend:** Node.js, Express.js, MongoDB Atlas
- **AI Microservice:** Python 3.11, FastAPI, Groq SDK (`qwen/qwen3-32b` / `openai/gpt-oss-120b`)
- **Memory Engine:** Hindsight Cloud SDK (by Vectorize)

---

## 🧠 How Hindsight Memory is Used

Hindsight is the central intelligence engine of this project (accounting for persistent recall across the deal lifecycle):

1. **Ingestion (`/memory/retain`):** Post-call transcripts, CRM notes, and email logs are sent to Hindsight, tagged with `deal_id`, `client_id`, and `stakeholder_id`.
2. **Context Retrieval (`/memory/recall`):** When a rep opens a deal page or starts a meeting, the overlay queries Hindsight for past unresolved objections, competitor mentions, and pricing constraints.
3. **Adaptive Learning:** Hindsight tracks which objection-handling approaches led to successful outcomes, surfacing winning tactics over time.

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** v18+ and **npm**
- **Python** 3.10+
- **MongoDB** instance (Local or Atlas)
- **Hindsight Cloud Account** ([Register here](https://ui.hindsight.vectorize.io) — Use code `MEMHACK99` for free credits)
- **Groq API Key** ([Get free key here](https://groq.com/))

### Local API

DealMind exposes a small FastAPI layer over the existing intelligence services.
Keep credentials in the local `.env` file; do not commit or share that file.

Install dependencies and start the API with:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload
```

The local API is available at `http://127.0.0.1:8000` and its interactive
OpenAPI documentation is at `http://127.0.0.1:8000/docs`.

Available endpoints:

- `GET /health`
- `POST /api/deals/{deal_id}/interactions`
- `GET /api/deals/{deal_id}/brief`
- `GET /api/deals/{deal_id}/changes`
- `GET /api/deals/{deal_id}/similar`
- `POST /api/deals/{deal_id}/why`
- `POST /api/deals/{deal_id}/outcome`
- `POST /api/deals/{deal_id}/autopsy`

---
