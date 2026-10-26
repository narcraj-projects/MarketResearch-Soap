export NEXT_TELEMETRY_DISABLED := 1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD := 1
export LANGSMITH_TRACING := false
export LANGCHAIN_TRACING_V2 := false
export LANGGRAPH_STRICT_MSGPACK := true

.PHONY: install lint typecheck test build check api web auth-start auth-prepare auth-test auth-stop test-e2e
install:
	cd backend && uv sync --frozen --extra test --python 3.13
	cd frontend && npm ci --no-audit --fund=false
lint:
	cd backend && uv run --frozen --extra test --no-sync ruff check app tests tools migrations
	cd frontend && npm run lint
typecheck:
	cd backend && uv run --frozen --extra test --no-sync mypy
	cd frontend && npm run typecheck
test:
	cd backend && uv run --frozen --extra test --no-sync pytest -q -m 'not integration' -p no:cacheprovider
	cd frontend && npm test
build:
	cd backend && uv build --offline
	cd backend && uv run --frozen --extra test --no-sync alembic heads
	cd frontend && npm run build
check: lint typecheck test build
api:
	cd backend && uv run --frozen --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8000
web:
	cd frontend && npm run dev
auth-start:
	pwsh -NoProfile -File scripts/local-auth.ps1 -Action start
auth-prepare:
	pwsh -NoProfile -File scripts/local-auth.ps1 -Action prepare
auth-test:
	pwsh -NoProfile -File scripts/local-auth.ps1 -Action test
auth-stop:
	pwsh -NoProfile -File scripts/local-auth.ps1 -Action stop
test-e2e:
	cd frontend && npm run test:e2e
