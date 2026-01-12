# Ava - Agentic AI Telegram Bot
## Technical Specification Document

**Version:** 1.0  
**Last Updated:** January 12, 2026  
**Status:** Active Development

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Database Schema](#4-database-schema)
5. [LangGraph Agent Design](#5-langgraph-agent-design)
6. [Core Features](#6-core-features)
7. [Goal Tracking System](#7-goal-tracking-system)
8. [API Integrations](#8-api-integrations)
9. [Security & Access Control](#9-security--access-control)
10. [Deployment Architecture](#10-deployment-architecture)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [Monitoring & Observability](#12-monitoring--observability)
13. [API Reference](#13-api-reference)
14. [Configuration](#14-configuration)

---

## 1. Executive Summary

### 1.1 Overview

Ava is a multi-user agentic AI personal assistant delivered through Telegram. It helps users with task automation, web research, goal tracking with OKR-style objectives, calendar management, email handling, and more. Built with modern AI orchestration frameworks, Ava provides intelligent assistance with long-term memory and adaptive learning.

### 1.2 Key Features

- **Conversational AI**: Natural language interaction powered by Google Gemini
- **Long-term Memory**: Semantic memory using PostgreSQL with pgvector for context-aware conversations
- **Goal Tracking**: OKR-style goal management with best practices research and adaptive task suggestions
- **Task Automation**: Background task processing for reminders, web monitoring, and scheduled operations
- **API Integrations**: Google Calendar, Gmail, Weather, News APIs
- **Multi-user Support**: Approval-based access control with generous per-user quotas
- **Hybrid Execution**: Real-time streaming for quick responses, background processing for long-running tasks
- **Adaptive Learning**: System learns from user behavior to personalize suggestions

### 1.3 Design Principles

- **Agent-First Architecture**: LangGraph state machine for reliable orchestration
- **User Privacy**: User-configurable data retention and encryption for sensitive data
- **Scalability**: Designed to scale from dozens to thousands of users
- **Observability**: Comprehensive logging and metrics for debugging and optimization
- **Extensibility**: Plugin-based tool system for easy feature additions

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Telegram Users                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Telegram Bot (Application)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Message    │  │   Command    │  │   Callback   │          │
│  │   Handler    │  │   Handler    │  │   Handler    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
└────────────────────────────┼─────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    User Access Control                           │
│  - Approval-based registration                                   │
│  - User quota enforcement                                        │
│  - Rate limiting (generous: 30 msg/min)                         │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              LangGraph Agent (State Machine)                     │
│                                                                   │
│  ┌────────────┐     ┌────────────┐     ┌────────────┐          │
│  │   Router   │────▶│  Memory    │────▶│  Planner   │          │
│  │    Node    │     │ Retriever  │     │    Node    │          │
│  └────────────┘     └────────────┘     └──────┬─────┘          │
│                                                 │                 │
│                                                 ▼                 │
│                                        ┌────────────────┐        │
│                                        │  Executor Node │        │
│                                        └────────┬───────┘        │
│                                                 │                 │
│              ┌──────────────────────────────────┤                │
│              │                 │                │                 │
│              ▼                 ▼                ▼                 │
│    ┌─────────────┐   ┌─────────────┐  ┌─────────────┐          │
│    │   Quick     │   │  Background │  │   Response  │          │
│    │  Execution  │   │  Task Queue │  │  Generator  │          │
│    │  (Stream)   │   │  (Celery)   │  │    Node     │          │
│    └─────────────┘   └─────────────┘  └─────────────┘          │
│              │                 │                │                 │
│              └─────────────────┴────────────────┘                │
│                              │                                    │
│                              ▼                                    │
│                     ┌─────────────────┐                          │
│                     │  Memory Writer  │                          │
│                     │      Node       │                          │
│                     └─────────────────┘                          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │  Search  │      │   Goal   │      │  Memory  │
    │ Service  │      │ Manager  │      │ Service  │
    └────┬─────┘      └────┬─────┘      └────┬─────┘
         │                 │                  │
         │                 │                  │
         ▼                 ▼                  ▼
    ┌─────────────────────────────────────────────┐
    │        PostgreSQL + pgvector                 │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
    │  │  Users   │  │  Memory  │  │  Goals   │  │
    │  │  Access  │  │ Vectors  │  │  Tasks   │  │
    │  └──────────┘  └──────────┘  └──────────┘  │
    └─────────────────────────────────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │    Redis     │
              │ (Cache + Msg)│
              └──────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **Telegram Bot** | Handle incoming messages, commands, callbacks; format responses |
| **Access Control** | Authenticate users, enforce quotas, rate limiting |
| **LangGraph Agent** | Orchestrate conversation flow, tool execution, decision-making |
| **Memory Service** | Store and retrieve semantic memories using pgvector |
| **Goal Manager** | Create goals, research best practices, generate tasks, track progress |
| **Search Service** | Perform web searches, parse results, extract content |
| **Task Queue (Celery)** | Execute background tasks: reminders, monitors, API syncs |
| **PostgreSQL** | Primary data store for users, conversations, goals, tasks |
| **Redis** | Caching, Celery message broker, session storage |

### 2.3 Data Flow

**Typical Conversation Flow:**
1. User sends message → Telegram Bot
2. Bot checks authentication & rate limits
3. Message passed to LangGraph Agent
4. Agent classifies intent (Router Node)
5. Agent retrieves relevant memories (Memory Retrieval Node)
6. Agent plans execution (Planner Node)
7. Agent executes tools (Executor Node)
8. Agent generates response (Response Generator Node)
9. Agent writes new memories (Memory Writer Node)
10. Response sent back to user via Telegram

**Background Task Flow:**
1. User creates reminder/monitor → Stored in database
2. Celery Beat scheduler triggers task at scheduled time
3. Celery Worker executes task
4. Result notification sent to user via Telegram

---

## 3. Technology Stack

### 3.1 Core Technologies

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Runtime** | Python | 3.11+ | Application runtime |
| **Agent Framework** | LangGraph | 0.2+ | State machine orchestration |
| **LLM** | Google Gemini | gemini-2.0-flash-exp | Text generation & reasoning |
| **Embeddings** | Google | text-embedding-004 | Semantic memory (768-dim vectors) |
| **Bot Framework** | python-telegram-bot | 20.7+ | Telegram API wrapper |
| **Database** | PostgreSQL | 15+ | Primary data store |
| **Vector Extension** | pgvector | 0.5+ | Similarity search with HNSW index |
| **Task Queue** | Celery | 5.3+ | Async task processing |
| **Message Broker** | Redis | 7.0+ | Celery backend + caching |
| **ORM** | SQLAlchemy | 2.0+ | Database abstraction (async) |
| **Migrations** | Alembic | 1.13+ | Schema versioning |
| **HTTP Client** | httpx | 0.27+ | Async HTTP requests |
| **Web Scraping** | BeautifulSoup4 + lxml | Latest | HTML parsing |
| **Config** | Pydantic Settings | 2.1+ | Configuration management |
| **Logging** | structlog | 24.1+ | Structured logging |
| **Encryption** | cryptography | 42.0+ | Credential encryption |

### 3.2 External APIs

| Service | Purpose | Cost Model |
|---------|---------|-----------|
| **Google Gemini API** | LLM and embeddings | $0.000075/1K tokens (generous free tier) |
| **Google Custom Search** | Web search | $5/1000 queries (100 free/day) |
| **Google Calendar API** | Calendar integration | Free |
| **Gmail API** | Email operations | Free |
| **OpenWeatherMap API** | Weather data | Free tier: 1000 calls/day |
| **NewsAPI** | News aggregation | Free tier: 100 requests/day |

### 3.3 Development Tools

| Tool | Purpose |
|------|---------|
| **Poetry** | Dependency management |
| **pytest** | Testing framework |
| **mypy** | Static type checking |
| **black** | Code formatting |
| **ruff** | Linting |
| **Docker Compose** | Local development environment |
| **Alembic** | Database migrations |

---

## 4. Database Schema

### 4.1 User Management

```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    language_code VARCHAR(10),
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Access control
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, suspended, banned
    approved_by INTEGER REFERENCES users(id),
    approved_at TIMESTAMP,
    
    -- Preferences (JSONB for flexibility)
    preferences JSONB DEFAULT '{}',
    
    -- Retention settings (user-configurable)
    conversation_retention_days INTEGER DEFAULT 180,
    auto_archive_enabled BOOLEAN DEFAULT true,
    
    -- Usage tracking
    message_count INTEGER DEFAULT 0,
    last_message_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_status ON users(status);

-- User quotas (generous limits)
CREATE TABLE user_quotas (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    quota_type VARCHAR(50) NOT NULL, -- daily_messages, monthly_searches, etc.
    limit_value INTEGER NOT NULL,
    current_usage INTEGER DEFAULT 0,
    reset_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_quotas_user_type ON user_quotas(user_id, quota_type);

-- Access requests (approval workflow)
CREATE TABLE access_requests (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    
    -- Request details
    reason TEXT,
    referral_code VARCHAR(50),
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected
    reviewed_by INTEGER REFERENCES users(id),
    reviewed_at TIMESTAMP,
    rejection_reason TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_access_requests_status ON access_requests(status);
CREATE INDEX idx_access_requests_telegram ON access_requests(telegram_id);
```

### 4.2 Conversations & Messages

```sql
-- Conversations
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    telegram_chat_id BIGINT NOT NULL,
    title VARCHAR(255),
    context JSONB DEFAULT '{}', -- Session context
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    archived BOOLEAN DEFAULT false,
    message_count INTEGER DEFAULT 0
);

CREATE INDEX idx_conversations_user ON conversations(user_id);
CREATE INDEX idx_conversations_chat ON conversations(telegram_chat_id);
CREATE INDEX idx_conversations_active ON conversations(user_id, ended_at) 
    WHERE ended_at IS NULL;

-- Messages
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    telegram_message_id INTEGER,
    role VARCHAR(20) NOT NULL, -- user, assistant, system, tool
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}', -- Tool calls, attachments, etc.
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_created ON messages(created_at);
```

### 4.3 Memory System (pgvector)

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Memory embeddings (semantic long-term memory)
CREATE TABLE memory_embeddings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    
    -- Memory content
    content TEXT NOT NULL,
    summary TEXT, -- Condensed version
    embedding VECTOR(768), -- text-embedding-004 produces 768-dim vectors
    
    -- Memory categorization
    memory_type VARCHAR(50) NOT NULL, -- fact, preference, conversation, entity, workflow
    entity_type VARCHAR(50), -- person, place, event, etc.
    
    -- Context
    source_conversation_id INTEGER REFERENCES conversations(id),
    source_message_ids INTEGER[], -- Array of message IDs
    
    -- Importance and retrieval
    importance_score FLOAT DEFAULT 0.5, -- 0.0 to 1.0
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    tags VARCHAR(100)[],
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Soft delete
    deleted_at TIMESTAMP
);

-- HNSW index for fast similarity search
CREATE INDEX idx_memory_embedding_hnsw ON memory_embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_memory_user ON memory_embeddings(user_id);
CREATE INDEX idx_memory_type ON memory_embeddings(memory_type);
CREATE INDEX idx_memory_importance ON memory_embeddings(importance_score DESC);
CREATE INDEX idx_memory_active ON memory_embeddings(user_id, deleted_at) 
    WHERE deleted_at IS NULL;

-- Memory consolidation tracking
CREATE TABLE memory_consolidations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    source_memory_ids INTEGER[],
    consolidated_memory_id INTEGER REFERENCES memory_embeddings(id),
    consolidation_reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 4.4 Task Management

```sql
-- Tasks
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    
    -- Task details
    task_type VARCHAR(50) NOT NULL, -- reminder, web_monitor, api_call, recurring
    title VARCHAR(500) NOT NULL,
    description TEXT,
    parameters JSONB DEFAULT '{}',
    
    -- Execution
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed, cancelled
    celery_task_id VARCHAR(255), -- Celery task UUID
    
    -- Scheduling
    schedule VARCHAR(100), -- Cron expression for recurring tasks
    scheduled_at TIMESTAMP,
    next_run TIMESTAMP,
    last_run TIMESTAMP,
    run_count INTEGER DEFAULT 0,
    
    -- Results
    result JSONB,
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_next_run ON tasks(next_run) WHERE status = 'pending';
CREATE INDEX idx_tasks_type ON tasks(task_type);

-- Web monitors (for tracking website changes)
CREATE TABLE web_monitors (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    
    url TEXT NOT NULL,
    selector VARCHAR(500), -- CSS selector for specific content
    check_frequency INTERVAL DEFAULT '1 hour',
    
    last_check TIMESTAMP,
    last_content_hash VARCHAR(64), -- SHA-256 hash
    last_change_detected TIMESTAMP,
    
    alert_on_change BOOLEAN DEFAULT true,
    alert_telegram BOOLEAN DEFAULT true,
    
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_web_monitors_user ON web_monitors(user_id);
CREATE INDEX idx_web_monitors_active ON web_monitors(active, last_check);
```

### 4.5 Goal Tracking System

```sql
-- Goals (OKR-style)
CREATE TABLE goals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    
    -- Goal details
    title VARCHAR(500) NOT NULL,
    description TEXT,
    goal_type VARCHAR(50) DEFAULT 'objective', -- objective, habit, milestone
    
    -- OKR structure
    parent_goal_id INTEGER REFERENCES goals(id) ON DELETE CASCADE,
    level INTEGER DEFAULT 0, -- 0=objective, 1=key result, 2=sub-key result
    
    -- Progress tracking
    status VARCHAR(50) DEFAULT 'active', -- active, completed, paused, archived, abandoned
    progress_percentage FLOAT DEFAULT 0.0, -- 0-100
    completion_criteria TEXT,
    
    -- Timeline
    created_at TIMESTAMP DEFAULT NOW(),
    start_date DATE,
    target_date DATE, -- Smart deadline
    completed_at TIMESTAMP,
    estimated_duration INTERVAL, -- Bot's estimate
    
    -- Best practices
    best_practices_researched BOOLEAN DEFAULT false,
    best_practices_summary TEXT,
    research_sources JSONB DEFAULT '[]',
    
    -- Reminder preferences
    reminder_frequency VARCHAR(50), -- daily, weekly, custom
    reminder_custom_schedule VARCHAR(100), -- Cron expression
    next_reminder_at TIMESTAMP,
    last_reminder_sent TIMESTAMP,
    
    -- Metadata
    tags VARCHAR(100)[],
    metadata JSONB DEFAULT '{}',
    
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_goals_user ON goals(user_id);
CREATE INDEX idx_goals_status ON goals(status);
CREATE INDEX idx_goals_parent ON goals(parent_goal_id);
CREATE INDEX idx_goals_next_reminder ON goals(next_reminder_at) 
    WHERE next_reminder_at IS NOT NULL AND status = 'active';

-- Goal relationships/dependencies
CREATE TABLE goal_relationships (
    id SERIAL PRIMARY KEY,
    from_goal_id INTEGER REFERENCES goals(id) ON DELETE CASCADE,
    to_goal_id INTEGER REFERENCES goals(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL, -- prerequisite, related, supports, blocks
    strength FLOAT DEFAULT 0.5, -- 0-1, how strongly related
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(from_goal_id, to_goal_id, relationship_type)
);

CREATE INDEX idx_goal_relationships_from ON goal_relationships(from_goal_id);
CREATE INDEX idx_goal_relationships_to ON goal_relationships(to_goal_id);

-- Goal tasks (suggested actions)
CREATE TABLE goal_tasks (
    id SERIAL PRIMARY KEY,
    goal_id INTEGER REFERENCES goals(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    
    -- Task details
    title VARCHAR(500) NOT NULL,
    description TEXT,
    task_type VARCHAR(50) DEFAULT 'action', -- action, habit, research, milestone
    
    -- Source of suggestion
    source VARCHAR(50) DEFAULT 'ai_generated', -- ai_generated, user_created, template
    confidence_score FLOAT DEFAULT 0.5, -- Bot's confidence (0-1)
    reasoning TEXT, -- Why this task was suggested
    
    -- Priority and effort
    priority VARCHAR(20) DEFAULT 'medium', -- low, medium, high
    estimated_effort VARCHAR(20), -- 5min, 30min, 1hr, etc.
    difficulty VARCHAR(20), -- easy, medium, hard
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'suggested', -- suggested, accepted, in_progress, completed, skipped, rejected
    accepted_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- User feedback (for adaptive learning)
    user_rating INTEGER, -- 1-5 stars
    was_helpful BOOLEAN,
    completion_notes TEXT,
    actual_effort VARCHAR(20),
    
    -- Scheduling
    suggested_date DATE,
    due_date DATE,
    reminder_time TIMESTAMP,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_goal_tasks_goal ON goal_tasks(goal_id);
CREATE INDEX idx_goal_tasks_user ON goal_tasks(user_id);
CREATE INDEX idx_goal_tasks_status ON goal_tasks(status);
CREATE INDEX idx_goal_tasks_reminder ON goal_tasks(reminder_time) 
    WHERE reminder_time IS NOT NULL AND status IN ('suggested', 'accepted', 'in_progress');

-- Goal progress history
CREATE TABLE goal_progress_history (
    id SERIAL PRIMARY KEY,
    goal_id INTEGER REFERENCES goals(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    
    -- Progress snapshot
    progress_percentage FLOAT NOT NULL,
    event_type VARCHAR(50) NOT NULL, -- task_completed, milestone_reached, manual_update, reflection
    description TEXT,
    
    -- Related entities
    related_task_id INTEGER REFERENCES goal_tasks(id),
    related_conversation_id INTEGER REFERENCES conversations(id),
    
    -- Reflection
    reflection TEXT,
    challenges TEXT,
    learnings TEXT,
    
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_goal_progress_goal ON goal_progress_history(goal_id);
CREATE INDEX idx_goal_progress_created ON goal_progress_history(created_at);

-- Goal templates
CREATE TABLE goal_templates (
    id SERIAL PRIMARY KEY,
    
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100), -- fitness, learning, career, finance, etc.
    keywords VARCHAR(100)[],
    
    -- Template content
    best_practices JSONB NOT NULL,
    suggested_tasks JSONB NOT NULL,
    typical_duration INTERVAL,
    difficulty_level VARCHAR(20),
    
    -- Success metrics
    completion_rate FLOAT DEFAULT 0,
    average_rating FLOAT,
    usage_count INTEGER DEFAULT 0,
    
    -- Source
    sources JSONB DEFAULT '[]',
    created_by VARCHAR(50) DEFAULT 'system',
    verified BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_goal_templates_category ON goal_templates(category);
CREATE INDEX idx_goal_templates_keywords ON goal_templates USING GIN(keywords);

-- User learning profile (adaptive learning)
CREATE TABLE user_goal_patterns (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    
    -- Behavioral patterns
    preferred_task_types VARCHAR(50)[],
    preferred_times JSONB, -- When user prefers to work
    average_task_completion_rate FLOAT,
    typical_effort_level VARCHAR(20),
    
    -- Learning insights
    successful_strategies JSONB DEFAULT '[]',
    challenging_areas JSONB DEFAULT '[]',
    
    -- Productivity patterns
    best_reminder_frequency VARCHAR(50),
    optimal_task_batch_size INTEGER,
    engagement_score FLOAT DEFAULT 0.5,
    
    -- Stats
    total_goals_created INTEGER DEFAULT 0,
    total_goals_completed INTEGER DEFAULT 0,
    total_tasks_completed INTEGER DEFAULT 0,
    average_goal_completion_time INTERVAL,
    
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_goal_patterns_user ON user_goal_patterns(user_id);
```

### 4.6 API Integrations

```sql
-- API integrations (encrypted credentials)
CREATE TABLE api_integrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    
    service_name VARCHAR(100) NOT NULL, -- gmail, google_calendar, github, etc.
    service_type VARCHAR(50), -- email, calendar, code, etc.
    
    -- Encrypted credentials
    encrypted_credentials BYTEA NOT NULL,
    encryption_key_id VARCHAR(100),
    
    -- OAuth tokens
    access_token_encrypted BYTEA,
    refresh_token_encrypted BYTEA,
    token_expires_at TIMESTAMP,
    
    -- Configuration
    config JSONB DEFAULT '{}',
    scopes VARCHAR(500)[],
    
    -- Status
    active BOOLEAN DEFAULT true,
    last_sync TIMESTAMP,
    last_error TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_api_integrations_user_service ON api_integrations(user_id, service_name);
CREATE INDEX idx_api_integrations_active ON api_integrations(active);
```

### 4.7 Audit & Monitoring

```sql
-- Audit log
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id INTEGER,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_created ON audit_log(created_at);
```

---

## 5. LangGraph Agent Design

### 5.1 Agent State

```python
from typing import TypedDict, Annotated, Sequence, Optional, List, Dict, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """State for the LangGraph agent."""
    
    # Messages
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # User context
    user_id: int
    telegram_chat_id: int
    conversation_id: int
    
    # Intent and planning
    intent: Optional[str]
    intent_confidence: float
    plan: Optional[List[Dict[str, Any]]]
    current_step: int
    
    # Memory context
    relevant_memories: List[Dict[str, Any]]
    memory_summary: Optional[str]
    
    # Tool execution
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    
    # Execution mode
    should_stream: bool
    is_background_task: bool
    task_id: Optional[int]
    
    # Response generation
    final_response: Optional[str]
    response_chunks: List[str]
    
    # Error handling
    error: Optional[str]
    retry_count: int
```

### 5.2 Graph Structure

```python
from langgraph.graph import StateGraph, START, END

# Create the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("classify_intent", classify_intent_node)
workflow.add_node("retrieve_memory", retrieve_memory_node)
workflow.add_node("plan", planner_node)
workflow.add_node("execute_tools", tool_executor_node)
workflow.add_node("background_task", background_task_node)
workflow.add_node("generate_response", response_generator_node)
workflow.add_node("write_memory", memory_writer_node)

# Define edges
workflow.add_edge(START, "classify_intent")
workflow.add_edge("classify_intent", "retrieve_memory")

# Conditional routing after memory retrieval
workflow.add_conditional_edges(
    "retrieve_memory",
    route_after_memory,
    {
        "simple_conversation": "generate_response",
        "complex_task": "plan",
        "task_management": "plan"
    }
)

# Planning routes to execution
workflow.add_conditional_edges(
    "plan",
    route_execution_mode,
    {
        "quick_execution": "execute_tools",
        "background_task": "background_task"
    }
)

# Tool execution routes to response or more execution
workflow.add_conditional_edges(
    "execute_tools",
    should_continue_execution,
    {
        "continue": "execute_tools",
        "generate": "generate_response"
    }
)

# Background task goes directly to initial response
workflow.add_edge("background_task", "generate_response")

# Response generation writes memory then ends
workflow.add_edge("generate_response", "write_memory")
workflow.add_edge("write_memory", END)

# Compile
agent = workflow.compile()
```

### 5.3 Intent Classification

**Supported Intents:**
- `conversation` - General chat, Q&A
- `search` - Web search request
- `task_create` - Create reminder/monitor/recurring task
- `task_manage` - List/cancel/modify tasks
- `goal_create` - Create a new goal
- `goal_manage` - View, edit, pause, complete goals
- `goal_research` - Research best practices
- `goal_task_suggest` - Generate task suggestions
- `goal_progress` - Update or view progress
- `calendar` - Calendar operations
- `email` - Email operations
- `weather` - Weather query
- `news` - News request

### 5.4 Agent Tools

**Core Tools:**
- `web_search` - Search the web using Google Custom Search
- `web_scrape` - Extract content from URLs
- `calculator` - Perform calculations
- `datetime` - Date and time operations

**Task Management Tools:**
- `create_reminder` - Create a reminder
- `create_web_monitor` - Monitor website for changes
- `list_tasks` - List user's tasks
- `cancel_task` - Cancel a task

**Goal Management Tools:**
- `create_goal` - Create new goal with smart deadline
- `research_best_practices` - Research goal achievement strategies
- `generate_goal_tasks` - Generate task suggestions
- `complete_goal_task` - Mark task as complete
- `update_goal_progress` - Update goal progress
- `list_goals` - List user's goals

**Integration Tools:**
- `calendar_create_event` - Create calendar event
- `calendar_list_events` - List upcoming events
- `gmail_read` - Read emails
- `gmail_send` - Send email
- `weather_get` - Get weather forecast
- `news_get` - Get latest news

---

## 6. Core Features

### 6.1 Natural Language Conversation

**Features:**
- Context-aware conversations using retrieved memories
- Multi-turn dialogues with state preservation
- Streaming responses for real-time feedback
- Markdown formatting support

**Implementation:**
- Gemini 2.0 Flash for fast, high-quality generation
- Temperature: 0.7 for balanced creativity/consistency
- Max tokens: 2048 per response
- Conversation history: Last 10 messages + relevant memories

### 6.2 Semantic Memory System

**Features:**
- Long-term memory with semantic search
- Automatic fact extraction from conversations
- User-configurable retention policies
- Memory importance scoring
- Periodic consolidation to reduce redundancy

**Implementation:**
- text-embedding-004 for 768-dimensional embeddings
- pgvector HNSW index for fast similarity search
- Top-k retrieval (k=5) with recency weighting
- Importance score = LLM-assigned value (0-1)
- Weekly consolidation job for similar memories

**Memory Types:**
- `fact` - User-stated facts ("I live in San Francisco")
- `preference` - User preferences ("I prefer morning workouts")
- `conversation` - Important conversation excerpts
- `entity` - People, places, events mentioned
- `workflow` - Learned patterns ("User always checks email at 9 AM")

### 6.3 Web Search & Research

**Features:**
- Google Custom Search integration
- Result ranking and filtering
- Content extraction from web pages
- Automatic summarization
- Citation tracking

**Implementation:**
- Up to 10 search results per query
- BeautifulSoup for HTML parsing
- Readability heuristics for main content extraction
- LLM summarization of long articles
- Source attribution in responses

### 6.4 Task Automation

**Features:**
- Reminders with flexible scheduling
- Web monitoring with change detection
- Recurring tasks with cron expressions
- Background processing with Celery
- Task status notifications

**Implementation:**
- Celery Beat for scheduling
- Celery Workers for execution (auto-scaling)
- SHA-256 hashing for change detection
- Redis as message broker
- Task retry logic with exponential backoff

---

## 7. Goal Tracking System

### 7.1 OKR-Style Goal Structure

**Hierarchy:**
- **Objectives** (Level 0): High-level goals ("Learn Machine Learning")
- **Key Results** (Level 1): Measurable outcomes ("Complete 3 ML projects")
- **Sub-Key Results** (Level 2): Detailed milestones ("Build linear regression model")

**Goal Relationships:**
- `prerequisite` - Goal A must be completed before Goal B
- `related` - Goals share similar themes
- `supports` - Goal A helps achieve Goal B
- `blocks` - Goal A prevents progress on Goal B

### 7.2 Best Practices Research

**Process:**
1. User creates goal
2. System searches for best practices:
   - Check for matching templates
   - If no template: Perform web search
   - Extract strategies from 3-5 top results
3. LLM synthesizes research into structured guide:
   - Overview
   - Key principles
   - Common pitfalls
   - Success indicators
4. Save research with source citations

### 7.3 Task Generation & Suggestion

**Initial Task Generation:**
When goal is created, system generates 5-7 starter tasks:
- Mix of priorities (high, medium, low)
- Varied effort levels (15min to 2hrs)
- Sequenced logically
- Personalized to user's profile

**Adaptive Task Suggestions:**
As user completes tasks, system learns and suggests:
- Tasks similar to completed ones (if rated highly)
- Next logical steps based on progress
- Tasks matching user's preferred difficulty
- Tasks scheduled at user's productive times

**Learning Signals:**
- Task completion rate
- User ratings (1-5 stars)
- Skip patterns
- Effort accuracy
- Completion timing

### 7.4 Smart Deadlines

**Estimation Process:**
1. Analyze goal complexity using LLM
2. Consider typical timeframes for similar goals
3. Factor in user's historical completion rates
4. Suggest realistic deadline (not aspirational)
5. Allow user to adjust

### 7.5 Progress Tracking

**Progress Calculation:**
```python
progress = (completed_weight / total_weight) * 100

where:
  weights = {high: 3, medium: 2, low: 1}
  completed_weight = sum of weights for completed tasks
  total_weight = sum of weights for all tasks
```

**Progress Events:**
- Task completion
- Milestone achievement
- Manual updates
- Reflection entries

### 7.6 Reminders & Check-ins

**Reminder Frequencies:**
- `daily` - Every day at preferred time
- `weekly` - Once per week (user picks day)
- `biweekly` - Every 2 weeks
- `custom` - Cron expression

---

## 8. API Integrations

### 8.1 Google Calendar

**OAuth Flow:**
1. User initiates: `/connect calendar`
2. Bot sends OAuth URL (deep link or web page)
3. User authorizes
4. Bot receives tokens, encrypts and stores
5. Ready for calendar operations

**Operations:**
- Create, list, update, delete events
- Check availability
- Sync task deadlines

### 8.2 Gmail

**Operations:**
- Read inbox, send emails
- Email summaries
- Email-based task creation
- Accountability partner updates

### 8.3 Weather API

**API:** OpenWeatherMap (Free tier: 1000 calls/day)

**Use Cases:**
- Weather-based task suggestions
- Outdoor activity planning
- Travel planning

### 8.4 News API

**API:** NewsAPI (Free tier: 100 requests/day)

**Use Cases:**
- Daily news briefings
- Topic-specific news
- Goal-relevant news

---

## 9. Security & Access Control

### 9.1 Authentication

**Telegram Authentication:**
- Primary: Telegram user ID (verified by Telegram)
- No password required

**Access Flow:**
1. New user sends `/start`
2. System creates access request (pending)
3. Admin receives notification
4. Admin approves/rejects
5. User notified

### 9.2 Authorization

**User Roles:**
- `pending` - Waiting for approval
- `approved` - Full access with quotas
- `admin` - Can approve users
- `suspended` - Temporary revocation
- `banned` - Permanent ban

**Data Isolation:**
- Row-Level Security in PostgreSQL
- All queries filtered by `user_id`

### 9.3 Rate Limiting

**Generous Limits (per user):**
- Messages: 30/minute
- Searches: 100/day
- Goal Tasks: 200/month
- Web Monitors: 50 active
- API Calls: 1000/day

### 9.4 Data Protection

**Encryption:**
- API credentials: AES-256-GCM
- OAuth tokens: Encrypted at rest
- Database: RDS encryption
- Transit: TLS 1.3

**GDPR Compliance:**
- `/export_data` - Download all data
- `/delete_data` - Permanent deletion
- User-configurable retention
- Audit log of operations

---

## 10. Deployment Architecture

### 10.1 AWS Infrastructure

**Services:**
- **ECS Fargate**: Bot application & Celery workers
- **RDS PostgreSQL 15**: Primary database with pgvector
- **ElastiCache Redis**: Caching & message broker
- **Application Load Balancer**: Health checks, SSL
- **S3**: Backups, uploads, logs
- **Secrets Manager**: API keys, credentials
- **CloudWatch**: Logs & metrics
- **VPC**: Network isolation

### 10.2 Cost Estimation

**Monthly Costs (USD):**
- Infrastructure: ~$238/month
  - RDS: $72
  - ElastiCache: $36
  - ECS: $75
  - ALB: $20
  - Other: $35
- API costs: ~$20-50/month
- **Total: ~$260-290/month**

---

## 11. Implementation Roadmap

### 11.0 Current Status (As Implemented)

As of January 12, 2026, the repository includes working or in-progress implementations for:
- **Phase 1 (Foundation)**: project structure, Docker Compose, core database schema/migrations, basic Telegram bot loop, user approval workflow
- **Phase 2 (Memory System)**: pgvector-backed semantic memory foundations (schema + retrieval plumbing)
- **Goal + reminder tracking MVP**: goal tracking and reminder tracking features in place
- **Production readiness improvements**: production prep work and Docker image size reductions

### Phase 1: Foundation (Week 1)
- Project structure, Docker Compose
- Database schema (users, conversations)
- Basic Telegram bot
- User approval workflow

### Phase 2: Memory System (Week 2)
- Memory embeddings with pgvector
- Embedding generation
- Semantic retrieval
- User retention settings

### Phase 3: LangGraph Agent (Week 2-3)
- State machine implementation
- Intent classification
- Tool execution
- Streaming responses

### Phase 4: Web Search (Week 3)
- Google Custom Search integration
- Result parsing
- Summarization
- Citations

### Phase 5: Goal Tracking MVP (Week 4)
- Goals and tasks tables
- Best practices research
- Task generation
- Progress tracking

### Phase 6: Task System (Week 4)
- Celery setup
- Reminders
- Background workers
- Task notifications

### Phase 7: Adaptive Learning (Week 5)
- User patterns analysis
- Feedback loops
- Adaptive suggestions
- Milestones

### Phase 8: OKR & Dependencies (Week 5-6)
- Key results
- Goal relationships
- Progress rollup
- Smart deadlines

### Phase 9: Calendar Integration (Week 6)
- OAuth flow
- Calendar operations
- Event sync
- Calendar-aware scheduling

### Phase 10: Production Deployment (Week 7)
- AWS infrastructure
- CI/CD pipeline
- Monitoring
- Documentation

---

## 12. Monitoring & Observability

### 12.1 Metrics

**Application Metrics:**
- `messages_processed_total`
- `message_processing_duration_seconds`
- `llm_api_calls_total`
- `tool_executions_total`
- `memory_retrievals_total`
- `goal_tasks_completed_total`

**System Metrics:**
- `active_users_gauge`
- `database_connections_gauge`
- `celery_queue_depth_gauge`

### 12.2 Logging

**Structured Logging:**
```json
{
  "timestamp": "2026-01-10T12:34:56.789Z",
  "level": "INFO",
  "logger": "ava.agent.graph",
  "message": "Agent execution completed",
  "user_id": 123,
  "duration_ms": 1234
}
```

### 12.3 Alerts

**Critical:**
- Database failures
- ECS task failures
- Error rate > 10%

**Warning:**
- Error rate > 5%
- API quota > 80%
- High latency

---

## 13. API Reference

### 13.1 Bot Commands

**User Commands:**
```
/start - Start the bot
/help - Show help
/settings - Configure preferences
/search <query> - Web search
/goal create <title> - Create goal
/goal list - List goals
/goal tasks <id> - View tasks
/task create <title> - Create reminder
/connect calendar - Connect Google Calendar
```

**Admin Commands:**
```
/approve <telegram_id> - Approve user
/reject <telegram_id> - Reject user
/list_pending - List pending requests
/stats - System statistics
```

---

## 14. Configuration

### 14.1 Environment Variables

**Critical Variables:**
```bash
TELEGRAM_BOT_TOKEN=required
TELEGRAM_ADMIN_IDS=required
DATABASE_URL=required
REDIS_URL=required
GOOGLE_API_KEY=required
GOOGLE_SEARCH_API_KEY=required
SECRET_KEY=required
```

**Formatting Notes:**
- When using Docker Compose `env_file`, avoid inline comments after values (e.g. `KEY=value # comment`). Prefer full-line comments starting with `#`.
- When running inside Docker Compose, service-to-service hosts should use Compose service names (e.g. `postgres`, `redis`) rather than `localhost`.

### 14.2 Database Migrations

```bash
# Create migration
poetry run alembic revision --autogenerate -m "message"

# Apply migrations
poetry run alembic upgrade head

# Rollback
poetry run alembic downgrade -1
```

**Notes:**
- If you run migrations inside Docker (e.g. `docker compose run --rm bot poetry run alembic upgrade head`), set `DATABASE_URL` to use `postgres` (not `localhost`) and `REDIS_URL` to use `redis`.
- If `DATABASE_URL` points at Supabase and you see `OSError: [Errno 101] Network is unreachable`, the direct `db.<project>.supabase.co` endpoint may be IPv6-only; use Supabase's pooler (IPv4) connection string or enable IPv6 in your Docker/host network. Alembic logs a more actionable message for this case in `src/db/migrations/env.py`.

---

## Appendix: References

- [LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/overview)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [python-telegram-bot Docs](https://docs.python-telegram-bot.org/)
- [Google Gemini API](https://ai.google.dev/gemini-api/docs)
- [Celery Documentation](https://docs.celeryq.dev/)

---

**Document Version:** 1.0  
**Last Updated:** January 12, 2026  
**Status:** Active Development
