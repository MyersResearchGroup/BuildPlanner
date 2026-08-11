"""Explicit filesystem artifact boundaries for ``buildc``."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import sbol2

from buildcompiler.api import dumps_json_dto, serialize_stage_result
from buildcompiler.domain import StageResult

from .errors import CliInputError


def prepare_output_dir(path: Path, *, overwrite: bool) -> Path:
    """Create an empty output directory with conservative overwrite protection."""

    resolved = path.expanduser().resolve()
    protected = {Path(resolved.anchor), Path.home().resolve(), Path.cwd().resolve()}
    if resolved in protected:
        raise CliInputError(
            f"Refusing to use protected path as an output directory: {resolved}"
        )
    if resolved.exists() and not resolved.is_dir():
        raise CliInputError(f"Output path exists and is not a directory: {resolved}")
    if resolved.exists() and any(resolved.iterdir()):
        if not overwrite:
            raise CliInputError(
                f"Output directory is not empty: {resolved}. Pass --overwrite to replace it."
            )
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def write_json(path: Path, payload: Any) -> Path:
    """Write stable, human-readable JSON and return its path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_plan(path: Path, plan: Any) -> Path:
    """Write a serialized build plan and return its path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_json_dto(plan, indent=2) + "\n", encoding="utf-8")
    return path


def write_build_outputs(
    *,
    output_dir: Path,
    result: Any,
    command: str,
    workflow: str,
    protocol_mode: str,
) -> list[Path]:
    """Write the stable full-build artifact set and return all written paths."""

    written = [
        _write_text(
            output_dir / "result.json", dumps_json_dto(result, indent=2) + "\n"
        ),
        _write_text(output_dir / "products.xml", result.build_document.writeString()),
    ]
    written.extend(
        _write_stage_outputs(
            output_dir=output_dir,
            stage_results=result.stage_results,
            protocol_mode=protocol_mode,
        )
    )
    manifest_path = output_dir / "manifest.json"
    write_json(
        manifest_path,
        _manifest(
            root=output_dir,
            artifacts=written,
            command=command,
            workflow=workflow,
            status=result.status.value,
        ),
    )
    written.append(manifest_path)
    return written


def write_stage_outputs(
    *,
    output_dir: Path,
    stage_results: list[StageResult],
    document: sbol2.Document | None,
    command: str,
    workflow: str,
    protocol_mode: str,
) -> list[Path]:
    """Write independent-stage results using the same output conventions."""

    payload = {
        "kind": "stage_results",
        "schema_version": "1.0",
        "stage_results": [serialize_stage_result(result) for result in stage_results],
    }
    written = [write_json(output_dir / "result.json", payload)]
    if document is not None:
        written.append(_write_text(output_dir / "products.xml", document.writeString()))
    written.extend(
        _write_stage_outputs(
            output_dir=output_dir,
            stage_results=stage_results,
            protocol_mode=protocol_mode,
        )
    )
    successful = all(result.status.value == "success" for result in stage_results)
    manifest_path = output_dir / "manifest.json"
    write_json(
        manifest_path,
        _manifest(
            root=output_dir,
            artifacts=written,
            command=command,
            workflow=workflow,
            status="success" if successful else "failed",
        ),
    )
    written.append(manifest_path)
    return written


def _write_stage_outputs(
    *, output_dir: Path, stage_results: list[StageResult], protocol_mode: str
) -> list[Path]:
    by_stage: dict[str, list[StageResult]] = {}
    for result in stage_results:
        by_stage.setdefault(result.stage.value, []).append(result)

    written: list[Path] = []
    for stage, results in sorted(by_stage.items()):
        stage_payload = [serialize_stage_result(result) for result in results]
        written.append(
            write_json(
                output_dir / "stages" / f"{stage}.json",
                stage_payload[0] if len(stage_payload) == 1 else stage_payload,
            )
        )
        intermediates = [
            result.json_intermediate
            for result in results
            if result.json_intermediate is not None
        ]
        if intermediates:
            written.append(
                write_json(
                    output_dir / "protocols" / f"{stage}_pudu_input.json",
                    intermediates[0] if len(intermediates) == 1 else intermediates,
                )
            )

    plating_results = by_stage.get("plating", [])
    if plating_results:
        plate_map: dict[str, str] = {}
        plate_id = "buildcompiler_plate_1"
        for result in plating_results:
            plate_map.update(result.protocol_artifacts.get("plate_map", {}))
            plate_id = result.protocol_artifacts.get("plate_id", plate_id)
        written.append(write_json(output_dir / "plating" / "plate_map.json", plate_map))
        written.append(
            _write_plate_csv(output_dir / "plating" / "plate_map.csv", plate_map)
        )
        if protocol_mode == "manual":
            written.append(
                _write_manual_plating_protocol(
                    output_dir / "protocols" / "plating.md", plate_id, plate_map
                )
            )
    return written


def _write_plate_csv(path: Path, plate_map: dict[str, str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["well", "transformed_strain"])
        for well, identity in sorted(plate_map.items()):
            writer.writerow([well, identity])
    return path


def _write_manual_plating_protocol(
    path: Path, plate_id: str, plate_map: dict[str, str]
) -> Path:
    rows = "\n".join(
        f"| {well} | {identity} |" for well, identity in sorted(plate_map.items())
    )
    content = (
        "# BuildCompiler plating protocol\n\n"
        f"Plate: `{plate_id}`\n\n"
        "| Well | Transformed strain |\n"
        "|---|---|\n"
        f"{rows}\n\n"
        "1. Prepare and label the destination plate.\n"
        "2. Transfer each transformed strain to its assigned well.\n"
        "3. Incubate using the laboratory-approved conditions.\n"
    )
    return _write_text(path, content)


def _manifest(
    *, root: Path, artifacts: list[Path], command: str, workflow: str, status: str
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "command": command,
        "workflow": workflow,
        "status": status,
        "artifacts": [
            {
                "path": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in sorted(artifacts)
        ],
    }


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
