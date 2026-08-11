"""Rich terminal presentation for ``buildc`` human-facing output."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from buildcompiler.domain import BuildStatus, StageResult


_STATUS_STYLES = {
    "success": "bold green",
    "partial_success": "bold yellow",
    "blocked": "bold yellow",
    "failed": "bold red",
}


def error_console(*, no_color: bool = False) -> Console:
    """Create a console bound to the invocation's current stderr."""

    return Console(stderr=True, no_color=no_color, highlight=False)


def render_plan(console: Console, plan: Any, *, destination: Path | None) -> None:
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    table.add_column("Stage")
    table.add_column("Requests", justify="right")
    table.add_row("Assembly · Level 2", str(len(plan.lvl2_requests)))
    table.add_row("Assembly · Level 1", str(len(plan.lvl1_requests)))
    table.add_row("Domestication", str(len(plan.domestication_requests)))
    table.add_row(
        "Unsupported",
        str(len(plan.unsupported)),
        style="yellow" if plan.unsupported else None,
    )
    subtitle = f"Written to {destination}" if destination else "JSON written to stdout"
    console.print(
        Panel(
            table,
            title="[bold green]Golden Gate plan ready[/]",
            subtitle=subtitle,
            border_style="green",
        )
    )


def render_build_result(console: Console, result: Any) -> None:
    status = result.status.value
    summary = result.summary
    metrics = Table.grid(padding=(0, 3))
    metrics.add_column(style="dim")
    metrics.add_column(justify="right", style="bold")
    metrics.add_row("Final products", str(summary.final_product_count))
    metrics.add_row("Missing inputs", str(summary.missing_input_count))
    metrics.add_row("Approvals", str(summary.required_approval_count))
    metrics.add_row("Warnings", str(summary.warning_count))

    stages = _stage_table(result.stage_results)
    content: list[Any] = [metrics, Text(""), stages]
    if result.missing_inputs:
        content.extend([Text(""), _missing_table(result.missing_inputs)])
    console.print(
        Panel(
            Group(*content),
            title=Text(
                f"Build {status.replace('_', ' ')}", style=_STATUS_STYLES[status]
            ),
            border_style=_border_for_status(status),
        )
    )


def render_stage_results(console: Console, results: list[StageResult]) -> None:
    status = (
        "success"
        if all(item.status.value == "success" for item in results)
        else "failed"
    )
    console.print(
        Panel(
            _stage_table(results),
            title=Text("Stage results", style=_STATUS_STYLES[status]),
            border_style=_border_for_status(status),
        )
    )


def render_inventory(
    console: Console,
    *,
    designs: list[Any],
    inventory: Any,
    design_paths: list[Path],
    inventory_paths: list[Path],
) -> None:
    counts = Table.grid(padding=(0, 3))
    counts.add_column(style="dim")
    counts.add_column(justify="right", style="bold cyan")
    counts.add_row("Design files", str(len(design_paths)))
    counts.add_row("Inventory files", str(len(inventory_paths)))
    counts.add_row("Selected designs", str(len(designs)))
    counts.add_row("Plasmids", str(len(inventory.plasmids_by_identity)))
    counts.add_row("Backbones", str(len(inventory.backbones_by_identity)))
    counts.add_row("Reagents", str(len(inventory.reagents_by_identity)))

    design_table = Table(box=box.SIMPLE, header_style="bold cyan")
    design_table.add_column("Type", style="magenta")
    design_table.add_column("Display ID")
    design_table.add_column("Identity", overflow="fold")
    for design in designs:
        design_table.add_row(
            type(design).__name__,
            getattr(design, "displayId", None) or "—",
            design.identity,
        )
    console.print(
        Panel(
            Group(counts, Text(""), design_table),
            title="[bold cyan]BuildCompiler inputs[/]",
            border_style="cyan",
        )
    )


def render_artifacts(console: Console, *, root: Path, paths: list[Path]) -> None:
    tree = Tree(Text(str(root), style="bold cyan"))
    for path in sorted(paths):
        tree.add(str(path.relative_to(root)))
    console.print(Panel(tree, title="[bold]Artifacts[/]", border_style="dim"))


def render_error(console: Console, message: str, *, hint: str | None = None) -> None:
    content: list[Any] = [Text(message)]
    if hint:
        content.extend([Text(""), Text(hint, style="dim")])
    console.print(
        Panel(Group(*content), title="[bold red]buildc error[/]", border_style="red")
    )


def _stage_table(results: list[StageResult]) -> Table:
    counts = Counter((result.stage.value, result.status.value) for result in results)
    table = Table(box=box.SIMPLE, header_style="bold cyan")
    table.add_column("Stage")
    table.add_column("Status")
    table.add_column("Runs", justify="right")
    for (stage, status), count in sorted(counts.items()):
        table.add_row(
            stage.replace("_", " · ").title(),
            Text(status.replace("_", " "), style=_STATUS_STYLES[status]),
            str(count),
        )
    return table


def _missing_table(missing_inputs: list[Any]) -> Table:
    table = Table(box=box.SIMPLE, header_style="bold yellow")
    table.add_column("Missing input")
    table.add_column("Kind")
    table.add_column("Reason", overflow="fold")
    for missing in missing_inputs:
        table.add_row(
            missing.missing_display_id or missing.missing_identity,
            missing.missing_kind,
            missing.reason,
        )
    return table


def _border_for_status(status: str) -> str:
    if status == BuildStatus.SUCCESS.value:
        return "green"
    if status in {BuildStatus.PARTIAL_SUCCESS.value, "blocked"}:
        return "yellow"
    return "red"
