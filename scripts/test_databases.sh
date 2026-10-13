#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
    printf 'Interpréteur Python introuvable : %s\n' "$PYTHON_BIN" >&2
    exit 2
fi

if command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    COMPOSE=(podman compose)
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
else
    printf 'Docker Compose ou Podman Compose est requis.\n' >&2
    exit 2
fi

COMPOSE_FILE="$ROOT_DIR/compose.test.yaml"
PROJECT_NAME="georeforge-test-$$"
COMPOSE_CMD=("${COMPOSE[@]}" --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE")
COMPOSE_STARTED=0
FAILED=0

cleanup() {
    local exit_status=$?
    trap - EXIT
    if [[ "$COMPOSE_STARTED" == "1" ]]; then
        if ! "${COMPOSE_CMD[@]}" down; then
            exit_status=1
        fi
    fi
    exit "$exit_status"
}
trap cleanup EXIT

if [[ -z "${GEOREFORGE_TEST_PASSWORD:-}" ]]; then
    GEOREFORGE_TEST_PASSWORD="$("$PYTHON_BIN" -c 'import secrets; print(secrets.token_hex(24))')"
fi
if [[ ! "$GEOREFORGE_TEST_PASSWORD" =~ ^[A-Za-z0-9._~-]+$ ]]; then
    printf 'GEOREFORGE_TEST_PASSWORD doit contenir uniquement des caractères URL-safe.\n' >&2
    exit 2
fi
export GEOREFORGE_TEST_PASSWORD
export TEST_POSTGRES_URL="postgresql+psycopg2://georeforge_test:${GEOREFORGE_TEST_PASSWORD}@127.0.0.1:55432/georeforge_test"
export TEST_MYSQL_URL="mysql+pymysql://georeforge_test:${GEOREFORGE_TEST_PASSWORD}@127.0.0.1:53306/georeforge_test"
export TEST_MARIADB_URL="mariadb+pymysql://georeforge_test:${GEOREFORGE_TEST_PASSWORD}@127.0.0.1:53307/georeforge_test"

if ! "$PYTHON_BIN" -c 'import socket
for port in (55432, 53306, 53307):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))' >/dev/null 2>&1; then
    printf 'Un port de test (55432, 53306 ou 53307) est déjà utilisé.\n' >&2
    exit 2
fi

COMPOSE_STARTED=1
printf 'Démarrage des bases de test avec %s.\n' "${COMPOSE[*]}"
if ! "${COMPOSE_CMD[@]}" up -d postgres mysql mariadb; then
    printf 'Échec au démarrage d’au moins un service Compose.\n' >&2
    FAILED=1
fi

printf 'Exécution des tests paramétrés par backend.\n'
if PYTHONPATH="$ROOT_DIR/src:$ROOT_DIR/scripts" "$PYTHON_BIN" -m pytest -v \
    tests/test_data_pipeline.py tests/test_database.py tests/test_zones_maker.py; then
    printf 'Tous les tests pytest sont passés.\n'
else
    pytest_status=$?
    printf 'Échec pytest (code %s). Les autres cas paramétrés ont tout de même été exécutés.\n' \
        "$pytest_status" >&2
    FAILED=1
fi

if [[ "$FAILED" == "0" ]]; then
    printf 'Matrice terminée avec succès.\n'
else
    printf 'Matrice terminée avec au moins un échec.\n' >&2
fi
exit "$FAILED"

printf 'Exécution des tests paramétrés par backend.\n'
if ! PYTHONPATH="$ROOT_DIR/src:$ROOT_DIR/scripts" "$PYTHON_BIN" -m pytest -v \
    tests/test_data_pipeline.py tests/test_database.py tests/test_zones_maker.py; then
    FAILED=1
fi

exit "$FAILED"
