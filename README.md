# Procure AI - Setup & Database Guide

## Quick start (Docker)

The whole stack runs in Docker, so a fresh clone needs only **Docker** and
[**just**](https://github.com/casey/just) installed:

```bash
just start
```

That one command builds the images, starts Postgres, runs migrations, seeds a
demo login and a sample project (Gilmours Central, with its full WBS breakdown),
and starts the API + frontend. When it finishes:

| Service  | URL                             |
| -------- | ------------------------------- |
| Frontend | http://localhost:5173           |
| API      | http://localhost:8000/health    |

Sign in with:

| Email           | Password |
| --------------- | -------- |
| `user@test.com` | `user`   |

Other handy recipes: `just logs` (follow all services), `just down` (stop,
keeping the database), `just reset` (wipe the database and start fresh),
`just migrate`, `just seed`. Run `just` on its own to list them all.

> AI features (claim parsing) need an LLM key — set the key for your chosen
> `LLM_PROVIDER` in `.env`. Everything else (login, projects, the UI) works
> without one.

## Prerequisites (native/host setup)

The steps below run the backend and frontend directly on your machine instead
of in Docker — useful for debugging or running the test suite.

- Docker and Docker Compose (for the database)
- [uv](https://docs.astral.sh/uv/) (Python package/venv manager; installs Python 3.12 for you if needed)
- Node.js (for frontend)

## Getting Started

1. **Copy the environment template:**

   ```bash
   cp .env.example .env
   ```

2. **Fill in required variables in `.env`:**
   - `POSTGRES_DB` - Database name (default: `claimreview`)
   - `POSTGRES_USER` - Database user (default: `claimreview`)
   - `POSTGRES_PASSWORD` - Database password
   - `SECRET_KEY` - Application secret key
   - `ANTHROPIC_API_KEY` - Optional, for AI features

3. **Set up the Python virtual environment with uv:**

   ```bash
   cd backend
   uv sync              # creates backend/.venv and installs from uv.lock
   cd ..
   ```

   `uv sync --extra test` also installs the test dependencies.

   Either activate the venv at the start of each session, or prefix commands with
   `uv run` (e.g. `uv run python scripts/seed_user.py`):

   ```bash
   source backend/.venv/bin/activate
   ```

4. **Start the database and run migrations:**

   ```bash
   ./scripts/db.sh start
   ./scripts/db.sh makemigrations "initial schema"
   ./scripts/db.sh migrate
   ```

5. **Seed the demo login and sample project:**

   ```bash
   python scripts/seed_user.py      # default login (below)
   python scripts/seed_project.py   # Gilmours Central project + WBS breakdown
   ```

   `seed_user.py` creates a default user so you can sign in immediately — no
   registration needed — and `seed_project.py` loads a sample project so the
   workspace opens with one already there:

   | Email           | Password |
   | --------------- | -------- |
   | `user@test.com` | `user`   |

## Sample data

This repo ships a single sample project under `claim/Gilmours/` — the Gilmours
Central progress claims and matching seismic payment recommendations — so you can
run the claim-review harness end to end against real documents.

## Scripts

### `scripts/db.sh`

Database management script. Requires the Python venv to be active and `.env` to be configured.

```bash
./scripts/db.sh [command]
```

| Command          | Description                                                        |
| ---------------- | ------------------------------------------------------------------ |
| `start`          | Start PostgreSQL in Docker (available on `localhost:6000`)          |
| `stop`           | Stop PostgreSQL container                                          |
| `migrate`        | Apply all pending Alembic migrations                               |
| `makemigrations` | Auto-generate a migration from model changes (accepts a message)   |
| `reset`          | Drop and recreate database, then run migrations (DESTRUCTIVE)      |
| `status`         | Show database container status                                     |
| `logs`           | Follow database logs                                               |
| `help`           | Show help message                                                  |

**Examples:**

```bash
./scripts/db.sh start                              # Start the database
./scripts/db.sh makemigrations "add user table"     # Generate migration after model changes
./scripts/db.sh migrate                             # Apply migrations
./scripts/db.sh reset                               # Wipe and recreate (prompts for confirmation)
./scripts/db.sh logs                                # Tail database logs
```

### Direct Database Connection

```bash
psql -h localhost -p 6000 -U claimreview -d claimreview
```

## Running the Full Application

```bash
docker-compose up
```

This starts:

- PostgreSQL on `localhost:6000`
- API on `http://localhost:8000`
- Frontend on `http://localhost:5173`

## Troubleshooting

### Database Connection Refused

```bash
./scripts/db.sh status    # Check container is running
./scripts/db.sh logs      # Check for startup errors
```

### Migration Failures

Ensure the database is running and venv is active:

```bash
./scripts/db.sh start
source backend/.venv/bin/activate
./scripts/db.sh migrate
```

### Port Already in Use

Stop the conflicting service, or change the port mapping in `docker-compose.db.yml` (`6000:5432`).
