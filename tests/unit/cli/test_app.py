import json
from pathlib import Path

import sbol2
from typer.testing import CliRunner

from buildcompiler.cli import app


runner = CliRunner()


def _write_lvl1_design(path: Path) -> Path:
    document = sbol2.Document()
    design = sbol2.ComponentDefinition("https://example.org/design/1")
    design.displayId = "design"
    roles = [
        "http://identifiers.org/so/SO:0000167",
        "http://identifiers.org/so/SO:0000139",
        "http://identifiers.org/so/SO:0000316",
        "http://identifiers.org/so/SO:0000141",
    ]
    for index, role in enumerate(roles, start=1):
        part = sbol2.ComponentDefinition(f"https://example.org/part-{index}/1")
        part.roles = [role]
        document.add(part)
        child = design.components.create(f"part-{index}")
        child.definition = part.identity
    document.add(design)
    path.write_text(document.writeString(), encoding="utf-8")
    return path


def _write_transformation_result(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "kind": "stage_results",
                "stage_results": [
                    {
                        "stage": "transformation",
                        "products": [
                            {
                                "kind": "strain",
                                "identity": "https://example.org/strain/1",
                                "display_id": "strain_1",
                                "name": "strain 1",
                                "state": "transformed",
                                "roles": [],
                                "metadata": {"plasmid_identity": "plasmid-1"},
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_root_help_is_grouped_and_lists_the_complete_surface():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Compile SBOL designs" in result.stdout
    for command in ("plan", "run", "assemble", "transform", "plate", "inspect"):
        assert command in result.stdout
    assert "--install-completion" in result.stdout


def test_version_uses_the_installed_distribution_metadata():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "buildc 0.0.1a1"


def test_plan_keeps_stdout_machine_readable_in_quiet_mode(tmp_path):
    design = _write_lvl1_design(tmp_path / "design.xml")

    result = runner.invoke(app, ["--quiet", "plan", "--design", str(design)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "build_plan"
    assert len(payload["lvl1_requests"]) == 1


def test_plan_human_output_is_sent_to_stderr(tmp_path):
    design = _write_lvl1_design(tmp_path / "design.xml")
    plan_path = tmp_path / "outputs" / "plan.json"

    result = runner.invoke(
        app,
        ["--no-color", "plan", "--design", str(design), "--output", str(plan_path)],
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Golden Gate plan ready" in result.stderr
    assert json.loads(plan_path.read_text(encoding="utf-8"))["kind"] == "build_plan"


def test_inspect_has_a_json_mode_for_automation(tmp_path):
    design = _write_lvl1_design(tmp_path / "design.xml")

    result = runner.invoke(
        app,
        ["--quiet", "inspect", "--design", str(design), "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["workflow"] == "golden-gate"
    assert payload["designs"][0]["display_id"] == "design"


def test_plate_writes_a_manifest_maps_and_manual_protocol(tmp_path):
    transformations = _write_transformation_result(tmp_path / "transformations.json")
    output = tmp_path / "plate"

    result = runner.invoke(
        app,
        [
            "--quiet",
            "plate",
            "--transformations",
            str(transformations),
            "--output",
            str(output),
            "--plate-id",
            "demo-plate",
            "--parameter",
            "incubation_temperature_c=37",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["bacterium_locations"] == {
        "A1": "https://example.org/strain/1"
    }
    assert (output / "manifest.json").is_file()
    assert (output / "plating" / "plate_map.csv").is_file()
    assert (output / "protocols" / "plating.md").is_file()


def test_nonempty_output_requires_explicit_overwrite(tmp_path):
    transformations = _write_transformation_result(tmp_path / "transformations.json")
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--quiet",
            "plate",
            "--transformations",
            str(transformations),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 2
    assert sentinel.read_text(encoding="utf-8") == "keep"
