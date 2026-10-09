# Guide de création du fichier zones.toml

Le fichier `zones.toml` permet de définir les zones géographiques à récupérer depuis Natural Earth.

Par défaut, le conteneur embarque un fichier comprenant les définitions hautes, basses et faibles des pays, océans et mers. Vous pouvez personnaliser ce fichier en créant votre propre fichier en suivant le guide qui suit.

## Structure du fichier zones.toml

```toml
# Config file to define zones to download from the source path

# Adresse source des données Natural Earth
source_path = "https://naturalearth.s3.amazonaws.com"

# Définition de trois familles possibles : cultural, physical, raster
[[data_family.cultural]]    # Ici, on définit la famille de données culturelles
name = "Countries"  # Nom d'affichage de la zone dans l'interface utilisateur
precision = ["low", "medium", "high"]   # Précisions disponibles pour cette zone
link = "admin_0_countries"  # Parties du lien à récupérer sur le site internet

[[data_family.physical]]
name = "Oceans"
precision = ["low", "medium", "high"]
link = "ocean"

[[data_family.physical]]
name = "Marine Polygons"
precision = ["low", "medium", "high"]
link = "geography_marine_polys"
```

## Récupérer `precision` et `link` d'une zone

Aller sur [Natural Earth](https://www.naturalearthdata.com/features/)

![Site Natural Earth](ne1.png)

Pour chaque zone, vous avez trois rectangles avec des chiffres représentant les différentes précisions disponibles :

- 10 : haute précision
- 50 : précision moyenne
- 110 : basse précision

Cliquez sur le carré correspondant à la définition de la zone souhaitée pour accéder aux liens de téléchargement correspondant.

![Récupération du lien](ne2.png)

Cliquez sur _Copier l'adresse du lien_.

```txt
https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/110m/cultural/ne_110m_admin_0_countries.zip
```

Sur le nom du fichier, `ne` représente Natural Earth, `110m` représente la précision (ici basse précision), ne conservez que `admin_0_countries` pour le champ `link` dans votre fichier `zones.toml`.

Pour la précision, utilisez `low` pour 110m, `medium` pour 50m et `high` pour 10m  à l'intérieur d'une liste dans le champ `precision` de votre fichier `zones.toml`. Je ne suis pas obligé de récupérer toutes les précisions possibles.

```toml
[[data_family.cultural]]
name = "Countries"
precision = ["low", "medium", "high"]
link = "admin_0_countries"
```

Faites ceci pour chacune des zones que vous souhaitez ajouter à votre fichier `zones.toml` avant le premier lancement de l'application.
