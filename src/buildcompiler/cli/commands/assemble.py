"""Implementation of ``buildc assemble``."""

from __future__ import annotations

import typer

from buildcompiler.api import ProtocolMode, dumps_json_dto

from ..artifacts import prepare_output_dir, write_build_outputs
from ..context import build_options, exit_for_build, handle, state, status
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


def assemble(
    ctx: typer.Context,
    design: DesignOption = [],
    inventory: InventoryOption = [],
    select: SelectOption = [],
    collection: CollectionOption = [],
    registry: RegistryOption = None,
    workflow: WorkflowOption = Workflow.GOLDEN_GATE,
    output: OutputDirOption = ...,
    protocol: ProtocolOption = ProtocolMode.NONE,
    overwrite: OverwriteOption = False,
    json_output: JsonOption = False,
) -> None:
    """Resolve domestication and level-1/level-2 Golden Gate assembly."""

    cli_state = state(ctx)

    def operation() -> None:
        options = build_options(
            transformation_enabled=False,
            chassis=None,
            protocol=protocol,
            output=output,
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
            build_plan = loaded.compiler.plan(loaded.designs)
        output_dir = prepare_output_dir(output, overwrite=overwrite)
        with status(cli_state, "Running Golden Gate assembly…"):
            result = loaded.compiler.execute(build_plan, options=options)
        paths = write_build_outputs(
            output_dir=output_dir,
            result=result,
            command="assemble",
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
