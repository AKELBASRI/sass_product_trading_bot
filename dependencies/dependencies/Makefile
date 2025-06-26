.PHONY: help build up down logs clean restart
help:
	@echo "Available commands:"
	@echo "  make build    - Build all Docker images"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make logs     - View logs"
	@echo "  make clean    - Clean up containers and volumes"
	@echo "  make restart  - Restart all services"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	docker system prune -f

restart:
	docker-compose restart

logs-backend:
	docker-compose logs -f trading-backend

logs-dashboard:
	docker-compose logs -f trading-dashboard

shell-backend:
	docker exec -it trading-backend /bin/bash

shell-redis:
	docker exec -it trading-redis redis-cli
