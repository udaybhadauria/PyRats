# RATS Backend Development Makefile

.PHONY: help install dev test lint format clean docker-build docker-up docker-down

help:
	@echo "RATS Backend - Available Commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make dev          - Run in development mode"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linting checks"
	@echo "  make format       - Format code with black"
	@echo "  make clean        - Clean up temporary files"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-up    - Start Docker containers"
	@echo "  make docker-down  - Stop Docker containers"

install:
	pip install -r requirements.txt
	@echo "✓ Dependencies installed"

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8888

test:
	pytest -v --cov=app tests/

lint:
	flake8 app/
	mypy app/

format:
	black app/

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name ".mypy_cache" -exec rm -r {} +
	@echo "✓ Cleaned up temporary files"

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f
