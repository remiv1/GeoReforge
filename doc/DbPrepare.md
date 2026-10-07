# Preparing the database

[Français](DbPrepare.fr.md) | [English]

At startup, GeoReforge prepares the spatial prerequisites and creates missing tables using SQLAlchemy and GeoAlchemy2 **before** Gunicorn starts. Re-running the bootstrap does not remove tables or data. It does not update the structure of existing tables either; model changes will need separate migrations.

## SQLite and SpatiaLite

The default setup uses `DB_TYPE=sqlite`, `EXTERNAL_DB=false`, and `DB_PATH=/var/lib/app/database.db`. The image includes the SpatiaLite module. The database directory must be writable by `appuser`, especially when mounted as a volume. On the first connection, the bootstrap initializes the spatial metadata and creates `geo_zones` and its indexes.

## External database

Create **the database** on the server before starting GeoReforge. The bootstrap does not create a server, `DB_NAME`, or a user. Set the following variables in an `env.conf` mounted at `/etc/app/env.conf`, or inject them into the container environment:

| Variable | Purpose |
| --- | --- |
| `EXTERNAL_DB` | Set to `true` for an external database. |
| `DB_TYPE` | `postgres`, `mysql`, or `mariadb`. |
| `DB_HOST`, `DB_PORT` | Address and port reachable from the container (typically `5432` or `3306`). |
| `DB_USER`, `DB_PASSWORD` | Credentials with the permissions described below. |
| `DB_NAME` | Name of an **existing** database. |
| `DB_SCHEMA` | PostgreSQL schema in which tables are created; ignored for MySQL/MariaDB. |

For example, for PostgreSQL:

```dotenv
EXTERNAL_DB=true
DB_TYPE=postgres
DB_HOST=database
DB_PORT=5432
DB_USER=georeforge
DB_PASSWORD=<secret>
DB_NAME=georeforge
DB_SCHEMA=georeforge
```

For MySQL or MariaDB, set `DB_TYPE=mysql` or `DB_TYPE=mariadb`, use port `3306`, and omit `DB_SCHEMA`. Do not keep a production password in a shared image: the current image copies `src/env.conf` as default configuration. Mount a private file or inject environment variables at deployment time. Injected variables take precedence over Pydantic's env file.

### PostgreSQL / PostGIS

- Install the **PostGIS server packages** and create `DB_NAME` ahead of time.
- Give `DB_USER` access to `DB_NAME`, permission to create `DB_SCHEMA`, and permission to create tables/indexes in that schema.
- `DB_USER` must be allowed to run `CREATE EXTENSION IF NOT EXISTS postgis` in the database. If your security policy forbids this, an administrator may install the extension ahead of time; the application still needs permission to create its tables.

The bootstrap installs the extension if needed, creates the schema if needed, then creates `geo_zones` and its spatial indexes. If PostGIS is not installed on the server or a permission is missing, startup fails before Gunicorn.

### MySQL / MariaDB

- Use a server with spatial types (MySQL 8.0+ or a MariaDB version supported by GeoAlchemy2) and create `DB_NAME` ahead of time.
- Grant `DB_USER` access to this database and permission to create tables and indexes. For future application routes, also grant `SELECT`, `INSERT`, `UPDATE`, and `DELETE`.
- Do not use `DB_SCHEMA` to select another database: `DB_NAME` selects the target database. `DB_TYPE=mariadb` chooses the MariaDB dialect, which is required for spatial DDL.

MySQL/MariaDB do not need the PostGIS extension. The bootstrap directly creates any missing tables and indexes in the selected database.

## Checking with test containers

From the project root, install test dependencies into the venv and start the three disposable services in `compose.test.yaml`. Use a password **only for tests** and never point these checks at a production database:

```sh
.venv/bin/pip install -r src/requirements-test.txt
export GEOREFORGE_TEST_PASSWORD='local-test-password'
podman compose -p georeforge-dbtest -f compose.test.yaml up -d
export TEST_POSTGRES_URL="postgresql+psycopg2://georeforge_test:${GEOREFORGE_TEST_PASSWORD}@127.0.0.1:55432/georeforge_test"
export TEST_MYSQL_URL="mysql+pymysql://georeforge_test:${GEOREFORGE_TEST_PASSWORD}@127.0.0.1:53306/georeforge_test"
export TEST_MARIADB_URL="mariadb+pymysql://georeforge_test:${GEOREFORGE_TEST_PASSWORD}@127.0.0.1:53307/georeforge_test"
.venv/bin/python -m pytest -q tests/test_database.py
podman compose -p georeforge-dbtest -f compose.test.yaml stop
```

External tests are skipped when their `TEST_*_URL` is unset. SQLite/SpatiaLite is tested without a server container. Ports are bound to `127.0.0.1`; change them if already in use. URL-encode reserved characters in passwords used in `TEST_*_URL` values.
