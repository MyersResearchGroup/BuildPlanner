"""SBOL and JSON input boundaries for ``buildc``."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sbol2

from buildcompiler.api import BuildCompiler, BuildOptions, index_collections
from buildcompiler.domain import IndexedPlasmid, IndexedStrain, MaterialState
from buildcompiler.planning import FullBuildPlanner
from buildcompiler.sbol import PullPolicy, SbolResolver, load_synbiohub_collections

from .errors import CliInputError


@dataclass(frozen=True)
class CompilerInputs:
    document: sbol2.Document
    designs: list[Any]
    compiler: BuildCompiler


def read_sbol(path: Path) -> sbol2.Document:
    """Load one SBOL file with a path-specific error."""

    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise CliInputError(f"SBOL input does not exist or is not a file: {resolved}")
    document = sbol2.Document()
    try:
        document.read(str(resolved))
    except Exception as exc:
        raise CliInputError(f"Could not read SBOL input {resolved}: {exc}") from exc
    return document


def merge_sbol_documents(documents: list[sbol2.Document]) -> sbol2.Document:
    """Merge documents in order, allowing later explicit inputs to replace duplicates."""

    merged = sbol2.Document()
    for document in documents:
        try:
            merged.appendString(document.writeString())
        except (RuntimeError, sbol2.SBOLError) as exc:
            duplicate_markers = (
                "SBOL_ERROR_URI_NOT_UNIQUE",
                "DUPLICATE_URI_ERROR",
                "would require overwriting",
            )
            if not any(marker in str(exc) for marker in duplicate_markers):
                raise CliInputError(f"Could not merge SBOL inputs: {exc}") from exc
            merged.appendString(document.writeString(), overwrite=True)
    return merged


def load_compiler_inputs(
    *,
    design_paths: list[Path],
    inventory_paths: list[Path],
    selectors: list[str],
    options: BuildOptions,
    collections: list[str] | None = None,
    registry: str | None = None,
) -> CompilerInputs:
    """Load local/remote material, select designs, and construct the clean compiler."""

    if not design_paths:
        raise CliInputError("At least one --design SBOL file is required.")
    design_documents = [read_sbol(path) for path in _stable_paths(design_paths)]
    inventory_documents = [read_sbol(path) for path in _stable_paths(inventory_paths)]
    document = merge_sbol_documents([*inventory_documents, *design_documents])

    collection_ids = sorted(set(collections or []))
    if collection_ids:
        if not registry:
            raise CliInputError("--registry is required when --collection is used.")
        token = os.environ.get("BUILDC_SYNBIOHUB_TOKEN")
        if not token:
            raise CliInputError(
                "Set BUILDC_SYNBIOHUB_TOKEN when loading SynBioHub collections."
            )
        load_synbiohub_collections(
            collection_ids,
            sbh_registry=registry,
            auth_token=token,
            document=document,
        )

    designs = discover_designs(
        design_documents=design_documents,
        merged_document=document,
        selectors=selectors,
    )
    resolver = SbolResolver(document, pull_policy=PullPolicy.NEVER)
    inventory = index_collections(
        document,
        collection_identities=collection_ids,
        resolver=resolver,
    )
    compiler = BuildCompiler(
        inventory=inventory,
        sbol_document=document,
        planner=FullBuildPlanner(options=options, resolver=resolver),
        resolver=resolver,
        options=options,
    )
    return CompilerInputs(document=document, designs=designs, compiler=compiler)


def discover_designs(
    *,
    design_documents: list[sbol2.Document],
    merged_document: sbol2.Document,
    selectors: list[str],
) -> list[Any]:
    """Find uncontained top-level designs, or resolve explicit selectors."""

    objects = _design_objects(design_documents)
    if selectors:
        selected: list[Any] = []
        for selector in selectors:
            matches = [obj for obj in objects if _matches_selector(obj, selector)]
            if not matches:
                raise CliInputError(
                    f"Design selector did not match an SBOL object: {selector}"
                )
            identities = sorted({obj.identity for obj in matches})
            if len(identities) > 1:
                raise CliInputError(
                    f"Design selector is ambiguous: {selector} matches {identities}"
                )
            selected.append(matches[0])
    else:
        referenced_components: set[str] = set()
        referenced_modules: set[str] = set()
        derivation_templates: set[str] = set()
        for document in design_documents:
            for component in document.componentDefinitions:
                referenced_components.update(
                    str(child.definition) for child in component.components
                )
            for module in document.moduleDefinitions:
                referenced_components.update(
                    str(child.definition) for child in module.functionalComponents
                )
                referenced_modules.update(
                    str(child.definition) for child in module.modules
                )
            for derivation in document.combinatorialderivations:
                derivation_templates.add(str(derivation.masterTemplate))

        selected = []
        for obj in objects:
            if isinstance(obj, sbol2.CombinatorialDerivation):
                selected.append(obj)
            elif isinstance(obj, sbol2.ModuleDefinition):
                if obj.identity not in referenced_modules:
                    selected.append(obj)
            elif isinstance(obj, sbol2.ComponentDefinition):
                if (
                    obj.identity not in referenced_components
                    and obj.identity not in derivation_templates
                ):
                    selected.append(obj)

    resolved = []
    seen: set[str] = set()
    for obj in sorted(selected, key=lambda item: item.identity):
        if obj.identity in seen:
            continue
        merged = merged_document.find(obj.identity)
        if merged is None:
            raise CliInputError(
                f"Selected design was lost while merging: {obj.identity}"
            )
        resolved.append(merged)
        seen.add(obj.identity)
    if not resolved:
        raise CliInputError(
            "No top-level SBOL designs were found; use --select to choose one explicitly."
        )
    return resolved


def load_plasmids(
    path: Path, selectors: list[str]
) -> tuple[sbol2.Document, list[IndexedPlasmid]]:
    """Load assembled plasmids from SBOL for an independent transformation."""

    document = read_sbol(path)
    implementation_by_built = {
        str(implementation.built): implementation
        for implementation in document.implementations
        if implementation.built
    }
    components = list(document.componentDefinitions)
    if selectors:
        selected = []
        for selector in selectors:
            matches = [item for item in components if _matches_selector(item, selector)]
            if len(matches) != 1:
                raise CliInputError(
                    f"Plasmid selector must match exactly one ComponentDefinition: {selector}"
                )
            selected.append(matches[0])
    else:
        selected = [
            component
            for component in components
            if component.identity in implementation_by_built
            and any("plasmid" in str(role).lower() for role in component.roles)
        ]
        if not selected:
            selected = [
                component
                for component in components
                if component.identity in implementation_by_built
            ]
        if len(selected) != 1:
            raise CliInputError(
                "Could not infer one plasmid from the SBOL file; use --select for each plasmid."
            )

    plasmids = []
    for component in sorted(selected, key=lambda item: item.identity):
        implementation = implementation_by_built.get(component.identity)
        metadata = {}
        if implementation is not None:
            metadata["implementation_identity"] = implementation.identity
        plasmids.append(
            IndexedPlasmid(
                identity=component.identity,
                display_id=component.displayId or None,
                name=component.name or None,
                state=MaterialState.ASSEMBLED,
                roles=list(component.roles),
                metadata=metadata,
                sbol_component=component,
            )
        )
    return document, plasmids


def load_strains(path: Path) -> list[IndexedStrain]:
    """Load transformed strains from a buildc JSON result."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliInputError(
            f"Could not read transformed-strain JSON {path}: {exc}"
        ) from exc
    records: dict[str, dict[str, Any]] = {}
    _collect_strain_records(payload, records)
    if not records:
        raise CliInputError(f"No serialized transformed strains found in {path}.")
    return [
        IndexedStrain(
            identity=record["identity"],
            display_id=record.get("display_id"),
            name=record.get("name"),
            state=MaterialState(record.get("state", MaterialState.TRANSFORMED.value)),
            roles=list(record.get("roles", [])),
            metadata=dict(record.get("metadata", {})),
        )
        for record in sorted(records.values(), key=lambda item: item["identity"])
    ]


def _stable_paths(paths: list[Path]) -> list[Path]:
    return sorted({path.expanduser().resolve() for path in paths}, key=str)


def _design_objects(documents: list[sbol2.Document]) -> list[Any]:
    objects: dict[str, Any] = {}
    for document in documents:
        for collection in (
            document.moduleDefinitions,
            document.combinatorialderivations,
            document.componentDefinitions,
        ):
            for obj in collection:
                objects[obj.identity] = obj
    return list(objects.values())


def _matches_selector(obj: Any, selector: str) -> bool:
    return selector in {
        str(getattr(obj, "identity", "")),
        str(getattr(obj, "persistentIdentity", "")),
        str(getattr(obj, "displayId", "")),
    }


def _collect_strain_records(payload: Any, records: dict[str, dict[str, Any]]) -> None:
    if isinstance(payload, list):
        for item in payload:
            _collect_strain_records(item, records)
        return
    if not isinstance(payload, dict):
        return
    if payload.get("kind") == "strain" and isinstance(payload.get("identity"), str):
        records[payload["identity"]] = payload
    for value in payload.values():
        if isinstance(value, (dict, list)):
            _collect_strain_records(value, records)
