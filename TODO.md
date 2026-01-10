# TODO

High-level goal: Build **Ava**, an agentic persistent-memory Telegram bot that helps users achieve long-term goals via reminders, memory, calendar, and personal GPT features.

## Phase 1 – Project setup
- [x] Initialize project structure (src, infra, docs, tests)
- [x] Choose runtime (Python) and create base app entrypoint
- [x] Add dependency management (pyproject.toml with setuptools)
- [x] Configure environment variable handling (API keys, DB URL, etc.)

## Phase 2 – Core infrastructure
- [x] Provision Postgres database (configure DATABASE_URL)
- [x] Enable PGVector extension in Postgres (via init_db/ava-migrate)
- [x] Create migrations for core tables (via SQLAlchemy models):
  - [x] Users
  - [x] Goals
  - [x] Reminders
  - [x] Memories (with vector embeddings column)
  - [x] Events / calendar links
- [x] Implement database access layer (SQLAlchemy ORM models and session helpers)

## Phase 3 – Telegram bot
- [ ] Register Telegram bot and obtain bot token
- [ ] Implement webhook or long-polling handler
- [ ] Implement basic commands/flows:
  - [ ] `/start` – onboarding and intro to Ava
  - [ ] `/help` – show capabilities (reminders, memory, calendar, GPT)
  - [ ] Command/flow to set long-term goals
  - [ ] Command/flow to manage reminders
- [ ] Add basic error handling and logging for bot interactions

## Phase 4 – LangGraph agent
- [ ] Design agent graph for Ava (nodes, tools, memory)
- [ ] Implement tools for:
  - [ ] Creating/updating goals
  - [ ] Creating/updating reminders
  - [ ] Storing and querying memories (via PGVector)
  - [ ] Creating calendar events
- [ ] Add conversational state & persistence (per-user context)
- [ ] Integrate the agent with the Telegram handler

## Phase 5 – Gemini models integration
- [ ] Obtain Gemini API credentials
- [ ] Implement client wrapper for Gemini models
- [ ] Add functions for:
  - [ ] General Q&A / “personal GPT” search
  - [ ] Embedding generation for memories (PGVector)
- [ ] Plug Gemini into LangGraph as the LLM/embedding backend

## Phase 6 – Memory system
- [ ] Define schema for stored memories (type, tags, timestamps, owner)
- [ ] Implement API for storing new memories from natural language
- [ ] Implement semantic search over memories using PGVector
- [ ] Add commands / flows in Telegram to:
  - [ ] Save a memory
  - [ ] Search/retrieve memories using natural language

## Phase 7 – Reminders and goals
- [ ] Define schema & logic for long-term goals
- [ ] Implement daily reminders scoped to goals
- [ ] Implement scheduling mechanism (e.g. cron, scheduled Lambda, or queue)
- [ ] Add Telegram flows for:
  - [ ] Creating/updating/deleting goals
  - [ ] Configuring reminder frequency and channels
- [ ] Ensure reminders contain helpful context from stored memories when relevant

## Phase 8 – Calendar (Google Calendar)
- [ ] Set up Google Cloud project and enable Calendar API
- [ ] Implement OAuth or token-based auth per user
- [ ] Implement functions to:
  - [ ] Create events
  - [ ] List upcoming events
  - [ ] Attach events to goals/memories when appropriate
- [ ] Add Telegram flows to add events and view schedule

## Phase 9 – Deployment (AWS Lambda)
- [ ] Define deployment approach (SAM, CDK, Serverless Framework, etc.)
- [ ] Package Telegram webhook handler + LangGraph agent for Lambda
- [ ] Set up API Gateway (or equivalent) endpoint for Telegram webhook
- [ ] Configure environment variables and secrets (Gemini, DB, Telegram, Google)
- [ ] Set up CI workflow to build, test, and deploy

## Phase 10 – Observability & polish
- [ ] Add structured logging
- [ ] Add basic metrics (request counts, latency, errors) and dashboards
- [ ] Implement simple alerting for failures
- [ ] Add unit/integration tests for:
  - [ ] Telegram bot handlers
  - [ ] LangGraph tools and flows
  - [ ] Memory search and retrieval
  - [ ] Reminder scheduling
  - [ ] Calendar integration
- [ ] Improve UX copy and default prompts in conversations

## Phase 11 – Stretch ideas
- [ ] Goal progress analytics (e.g. streaks, completion rates)
- [ ] Smart suggestions based on past memories and events
- [ ] Multi-language support
- [ ] Web dashboard to complement Telegram interface
