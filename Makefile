.PHONY: setup smoke mvp matrix lint format test clean docker-build

setup:
	uv sync --all-extras

docker-build:
	docker build -t acb-sandbox:latest -f sandbox/Dockerfile sandbox/

smoke:
	uv run python scripts/smoke_test.py

mvp:
	uv run python scripts/run_mvp.py

matrix:
	uv run python scripts/run_matrix.py

lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run pytest -v

clean:
	rm -rf .venv __pycache__ .ruff_cache .mypy_cache .pytest_cache
	docker container prune -f
