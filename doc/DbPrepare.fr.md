# Préparer la base de données

[Français] | [English](DbPrepare.md)

Au démarrage, GeoReforge prépare les objets spatiaux nécessaires et crée les tables manquantes avec SQLAlchemy et GeoAlchemy2, **avant** de lancer Gunicorn. Le bootstrap peut être relancé : il ne supprime ni les tables ni leurs données. Il ne modifie toutefois pas la structure d'une table existante ; une évolution du modèle nécessitera des migrations distinctes.

## SQLite et SpatiaLite

Le mode par défaut utilise `DB_TYPE=sqlite`, `EXTERNAL_DB=false` et `DB_PATH=/var/lib/app/database.db`. L'image contient le module SpatiaLite. Le répertoire de la base doit être accessible en écriture par `appuser`, notamment lorsqu'il est monté en volume. Le bootstrap initialise les métadonnées spatiales lors de la première connexion et crée `geo_zones` et ses index.

## Base externe

Créez **la base de données** sur le serveur avant le démarrage de GeoReforge. Le bootstrap ne crée ni serveur, ni `DB_NAME`, ni utilisateur. Définissez ensuite ces variables dans un `env.conf` monté à `/etc/app/env.conf` ou injectez-les dans l'environnement du conteneur :

| Variable | Rôle |
| --- | --- |
| `EXTERNAL_DB` | `true` pour une base externe. |
| `DB_TYPE` | `postgres`, `mysql` ou `mariadb`. |
| `DB_HOST`, `DB_PORT` | Adresse et port accessibles depuis le conteneur (typiquement `5432` ou `3306`). |
| `DB_USER`, `DB_PASSWORD` | Identifiants ayant les droits décrits ci-dessous. |
| `DB_NAME` | Nom d'une base **déjà créée**. |
| `DB_SCHEMA` | Schéma PostgreSQL où créer les tables ; sans effet pour MySQL/MariaDB. |

Par exemple, pour PostgreSQL :

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

Pour MySQL ou MariaDB, choisissez `DB_TYPE=mysql` ou `DB_TYPE=mariadb`, port `3306`, et omettez `DB_SCHEMA`. Le mot de passe ne doit pas être conservé dans une image partagée : l'image actuelle copie `src/env.conf` comme configuration par défaut ; montez un fichier privé en volume ou injectez les variables au déploiement. Les variables injectées ont priorité sur le fichier lu par Pydantic.

### PostgreSQL / PostGIS

- Installez les **paquets PostGIS sur le serveur** PostgreSQL et créez `DB_NAME` au préalable.
- Accordez à `DB_USER` la connexion à `DB_NAME`, la possibilité d'y créer le schéma `DB_SCHEMA` et les droits de création des tables/index dans ce schéma.
- `DB_USER` doit pouvoir exécuter `CREATE EXTENSION IF NOT EXISTS postgis` dans cette base. Si votre politique de sécurité l'interdit, un administrateur peut installer l'extension au préalable ; l'application a toujours besoin des droits nécessaires pour les tables.

Le bootstrap installe l'extension si elle manque, crée le schéma s'il manque, puis la table `geo_zones` et ses index spatiaux. Si PostGIS est absent du serveur ou si un droit manque, le démarrage s'arrête avant Gunicorn.

### MySQL / MariaDB

- Utilisez un serveur avec types spatiaux (MySQL 8.0+ ou version MariaDB compatible avec GeoAlchemy2) et créez `DB_NAME` au préalable.
- Accordez à `DB_USER` l'accès à cette base et les droits de création des tables et index. Pour utiliser les futures routes métier, prévoyez également `SELECT`, `INSERT`, `UPDATE` et `DELETE`.
- N'utilisez pas `DB_SCHEMA` pour sélectionner une autre base : c'est `DB_NAME` qui détermine la base ciblée. `DB_TYPE=mariadb` sélectionne le dialecte MariaDB, nécessaire au DDL spatial.

MySQL/MariaDB ne requièrent pas d'extension PostGIS. Le bootstrap crée directement les tables et index manquants dans la base indiquée.

## Vérification sur des conteneurs de test

Depuis la racine du projet, installez les dépendances de test dans le venv, puis démarrez les trois services jetables de `compose.test.yaml`. Choisissez un mot de passe **réservé aux tests** et n'utilisez aucune base de production :

```sh
.venv/bin/pip install -r src/requirements-test.txt
export GEOREFORGE_TEST_PASSWORD='mot-de-passe-de-test'
podman compose -p georeforge-dbtest -f compose.test.yaml up -d
export TEST_POSTGRES_URL="postgresql+psycopg2://georeforge_test:${GEOREFORGE_TEST_PASSWORD}@127.0.0.1:55432/georeforge_test"
export TEST_MYSQL_URL="mysql+pymysql://georeforge_test:${GEOREFORGE_TEST_PASSWORD}@127.0.0.1:53306/georeforge_test"
export TEST_MARIADB_URL="mariadb+pymysql://georeforge_test:${GEOREFORGE_TEST_PASSWORD}@127.0.0.1:53307/georeforge_test"
.venv/bin/python -m pytest -q tests/test_database.py
podman compose -p georeforge-dbtest -f compose.test.yaml stop
```

Les tests externes sont ignorés si leur URL `TEST_*_URL` n'est pas définie. SQLite/SpatiaLite est testé sans conteneur serveur. Les ports sont liés à `127.0.0.1` ; adaptez-les si déjà utilisés. Si le mot de passe choisi comporte des caractères réservés dans une URL, encodez-les dans les `TEST_*_URL`.
