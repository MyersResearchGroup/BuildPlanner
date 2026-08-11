"""Implementation of ``buildc plate``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from buildcompiler.api import ProtocolMode, plating

from ..artifacts import prepare_output_dir, write_stage_outputs
from ..context import (
    build_options,
    exit_for_stages,
    handle,
    parse_parameters,
    state,
)
from ..inputs import load_strains
from ..options import (
    JsonOption,
    OutputDirOption,
    OverwriteOption,
    ProtocolOption,
    Workflow,
    WorkflowOption,
)
from ..render import error_console, render_artifacts, render_stage_results


def plate(
    ctx: typer.Context,
    transformations: Annotated[
        Path,
        typer.Option(
            "--transformations",
            dir_okay=False,
            help="buildc transformation or workflow result JSON.",
            rich_help_panel="Inputs",
        ),
    ] = ...,
    output: OutputDirOption = ...,
    plate_id: Annotated[
        str,
        typer.Option(
            "--plate-id",
            help="Stable identifier for the destination plate.",
            rich_help_panel="Workflow",
        ),
    ] = "buildcompiler_plate_1",
    parameter: Annotated[
        list[str],
        typer.Option(
            "--parameter",
            help="Advanced plating parameter as KEY=JSON. Repeat as needed.",
            rich_help_panel="Workflow",
        ),
    ] = [],
    workflow: WorkflowOption = Workflow.GOLDEN_GATE,
    protocol: ProtocolOption = ProtocolMode.MANUAL,
    overwrite: OverwriteOption = False,
    json_output: JsonOption = False,
) -> None:
    """Create a deterministic 96-well plate map and protocol handoff."""

    cli_state = state(ctx)

    def operation() -> None:
        options = build_options(
            transformation_enabled=False,
            chassis=None,
            protocol=protocol,
            output=output,
        )
        strains = load_strains(transformations)
        advanced_parameters = parse_parameters(parameter)
        output_dir = prepare_output_dir(output, overwrite=overwrite)
        result = plating(
            strains,
            options=options,
            plate_id=plate_id,
            advanced_parameters=advanced_parameters,
        )
        paths = write_stage_outputs(
            output_dir=output_dir,
            stage_results=[result],
            document=None,
            command="plate",
            workflow=workflow.value,
            protocol_mode=protocol.value,
        )
        if json_output:
            typer.echo(json.dumps(result.json_intermediate, indent=2, sort_keys=True))
        if not cli_state.quiet:
            console = error_console(no_color=cli_state.no_color)
            render_stage_results(console, [result])
            render_artifacts(console, root=output_dir, paths=paths)
        exit_for_stages([result])

    handle(cli_state, operation)
