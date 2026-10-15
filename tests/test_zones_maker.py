"""Tests des fonctions métier de création de zones.toml."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from urllib.request import Request
from zipfile import ZIP_DEFLATED, ZipFile
import tomllib

import pytest

from zones_maker.utils import ( # pylint: disable=E0401
    Dataset,
    DatasetSelection,
    ZonesConfig,
    build_zones_config,
    load_catalog,
    resolve_selected_shapefile,
    save_zones_config,
    validate_zones_config,
    zones_config_to_toml,
)


DATASET = Dataset(
    family="cultural",
    identifier="admin_0_countries",
    name="Countries",
    precisions=("high", "medium", "low"),
    link_part="admin_0_countries",
    description="Country polygons",
)
MAPPING: dict[str, object] = {
    "name": "NAME_LONG",
    "code": "ISO_A3",
    "geometry": "geometry",
    "class": "featurecla",
    "classes": {"Admin-0 country": "Country"},
}


def complete_config() -> ZonesConfig:
    """Retourne une configuration complète pour les tests."""
    return build_zones_config(
        [DatasetSelection(DATASET, ("high", "medium"))],
        {DATASET.link_part: MAPPING},
    )


def make_archive(member_name: str) -> bytes:
    """Crée une archive ZIP en mémoire contenant un fichier avec le nom donné."""
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(member_name, b"test shapefile")
    return buffer.getvalue()


def test_load_catalog_validates_and_returns_typed_datasets() -> None:
    """Teste que le catalogue est chargé correctement et que les datasets sont typés."""
    catalog_path = Path(__file__).resolve().parents[1] / "src" / "naturalearth.json"

    datasets = load_catalog(catalog_path)

    countries = next(item for item in datasets if item.link_part == "admin_0_countries")
    assert countries.family == "cultural"
    assert countries.precisions == ("high", "medium", "low")


def test_build_config_preserves_selection_and_only_selected_mappings() -> None:
    """
    Teste que la configuration conserve la sélection des datasets et n'inclut que les mappings
    sélectionnés.
    """
    config = build_zones_config(
        [DatasetSelection(DATASET, ("low", "high"))],
        {
            DATASET.link_part: MAPPING,
            "not_selected": MAPPING,
        },
    )

    assert config["source_path"] == "https://naturalearth.s3.amazonaws.com"
    assert config["data_family"]["cultural"] == [
        {
            "name": "Countries",
            "precision": ["high", "low"],
            "link": "admin_0_countries",
        }
    ]
    assert config["data_family"]["physical"] == []
    assert config["data_family"]["raster"] == []
    assert config["data_family"]["mapping"] == {
        DATASET.link_part: MAPPING,
    }


def test_validation_requires_mapping_for_every_selected_dataset() -> None:
    """Teste que la validation échoue si un mapping est manquant pour un dataset sélectionné."""
    config = build_zones_config([DatasetSelection(DATASET, ("high",))])

    assert any("Mapping manquant" in error for error in validate_zones_config(config))


def test_toml_serialization_round_trips() -> None:
    """
    Teste que la sérialisation en TOML et la désérialisation conservent la configuration intacte.
    """

    config = complete_config()

    assert tomllib.loads(zones_config_to_toml(config)) == config


def test_save_dated_copy_uses_date_and_never_overwrites(tmp_path: Path) -> None:
    """
    Teste que la sauvegarde avec la date utilise la date et ne réécrit jamais le fichier existant.
    """
    config = complete_config()
    zones_path = tmp_path / "zones.toml"
    dated_path = tmp_path / "26-10-12_zones.toml"

    saved_path = save_zones_config(config, zones_path, "dated", date(2026, 10, 12))

    assert saved_path == dated_path
    original_content = dated_path.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        save_zones_config(config, zones_path, "dated", date(2026, 10, 12))
    assert dated_path.read_text(encoding="utf-8") == original_content
    assert not zones_path.exists()


def test_replace_mode_only_writes_the_explicit_target(tmp_path: Path) -> None:
    """Teste que le mode 'replace' n'écrit que le fichier cible explicite."""
    zones_path = tmp_path / "zones.toml"

    saved_path = save_zones_config(complete_config(), zones_path, "replace")

    assert saved_path == zones_path
    assert zones_path.is_file()


def test_resolve_existing_shapefile_does_not_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Teste que la fonction ne télécharge pas le shapefile si celui-ci existe déjà."""
    dataset_path = tmp_path / "cultural" / "10m" / DATASET.link_part
    dataset_path.mkdir(parents=True)
    shapefile = dataset_path / "countries.shp"
    shapefile.touch()

    def unexpected_download(*args: object, **kwargs: object) -> None:
        raise AssertionError("Le fichier local ne devait pas être téléchargé.")

    monkeypatch.setattr("zones_maker.utils.urlopen", unexpected_download)

    assert resolve_selected_shapefile(DATASET, "high", tmp_path) == shapefile


def test_resolve_missing_shapefile_downloads_only_selected_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Teste que la fonction télécharge uniquement l'archive sélectionnée si le shapefile
    est manquant.
    """
    requested_urls: list[str] = []

    class FakeResponse(BytesIO):
        """Réponse factice pour simuler le téléchargement d'un shapefile."""
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            self.close()

    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        del timeout
        requested_urls.append(request.full_url)
        return FakeResponse(make_archive("ne_10m_admin_0_countries.shp"))

    monkeypatch.setattr("zones_maker.utils.urlopen", fake_urlopen)

    shapefile = resolve_selected_shapefile(DATASET, "high", tmp_path)

    assert requested_urls == [
        "https://naturalearth.s3.amazonaws.com/10m_cultural/"
        "ne_10m_admin_0_countries.zip"
    ]
    assert shapefile.is_file()


@pytest.mark.parametrize("link_part", ["lakes", "ocean"])
def test_resolve_physical_dataset_uses_natural_earth_archive_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    link_part: str,
) -> None:
    """Teste les URL Natural Earth des couches physiques Lakes et Ocean."""
    dataset = Dataset(
        family="physical",
        identifier=link_part,
        name=link_part.capitalize(),
        precisions=("high",),
        link_part=link_part,
        description="",
    )
    requested_urls: list[str] = []

    class FakeResponse(BytesIO):
        """Réponse factice pour simuler le téléchargement d’un shapefile."""

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            self.close()

    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        del timeout
        requested_urls.append(request.full_url)
        return FakeResponse(make_archive(f"ne_10m_{link_part}.shp"))

    monkeypatch.setattr("zones_maker.utils.urlopen", fake_urlopen)

    shapefile = resolve_selected_shapefile(dataset, "high", tmp_path)

    assert requested_urls == [
        f"https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_{link_part}.zip"
    ]
    assert shapefile.is_file()


def test_resolve_rejects_archive_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Teste que la fonction rejette les chemins d'archive contenant des tentatives de traversal.
    """
    class FakeResponse(BytesIO):
        """Réponse factice pour simuler le téléchargement d'un shapefile."""
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            self.close()

    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        del request, timeout
        return FakeResponse(make_archive("../escaped.shp"))

    monkeypatch.setattr("zones_maker.utils.urlopen", fake_urlopen)

    with pytest.raises(ValueError, match="Chemin non sûr"):
        resolve_selected_shapefile(DATASET, "high", tmp_path)
