# Ava - Your AI Personal Assistant

An agentic AI Telegram bot built with LangGraph, PostgreSQL (pgvector), and Google Gemini. Ava helps users with natural conversations, goal tracking, task automation, and more.

## Features

- **Natural Language Conversations**: Chat naturally with Gemini-powered AI
- **Long-term Memory**: Semantic memory using pgvector for context-aware conversations
- **User Management**: Approval-based access control with admin commands
- **Goal Tracking** (Coming Soon): OKR-style goals with best practices research
- **Task Automation** (Coming Soon): Reminders, web monitoring, scheduled tasks

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Poetry (Python package manager)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Google API Key (from [AI Studio](https://makersuite.google.com/app/apikey))

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ava
   ```

2. **Install uv** (if not already installed)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Create virtual environment and install dependencies**
   ```bash
   uv venv  # Create virtual environment
   source .venv/bin/activate  # Activate venv
   uv pip install -e .[dev]  # Install project and dev dependencies
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   # Note: When using Docker Compose `env_file`, do not put inline comments after values.
   # Use full-line comments starting with `#`.
   ```

5. **Start the database services**
   ```bash
   docker-compose up -d postgres redis
   ```

6. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

   If you run migrations inside Docker (e.g. `docker compose run --rm bot alembic upgrade head`), set `DATABASE_URL` to use `postgres` (not `localhost`) and `REDIS_URL` to use `redis`.

   If `DATABASE_URL` points at Supabase and you see `OSError: [Errno 101] Network is unreachable`, the Supabase `db.<project>.supabase.co` endpoint may be IPv6-only; use Supabase's pooler (IPv4) connection string or enable IPv6 in your Docker/host network.

7. **Start the bot**
   ```bash
   python -m src.main
   ```

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | Yes |
| `TELEGRAM_ADMIN_IDS` | Comma-separated admin Telegram IDs | Yes |
| `GOOGLE_API_KEY` | Google Gemini API key | Yes |
| `DATABASE_URL` | PostgreSQL connection URL | Yes |
| `REDIS_URL` | Redis connection URL | Yes |
| `SECRET_KEY` | Encryption key (min 32 chars) | Yes |

## Development

### Project Structure

```
ava/
├── src/
│   ├── bot/           # Telegram bot handlers
│   ├── config/        # Configuration management
│   ├── db/            # Database models and repositories
│   ├── services/      # LLM and external services
│   └── main.py        # Entry point
├── tests/             # Test suite
├── docker-compose.yml # Docker services
└── pyproject.toml     # Project dependencies
```

### Running Tests

```bash
# Create test database first
docker-compose exec postgres createdb -U ava ava_test

# Run tests
pytest
```

### Code Quality

```bash
# Format code
black src tests

# Lint code
ruff check src tests

# Type checking
mypy src
```

2. **Install Poetry** (if not already installed)
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. **Install dependencies**
   ```bash
   poetry install
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   # Note: When using Docker Compose `env_file`, do not put inline comments after values.
   # Use full-line comments starting with `#`.
   ```

5. **Start the database services**
   ```bash
   docker-compose up -d postgres redis
   ```

6. **Run database migrations**
   ```bash
   poetry run alembic upgrade head
   ```

7. **Start the bot**
   ```bash
   poetry run python -m src.main
   ```

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | Yes |
| `TELEGRAM_ADMIN_IDS` | Comma-separated admin Telegram IDs | Yes |
| `GOOGLE_API_KEY` | Google Gemini API key | Yes |
| `DATABASE_URL` | PostgreSQL connection URL | Yes |
| `REDIS_URL` | Redis connection URL | Yes |
| `SECRET_KEY` | Encryption key (min 32 chars) | Yes |

## Commands

### User Commands
- `/start` - Start the bot or check your status
- `/help` - Show help message
- `/settings` - View your settings

### Admin Commands
- `/pending` - View pending access requests
- `/approve <telegram_id>` - Approve a user
- `/reject <telegram_id>` - Reject a user
- `/stats` - View system statistics

## Development

### Project Structure

```
ava/
├── src/
│   ├── bot/           # Telegram bot handlers
│   ├── config/        # Configuration management
│   ├── db/            # Database models and repositories
│   ├── services/      # LLM and external services
│   └── main.py        # Entry point
├── tests/             # Test suite
├── docker-compose.yml # Docker services
└── pyproject.toml     # Project dependencies
```

### Running Tests

```bash
# Create test database first
docker-compose exec postgres createdb -U ava ava_test

# Run tests
poetry run pytest
```

### Code Quality

```bash
# Format code
poetry run black src tests

# Lint code
poetry run ruff check src tests

# Type checking
poetry run mypy src
```

## Architecture

- **Bot Framework**: python-telegram-bot
- **LLM**: Google Gemini (gemini-2.0-flash-exp)
- **Database**: PostgreSQL 16 with pgvector extension
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Caching**: Redis

## License

MIT License

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.
