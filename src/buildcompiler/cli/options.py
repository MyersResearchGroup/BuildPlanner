"""Reusable Typer option declarations for ``buildc`` commands."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from buildcompiler.api import ProtocolMode


class Workflow(str, Enum):
    """Supported compiler workflows."""

    GOLDEN_GATE = "golden-gate"


DesignOption = Annotated[
    list[Path],
    typer.Option(
        "--design",
        "-d",
        help="SBOL design file. Repeat for multiple files.",
        rich_help_panel="Inputs",
    ),
]
InventoryOption = Annotated[
    list[Path],
    typer.Option(
        "--inventory",
        "-i",
        help="SBOL inventory file. Repeat for multiple files.",
        rich_help_panel="Inputs",
    ),
]
SelectOption = Annotated[
    list[str],
    typer.Option(
        "--select",
        help="Design or product identity/display ID. Repeat to select several.",
        rich_help_panel="Inputs",
    ),
]
CollectionOption = Annotated[
    list[str],
    typer.Option(
        "--collection",
        help="SynBioHub collection identity. Repeat for multiple collections.",
        rich_help_panel="SynBioHub",
    ),
]
RegistryOption = Annotated[
    str | None,
    typer.Option(
        "--registry",
        help="SynBioHub registry URL.",
        rich_help_panel="SynBioHub",
    ),
]
WorkflowOption = Annotated[
    Workflow,
    typer.Option(
        "--workflow",
        help="Biological build workflow.",
        rich_help_panel="Workflow",
    ),
]
OutputDirOption = Annotated[
    Path,
    typer.Option(
        "--output",
        "-o",
        file_okay=False,
        help="Directory for explicit workflow artifacts.",
        rich_help_panel="Outputs",
    ),
]
OverwriteOption = Annotated[
    bool,
    typer.Option(
        "--overwrite",
        help="Replace a non-empty output directory.",
        rich_help_panel="Outputs",
    ),
]
JsonOption = Annotated[
    bool,
    typer.Option(
        "--json",
        help="Also emit the machine-readable result to stdout.",
        rich_help_panel="Outputs",
    ),
]
ProtocolOption = Annotated[
    ProtocolMode,
    typer.Option(
        "--protocol",
        case_sensitive=False,
        help="Protocol handoff mode.",
        rich_help_panel="Workflow",
    ),
]


__all__ = [
    "CollectionOption",
    "DesignOption",
    "InventoryOption",
    "JsonOption",
    "OutputDirOption",
    "OverwriteOption",
    "ProtocolOption",
    "RegistryOption",
    "SelectOption",
    "Workflow",
    "WorkflowOption",
]
