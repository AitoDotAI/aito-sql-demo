{ pkgs ? import <nixpkgs> {} }:

let
  python = pkgs.python312;
in
pkgs.mkShell {
  name = "aito-sql-demo";

  buildInputs = [
    # Python (backend: FastAPI + uvicorn via uv)
    python
    pkgs.uv

    # Node / Next.js frontend
    # Pinned to the active LTS. Node 20 went EOL and nixpkgs marks EOL
    # releases insecure, which makes the shell refuse to evaluate.
    pkgs.nodejs_24
    pkgs.corepack_24

    # Playwright system dependencies (screenshot scripts in frontend/scripts/)
    pkgs.playwright-driver.browsers

    # Postgres client — the spine of this demo is a psql session against Aito's
    # pgwire listener, so psql is a hard dependency, not a convenience. Brings
    # pg_dump/pg_isready along, which the probe scripts use.
    pkgs.postgresql_17

    # Dev tools
    pkgs.jq
    pkgs.curl
    pkgs.httpie
    pkgs.watchexec
  ];

  shellHook = ''
    # Let uv manage the virtualenv against the nix-provided interpreter.
    export UV_PYTHON_PREFERENCE=only-system

    # Sync deps on shell entry (no-op if already in sync).
    if [ -f pyproject.toml ]; then
      uv sync --quiet 2>/dev/null || true
    fi

    # Use nix-managed Playwright browsers rather than `npx playwright install`.
    export PLAYWRIGHT_BROWSERS_PATH="${pkgs.playwright-driver.browsers}"
    export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

    # Load .env if present (gitignored; holds AITO_API_KEY etc.)
    if [ -f .env ]; then
      set -a
      # shellcheck disable=SC1091
      . ./.env
      set +a
    fi

    # Project env defaults
    export AITO_API_URL="''${AITO_API_URL:-http://localhost:8200}"
    export AITO_API_KEY="''${AITO_API_KEY:-}"
    export PYTHONDONTWRITEBYTECODE=1
    export PYTHONUNBUFFERED=1

    # pgwire connection, derived from the Aito instance so `psql` alone connects.
    # Per the SQL guide: the password IS the API key and `user` is ignored.
    #
    # `dbname` means one of two things and the URL tells us which. On a
    # MULTI-database server (served as `<host>/db/<name>/...`) it selects the
    # DATABASE, optionally `<db>.<env>`. On a single-database server it selects
    # the ENVIRONMENT, where aito/postgres/empty mean the master env. Getting
    # this wrong is not a clear error: an unknown database is reported as
    # "password authentication failed", deliberately, so that a reachable port
    # cannot be used to enumerate databases. So derive it rather than guess.
    export PGHOST="''${PGHOST:-$(echo "$AITO_API_URL" | sed -E 's#^[a-z]+://##; s#[:/].*$##')}"
    export PGPORT="''${PGPORT:-5432}"
    export PGUSER="''${PGUSER:-aito}"
    if [ -z "''${PGDATABASE:-}" ]; then
      case "$AITO_API_URL" in
        */db/*) PGDATABASE=$(echo "$AITO_API_URL" | sed -E 's#.*/db/##; s#/.*##') ;;
        *)      PGDATABASE="''${AITO_ENV:-aito}" ;;
      esac
      export PGDATABASE
    fi
    export PGPASSWORD="$AITO_API_KEY"

    # Remind if Aito key is missing
    if [ -z "$AITO_API_KEY" ]; then
      echo ""
      echo "  AITO_API_KEY not set. Export it or add to .env"
      echo "  export AITO_API_KEY=your-key-here"
      echo ""
    fi

    echo ""
    echo "Aito SQL demo — run ./do help for available commands"
    echo "  psql target: $PGHOST:$PGPORT db=$PGDATABASE  (just run \`psql\`)"
    echo ""
  '';
}
