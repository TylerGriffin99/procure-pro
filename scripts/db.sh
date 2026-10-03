#!/bin/bash

set -e

# Color output for clarity
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and fill in the required values"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '#' | xargs)

# Function to validate required environment variables
validate_env() {
    for var in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
        if [ -z "$(eval echo \$$var)" ]; then
            echo -e "${RED}Error: $var is not set in .env file${NC}"
            exit 1
        fi
    done
}

# Function to start the database
start_db() {
    echo -e "${YELLOW}Starting PostgreSQL database...${NC}"
    docker-compose -f docker-compose.db.yml up -d

    # Wait for database to be ready
    echo -e "${YELLOW}Waiting for database to be ready...${NC}"
    for i in {1..30}; do
        if docker-compose -f docker-compose.db.yml exec -T db pg_isready -U "$POSTGRES_USER" > /dev/null 2>&1; then
            echo -e "${GREEN}Database is ready!${NC}"
            return 0
        fi
        echo "Attempt $i/30..."
        sleep 1
    done

    echo -e "${RED}Database failed to start${NC}"
    exit 1
}

# Function to stop the database
stop_db() {
    echo -e "${YELLOW}Stopping PostgreSQL database...${NC}"
    docker-compose -f docker-compose.db.yml down
    echo -e "${GREEN}Database stopped${NC}"
}

# Function to run migrations
run_migrations() {
    echo -e "${YELLOW}Running migrations...${NC}"

    if [ ! -f "backend/alembic.ini" ]; then
        echo -e "${RED}Error: alembic.ini not found in backend directory${NC}"
        exit 1
    fi

    # Set DATABASE_URL for alembic
    export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:6000/${POSTGRES_DB}"

    cd backend
    PYTHONPATH=. alembic upgrade head
    cd ..

    echo -e "${GREEN}Migrations completed${NC}"
}

# Function to generate a new migration
generate_migration() {
    local msg="${1:-auto}"
    echo -e "${YELLOW}Generating migration: ${msg}...${NC}"

    export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:6000/${POSTGRES_DB}"

    cd backend
    PYTHONPATH=. alembic revision --autogenerate -m "$msg"
    cd ..

    echo -e "${GREEN}Migration generated${NC}"
}

# Function to reset the database (drop and recreate)
reset_db() {
    echo -e "${YELLOW}Resetting database (this will drop all data)...${NC}"
    read -p "Are you sure? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose -f docker-compose.db.yml down -v
        start_db
        run_migrations
        echo -e "${GREEN}Database reset completed${NC}"
    else
        echo "Reset cancelled"
    fi
}

# Function to show database status
status_db() {
    echo -e "${YELLOW}Database status:${NC}"
    docker-compose -f docker-compose.db.yml ps
}

# Function to show logs
logs_db() {
    docker-compose -f docker-compose.db.yml logs -f
}

# Usage information
usage() {
    cat << EOF
Database management script for claim-review

Usage: ./scripts/db.sh [command]

Commands:
    start       Start the PostgreSQL database
    stop        Stop the PostgreSQL database
    migrate         Run database migrations (requires database to be running)
    makemigrations  Generate a new migration from model changes (optional: message)
    reset           Drop and recreate database, then run migrations (DESTRUCTIVE)
    status      Show database status
    logs        Show database logs (follow mode)
    help        Show this help message

Examples:
    ./scripts/db.sh start
    ./scripts/db.sh migrate
    ./scripts/db.sh reset

Environment variables required in .env:
    POSTGRES_DB
    POSTGRES_USER
    POSTGRES_PASSWORD
EOF
}

# Main script logic
validate_env

case "${1:-help}" in
    start)
        start_db
        ;;
    stop)
        stop_db
        ;;
    migrate)
        run_migrations
        ;;
    makemigrations)
        generate_migration "${2:-auto}"
        ;;
    reset)
        reset_db
        ;;
    status)
        status_db
        ;;
    logs)
        logs_db
        ;;
    help|*)
        usage
        ;;
esac
