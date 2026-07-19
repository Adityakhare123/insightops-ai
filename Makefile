.PHONY: up down logs test backend-test frontend-test format

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

test: backend-test frontend-test

backend-test:
	docker compose run --rm api pytest

frontend-test:
	docker compose run --rm frontend npm run test -- --run

format:
	docker compose run --rm api ruff format .
	docker compose run --rm frontend npm run format
