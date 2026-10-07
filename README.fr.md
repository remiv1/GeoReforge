# GeoReforge

**Transformez des référentiels géographiques en zones métier exploitables.**

Français | [English](README.md)

GeoReforge est un moteur open source conçu pour construire, transformer et versionner des zones géographiques métier à partir de référentiels géographiques publics.

De nombreuses décisions réglementaires, fiscales, administratives, logistiques ou commerciales dépendent de la géographie. Une organisation peut avoir besoin de savoir où un produit peut être commercialisé, quelles réglementations s'appliquent à un territoire, ou comment définir et réutiliser une zone métier dans plusieurs applications.

Les référentiels géographiques fournissent des pays, des régions et des frontières administratives, mais rarement les zones métier propres aux besoins des organisations. GeoReforge vise à combler cet écart.

## Principe

À partir de référentiels géographiques tels que [Natural Earth](https://www.naturalearthdata.com/), [GADM](https://gadm.org/) ou [geoBoundaries](https://www.geoboundaries.org/), GeoReforge vise à permettre la composition de nouvelles zones à partir de territoires existants.

Par exemple, une zone peut être définie comme l'union de la Belgique, des Pays-Bas et du Luxembourg :

```text
Belgique + Pays-Bas + Luxembourg = Benelux
```

Une zone personnalisée peut aussi être construite en retirant des territoires de l'Europe :

```text
Europe - Suisse - Royaume-Uni = Zone personnalisée
```

Les zones générées ont vocation à devenir des objets géographiques réutilisables dans d'autres projets et systèmes.

## Philosophie

GeoReforge ne se limite pas au stockage de géométries. Le projet vise à permettre de :

- décrire la construction d'une zone ;
- versionner sa définition ;
- reproduire sa génération ;
- exporter le résultat dans différents formats ;
- le réutiliser dans des systèmes tiers.

Une zone métier peut être décrite par des règles, par exemple :

```yaml
zone:
  code: BENELUX
  name: Benelux
  from: 2026-01-01
  to: 2026-12-31

operations:
  - union:
      - belgium
      - netherlands
      - luxembourg
```

Conservée dans Git, cette définition peut être auditée, examinée et régénérée au fil du temps.

## Cas d'usage

### Réglementation

Associer des réglementations à des zones géographiques et déterminer les règles applicables à un produit ou à l'un de ses composants sur un territoire donné.

```text
Produit -> Composants -> Réglementations -> Zones -> Territoire du client
```

### Fiscalité

Déterminer les règles fiscales applicables en fonction d'un territoire.

### Logistique

Construire des zones de distribution et d'approvisionnement adaptées aux besoins opérationnels.

### Analyse métier

Créer des regroupements géographiques adaptés à une activité spécifique.

### Data Engineering

Construire et maintenir des référentiels enrichissant les données opérationnelles.

## Fonctionnalités visées

Les capacités ci-dessous décrivent les objectifs du projet ; elles ne signifient pas que toutes les fonctionnalités sont déjà implémentées.

### Référentiels géographiques

- continents et pays ;
- régions administratives ;
- subdivisions territoriales.

### Construction de zones

- unions, différences et intersections de territoires ;
- zones imbriquées ;
- zones composites.

### Versionnement et reproductibilité

- définitions au format YAML (ou peut-être TOML) ;
- génération reproductible ;
- historique des modifications.

### Export

- GeoJSON ;
- Shapefile ;
- GeoPackage ;
- PostgreSQL/PostGIS ;
- SQLite/SpatiaLite.

### API et interface Web

- générer et consulter des zones ;
- explorer les référentiels géographiques ;
- prévisualiser les zones sur une carte et télécharger les artefacts générés ;
- créer des zones visuellement et automatiser les intégrations.

## Architecture

[Architecture détaillée](doc/Architecture.fr.md)

```text
Référentiels géographiques
             |
             v
       GeoReforge <---- Définitions de zones versionnées
             |
             v
      Génération des zones
             |
             v
       Formats de sortie
             |
             v
    Outils SIG, API et bases de données
```

## Objectifs du projet

- Simplifier la création de référentiels géographiques métier.
- Fournir un moteur de génération reproductible et automatisable.
- Faciliter l'enrichissement des données par le contexte géographique.
- Réduire la duplication des définitions géographiques entre applications.
- Permettre une utilisation aussi bien en local qu'en production.

## Public visé

- Data Engineers et Data Analysts ;
- équipes SIG ;
- architectes de données ;
- consultants métiers ;
- éditeurs de logiciels ;
- projets open source.

**GeoReforge ne cherche pas à remplacer les référentiels géographiques existants. Son objectif est de les transformer en référentiels métier exploitables et maintenables par les organisations.**

## Utilisation

Pour utiliser GeoReforge, plusieurs cas de figure sont à envisager.

### RUN

Pour exécuter GeoReforge en utilisant Docker, vous pouvez utiliser la commande suivante :

```sh
docker run --rm -v $(pwd)/database:/var/lib/app georeforge:latest
```

Vous avez alors une instance GeoReforge en local et la base de données est persistée dans le répertoire `database` de votre machine.

Vous avez aussi possibilité de monter en volume le fichier de configuration `config.yaml` ou le fichier d'environnement `env.conf` de la manière suivante :

```sh
docker run --rm -v $(pwd)/database:/var/lib/app -v $(pwd)/config.yaml:/etc/app/config.yaml -v $(pwd)/env.conf:/etc/app/env.conf georeforge:latest
```

Vous avez toutefois possibilité d'utiliser un utilisateur spécifique pour exécuter l'image Docker en ajoutant l'option `--user $(id -u):$(id -g)` à la commande `docker run`.

### BUILD

Si vous souhaitez utiliser un ID utilisateur et un ID de groupe spécifiques pour l'utilisateur `appuser` dans le conteneur, vous pouvez passer les arguments `UID` et `GID` lors de la construction de l'image Docker :

```sh
docker build --build-arg UID=$(id -u) --build-arg GID=$(id -g) -t georeforge:latest .
```

Vous pouvez ensuite exécuter l'image construite avec la commande `docker run` comme décrit dans la section RUN.

### Intégration dans un compose

Vous pouvez intégrer GeoReforge dans un fichier `docker-compose.yaml` de la manière suivante :

```yaml
services:
  georeforge:
    image: georeforge:latest
    volumes:
      - ./database:/var/lib/app
      - ./config.yaml:/etc/app/config.yaml
      - ./env.conf:/etc/app/env.conf
    environment:
      DB_PASSWORD: ${DB_PASSWORD}
      DB_USER: ${DB_USER}
      DB_NAME: ${DB_NAME}
      DB_SCHEMA: ${DB_SCHEMA}
      DB_HOST: ${DB_HOST}
      DB_PORT: ${DB_PORT}
```

Il vous faudra définir les variables d'environnement dans un fichier .env à la racine de votre projet ainsi que le fichier `config.yaml` suivant le modèle dans [config.yaml](./src/config.yaml).
