"""Interface ipywidgets du notebook Natural Earth."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import html
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, cast

import geopandas as gpd
import ipywidgets as widgets

from .utils import (
    PRECISION_ORDER,
    Dataset,
    DatasetSelection,
    Precision,
    SaveMode,
    ZonesConfig,
    build_zones_config,
    load_catalog,
    resolve_selected_shapefile,
    save_zones_config,
    validate_mapping,
    validate_zones_config,
    zones_config_to_toml,
)

display_output: Callable[..., None] = cast(
    Callable[..., None], getattr(import_module("IPython.display"), "display")
)


def _button_callback(action: Callable[[], None]) -> Callable[[widgets.Button], None]:
    def callback(_button: widgets.Button) -> None:
        action()

    return callback


def _button(    # pylint: disable=R0902
    callback: Callable[[widgets.Button], None], **options: Any
) -> widgets.Button:
    button = widgets.Button(**options)
    register_callback = cast(Callable[..., None], getattr(button, "on_click"))
    register_callback(callback)
    return button


class ZonesNotebook:
    """Regroupe les widgets et callbacks du notebook de préparation TOML."""

    def __init__(self, catalog_path: Path, data_path: Path, zones_path: Path) -> None:
        self.datasets = load_catalog(catalog_path)
        self.datasets_by_key = {
            self._dataset_key(dataset): dataset for dataset in self.datasets
        }
        self.data_path = data_path
        self.zones_path = zones_path
        self.selected: dict[str, set[Precision]] = {}
        self.mappings: dict[str, dict[str, object]] = {}
        self.active_dataset: Dataset | None = None
        self.active_frame: gpd.GeoDataFrame | None = None
        self.class_inputs: dict[str, Any] = {}
        self.mapping_fields: dict[str, Any] = {}
        self.precision_checks: Sequence[tuple[Any, str]] = ()

        self.family_filter: Any = widgets.Dropdown(
            options=[("Toutes les familles", "all")]
            + [(family.capitalize(), family) for family in ("cultural", "physical", "raster")],
            value="all",
            description="Famille",
            layout=widgets.Layout(width="100%"),
        )
        self.search_box: Any = widgets.Text(
            placeholder="Rechercher un fichier…",
            description="Recherche",
            layout=widgets.Layout(width="100%"),
        )
        self.catalog_list: Any = widgets.Select(
            options=[],
            rows=13,
            layout=widgets.Layout(width="100%", height="280px"),
        )
        self.precision_box: Any = widgets.VBox(
            [widgets.HTML("<em>Sélectionnez d’abord un fichier.</em>")],
            layout=widgets.Layout(width="100%", min_height="120px"),
        )
        self.selection_status = widgets.HTML()
        self.selected_list = widgets.VBox(layout=widgets.Layout(width="100%"))
        self.selected_count = widgets.HTML()
        self.configuration_output: Any = widgets.Output()

        self.explorer_dataset: Any = widgets.Dropdown(
            options=[], description="Fichier", layout=widgets.Layout(width="100%")
        )
        self.explorer_precision: Any = widgets.Dropdown(
            options=[], description="Précision", layout=widgets.Layout(width="100%")
        )
        self.exploration_status = widgets.HTML()
        self.data_preview: Any = widgets.Output()
        self.mapping_panel = widgets.VBox()

        self.export_status = widgets.HTML()
        self.export_actions = widgets.VBox()
        self.toml_preview = widgets.HTML()

        self.family_filter.observe(self._refresh_catalog, names="value")
        self.search_box.observe(self._refresh_catalog, names="value")
        self.catalog_list.observe(self._show_precisions, names="value")
        self.explorer_dataset.observe(self._refresh_exploration_precisions, names="value")
        self._refresh_catalog()
        self._refresh_selected()
        self._refresh_configuration_output()
        self._refresh_toml_preview()

    @staticmethod
    def _dataset_key(dataset: Dataset) -> str:
        return f"{dataset.family}:{dataset.link_part}"

    def selection_view(self) -> widgets.Widget:
        """Construit les contrôles de recherche et de sélection."""
        columns = [
            widgets.VBox(
                [
                    widgets.HTML("<h3>1. Fichier</h3>"),
                    self.family_filter,
                    self.search_box,
                    self.catalog_list,
                ],
                layout=widgets.Layout(width="34%", padding="8px"),
            ),
            widgets.VBox(
                [
                    widgets.HTML("<h3>2. Précisions</h3>"),
                    self.precision_box,
                    _button(
                        self._add_dataset,
                        description="Ajouter les précisions",
                        icon="plus",
                        button_style="primary",
                    ),
                    self.selection_status,
                ],
                layout=widgets.Layout(width="33%", padding="8px"),
            ),
            widgets.VBox(
                [
                    widgets.HTML("<h3>3. Sélectionnés</h3>"),
                    self.selected_count,
                    self.selected_list,
                ],
                layout=widgets.Layout(width="33%", padding="8px"),
            ),
        ]
        return widgets.HBox(
            columns,
            layout=widgets.Layout(width="100%", align_items="stretch"),
        )

    def configuration_view(self) -> widgets.Output:
        """Expose l’aperçu actualisé du dictionnaire TOML."""
        return self.configuration_output

    def exploration_view(self) -> widgets.Widget:
        """Construit les contrôles d’exploration et de mapping."""
        controls = widgets.VBox(
            [
                widgets.HBox(
                    [
                        _button(
                            self._refresh_exploration_options,
                            description="Actualiser la sélection",
                            icon="refresh",
                        ),
                        _button(
                            self._explore_dataset,
                            description="Explorer le fichier",
                            icon="search",
                            button_style="primary",
                        ),
                    ]
                ),
                self.explorer_dataset,
                self.explorer_precision,
                self.exploration_status,
                self.data_preview,
            ],
            layout=widgets.Layout(width="42%", padding="8px"),
        )
        return widgets.HBox(
            [controls, self.mapping_panel],
            layout=widgets.Layout(width="100%", align_items="stretch"),
        )

    def export_view(self) -> widgets.Widget:
        """Construit l’aperçu TOML et les commandes d’export protégées."""
        return widgets.VBox(
            [
                widgets.HTML("<b>Aperçu TOML</b>"),
                self.toml_preview,
                _button(
                    self._prepare_export,
                    description="Générer le fichier TOML",
                    icon="file-export",
                    button_style="primary",
                ),
                self.export_status,
                self.export_actions,
            ],
            layout=widgets.Layout(width="100%"),
        )

    def current_config(self) -> ZonesConfig:
        """Construit la configuration avec les fonctions métier partagées."""
        selections = [
            DatasetSelection(
                self.datasets_by_key[key],
                tuple(
                    precision
                    for precision in PRECISION_ORDER
                    if precision in precisions
                ),
            )
            for key, precisions in self.selected.items()
        ]
        return build_zones_config(selections, self.mappings)

    def _refresh_catalog(self, change: Mapping[str, object] | None = None) -> None:
        del change
        family = cast(str | None, self.family_filter.value)
        query = cast(str, self.search_box.value).strip().casefold()
        options: list[tuple[str, str]] = []
        for dataset in self.datasets:
            if family != "all" and dataset.family != family:
                continue
            searchable = " ".join(
                (dataset.name, dataset.description, dataset.link_part)
            ).casefold()
            if query and query not in searchable:
                continue
            label = f"{dataset.name} · {', '.join(dataset.precisions)}"
            options.append((label, self._dataset_key(dataset)))
        previous = cast(str | None, self.catalog_list.value)
        self.catalog_list.options = options
        option_values = {value for _, value in options}
        if previous in option_values:
            self.catalog_list.value = previous
        elif options:
            self.catalog_list.value = options[0][1]
        else:
            self.catalog_list.value = None
        self._show_precisions()

    def _show_precisions(self, change: Mapping[str, object] | None = None) -> None:
        del change
        key = cast(str | None, self.catalog_list.value)
        dataset = self.datasets_by_key.get(key) if isinstance(key, str) else None
        if dataset is None:
            self.precision_box.children = [
                widgets.HTML("<em>Aucun fichier trouvé.</em>")
            ]
            return
        selected = self.selected.get(
            self._dataset_key(dataset), set[Precision]()
        )
        checkboxes = [
            (
                widgets.Checkbox(
                    value=precision in selected,
                    description=precision.capitalize(),
                    indent=False,
                    layout=widgets.Layout(width="100%"),
                ),
                precision,
            )
            for precision in dataset.precisions
        ]
        self.precision_checks = checkboxes
        description = html.escape(dataset.description)
        self.precision_box.children = [
            widgets.HTML(f"<b>{html.escape(dataset.name)}</b>"),
            *(checkbox for checkbox, _precision in checkboxes),
            widgets.HTML(f"<small>{description}</small>" if description else ""),
        ]

    def _add_dataset(self, _: widgets.Button) -> None:
        key = cast(str | None, self.catalog_list.value)
        if not isinstance(key, str):
            self.selection_status.value = "<span style='color:#9a3412'>Choisissez un fichier.</span>"
            return
        dataset = self.datasets_by_key.get(key)
        if dataset is None:
            self.selection_status.value = "<span style='color:#9a3412'>Choisissez un fichier.</span>"
            return
        chosen = {
            precision
            for checkbox, precision in self.precision_checks
            if checkbox.value
        }
        if not chosen:
            self.selection_status.value = (
                "<span style='color:#9a3412'>Cochez au moins une précision.</span>"
            )
            return
        if any(
            self.datasets_by_key[selected_key].link_part == dataset.link_part
            and selected_key != key
            for selected_key in self.selected
        ):
            self.selection_status.value = (
                "<span style='color:#9a3412'>Un jeu sélectionné utilise déjà ce lien.</span>"
            )
            return
        self.selected.setdefault(key, set[Precision]()).update(
            precision for precision in dataset.precisions if precision in chosen
        )
        self.selection_status.value = (
            f"<span style='color:#237a3b'>{html.escape(dataset.name)} ajouté.</span>"
        )
        self._refresh_selected()

    def _remove_dataset(self, key: str) -> None:
        dataset = self.datasets_by_key[key]
        self.selected.pop(key, None)
        self.mappings.pop(dataset.link_part, None)
        self._refresh_selected()

    def _refresh_selected(self) -> None:
        rows: list[widgets.Widget] = []
        for key, precisions in sorted(
            self.selected.items(),
            key=lambda item: self.datasets_by_key[item[0]].name.casefold(),
        ):
            dataset = self.datasets_by_key[key]
            precision_label = ", ".join(
                precision for precision in PRECISION_ORDER if precision in precisions
            )
            remove_button = _button(
                _button_callback(
                    lambda item_key=key: self._remove_dataset(item_key)
                ),
                description="",
                icon="trash",
                tooltip=f"Retirer {dataset.name}",
                layout=widgets.Layout(width="38px", flex="0 0 38px"),
            )
            rows.append(
                widgets.HBox(
                    [
                        widgets.HTML(
                            f"<b>{html.escape(dataset.name)}</b><br>"
                            f"<small>{dataset.family.capitalize()} · {precision_label}</small>"
                        ),
                        remove_button,
                    ],
                    layout=widgets.Layout(
                        width="100%",
                        justify_content="space-between",
                        align_items="center",
                    ),
                )
            )
        self.selected_list.children = rows or [
            widgets.HTML("<em>Aucun fichier sélectionné.</em>")
        ]
        self.selected_count.value = f"<b>{len(self.selected)} fichier(s)</b>"
        self._refresh_exploration_options()
        self._refresh_configuration_output()
        self._refresh_toml_preview()

    def _refresh_exploration_options(self, _: object | None = None) -> None:
        options = [
            (self.datasets_by_key[key].name, key)
            for key in sorted(
                self.selected,
                key=lambda item: self.datasets_by_key[item].name.casefold(),
            )
        ]
        current = cast(str | None, self.explorer_dataset.value)
        valid_values = {value for _, value in options}
        self.explorer_dataset.options = options
        if current in valid_values:
            self.explorer_dataset.value = current
        elif options:
            self.explorer_dataset.value = options[0][1]
        else:
            self.explorer_dataset.value = None
        if not options:
            self.explorer_precision.options = []
        self._refresh_exploration_precisions()

    def _refresh_exploration_precisions(
        self, change: Mapping[str, object] | None = None
    ) -> None:
        del change
        key = cast(str | None, self.explorer_dataset.value)
        precisions = (
            self.selected.get(key, set[Precision]())
            if isinstance(key, str)
            else set[Precision]()
        )
        options = [
            (precision.capitalize(), precision)
            for precision in PRECISION_ORDER
            if precision in precisions
        ]
        self.explorer_precision.options = options
        current = cast(str | None, self.explorer_precision.value)
        valid_values = {value for _, value in options}
        if current in valid_values:
            self.explorer_precision.value = current
        elif options:
            self.explorer_precision.value = options[0][1]
        else:
            self.explorer_precision.value = None

    def _explore_dataset(self, _: widgets.Button) -> None:
        key = cast(str | None, self.explorer_dataset.value)
        precision = cast(str | None, self.explorer_precision.value)
        if not isinstance(key, str) or not isinstance(precision, str):
            self.exploration_status.value = (
                "<span style='color:#9a3412'>Choisissez un fichier et une précision.</span>"
            )
            return
        dataset = self.datasets_by_key[key]
        try:
            shapefile = resolve_selected_shapefile(
                dataset, cast(Precision, precision), self.data_path
            )
            read_file = cast(
                Callable[..., gpd.GeoDataFrame], getattr(gpd, "read_file")
            )
            self.active_frame = read_file(shapefile, encoding="utf-8")
        except (OSError, ValueError, RuntimeError) as error:
            self.exploration_status.value = (
                f"<span style='color:#9a3412'>{html.escape(str(error))}</span>"
            )
            return

        self.active_dataset = dataset
        self._prepare_mapping_fields(dataset)
        frame = self.active_frame
        geometry_column = frame.geometry.name
        preview = frame.drop(columns=[geometry_column], errors="ignore").head(5)
        with self.data_preview:
            self.data_preview.clear_output(wait=True)
            display_output(
                widgets.HTML(
                    f"<b>{html.escape(dataset.name)}</b> · {html.escape(str(shapefile))}<br>"
                    f"Colonnes : {html.escape(', '.join(map(str, frame.columns)))}"
                )
            )
            display_output(preview)
        self.exploration_status.value = (
            "<span style='color:#237a3b'>Fichier chargé; renseignez les correspondances.</span>"
        )

    def _prepare_mapping_fields(self, dataset: Dataset) -> None:
        frame = self.active_frame
        if frame is None:
            return
        columns = [str(column) for column in frame.columns]
        existing = self.mappings.get(dataset.link_part, {})
        defaults = {
            "name": str(existing.get("name", "")),
            "code": str(existing.get("code", "")),
            "geometry": str(existing.get("geometry", frame.geometry.name)),
            "class": str(existing.get("class", "featurecla")),
        }
        self.mapping_fields = {}
        for field, default in defaults.items():
            value = default if default in columns else ""
            if field == "geometry" and frame.geometry.name in columns:
                value = frame.geometry.name
            selector = widgets.Dropdown(
                options=[("Choisir…", "")] + [(column, column) for column in columns],
                value=value,
                description=field.capitalize(),
                layout=widgets.Layout(width="100%"),
            )
            self.mapping_fields[field] = selector
        self.mapping_fields["class"].observe(self._refresh_class_values, names="value")
        self._refresh_class_values()
        self._render_mapping_panel()

    def _refresh_class_values(self, change: Mapping[str, object] | None = None) -> None:
        del change
        frame = self.active_frame
        selector = self.mapping_fields.get("class")
        if frame is None or selector is None or not selector.value:
            self.class_inputs = {}
            self._render_mapping_panel()
            return
        class_column = cast(str, selector.value)
        existing = self.mappings.get(
            self.active_dataset.link_part if self.active_dataset else "", {}
        ).get("classes", {})
        classes = cast(dict[str, str], existing) if isinstance(existing, dict) else {}
        self.class_inputs = {}
        values = cast(Any, frame[class_column])
        for raw_value in values.dropna().unique().tolist():
            source = str(raw_value)
            self.class_inputs[source] = widgets.Text(
                value=classes.get(source, ""),
                placeholder="Valeur cible",
                description="Vers",
                layout=widgets.Layout(width="60%"),
            )
        self._render_mapping_panel()

    def _render_mapping_panel(self) -> None:
        if not self.mapping_fields:
            self.mapping_panel.children = []
            return
        class_rows = [
            widgets.HBox(
                [widgets.HTML(html.escape(source)), target],
                layout=widgets.Layout(width="100%", justify_content="space-between"),
            )
            for source, target in self.class_inputs.items()
        ]
        self.mapping_panel.children = [
            widgets.HTML("<h3>Correspondance des colonnes</h3>"),
            *self.mapping_fields.values(),
            widgets.HTML("<b>Correspondances de classes</b>"),
            *(class_rows or [widgets.HTML("<em>Aucune valeur de classe.</em>")]),
            _button(
                self._save_mapping,
                description="Enregistrer le mapping",
                icon="save",
            ),
        ]

    def _save_mapping(self, _: widgets.Button) -> None:
        dataset = self.active_dataset
        if dataset is None or not self.mapping_fields:
            self.exploration_status.value = (
                "<span style='color:#9a3412'>Explorez d’abord un fichier.</span>"
            )
            return
        mapping: dict[str, object] = {
            field: selector.value
            for field, selector in self.mapping_fields.items()
        }
        mapping["classes"] = {
            source: target.value.strip()
            for source, target in self.class_inputs.items()
        }
        errors = validate_mapping(mapping)
        if errors:
            self.exploration_status.value = (
                f"<span style='color:#9a3412'>{html.escape(' '.join(errors))}</span>"
            )
            return
        self.mappings[dataset.link_part] = mapping
        self.exploration_status.value = (
            f"<span style='color:#237a3b'>Mapping enregistré pour {html.escape(dataset.name)}.</span>"
        )
        self._refresh_configuration_output()
        self._refresh_toml_preview()

    def _refresh_configuration_output(self) -> None:
        self.configuration_output.clear_output(wait=True)
        with self.configuration_output:
            display_output(self.current_config())

    def _refresh_toml_preview(self) -> None:
        serialized = zones_config_to_toml(self.current_config())
        self.toml_preview.value = f"<pre>{html.escape(serialized)}</pre>"

    def _prepare_export(self, _: widgets.Button) -> None:
        errors = validate_zones_config(self.current_config())
        self.export_actions.children = []
        if errors:
            message = " ".join(errors)
            self.export_status.value = (
                f"<span style='color:#9a3412'>Export bloqué : {html.escape(message)}</span>"
            )
            return
        if self.zones_path.exists():
            replace_button = _button(
                _button_callback(lambda: self._save("replace")),
                description="Remplacer zones.toml",
                icon="save",
                button_style="danger",
            )
            dated_button = _button(
                _button_callback(lambda: self._save("dated")),
                description="Enregistrer une copie datée",
                icon="copy",
            )
            self.export_status.value = (
                f"<b>{html.escape(str(self.zones_path))}</b> existe déjà. "
                "Choisissez explicitement la destination."
            )
            self.export_actions.children = [widgets.HBox([replace_button, dated_button])]
            return
        self._save("replace")

    def _save(self, mode: SaveMode) -> None:
        try:
            saved_path = save_zones_config(self.current_config(), self.zones_path, mode)
        except (OSError, ValueError) as error:
            self.export_status.value = (
                f"<span style='color:#9a3412'>{html.escape(str(error))}</span>"
            )
            return
        self.export_status.value = (
            f"<span style='color:#237a3b'>Fichier créé : {html.escape(str(saved_path))}</span>"
        )
        self.export_actions.children = []