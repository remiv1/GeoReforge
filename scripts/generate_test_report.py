#!/usr/bin/env python3  # pylint: disable=C0114

from __future__ import annotations

import sys
from pathlib import Path
import xml.etree.ElementTree as ET


def _shorten(value: str, limit: int = 240) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _duration(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def _test_result(test_case: ET.Element) -> tuple[str, str]:
    failure = test_case.find("failure")
    error = test_case.find("error")
    skipped = test_case.find("skipped")
    if failure is not None:
        return "failed", _shorten(failure.get("message") or failure.text or "")
    if error is not None:
        return "error", _shorten(error.get("message") or error.text or "")
    if skipped is not None:
        return "skipped", _shorten(skipped.get("message") or skipped.text or "")
    return "passed", ""


def _markdown_cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


def _append_language_section(
    lines: list[str],
    language: str,
    timestamp: str,
    grouped_cases: dict[str, list[ET.Element]],
    counts: dict[str, int],
    duration: float,
) -> None:
    if language == "en":
        lines.extend([
            "## English",
            "",
            f"- Date: {timestamp}",
            f"- Result: {'FAILED' if counts['failed'] or counts['error'] else 'PASSED'}",
            (
                f"- Tests: {counts['total']} | Passed: {counts['passed']} "
                f"| Failed: {counts['failed']} | Errors: {counts['error']} "
                f"| Skipped: {counts['skipped']}"
            ),
            f"- Duration: {duration:.2f} s",
            "",
            "### Results by test class",
        ])
        result_labels = {
            "passed": "passed",
            "failed": "failed",
            "error": "error",
            "skipped": "skipped",
        }
        headers = "| Test | Result | Duration | Details |"
    else:
        lines.extend([
            "## Français",
            "",
            f"- Date : {timestamp}",
            f"- Résultat : {'ÉCHEC' if counts['failed'] or counts['error'] else 'RÉUSSI'}",
            (
                f"- Tests : {counts['total']} | Réussis : {counts['passed']} "
                f"| Échecs : {counts['failed']} | Erreurs : {counts['error']} "
                f"| Ignorés : {counts['skipped']}"
            ),
            f"- Durée : {duration:.2f} s",
            "",
            "### Résultats par classe de test",
        ])
        result_labels = {
            "passed": "réussi",
            "failed": "échec",
            "error": "erreur",
            "skipped": "ignoré",
        }
        headers = "| Test | Résultat | Durée | Détails |"

    for class_name, test_cases in grouped_cases.items():
        language_label = "English" if language == "en" else "Français"
        lines.extend([
            "",
            f"#### `{_markdown_cell(class_name)}` - {language_label}",
            "",
            headers,
            "| --- | --- | ---: | --- |",
        ])
        for test_case in test_cases:
            result_en, detail = _test_result(test_case)
            test_name = _markdown_cell(test_case.get("name", "unnamed test / test sans nom"))
            test_duration = _duration(test_case.get("time"))
            lines.append(
                f"| `{test_name}` | {result_labels[result_en]} | "
                f"{test_duration:.3f} s | {_markdown_cell(detail) or '-'} |"
            )


def _generate_report(xml_path: Path, markdown_path: Path, timestamp: str) -> bool:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        root = ET.parse(xml_path).getroot()
    except (OSError, ET.ParseError) as error:
        detail = _shorten(str(error))
        markdown_path.write_text(
            "# Test report / Rapport de tests\n\n"
            "## Sommaire / Table of contents\n\n"
            "- [English](#english)\n"
            "- [Français](#français)\n\n"
            "## English\n\n"
            f"- Date: {timestamp}\n- Status: unavailable\n- Details: {detail}\n\n"
            "## Français\n\n"
            f"- Date : {timestamp}\n- Statut : indisponible\n- Détails : {detail}\n",
            encoding="utf-8",
        )
        return False

    test_cases = list(root.iter("testcase"))
    grouped_cases: dict[str, list[ET.Element]] = {}
    counts = {"total": len(test_cases), "passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for test_case in test_cases:
        class_name = test_case.get("classname") or "Unclassified / Non classé"
        grouped_cases.setdefault(class_name, []).append(test_case)
        result_en, _ = _test_result(test_case)
        counts[result_en] += 1

    suite_durations = [
        _duration(suite.get("time"))
        for suite in root.iter("testsuite")
        if suite.findall("./testcase")
    ]
    duration = (
        sum(suite_durations)
        if suite_durations
        else sum(_duration(test_case.get("time")) for test_case in test_cases)
    )
    lines = [
        "# Test report / Rapport de tests",
        "",
        "## Sommaire / Table of contents",
        "",
        "- [English](#english)",
        "- [Français](#français)",
        "",
    ]
    _append_language_section(lines, "en", timestamp, grouped_cases, counts, duration)
    lines.append("")
    _append_language_section(lines, "fr", timestamp, grouped_cases, counts, duration)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def main() -> int:
    """Génère le rapport Markdown bilingue depuis le XML JUnit."""
    if len(sys.argv) != 4:
        print(
            "Usage : generate_test_report.py <rapport.xml> <rapport.md> <horodatage>",
            file=sys.stderr,
        )
        return 2

    xml_path = Path(sys.argv[1])
    markdown_path = Path(sys.argv[2])
    timestamp = sys.argv[3]
    if _generate_report(xml_path, markdown_path, timestamp):
        return 0
    print(f"Impossible de lire le rapport XML : {xml_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
