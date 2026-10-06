# Architecture cible

[Français] | [English](Architecture.md)

L'architecture cible est un projet conteneurisé, Single Node, cloud-native.

```mermaid
flowchart TB

    User[Utilisateur]

    subgraph Frontend
        UI[HTML + HTMX + CSS]
    end

    subgraph Backend["Application GeoReforge"]
        Flask[Flask API]
        Services[Services métier]
        ORM[SQLAlchemy]
        Migrations[Alembic]
    end

    subgraph Spatial["Couche géospatiale"]
        Provider[Geometry Provider]
        SpatialiteProvider[SpatiaLite Provider]
        PostGISProvider[PostGIS Provider]
    end

    subgraph Databases["Bases de données"]
        SQLite["(SQLite + SpatiaLite)"]
        PostgreSQL["(PostgreSQL + PostGIS)"]
    end

    subgraph DataSources["Sources de données"]
        PublicData[Données publiques de frontières]
    end

    subgraph Outputs["Exports"]
        GeoJSON[GeoJSON]
        GPKG[GeoPackage]
        SHP[Shapefile]
        APIResponse[Réponse API]
    end

    User --> UI
    UI --> Flask

    Flask --> Services
    Services --> ORM
    ORM -. Migrations .-> Migrations

    PublicData --> Flask

    Services --> Provider

    Provider --> SpatialiteProvider
    Provider --> PostGISProvider

    SpatialiteProvider --> SQLite
    PostGISProvider --> PostgreSQL

    Services --> GeoJSON
    Services --> GPKG
    Services --> SHP
    Services --> APIResponse

    GeoJSON --> User
    GPKG --> User
    SHP --> User
    APIResponse --> User
```

## Vision métier

D'un point de vue métier, le processus de gestion des frontières publiques dans GeoReforge peut être représenté comme suit :

```mermaid
flowchart LR

    Import[Import des frontières publiques]
    Base["(Base géographique)"]

    Projet[Projet GeoReforge]

    Add[Zones à ajouter]
    Remove[Zones à retirer]

    Union[Union géométrique]
    Diff[Différence géométrique]
    Result[Frontière finale]

    Export[Export GeoJSON / GPKG / SHP]
    API[Retour API]

    Import --> Base
    Base --> Projet

    Projet --> Add
    Projet --> Remove

    Add --> Union
    Remove --> Diff

    Union --> Result
    Diff --> Result

    Result --> Export
    Result --> API
```
