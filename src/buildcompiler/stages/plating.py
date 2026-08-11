"""Deterministic plating-stage orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from buildcompiler.adapters.pudu import plating_to_pudu_json
from buildcompiler.api.options import BuildOptions
from buildcompiler.domain import (
    BuildStage,
    IndexedStrain,
    MaterialState,
    StageResult,
    StageStatus,
)


def plate_wells(limit: int) -> list[str]:
    """Return deterministic row-major wells for a 96-well plate."""

    if limit < 0:
        raise ValueError("Plating well count cannot be negative.")
    if limit > 96:
        raise ValueError("Plating supports at most 96 transformed strains per plate.")
    return [f"{row}{column}" for row in "ABCDEFGH" for column in range(1, 13)][:limit]


class PlatingStage:
    """Assign transformed strains to a plate without hidden file output."""

    def __init__(
        self,
        *,
        options: BuildOptions | None = None,
        plate_id: str = "buildcompiler_plate_1",
        advanced_parameters: dict[str, Any] | None = None,
    ) -> None:
        self.options = options or BuildOptions()
        self.plate_id = plate_id
        self.advanced_parameters = dict(advanced_parameters or {})

    def run(
        self,
        strain_or_strains: IndexedStrain | Sequence[IndexedStrain],
        *,
        source_document: Any | None = None,
        target_document: Any | None = None,
    ) -> StageResult:
        del source_document, target_document
        strains = (
            list(strain_or_strains)
            if isinstance(strain_or_strains, Sequence)
            else [strain_or_strains]
        )
        request_ids = [f"plate:{strain.identity}" for strain in strains]
        if not strains:
            return StageResult(
                id=f"plating:{self.plate_id}",
                stage=BuildStage.PLATING,
                status=StageStatus.FAILED,
                logs=["Plating requires at least one transformed strain."],
            )
        if any(not isinstance(strain, IndexedStrain) for strain in strains):
            return StageResult(
                id=f"plating:{self.plate_id}",
                stage=BuildStage.PLATING,
                status=StageStatus.FAILED,
                request_ids=request_ids,
                logs=["Plating inputs must be IndexedStrain values."],
            )
        try:
            wells = plate_wells(len(strains))
        except ValueError as exc:
            return StageResult(
                id=f"plating:{self.plate_id}",
                stage=BuildStage.PLATING,
                status=StageStatus.FAILED,
                request_ids=request_ids,
                logs=[str(exc)],
            )

        plate_map = {well: strain.identity for well, strain in zip(wells, strains)}
        pudu_payload = plating_to_pudu_json(
            bacterium_locations=plate_map,
            advanced_parameters=self.advanced_parameters,
        )
        products = [
            replace(
                strain,
                state=MaterialState.PLATED,
                metadata={
                    **strain.metadata,
                    "plate_id": self.plate_id,
                    "well": well,
                },
            )
            for well, strain in zip(wells, strains)
        ]
        return StageResult(
            id=f"plating:{self.plate_id}",
            stage=BuildStage.PLATING,
            status=StageStatus.SUCCESS,
            request_ids=request_ids,
            products=products,
            json_intermediate=pudu_payload,
            protocol_artifacts={
                "plate_id": self.plate_id,
                "plate_map": plate_map,
                "advanced_parameters": self.advanced_parameters,
            },
            logs=[f"Assigned {len(strains)} transformed strain(s) to {self.plate_id}."],
        )
