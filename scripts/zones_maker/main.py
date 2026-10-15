"""Textual Interface to create a `zones.toml` configuration.

.. note::
    To launch the TUI application, change directory to position yourself at the `scripts` folder
    and run `python zones_maker/main.py`.
    
    ```bash
    cd scripts
    python zones_maker/main.py # or python3 zones_maker/main.py
    ```

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0
"""

from __future__ import annotations

import sys

import argparse
from pathlib import Path
from typing import Callable, cast

import geopandas as gpd # pylint: disable=E0401
from textual.app import App, ComposeResult # pylint: disable=E0401
from textual.containers import Horizontal, Vertical # pylint: disable=E0401
from textual.widgets import ( # pylint: disable=E0401
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option # pylint: disable=E0401

PYTHONPATH = str(Path.cwd())
print(PYTHONPATH)
sys.path.insert(0, PYTHONPATH)

from zones_maker.utils import ( # pylint: disable=C0413
    FAMILY_NAMES,
    PRECISION_ORDER,
    Dataset,
    DatasetSelection,
    Precision,
    SaveMode,
    ZonesConfig,
    build_zones_config,
    load_catalog,
    is_precision,
    resolve_selected_shapefile,
    save_zones_config,
    validate_mapping,
    validate_zones_config,
    zones_config_to_toml,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NARROW_COLUMN_CLASS = "column narrow"
CHOOSE_DATASET_HELP = "Choisissez un jeu du catalogue."
ACTIVE_DATASET_SELECTOR = "#active-dataset"
ACTIVE_PRECISION_SELECTOR = "#active-precision"
SELECTION_STATUS_SELECTOR = "#selection-status"
MAPPING_STATUS_SELECTOR = "#mapping-status"
EXPORT_STATUS_SELECTOR = "#export-status"


class ZoneMakerApp(App[None]):  # pylint: disable=R0902, R0904
    """TUI plein écran de sélection et de configuration des jeux Natural Earth."""

    TITLE = "GeoReforge · Zones"
    SUB_TITLE = "Sélection, exploration et export TOML"
    CSS = """
    Screen {
        background: #101820;
    }
    TabbedContent {
        height: 1fr;
    }
    TabPane {
        padding: 1 2;
    }
    .pane-title {
        text-style: bold;
        color: #f4b942;
        margin-bottom: 1;
    }
    .column {
        width: 1fr;
        height: 1fr;
        border: round #40505c;
        padding: 1;
        margin-right: 1;
    }
    .wide {
        width: 2fr;
    }
    .narrow {
        width: 1fr;
    }
    .status {
        height: auto;
        min-height: 2;
        margin-top: 1;
        color: #d7e0e7;
    }
    #dataset-options, #selected-options {
        height: 1fr;
        border: tall #40505c;
    }
    #precision-options {
        height: auto;
        max-height: 12;
        margin: 1 0;
    }
    #mapping-fields {
        height: auto;
        margin-bottom: 1;
    }
    #class-table {
        height: 1fr;
    }
    #data-preview, #toml-preview {
        height: 1fr;
        border: round #40505c;
        padding: 1;
        overflow: auto;
    }
    #target-input {
        width: 1fr;
    }
    #mapping-status, #selection-status, #export-status {
        height: auto;
        min-height: 2;
        margin-top: 1;
    }
    """
    BINDINGS = [("ctrl+c", "quit", "Quitter"), ("q", "quit", "Quitter")]

    def __init__(
        self,
        catalog_path: Path = PROJECT_ROOT / "src" / "naturalearth.json",
        data_path: Path = PROJECT_ROOT / "tmp",
        zones_path: Path = PROJECT_ROOT / "src" / "zones.toml",
    ) -> None:
        super().__init__()
        self.catalog_path = catalog_path
        self.data_path = data_path
        self.zones_path = zones_path
        self.datasets = load_catalog(catalog_path)
        self.datasets_by_key = {
            self._dataset_key(dataset): dataset for dataset in self.datasets
        }
        self.selected: dict[str, set[Precision]] = {}
        self.mappings: dict[str, dict[str, object]] = {}
        self.active_dataset: Dataset | None = None
        self.active_frame: gpd.GeoDataFrame | None = None
        self.active_class_values: list[str] = []

    @staticmethod
    def _dataset_key(dataset: Dataset) -> str:
        return f"{dataset.family}:{dataset.link_part}"

    def _select(self, selector: str) -> Select[str]:
        return cast(Select[str], self.query_one(selector, Select))

    def _class_table(self) -> DataTable[str]:
        return cast(DataTable[str], self.query_one("#class-table", DataTable))

    def compose(self) -> ComposeResult:
        """Compose l’interface utilisateur de l’application."""
        yield Header()
        with TabbedContent(initial="selection-tab"):
            with TabPane("Sélection", id="selection-tab"), Horizontal():
                with Vertical(classes="column wide"):
                    yield Label("Catalogue Natural Earth", classes="pane-title")
                    yield Select(
                        [("Toutes les familles", "all")]
                        + [(family.capitalize(), family) for family in FAMILY_NAMES],
                        value="all",
                        allow_blank=False,
                        id="family-filter",
                    )
                    yield Input(placeholder="Rechercher un jeu…", id="catalog-search")
                    yield OptionList(id="dataset-options")
                with Vertical(classes=NARROW_COLUMN_CLASS):
                    yield Label("Précisions disponibles", classes="pane-title")
                    yield Static(CHOOSE_DATASET_HELP, id="dataset-description")
                    yield Vertical(id="precision-options")
                    yield Button(
                        "Ajouter la sélection", id="add-selection", variant="primary"
                    )
                    yield Static("", id="selection-status", classes="status")
                with Vertical(classes=NARROW_COLUMN_CLASS):
                    yield Label("Jeux retenus", classes="pane-title")
                    yield OptionList(id="selected-options")
                    yield Button("Retirer le jeu", id="remove-selection", variant="error")
            with TabPane("Exploration et mapping", id="mapping-tab"), Horizontal():
                with Vertical(classes=NARROW_COLUMN_CLASS):
                    yield Label("Jeu à explorer", classes="pane-title")
                    yield Select([], prompt="Sélectionner un jeu", id="active-dataset")
                    yield Select([], prompt="Précision", id="active-precision")
                    yield Button("Explorer le SHP", id="explore-dataset", variant="primary")
                    yield Static("Aucun fichier chargé.", id="mapping-status", classes="status")
                    yield Static("", id="data-preview")
                with Vertical(classes="column wide"):
                    yield Label("Correspondance des colonnes", classes="pane-title")
                    with Vertical(id="mapping-fields"):
                        yield Select([], prompt="Colonne du nom", id="mapping-name")
                        yield Select([], prompt="Colonne du code", id="mapping-code")
                        yield Select([], prompt="Colonne de géométrie", id="mapping-geometry")
                        yield Select([], prompt="Colonne de classe", id="mapping-class")
                    yield Label("Valeurs de classe", classes="pane-title")
                    yield DataTable(id="class-table", cursor_type="row")
                    with Horizontal():
                        yield Input(placeholder="Valeur métier", id="target-input")
                        yield Button("Appliquer", id="apply-class")
                    yield Button("Enregistrer le mapping", id="save-mapping", variant="primary")
            with TabPane("Export", id="export-tab"):
                yield Label("Aperçu TOML", classes="pane-title")
                yield Static("La configuration apparaîtra ici.", id="toml-preview")
                yield Button("Préparer l’export", id="prepare-export", variant="primary")
                with Horizontal():
                    yield Button(
                        "Remplacer zones.toml",
                        id="replace-file",
                        variant="error",
                        disabled=True,
                    )
                    yield Button("Enregistrer une copie datée", id="dated-file", disabled=True)
                yield Static("", id="export-status", classes="status")
        yield Footer()

    def on_mount(self) -> None:
        """Initialise les options des panneaux après leur montage."""
        self.query_one(DataTable).add_columns("Valeur source", "Valeur cible")
        self.refresh_catalog()
        self.refresh_selected()
        self.refresh_export_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Gère les changements dans les champs de saisie."""
        if event.input.id == "catalog-search":
            self.refresh_catalog()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Gère les changements dans les menus déroulants."""
        if event.select.id == "family-filter":
            self.refresh_catalog()
        elif event.select.id == "active-dataset":
            self.refresh_precision_options()
        elif event.select.id == "mapping-class":
            self.refresh_class_values()

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Gère la sélection d'options dans les listes d'options."""
        if event.option_list.id == "dataset-options" and event.option.id:
            self.active_dataset = self.datasets_by_key.get(event.option.id)
            await self.refresh_precision_checks()
        elif event.option_list.id == "selected-options" and event.option.id:
            self.query_one(ACTIVE_DATASET_SELECTOR, Select).value = event.option.id

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Gère la sélection d'une ligne dans le tableau de données."""
        source_value = str(event.row_key.value)
        mapping = (
            self.mappings.get(self.active_dataset.link_part, {})
            if self.active_dataset is not None
            else {}
        )
        classes = mapping.get("classes", {})
        class_mapping = cast(dict[str, str], classes) if isinstance(classes, dict) else {}
        target = class_mapping.get(source_value, "")
        self.query_one("#target-input", Input).value = target

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Gère les actions déclenchées par les boutons."""
        actions = {
            "add-selection": self.add_selection,
            "remove-selection": self.remove_selection,
            "explore-dataset": self.explore_dataset,
            "apply-class": self.apply_class,
            "save-mapping": self.save_mapping,
            "prepare-export": self.prepare_export,
            "replace-file": self.replace_file,
            "dated-file": self.save_dated_file,
        }
        action = actions.get(event.button.id or "")
        if action is not None:
            action()

    def refresh_catalog(self) -> None:
        """Applique les filtres et rafraîchit les jeux affichés."""
        family_value = self._select("#family-filter").value
        family_filter = family_value if isinstance(family_value, str) else "all"
        search = self.query_one("#catalog-search", Input).value.casefold().strip()
        option_list = self.query_one("#dataset-options", OptionList)
        option_list.clear_options()
        for dataset in self.datasets:
            if family_filter not in ("all", dataset.family):
                continue
            searchable = " ".join(
                (dataset.name, dataset.description, dataset.link_part)
            ).casefold()
            if search and search not in searchable:
                continue
            label = f"{dataset.name} · {', '.join(dataset.precisions)}"
            option_list.add_option(Option(label, id=self._dataset_key(dataset)))

    async def refresh_precision_checks(self) -> None:
        """Affiche les cases de précision du jeu actif."""
        container = self.query_one("#precision-options", Vertical)
        await container.remove_children()
        if self.active_dataset is None:
            self.query_one("#dataset-description", Static).update(
                CHOOSE_DATASET_HELP
            )
            return
        key = self._dataset_key(self.active_dataset)
        chosen = self.selected.get(key, set())
        self.query_one("#dataset-description", Static).update(
            self.active_dataset.description or self.active_dataset.name
        )
        for precision in self.active_dataset.precisions:
            checkbox = Checkbox(
                precision.capitalize(),
                value=precision in chosen,
                id=f"precision-{precision}",
            )
            await container.mount(checkbox)

    def refresh_selected(self) -> None:
        """Met à jour la liste des jeux et les choix d’exploration."""
        selected_list = self.query_one("#selected-options", OptionList)
        selected_list.clear_options()
        selected_options: list[tuple[str, str]] = []
        for key, precisions in self.selected.items():
            dataset = self.datasets_by_key[key]
            precision_label = ", ".join(
                precision for precision in PRECISION_ORDER if precision in precisions
            )
            selected_list.add_option(
                Option(f"{dataset.name} · {precision_label}", id=key)
            )
            selected_options.append((dataset.name, key))

        active_dataset = self._select(ACTIVE_DATASET_SELECTOR)
        active_dataset.set_options(selected_options)
        if selected_options:
            current = active_dataset.value
            valid_values = {value for _, value in selected_options}
            if not isinstance(current, str) or current not in valid_values:
                active_dataset.value = selected_options[0][1]
            self.refresh_precision_options()
        else:
            self._select(ACTIVE_PRECISION_SELECTOR).set_options([])
            self.query_one(MAPPING_STATUS_SELECTOR, Static).update(
                "Ajoutez un jeu pour commencer l’exploration."
            )
        self.refresh_export_preview()

    def refresh_precision_options(self) -> None:
        """Synchronise les précisions explorables avec le jeu retenu."""
        key_value = self._select(ACTIVE_DATASET_SELECTOR).value
        selected = (
            self.selected.get(key_value, set())
            if isinstance(key_value, str)
            else set[Precision]()
        )
        options = [
            (precision.capitalize(), precision)
            for precision in PRECISION_ORDER
            if precision in selected
        ]
        precision_select = self._select(ACTIVE_PRECISION_SELECTOR)
        precision_select.set_options(options)
        if options:
            precision_select.value = options[0][1]

    def add_selection(self) -> None:
        """Ajoute le jeu actif avec les précisions cochées."""
        if self.active_dataset is None:
            self.set_status(SELECTION_STATUS_SELECTOR, CHOOSE_DATASET_HELP)
            return
        container = self.query_one("#precision-options", Vertical)
        chosen: set[Precision] = {
            precision
            for precision in self.active_dataset.precisions
            if self._checkbox_is_checked(container, precision)
        }
        if not chosen:
            self.set_status(SELECTION_STATUS_SELECTOR, "Cochez au moins une précision.")
            return
        key = self._dataset_key(self.active_dataset)
        self.selected.setdefault(key, set()).update(chosen)
        self.set_status(SELECTION_STATUS_SELECTOR, f"{self.active_dataset.name} ajouté.")
        self.refresh_selected()

    @staticmethod
    def _checkbox_is_checked(container: Vertical, precision: Precision) -> bool:
        checkbox = container.query_one(f"#precision-{precision}", Checkbox)
        return checkbox.value

    def remove_selection(self) -> None:
        """Retire le jeu mis en surbrillance de la sélection."""
        selected_list = self.query_one("#selected-options", OptionList)
        if selected_list.highlighted is None:
            self.set_status(SELECTION_STATUS_SELECTOR, "Choisissez un jeu à retirer.")
            return
        option = selected_list.get_option_at_index(selected_list.highlighted)
        if option.id:
            dataset = self.datasets_by_key[option.id]
            self.selected.pop(option.id, None)
            self.set_status(SELECTION_STATUS_SELECTOR, f"{dataset.name} retiré.")
            self.refresh_selected()

    def explore_dataset(self) -> None:
        """Charge le SHP local ou le télécharge pour le jeu et la précision choisis."""
        key_value = self._select(ACTIVE_DATASET_SELECTOR).value
        precision_value = self._select(ACTIVE_PRECISION_SELECTOR).value
        if not isinstance(key_value, str) or not isinstance(precision_value, str):
            self.set_status(MAPPING_STATUS_SELECTOR, "Choisissez un jeu et une précision.")
            return
        if not is_precision(precision_value):
            self.set_status(MAPPING_STATUS_SELECTOR, "Précision inconnue.")
            return
        dataset = self.datasets_by_key[key_value]
        try:
            shapefile = resolve_selected_shapefile(
                dataset,
                precision_value,
                self.data_path,
            )
            read_file = cast(
                Callable[..., gpd.GeoDataFrame], getattr(gpd, "read_file")
            )
            self.active_frame = read_file(shapefile, encoding="utf-8")
        except (OSError, ValueError, RuntimeError) as error:
            self.set_status(MAPPING_STATUS_SELECTOR, f"Échec du chargement : {error}")
            return
        self.active_dataset = dataset
        self._prepare_mapping_fields(dataset)
        frame = self.active_frame
        geometry_column = frame.geometry.name
        preview = frame.drop(columns=[geometry_column], errors="ignore").head(6)
        columns = ", ".join(str(column) for column in frame.columns)
        self.query_one("#data-preview", Static).update(
            f"{shapefile}\nColonnes : {columns}\n\n{preview.to_string(index=False)}"
        )
        self.set_status(MAPPING_STATUS_SELECTOR, f"Fichier chargé : {shapefile.name}")

    def _prepare_mapping_fields(self, dataset: Dataset) -> None:
        frame = self.active_frame
        if frame is None:
            return
        columns = [str(column) for column in frame.columns]
        existing = self.mappings.get(dataset.link_part, {})
        defaults = {
            "mapping-name": str(existing.get("name", "")),
            "mapping-code": str(existing.get("code", "")),
            "mapping-geometry": str(existing.get("geometry", frame.geometry.name)),
            "mapping-class": str(existing.get("class", "featurecla")),
        }
        for field_id, default in defaults.items():
            selector = self._select(f"#{field_id}")
            selector.set_options([("Choisir…", "")] + [(column, column) for column in columns])
            selector.value = default if default in columns else ""
        self.refresh_class_values()

    def refresh_class_values(self) -> None:
        """Rafraîchit les valeurs sources de la colonne de classe."""
        frame = self.active_frame
        class_value = self._select("#mapping-class").value
        table = self._class_table()
        table.clear()
        self.active_class_values = []
        if frame is None or not isinstance(class_value, str) or class_value not in frame.columns:
            return
        self.active_class_values = [
            str(value) for value in frame[class_value].dropna().unique().tolist()
        ]
        existing = self.mappings.get(
            self.active_dataset.link_part if self.active_dataset else "", {}
        ).get("classes", {})
        classes = cast(dict[str, str], existing) if isinstance(existing, dict) else {}
        for source_value in self.active_class_values:
            target = classes.get(source_value, "")
            table.add_row(source_value, str(target), key=source_value)

    def apply_class(self) -> None:
        """Applique la valeur métier à la classe sélectionnée."""
        table = self._class_table()
        if not self.active_class_values:
            self.set_status(MAPPING_STATUS_SELECTOR, "Choisissez une classe dans le tableau.")
            return
        source_value = self.active_class_values[table.cursor_row]
        target = self.query_one("#target-input", Input).value.strip()
        if not target:
            self.set_status(MAPPING_STATUS_SELECTOR, "La valeur métier ne peut pas être vide.")
            return
        dataset = self.active_dataset
        if dataset is None:
            return
        mapping = self.mappings.setdefault(dataset.link_part, {})
        classes = mapping.get("classes")
        if not isinstance(classes, dict):
            classes = {}
            mapping["classes"] = classes
        classes[source_value] = target
        self.refresh_class_values()
        self.set_status(MAPPING_STATUS_SELECTOR, f"Classe « {source_value} » configurée.")

    def save_mapping(self) -> None:
        """Enregistre les colonnes choisies et les classes dans la configuration."""
        dataset = self.active_dataset
        if dataset is None or self.active_frame is None:
            self.set_status(MAPPING_STATUS_SELECTOR, "Explorez d’abord un fichier.")
            return
        field_ids = {
            "name": "#mapping-name",
            "code": "#mapping-code",
            "geometry": "#mapping-geometry",
            "class": "#mapping-class",
        }
        mapping: dict[str, object] = {
            key: self._select(selector_id).value
            for key, selector_id in field_ids.items()
        }
        previous_classes = self.mappings.get(dataset.link_part, {}).get("classes", {})
        mapping["classes"] = previous_classes if isinstance(previous_classes, dict) else {}
        self.mappings[dataset.link_part] = mapping
        errors = validate_mapping(mapping)
        if errors:
            self.set_status(MAPPING_STATUS_SELECTOR, " ".join(errors))
            return
        self.set_status(MAPPING_STATUS_SELECTOR, f"Mapping enregistré pour {dataset.name}.")
        self.refresh_export_preview()

    def current_config(self) -> ZonesConfig:
        """
        Construit la configuration actuelle des zones à partir des sélections et des mappings.
        """
        selections = [
            DatasetSelection(self.datasets_by_key[key], tuple(
                precision for precision in PRECISION_ORDER if precision in precisions
            ))
            for key, precisions in self.selected.items()
        ]
        return build_zones_config(selections, self.mappings)

    def refresh_export_preview(self) -> None:
        """Rafraîchit l’aperçu de l’export TOML en fonction de la configuration actuelle."""
        config = self.current_config()
        preview = zones_config_to_toml(config)
        self.query_one("#toml-preview", Static).update(preview)

    def prepare_export(self) -> None:
        """Valide la configuration et demande un choix explicite de destination."""
        config = self.current_config()
        errors = validate_zones_config(config)
        status = self.query_one(EXPORT_STATUS_SELECTOR, Static)
        replace_button = self.query_one("#replace-file", Button)
        dated_button = self.query_one("#dated-file", Button)
        if errors:
            status.update("Export bloqué : " + " ".join(errors))
            replace_button.disabled = True
            dated_button.disabled = True
            return
        if self.zones_path.exists():
            status.update(
                f"{self.zones_path} existe. Choisissez explicitement une destination."
            )
            replace_button.disabled = False
            dated_button.disabled = False
            return
        self._save("replace")

    def replace_file(self) -> None:
        """Remplace le fichier TOML uniquement après action explicite."""
        self._save("replace")

    def save_dated_file(self) -> None:
        """Enregistre une copie datée sans écraser une copie préexistante."""
        self._save("dated")

    def _save(self, mode: SaveMode) -> None:
        config = self.current_config()
        errors = validate_zones_config(config)
        if errors:
            self.query_one(EXPORT_STATUS_SELECTOR, Static).update(
                "Export bloqué : " + " ".join(errors)
            )
            return
        try:
            saved_path = save_zones_config(config, self.zones_path, mode)
        except (OSError, ValueError) as error:
            self.query_one(EXPORT_STATUS_SELECTOR, Static).update(str(error))
            return
        self.query_one(EXPORT_STATUS_SELECTOR, Static).update(f"Fichier enregistré : {saved_path}")
        self.query_one("#replace-file", Button).disabled = True
        self.query_one("#dated-file", Button).disabled = True

    def set_status(self, selector: str, message: str) -> None:
        """Met à jour le message de statut pour un sélecteur donné."""
        self.query_one(selector, Static).update(message)


def parse_arguments() -> argparse.Namespace:
    """Analyse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(description="Créer un fichier zones.toml Natural Earth.")
    parser.add_argument(
        "--catalog", type=Path, default=PROJECT_ROOT / "src" / "naturalearth.json"
    )
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "tmp")
    parser.add_argument("--zones", type=Path, default=PROJECT_ROOT / "src" / "zones.toml")
    return parser.parse_args()


def main() -> None:
    """Lance l’application Textual avec les chemins configurés."""
    args = parse_arguments()
    ZoneMakerApp(args.catalog, args.data, args.zones).run()


if __name__ == "__main__":
    main()
