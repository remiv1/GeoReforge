# Guide de création de `zones.toml`

Le fichier `zones.toml` définit les jeux Natural Earth et les précisions utilisés par GeoReforge. Vous pouvez le préparer avec la TUI Textual ou le notebook Jupyter ; les deux interfaces utilisent le même catalogue et les mêmes règles de validation.

## Sommaire

- [Guide de création de `zones.toml`](#guide-de-création-de-zonestoml)
  - [Sommaire](#sommaire)
  - [Fichier et interfaces](#fichier-et-interfaces)
  - [Identifiants Natural Earth](#identifiants-natural-earth)
  - [Utiliser la Textual UI (en console plein écran)](#utiliser-la-textual-ui-en-console-plein-écran)
  - [Utiliser le notebook Jupyter](#utiliser-le-notebook-jupyter)
  - [Export et chemins de sortie](#export-et-chemins-de-sortie)

## Fichier et interfaces

La configuration regroupe les jeux en trois familles : `cultural`, `physical` et `raster`. Chaque entrée contient un nom d’affichage, les précisions disponibles et la fin du nom de téléchargement Natural Earth.

```toml
source_path = "https://naturalearth.s3.amazonaws.com"

[[data_family.cultural]]
name = "Countries"
precision = ["low", "medium", "high"]
link = "admin_0_countries"

[[data_family.physical]]
name = "Oceans"
precision = ["low", "medium", "high"]
link = "ocean"
```

La configuration par défaut du dépôt se trouve dans `src/zones.toml`. L’assistant permet de préparer un fichier complet, avec les correspondances de colonnes et de classes nécessaires à l’API.

## Identifiants Natural Earth

Consultez la [page des données Natural Earth](https://www.naturalearthdata.com/features/) pour trouver un jeu et les précisions disponibles.

![Site Natural Earth](img/ne1.png)

Les numéros de résolution Natural Earth correspondent aux valeurs suivantes dans la configuration :

- `10m` : `high` (haute résolution)
- `50m` : `medium` (résolution moyenne)
- `110m` : `low` (basse résolution)

Ouvrez la page du jeu, puis copiez le lien de téléchargement de la résolution souhaitée.

![Recherche du lien de téléchargement Natural Earth](img/ne2.png)

Pour un nom de fichier comme `ne_110m_admin_0_countries.zip`, utilisez `admin_0_countries` comme valeur `link` et `low` comme valeur `precision`. N’indiquez que les précisions souhaitées. Répétez l’opération pour chaque jeu à configurer.

## Utiliser la Textual UI (en console plein écran)

Depuis la racine du dépôt, créez un environnement dédié et installez les dépendances de l’assistant :

```sh
python3.14 -m venv .venv-zones
source .venv-zones/bin/activate
python -m pip install -r scripts/zones_maker/requirements.txt
```

Lancez l’interface plein écran :

```sh
PYTHONPATH=scripts python -m zones_maker.main
```

Les dépendances de l’assistant sont séparées de celles de l’API et ne sont pas ajoutées à l’image Docker.

1. Dans l’onglet **Sélection**, filtrez ou recherchez le catalogue, choisissez un jeu, cochez une ou plusieurs précisions, puis ajoutez-le à la sélection.

  ![Sélection d’un jeu dans la TUI](img/tui1.png)

1. Dans **Exploration et mapping**, choisissez un jeu retenu et une précision, puis sélectionnez **Explorer le SHP**. L’assistant lit le fichier présent dans `tmp/` ; s’il manque, il télécharge uniquement le jeu et la précision choisis. Associez les colonnes du nom, du code, de la géométrie et de la classe. Pour chaque classe affichée, saisissez une valeur cible et appliquez-la, puis enregistrez le mapping. L’export reste bloqué tant que les correspondances requises ou les valeurs de classe sont invalides.

  ![Correspondance des colonnes et des classes dans la TUI](img/tui2.png)

1. Dans **Export**, vérifiez l’aperçu TOML et sélectionnez **Préparer l’export**. Si la destination existe, choisissez explicitement de la remplacer ou d’enregistrer une copie datée.

  ![Aperçu et export depuis la TUI](img/tui3.png)

Appuyez sur `q` ou `Ctrl+C` pour quitter la TUI.

## Utiliser le notebook Jupyter

Le notebook offre le même parcours de catalogue, de sélection, de mapping et d’export avec ipywidgets. Le fichier `scripts/zones_maker/requirements.txt` n’installe pas les dépendances du notebook : ajoutez le noyau Jupyter et ipywidgets à l’environnement dédié.

```sh
python3.14 -m venv .venv-zones
source .venv-zones/bin/activate
python -m pip install -r scripts/zones_maker/requirements.txt
python -m pip install ipykernel ipywidgets
```

Ouvrez [`explore_file.ipynb`](explore_file.ipynb) dans VS Code ou Jupyter, choisissez le noyau Python `.venv-zones`, puis exécutez les cellules dans l’ordre. Le notebook charge le catalogue local et affiche les vues de sélection, de configuration, d’exploration/mapping et d’export.

![Sélection Natural Earth et aperçu de configuration dans le notebook](img/notebook.png)

Sélectionnez un jeu et ses précisions avant de l’explorer. L’exploration lit le SHP dans `tmp/` s’il est disponible ; sinon, elle télécharge le jeu et la précision sélectionnés. Enregistrez les correspondances de colonnes et de classes avant de préparer l’export. L’ouverture du notebook et l’affichage de ses vues ne téléchargent pas de jeu et n’écrivent pas de fichier TOML.

## Export et chemins de sortie

Les deux interfaces utilisent `src/zones.toml` par défaut. La préparation de l’export écrit directement à cette destination si elle n’existe pas. Si elle existe déjà, l’interface demande un choix explicite : la remplacer ou enregistrer une copie datée. Une copie datée suit le format `YY-MM-DD_zones.toml` dans le même répertoire que la destination configurée ; un fichier daté existant n’est jamais écrasé.

La TUI accepte des chemins personnalisés avec `--catalog`, `--data` et `--zones` :

```sh
PYTHONPATH=scripts python -m zones_maker.main \
  --catalog doc/naturalearth.json \
  --data tmp \
  --zones src/zones.toml
```

Les chemins du notebook sont définis dans sa cellule d’initialisation : catalogue `doc/naturalearth.json`, données `tmp` et fichier de sortie `src/zones.toml`. Modifiez-les dans cette cellule si vous utilisez une autre organisation.
