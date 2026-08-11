"""Root Typer application and command registration for ``buildc``."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Annotated

import typer

from .commands import assemble, inspect_inputs, plan, plate, run, transform
from .context import CliState


app = typer.Typer(
    name="buildc",
    help="Compile SBOL designs into clear, reproducible build workflows.",
    epilog=(
        "BuildCompiler currently implements the Golden Gate workflow. "
        "Set BUILDC_SYNBIOHUB_TOKEN to load authenticated SynBioHub collections."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
    suggest_commands=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if not value:
        return
    try:
        package_version = version("synbio-buildcompiler")
    except PackageNotFoundError:
        package_version = "0.0.1a1"
    typer.echo(f"buildc {package_version}")
    raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version_requested: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the buildc version and exit.",
        ),
    ] = False,
    no_color: Annotated[
        bool, typer.Option("--no-color", help="Disable terminal colors.")
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress human-facing status output."),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Show tracebacks for unexpected internal errors."),
    ] = False,
) -> None:
    """BuildCompiler's technique-neutral workflow CLI."""

    del version_requested
    ctx.obj = CliState(no_color=no_color, quiet=quiet, debug=debug)


app.command(short_help="Compile designs into a reviewable build plan.")(plan)
app.command(short_help="Run the complete Golden Gate workflow.")(run)
app.command(short_help="Run Golden Gate assembly without downstream stages.")(assemble)
app.command(short_help="Transform one or more assembled plasmids.")(transform)
app.command(short_help="Assign transformed strains to a plate.")(plate)
app.command(name="inspect", short_help="Inspect resolved designs and inventory.")(
    inspect_inputs
)


if __name__ == "__main__":
    app()
