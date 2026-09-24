.PHONY: help up down install migrate run run-memory test cov test-db lint fmt docker-up

help:
	@echo "up        - sobe o PostGIS (docker compose)"
	@echo "docker-up - sobe a stack completa (API + PostGIS)"
	@echo "down      - derruba os containers"
	@echo "install   - instala as dependencias de dev"
	@echo "migrate   - aplica as migrations (alembic upgrade head)"
	@echo "run       - inicia a API contra o PostGIS"
	@echo "run-memory- inicia a API sem banco, com o adaptador em memoria"
	@echo "test      - roda a suite (sem banco externo)"
	@echo "cov       - roda a suite com cobertura (minimo 90%)"
	@echo "test-db   - roda os testes contra o PostGIS de verdade"
	@echo "lint      - flake8"
	@echo "fmt       - black"

up:
	docker compose up -d postgis

docker-up:
	docker compose up -d --build

down:
	docker compose down

install:
	pip install -r requirements-dev.txt

migrate:
	alembic upgrade head

run:
	uvicorn app.main:app --reload

run-memory:
	REPOSITORIO=memory uvicorn app.main:app --reload

test:
	pytest -q

cov:
	pytest -q --cov --cov-fail-under=90

test-db:
	TEST_POSTGRES_URL=postgresql+psycopg://app:change-me@localhost:5432/partners pytest -q -m db

lint:
	flake8 app tests migrations

fmt:
	black app tests migrations
