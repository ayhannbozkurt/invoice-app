.PHONY: build up down logs test clean format lint

# Docker commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

# Local development
install:
	uv sync

run:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	uv run celery -A app.tasks.celery worker --loglevel=info --concurrency=2

# Quality & Testing
test:
	uv run pytest tests/ -v

format:
	uv run black . && uv run isort .

lint:
	uv run flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	uv run mypy .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
