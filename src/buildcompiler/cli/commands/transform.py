"""Implementation of ``buildc transform``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from buildcompiler.api import ProtocolMode, transformation

from ..artifacts import prepare_output_dir, write_stage_outputs
from ..context import build_options, exit_for_stages, handle, state, status
from ..inputs import load_plasmids
from ..options import (
    JsonOption,
    OutputDirOption,
    OverwriteOption,
    ProtocolOption,
    SelectOption,
    Workflow,
    WorkflowOption,
)
from ..render import error_console, render_artifacts, render_stage_results


def transform(
    ctx: typer.Context,
    plasmids: Annotated[
        Path,
        typer.Option(
            "--plasmids",
            dir_okay=False,
            help="SBOL file containing assembled plasmids.",
            rich_help_panel="Inputs",
        ),
    ] = ...,
    select: SelectOption = [],
    chassis: Annotated[
        str,
        typer.Option(
            "--chassis",
            help="Chassis SBOL identity or stable identifier.",
            rich_help_panel="Workflow",
        ),
    ] = ...,
    output: OutputDirOption = ...,
    workflow: WorkflowOption = Workflow.GOLDEN_GATE,
    protocol: ProtocolOption = ProtocolMode.NONE,
    overwrite: OverwriteOption = False,
    json_output: JsonOption = False,
) -> None:
    """Create transformed-strain SBOL and PUDU-compatible JSON."""

    cli_state = state(ctx)

    def operation() -> None:
        options = build_options(
            transformation_enabled=True,
            chassis=chassis,
            protocol=protocol,
            output=output,
        )
        document, indexed_plasmids = load_plasmids(plasmids, select)
        output_dir = prepare_output_dir(output, overwrite=overwrite)
        with status(cli_state, "Preparing transformations…"):
            results = [
                transformation(
                    plasmid,
                    source_document=document,
                    target_document=document,
                    options=options,
                )
                for plasmid in indexed_plasmids
            ]
        paths = write_stage_outputs(
            output_dir=output_dir,
            stage_results=results,
            document=document,
            command="transform",
            workflow=workflow.value,
            protocol_mode=protocol.value,
        )
        if json_output:
            typer.echo(
                json.dumps(
                    [result.json_intermediate for result in results],
                    indent=2,
                    sort_keys=True,
                )
            )
        if not cli_state.quiet:
            console = error_console(no_color=cli_state.no_color)
            render_stage_results(console, results)
            render_artifacts(console, root=output_dir, paths=paths)
        exit_for_stages(results)

    handle(cli_state, operation)
