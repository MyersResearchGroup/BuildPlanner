"""Shared invocation state and command policies for ``buildc``."""

from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

import sbol2
import typer

from buildcompiler.api import (
    BuildCompilerError,
    BuildOptions,
    ProtocolMode,
    deserialize_build_plan,
)
from buildcompiler.domain import BuildStatus, StageStatus

from .errors import CliInputError
from .render import error_console, render_error


@dataclass(frozen=True)
class CliState:
    no_color: bool = False
    quiet: bool = False
    debug: bool = False


T = TypeVar("T")


def state(ctx: typer.Context) -> CliState:
    """Return the initialized state for the current invocation."""

    return ctx.ensure_object(CliState)


def handle(cli_state: CliState, operation: Callable[[], T]) -> T | None:
    """Apply the CLI's stable error-rendering and exit-code policy."""

    try:
        return operation()
    except typer.Exit:
        raise
    except CliInputError as exc:
        if not cli_state.quiet:
            render_error(error_console(no_color=cli_state.no_color), str(exc))
        raise typer.Exit(code=2) from exc
    except (BuildCompilerError, sbol2.SBOLError) as exc:
        if not cli_state.quiet:
            render_error(error_console(no_color=cli_state.no_color), str(exc))
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        if cli_state.debug:
            raise
        if not cli_state.quiet:
            render_error(
                error_console(no_color=cli_state.no_color),
                f"Unexpected internal error: {exc}",
                hint="Re-run with --debug to see the full traceback.",
            )
        raise typer.Exit(code=1) from exc


def status(cli_state: CliState, message: str):
    """Render a transient status unless human-facing output is disabled."""

    if cli_state.quiet:
        return nullcontext()
    return error_console(no_color=cli_state.no_color).status(message, spinner="dots")


def build_options(
    *,
    transformation_enabled: bool,
    chassis: str | None,
    protocol: ProtocolMode,
    output: Path,
    max_iterations: int = 5,
    detailed_report: bool = False,
    approvals: list[str] | None = None,
    allow_sequence_edits: bool = False,
    continue_on_error: bool = False,
) -> BuildOptions:
    """Translate CLI options into the public compiler contract."""

    options = BuildOptions()
    options.execution.max_iterations = max_iterations
    options.execution.continue_on_error = continue_on_error
    options.protocol.mode = protocol
    options.protocol.results_dir = output / "protocols"
    options.reporting.include_detailed_report = detailed_report
    options.approvals.approved_processes.update(approvals or [])
    options.domestication.allow_sequence_domestication_edits = allow_sequence_edits
    options.transformation.enabled = transformation_enabled
    options.transformation.chassis_identity = chassis
    options.transformation.chassis_display_id = (
        chassis.rsplit("/", 1)[-1] if chassis else None
    )
    return options


def read_plan(path: Path) -> Any:
    """Read a serialized build plan with a user-facing input error."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliInputError(f"Could not read build plan {path}: {exc}") from exc
    return deserialize_build_plan(payload)


def parse_parameters(values: list[str]) -> dict[str, Any]:
    """Parse repeatable ``KEY=JSON`` advanced stage parameters."""

    parameters: dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise CliInputError(
                f"Invalid --parameter {value!r}; expected KEY=JSON (for example, replicates=2)."
            )
        key, raw = value.split("=", 1)
        if not key:
            raise CliInputError("Plating parameter keys cannot be empty.")
        try:
            parameters[key] = json.loads(raw)
        except json.JSONDecodeError:
            parameters[key] = raw
    return parameters


def exit_for_build(result: Any) -> None:
    """Map a full build status to the documented process exit code."""

    if result.status == BuildStatus.SUCCESS:
        return
    if result.status == BuildStatus.PARTIAL_SUCCESS:
        raise typer.Exit(code=4)
    if result.missing_inputs or result.required_approvals:
        raise typer.Exit(code=3)
    raise typer.Exit(code=1)


def exit_for_stages(results: list[Any]) -> None:
    """Map independent stage statuses to the documented process exit code."""

    statuses = {result.status for result in results}
    if statuses == {StageStatus.SUCCESS}:
        return
    if StageStatus.PARTIAL_SUCCESS in statuses:
        raise typer.Exit(code=4)
    if StageStatus.BLOCKED in statuses:
        raise typer.Exit(code=3)
    raise typer.Exit(code=1)
