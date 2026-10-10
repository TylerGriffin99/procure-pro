# Procure AI — local dev stack.
#
# `just start` is the one command: it builds the images, starts Postgres, runs
# migrations, seeds the demo login (user@test.com / user) and starts the
# API + frontend — all in Docker, so a fresh clone needs only Docker + just.
#
#   frontend  http://localhost:5173   (sign in with user@test.com / user)
#   api       http://localhost:8000/health
#
# The native/host helpers below (db, test*) are for running pieces outside
# Docker with a uv venv; see README.md.

set dotenv-load := true

_default:
    @just --list --unsorted

# ── The one command ───────────────────────────────────────────────────────

# Build, start the db, migrate, seed the demo user, and start the API + frontend.
start: _env
    docker compose build
    docker compose up -d db
    @echo "→ running migrations …"
    docker compose run --rm api alembic upgrade head
    @echo "→ seeding demo user (user@test.com / user) …"
    docker compose run --rm api python scripts/seed_user.py
    @echo "→ seeding sample project (Gilmours Central) …"
    docker compose run --rm api python scripts/seed_project.py
    docker compose up -d api frontend
    @just _urls

# Start the stack without rebuilding or migrating (fast).
up: _env
    docker compose up -d
    @just _urls

# Stop the stack. The database volume survives, so the next start is fast.
down:
    docker compose down --remove-orphans

# Restart the running services.
restart:
    docker compose restart

# Follow logs for every service, or one: `just logs api`
logs service="":
    docker compose logs -f --tail=100 {{service}}

# Show container status.
ps:
    docker compose ps

# Run migrations against the stack.
migrate:
    docker compose run --rm api alembic upgrade head

# Seed the demo login (user@test.com / user) and sample project. Idempotent.
seed:
    docker compose run --rm api python scripts/seed_user.py
    docker compose run --rm api python scripts/seed_project.py

# THE RESET: delete containers AND the database volume, then start fresh.
reset: _env
    docker compose down -v --remove-orphans
    @just start

# A shell in a service: `just shell api`, `just shell frontend`
shell service:
    docker compose exec {{service}} sh

# ── Native (host) helpers — run pieces outside Docker with a uv venv ────────

# Start only the database in Docker and run migrations on the host.
db:
    ./scripts/db.sh start
    ./scripts/db.sh migrate

# Run all tests
test *args:
    ./scripts/test.sh all {{args}}

# Run unit tests
test-unit *args:
    ./scripts/test.sh unit {{args}}

# Run e2e tests (real LLM calls, requires OPEN_ROUTER_API_KEY)
test-e2e *args:
    ./scripts/test.sh e2e {{args}}

# Run a single e2e test file (e.g. just test-e2e-one backend/tests/e2e/test_e2e_second_claim.py)
test-e2e-one file *args:
    ./scripts/test.sh e2e-file {{file}} {{args}}

# Run the Jev matcher eval: real Jev + LLM over the golden set, N runs, prints a
# spread report (paid, requires OPEN_ROUTER_API_KEY). `just eval runs=3` for a demo.
eval runs="10" *args:
    EVAL_RUNS={{runs}} ./scripts/test.sh eval {{args}}

# ── Lint & type-check (backend app code only) ───────────────────────────────

# Lint the backend app with ruff (app/ only; tests, migrations and scripts
# are excluded via pyproject). `just lint --fix` to apply safe fixes.
lint *args:
    cd backend && uvx ruff@0.16.10 check app {{args}}

# Type-check the backend app with ty (scoped to app/ via pyproject [tool.ty]).
typecheck:
    cd backend && uvx ty@0.0.84 check

# ── Internals ───────────────────────────────────────────────────────────────

# Create .env from the template on a fresh clone so compose can interpolate.
_env:
    @test -f .env || (cp .env.example .env && echo "→ created .env from .env.example")

_urls:
    @echo ""
    @echo "  frontend   http://localhost:5173   (sign in with user@test.com / user)"
    @echo "  api        http://localhost:8000/health"
    @echo "  postgres   postgres://localhost:6000"
    @echo ""
    @echo "  just logs        follow every service"
    @echo "  just down        stop the stack"
    @echo ""
