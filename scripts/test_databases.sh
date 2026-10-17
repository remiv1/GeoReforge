#!/usr/bin/env bash

# Base test script for running database-related tests
# .. module_author:: Rémi Verschuur <rvershuur@audit-io.fr>
# .. version:: 1.0.0

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REPORT=false
while (($# > 0)); do
    case "$1" in
        --report)
            if (($# < 2)); then
                printf 'Usage : %s [--report true|false]\n' "${BASH_SOURCE[0]}" >&2
                exit 2
            fi
            report_value="$2"
            shift 2
            ;;
        --report=*)
            report_value="${1#*=}"
            shift
            ;;
        --help|-h)
            printf 'Usage : %s [--report true|false]\n' "${BASH_SOURCE[0]}"
            exit 0
            ;;
        *)
            printf 'Argument inconnu : %s\nUsage : %s [--report true|false]\n' \
                "$1" "${BASH_SOURCE[0]}" >&2
            exit 2
            ;;
    esac
    case "$report_value" in
        true|false) REPORT="$report_value" ;;
        *)
            printf 'Valeur invalide pour --report : %s (true ou false attendu).\n' \
                "$report_value" >&2
            exit 2
            ;;
    esac
done

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

REPORT_READY=0
PYTEST_ARGS=(
    -v
    tests/test_data_pipeline.py
    tests/test_database.py
    tests/test_zones_maker.py
    tests/test_auth.py
    tests/test_front.py
)
if [[ "$REPORT" == "true" ]]; then
    REPORT_TIMESTAMP="$(date '+%y-%m-%d_%H-%M')"
    REPORT_XML="$ROOT_DIR/tests/reports/xml/${REPORT_TIMESTAMP}_tests-report.xml"
    REPORT_MARKDOWN="$ROOT_DIR/tests/reports/${REPORT_TIMESTAMP}_tests-reports.md"
    if mkdir -p "$ROOT_DIR/tests/reports/xml"; then
        PYTEST_ARGS+=(--junitxml "$REPORT_XML")
        REPORT_READY=1
    else
        printf 'Impossible de créer le dossier des rapports de test.\n' >&2
        FAILED=1
    fi
fi

printf 'Exécution des tests paramétrés par backend.\n'
if PYTHONPATH="$ROOT_DIR/src:$ROOT_DIR/scripts" "$PYTHON_BIN" -m pytest \
    "${PYTEST_ARGS[@]}"; then
    printf 'Tous les tests pytest sont passés.\n'
else
    pytest_status=$?
    printf 'Échec pytest (code %s). Les autres cas paramétrés ont tout de même été exécutés.\n' \
        "$pytest_status" >&2
    FAILED=1
fi

if [[ "$REPORT_READY" == "1" ]]; then
    if "$PYTHON_BIN" "$ROOT_DIR/scripts/generate_test_report.py" \
        "$REPORT_XML" "$REPORT_MARKDOWN" "$REPORT_TIMESTAMP"; then
        printf 'Rapports générés : %s et %s.\n' \
            "${REPORT_XML#"$ROOT_DIR/"}" "${REPORT_MARKDOWN#"$ROOT_DIR/"}"
    else
        printf 'Échec de la génération du rapport Markdown.\n' >&2
        FAILED=1
    fi
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
