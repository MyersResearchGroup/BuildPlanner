from buildcompiler.api import BuildOptions
from buildcompiler.domain import IndexedStrain, MaterialState, StageStatus
from buildcompiler.stages import PlatingStage, plate_wells


def test_plating_stage_assigns_row_major_wells_without_mutating_inputs():
    strains = [
        IndexedStrain("strain-a", metadata={"source": "transformation"}),
        IndexedStrain("strain-b", metadata={"source": "transformation"}),
    ]

    result = PlatingStage(
        options=BuildOptions(),
        plate_id="plate-7",
        advanced_parameters={"replicates": 1},
    ).run(strains)

    assert result.status == StageStatus.SUCCESS
    assert result.protocol_artifacts["plate_map"] == {
        "A1": "strain-a",
        "A2": "strain-b",
    }
    assert result.json_intermediate == {
        "bacterium_locations": {"A1": "strain-a", "A2": "strain-b"},
        "replicates": 1,
    }
    assert [product.state for product in result.products] == [
        MaterialState.PLATED,
        MaterialState.PLATED,
    ]
    assert [strain.state for strain in strains] == [
        MaterialState.TRANSFORMED,
        MaterialState.TRANSFORMED,
    ]


def test_plating_stage_reports_capacity_failure_as_a_stage_result():
    result = PlatingStage().run(
        [IndexedStrain(f"strain-{index}") for index in range(97)]
    )

    assert result.status == StageStatus.FAILED
    assert "at most 96" in result.logs[0]


def test_plate_wells_are_row_major_and_bounded():
    assert plate_wells(1) == ["A1"]
    assert plate_wells(13)[-1] == "B1"
    assert plate_wells(96)[-1] == "H12"
