import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from buildcompiler.cli import app


def test_buildc_runs_real_lvl1_assembly_transformation_and_plating(tmp_path):
    repo = Path(__file__).parents[2]
    fixtures = repo / "tests" / "test_files"
    output = tmp_path / "full-build"
    args = [
        "--quiet",
        "run",
        "--design",
        str(fixtures / "abstract_design.xml"),
    ]
    for filename in (
        "CIDARMoCloParts_collection.xml",
        "CIDARMoCloPlasmidsKit_collection.xml",
        "Enzyme_Implementations_collection.xml",
        "impl_test_collection.xml",
    ):
        args.extend(["--inventory", str(fixtures / filename)])
    args.extend(
        [
            "--chassis",
            "DH5alpha",
            "--protocol",
            "manual",
            "--output",
            str(output),
            "--json",
        ]
    )

    result = CliRunner().invoke(app, args)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert {item["stage"] for item in payload["stage_results"]} == {
        "assembly_lvl1",
        "transformation",
        "plating",
    }
    assert any(product["state"] == "plated" for product in payload["final_products"])

    expected = {
        "result.json",
        "products.xml",
        "stages/assembly_lvl1.json",
        "stages/transformation.json",
        "stages/plating.json",
        "protocols/assembly_lvl1_pudu_input.json",
        "protocols/transformation_pudu_input.json",
        "protocols/plating_pudu_input.json",
        "protocols/plating.md",
        "plating/plate_map.json",
        "plating/plate_map.csv",
    }
    assert all((output / relative).is_file() for relative in expected)

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "run"
    assert manifest["workflow"] == "golden-gate"
    recorded = {item["path"]: item for item in manifest["artifacts"]}
    assert expected == set(recorded)
    for relative, item in recorded.items():
        path = output / relative
        assert item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
