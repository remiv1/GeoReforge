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
