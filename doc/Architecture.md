# Target Architecture

[Français](Architecture.fr.md) | English

The target architecture is a cloud-native, single-node, containerized application.

```mermaid
flowchart TB

    User[User]

    subgraph Frontend
        UI[HTML + HTMX + CSS]
    end

    subgraph Backend["GeoReforge Application"]
        Flask[Flask API]
        Services[Business Services]
        ORM[SQLAlchemy]
        Migrations[Alembic]
    end

    subgraph Spatial["Geospatial Layer"]
        Provider[Geometry Provider]
        SpatialiteProvider[SpatiaLite Provider]
        PostGISProvider[PostGIS Provider]
    end

    subgraph Databases["Databases"]
        SQLite["(SQLite + SpatiaLite)"]
        PostgreSQL["(PostgreSQL + PostGIS)"]
    end

    subgraph DataSources["Data Sources"]
        PublicData[Public boundary data]
    end

    subgraph Outputs["Exports"]
        GeoJSON[GeoJSON]
        GPKG[GeoPackage]
        SHP[Shapefile]
        APIResponse[API Response]
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

## Business View

From a business perspective, the process for managing public boundaries in GeoReforge can be represented as follows:

```mermaid
flowchart LR

    Import[Import public boundaries]
    Base["(Geographic database)"]

    Project[GeoReforge project]

    Add[Zones to add]
    Remove[Zones to remove]

    Union[Geometric union]
    Diff[Geometric difference]
    Result[Final boundary]

    Export[GeoJSON / GPKG / SHP export]
    API[API response]

    Import --> Base
    Base --> Project

    Project --> Add
    Project --> Remove

    Add --> Union
    Remove --> Diff

    Union --> Result
    Diff --> Result

    Result --> Export
    Result --> API
```
