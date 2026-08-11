"""Implementation of ``buildc run``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from buildcompiler.api import ProtocolMode, dumps_json_dto

from ..artifacts import prepare_output_dir, write_build_outputs
from ..context import build_options, exit_for_build, handle, read_plan, state, status
from ..inputs import load_compiler_inputs
from ..options import (
    CollectionOption,
    DesignOption,
    InventoryOption,
    JsonOption,
    OutputDirOption,
    OverwriteOption,
    ProtocolOption,
    RegistryOption,
    SelectOption,
    Workflow,
    WorkflowOption,
)
from ..render import error_console, render_artifacts, render_build_result


def run(
    ctx: typer.Context,
    design: DesignOption = [],
    inventory: InventoryOption = [],
    select: SelectOption = [],
    collection: CollectionOption = [],
    registry: RegistryOption = None,
    workflow: WorkflowOption = Workflow.GOLDEN_GATE,
    output: OutputDirOption = ...,
    chassis: Annotated[
        str,
        typer.Option(
            "--chassis",
            help="Chassis SBOL identity or stable identifier.",
            rich_help_panel="Workflow",
        ),
    ] = ...,
    protocol: ProtocolOption = ProtocolMode.NONE,
    plan_file: Annotated[
        Path | None,
        typer.Option(
            "--plan",
            dir_okay=False,
            help="Execute a previously reviewed buildc plan JSON.",
            rich_help_panel="Inputs",
        ),
    ] = None,
    max_iterations: Annotated[
        int,
        typer.Option(
            "--max-iterations",
            min=1,
            max=100,
            help="Bound dependency-resolution retries.",
            rich_help_panel="Workflow",
        ),
    ] = 5,
    detailed_report: Annotated[
        bool,
        typer.Option(
            "--detailed-report",
            help="Include route details and next actions.",
            rich_help_panel="Outputs",
        ),
    ] = False,
    approve: Annotated[
        list[str],
        typer.Option(
            "--approve",
            help="Approve a named process for this run. Repeat as needed.",
            rich_help_panel="Safety and approvals",
        ),
    ] = [],
    allow_sequence_edits: Annotated[
        bool,
        typer.Option(
            "--allow-sequence-edits",
            help="Allow proposed domestication sequence edits.",
            rich_help_panel="Safety and approvals",
        ),
    ] = False,
    continue_on_error: Annotated[
        bool,
        typer.Option(
            "--continue-on-error",
            help="Record unexpected stage errors and continue where possible.",
            rich_help_panel="Safety and approvals",
        ),
    ] = False,
    overwrite: OverwriteOption = False,
    json_output: JsonOption = False,
) -> None:
    """Run assembly, transformation, and plating as one bounded workflow."""

    cli_state = state(ctx)

    def operation() -> None:
        options = build_options(
            transformation_enabled=True,
            chassis=chassis,
            protocol=protocol,
            output=output,
            max_iterations=max_iterations,
            detailed_report=detailed_report,
            approvals=approve,
            allow_sequence_edits=allow_sequence_edits,
            continue_on_error=continue_on_error,
        )
        with status(cli_state, "Reading SBOL and indexing inventory…"):
            loaded = load_compiler_inputs(
                design_paths=design,
                inventory_paths=inventory,
                selectors=select,
                options=options,
                collections=collection,
                registry=registry,
            )
            build_plan = (
                read_plan(plan_file)
                if plan_file
                else loaded.compiler.plan(loaded.designs)
            )
        output_dir = prepare_output_dir(output, overwrite=overwrite)
        with status(cli_state, "Running Golden Gate workflow…"):
            result = loaded.compiler.execute(build_plan, options=options)
        paths = write_build_outputs(
            output_dir=output_dir,
            result=result,
            command="run",
            workflow=workflow.value,
            protocol_mode=protocol.value,
        )
        if json_output:
            typer.echo(dumps_json_dto(result, indent=2))
        if not cli_state.quiet:
            console = error_console(no_color=cli_state.no_color)
            render_build_result(console, result)
            render_artifacts(console, root=output_dir, paths=paths)
        exit_for_build(result)

    handle(cli_state, operation)
