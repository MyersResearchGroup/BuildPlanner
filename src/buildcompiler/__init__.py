"""BuildCompiler public package exports."""

from typing import Any

from .sbol2build import *  # noqa: F403
from .api import (
    BuildOptions as BuildOptions,
    assembly_lvl1 as assembly_lvl1,
    assembly_lvl2 as assembly_lvl2,
    domestication as domestication,
    full_build as full_build,
    transformation as transformation,
)


def __getattr__(name: str) -> Any:
    """Load the artifact-producing compiler only when it is requested."""
    if name == "BuildCompiler":
        from .buildcompiler import BuildCompiler

        globals()[name] = BuildCompiler
        return BuildCompiler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
