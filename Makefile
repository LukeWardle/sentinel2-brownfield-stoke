# Makefile — developer shortcuts (P0-5).
# Windows note: `make` is not bundled with Git Bash. Either install it
# (pacman/choco) or run the underlying commands directly — each target is
# a single line for exactly that reason.

.PHONY: db db-down run test psql

db:
	docker compose up -d db

db-down:
	docker compose down

run:
	python -m src.main --gss_code E06000021 --date 2026-05-25

test:
	python -m pytest tests/ -q

psql:
	docker compose exec db psql -U postgres -d sentinel2_brownfield
