"""Implementation of ``buildc plan``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from buildcompiler.api import BuildOptions, dumps_json_dto

from ..artifacts import write_plan
from ..context import handle, state, status
from ..inputs import load_compiler_inputs
from ..options import (
    CollectionOption,
    DesignOption,
    InventoryOption,
    RegistryOption,
    SelectOption,
    Workflow,
    WorkflowOption,
)
from ..render import error_console, render_plan


def plan(
    ctx: typer.Context,
    design: DesignOption = [],
    inventory: InventoryOption = [],
    select: SelectOption = [],
    collection: CollectionOption = [],
    registry: RegistryOption = None,
    workflow: WorkflowOption = Workflow.GOLDEN_GATE,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            dir_okay=False,
            help="Plan JSON path. Defaults to stdout.",
            rich_help_panel="Outputs",
        ),
    ] = None,
) -> None:
    """Classify SBOL designs and emit a deterministic, reviewable plan."""

    cli_state = state(ctx)

    def operation() -> None:
        options = BuildOptions()
        with status(cli_state, "Reading SBOL and indexing inventory…"):
            loaded = load_compiler_inputs(
                design_paths=design,
                inventory_paths=inventory,
                selectors=select,
                options=options,
                collections=collection,
                registry=registry,
            )
            build_plan = loaded.compiler.plan(loaded.designs)
        if output is None:
            typer.echo(dumps_json_dto(build_plan, indent=2))
        else:
            write_plan(output.expanduser().resolve(), build_plan)
        if not cli_state.quiet:
            render_plan(
                error_console(no_color=cli_state.no_color),
                build_plan,
                destination=output.expanduser().resolve() if output else None,
            )

    handle(cli_state, operation)
