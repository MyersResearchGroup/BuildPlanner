"""Implementation of ``buildc inspect``."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from buildcompiler.api import BuildOptions

from ..context import handle, state
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
from ..render import error_console, render_inventory


def inspect_inputs(
    ctx: typer.Context,
    design: DesignOption = [],
    inventory: InventoryOption = [],
    select: SelectOption = [],
    collection: CollectionOption = [],
    registry: RegistryOption = None,
    workflow: WorkflowOption = Workflow.GOLDEN_GATE,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emit the inspection result to stdout.",
            rich_help_panel="Outputs",
        ),
    ] = False,
) -> None:
    """Resolve inputs exactly as a build would, without executing stages."""

    cli_state = state(ctx)

    def operation() -> None:
        options = BuildOptions()
        loaded = load_compiler_inputs(
            design_paths=design,
            inventory_paths=inventory,
            selectors=select,
            options=options,
            collections=collection,
            registry=registry,
        )
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "workflow": workflow.value,
                        "designs": [
                            {
                                "type": type(item).__name__,
                                "display_id": item.displayId or None,
                                "identity": item.identity,
                            }
                            for item in loaded.designs
                        ],
                        "inventory": {
                            "plasmids": len(
                                loaded.compiler.inventory.plasmids_by_identity
                            ),
                            "backbones": len(
                                loaded.compiler.inventory.backbones_by_identity
                            ),
                            "reagents": len(
                                loaded.compiler.inventory.reagents_by_identity
                            ),
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        if not cli_state.quiet:
            render_inventory(
                error_console(no_color=cli_state.no_color),
                designs=loaded.designs,
                inventory=loaded.compiler.inventory,
                design_paths=design,
                inventory_paths=inventory,
            )

    handle(cli_state, operation)
