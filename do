#!/usr/bin/env bash
# Local-dev wrapper for the demo template. Replace name + commands as your
# demo grows; the platform only requires that production `uvicorn src.app:app`
# can be started and that `frontend/out/` exists for static export.
#
#   ./do install                  uv sync + npm install (one-time after bootstrap)
#   ./do dev                      run backend (uvicorn) + frontend (next dev)
#   ./do build                    build the frontend static export (frontend/out/)
#   ./do backend                  run backend only (foreground; matches production shape)
#   ./do test                     run all tests (pytest discovers book/ + tests/)
#   ./do test-book                run booktest snapshot tests only (book/)
#   ./do screenshot-teaser        render assets/teaser.html → assets/teaser.png (1200×630)
#   ./do screenshot-pages [...]   desktop full-page screenshots of given paths
#   ./do inspect-mobile [...]     iPhone-sized screenshots of given paths
#   ./do clean                    wipe build artifacts

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Dev ports. 88xx is this demo's block, and the block matters: the sibling
# demos each own one (8200 accounting, 8400/01 erp, 8500/01 ecommerce,
# 8600 hacker-news, 8700-02 uam), and the template's defaults of 8401/3000
# collide with four demos and three demos respectively. Several of these run
# side by side on one machine, so a collision is a silent wrong-backend proxy
# rather than a bind error.
BACKEND_PORT="${BACKEND_PORT:-8800}"
FRONTEND_PORT="${FRONTEND_PORT:-8801}"

die() { echo "✗ $*" >&2; exit 1; }
say() { echo "→ $*"; }

cmd_install() {
  command -v uv >/dev/null 2>&1 || die "uv not found (see https://docs.astral.sh/uv/)"
  command -v npm >/dev/null 2>&1 || die "npm not found"
  say "uv sync"
  uv sync
  say "npm install (frontend)"
  ( cd frontend && npm install --no-audit --no-fund )
}

cmd_build() {
  ( cd frontend && NODE_ENV=production npx next build )
  say "frontend/out/ ready ($(find frontend/out -type f | wc -l) files)"
}

cmd_backend() {
  exec uv run uvicorn src.app:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload
}

cmd_dev() {
  [ -d frontend/node_modules ] || cmd_install
  say "backend → http://localhost:${BACKEND_PORT} (uvicorn, hot-reload)"
  say "frontend → http://localhost:${FRONTEND_PORT} (next dev, proxies /api/* → backend)"
  ( BACKEND_PORT="$BACKEND_PORT" uv run uvicorn src.app:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload ) &
  BACK=$!
  trap 'kill $BACK 2>/dev/null || true' EXIT INT TERM
  ( cd frontend && BACKEND_PORT="$BACKEND_PORT" npx next dev -p "$FRONTEND_PORT" )
}

cmd_test() {
  exec uv run pytest "$@"
}

cmd_test_book() {
  # booktest tests live under book/, snapshots in books/.
  #
  # NOT pytest: booktest ships a console script and no pytest11 plugin, so
  # `pytest book/` collects the tests and then fails every one of them with
  # "fixture 't' not found". Use its own runner.
  #
  #   ./do test-book              run and compare against accepted snapshots
  #   ./do test-book -a           accept the current output as the snapshot
  #   ./do test-book -v           verbose (prints the book as it runs)
  #   ./do test-book -i           interactive review of diffs
  exec uv run booktest book/ "$@"
}

cmd_provision() {
  # Fill a fresh Aito database with the whole demo: generate, load, views,
  # and a verification pass. Idempotent — it drops and reloads.
  #
  #   AITO_API_URL=https://shared.aito.ai/db/aito-sql-demo \
  #   AITO_API_KEY=<read-write key, for the load only> ./do provision
  #
  # The load needs a READ-WRITE key because it does DDL and COPY. The DEPLOYED
  # demo must be given a READ-ONLY key instead: it only ever SELECTs, and
  # /api/sql runs arbitrary user SQL from the browser.
  [ -n "$AITO_API_URL" ] || die "AITO_API_URL not set"
  [ -n "$AITO_API_KEY" ] || die "AITO_API_KEY not set"
  say "target: $AITO_API_URL"

  uv run python -m src.generate --out data
  uv run python -m src.load --drop
  uv run python -m src.map --out data/map.json

  say "verifying…"
  uv run python - <<'EOF'
from src.config import load_config
from src.sql_client import SqlClient
c = SqlClient(load_config(), timeout=120)
rows = c.query("SELECT count(*) FROM analysis").rows
n = int(next(iter(rows[0].values())))
assert n == 3000, f"expected 3000 installs, got {n}"
for v in ("hot_sites", "temperate_sites", "three_shift", "consumer_grade"):
    c.query(f"SELECT count(*) FROM {v}")
p = c.query("SELECT value, p FROM predict('analysis','churned')").rows
print(f"  analysis: {n} rows · 4 card views present · baseline churn "
      f"{round(100 * (1 - float(p[0]['p'])), 1)}%")
EOF
  say "provisioned. Give the DEPLOYED demo a READ-ONLY key, not this one."
}

cmd_federate() {
  # Proof that a third-party engine can query Aito with no Aito-specific code.
  # Needs nothing installed: nix-shell fetches duckdb if it is not on PATH.
  local host db
  host=$(echo "$AITO_API_URL" | sed -E 's#^[a-z]+://##; s#[:/].*$##')
  db=$(echo "$AITO_API_URL" | sed -E 's#.*/db/##; s#/.*##')
  [ -n "$AITO_API_KEY" ] || die "AITO_API_KEY not set (see .env)"

  local tmp; tmp=$(mktemp)
  sed -e "s|\${AITO_HOST}|$host|" -e "s|\${AITO_DB}|$db|" -e "s|\${AITO_KEY}|$AITO_API_KEY|" \
      sql/06_federation.sql > "$tmp"
  if command -v duckdb >/dev/null 2>&1; then
    duckdb -init /dev/null < "$tmp"
  else
    say "duckdb not on PATH — fetching via nix-shell"
    nix-shell -p duckdb --run "duckdb -init /dev/null < $tmp"
  fi
  rm -f "$tmp"
}

cmd_screenshot_teaser() {
  [ -d frontend/node_modules ] || cmd_install
  ( cd frontend && node scripts/screenshot-teaser.cjs )
}

cmd_screenshot_pages() {
  [ -d frontend/node_modules ] || cmd_install
  ( cd frontend && node scripts/screenshot-pages.cjs "$@" )
}

cmd_inspect_mobile() {
  [ -d frontend/node_modules ] || cmd_install
  ( cd frontend && node scripts/inspect-mobile.cjs "$@" )
}

cmd_clean() {
  rm -rf frontend/.next frontend/out .pytest_cache frontend/scripts/output/*
  find . -type d -name __pycache__ -prune -exec rm -rf {} +
  say "cleaned"
}

cmd_help() { sed -n '1,20p' "$0" | sed -n '/^#/p'; }

case "${1:-help}" in
  install)             shift; cmd_install "$@" ;;
  dev)                 shift; cmd_dev "$@" ;;
  build)               shift; cmd_build "$@" ;;
  backend)             shift; cmd_backend "$@" ;;
  test)                shift; cmd_test "$@" ;;
  test-book)           shift; cmd_test_book "$@" ;;
  provision)           shift; cmd_provision "$@" ;;
  federate)            shift; cmd_federate "$@" ;;
  screenshot-teaser)   shift; cmd_screenshot_teaser "$@" ;;
  screenshot-pages)    shift; cmd_screenshot_pages "$@" ;;
  inspect-mobile)      shift; cmd_inspect_mobile "$@" ;;
  clean)               shift; cmd_clean "$@" ;;
  help|-h|--help)      cmd_help ;;
  *) die "unknown command: $1 (run './do help')" ;;
esac
