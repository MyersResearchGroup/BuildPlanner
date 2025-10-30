import sbol2
from typing import Dict, List
from .constants import FUSION_SITES


class MocloPlasmid:
    def __init__(
        self, name: str, definition: sbol2.ComponentDefinition, doc: sbol2.document
    ):
        self.definition = definition
        self.fusion_sites = self.match_fusion_sites(doc)
        self.name = name + "".join(f"_{s}" for s in self.fusion_sites)

    def match_fusion_sites(self, doc: sbol2.document) -> List[str]:
        fusion_site_definitions = extract_fusion_sites(self.definition, doc)
        fusion_sites = []
        for site in fusion_site_definitions:
            sequence_obj = doc.getSequence(site.sequences[0])
            sequence = sequence_obj.elements

            for key, seq in FUSION_SITES.items():
                if seq == sequence.upper():
                    fusion_sites.append(key)

        fusion_sites.sort()
        return fusion_sites

    def __repr__(self) -> str:
        return (
            f"MocloPlasmid:\n"
            f"  Name: {self.name}\n"
            f"  Definition: {self.definition.identity}\n"
            f"  Fusion Sites: {self.fusion_sites or 'Not found'}"
        )


def extract_fusion_sites(
    plasmid: sbol2.ComponentDefinition, doc: sbol2.Document
) -> List[sbol2.ComponentDefinition]:
    """
    Returns all fusion site component definitions from a plasmid.

    Args:
        plasmid: :class:`sbol2.ComponentDefinition` representing the plasmid.
        doc: :class:`sbol2.Document` containing component definitions.

    Returns:
        A list of fusion site component definitions.
    """
    fusion_sites = []
    for component in plasmid.components:
        definition = doc.getComponentDefinition(component.definition)
        if "http://identifiers.org/so/SO:0001953" in definition.roles:
            fusion_sites.append(definition)

    return fusion_sites


def extract_design_parts(
    design: sbol2.ComponentDefinition, doc: sbol2.Document
) -> List[sbol2.ComponentDefinition]:
    """
    Returns definitions of parts in a design in sequential order.

    Args:
        design: :class:`sbol2.ComponentDefinition` to extract parts from.
        doc: :class:`sbol2.Document` containing all component definitions.

    Returns:
        A list of component definitions in sequential order.
    """
    component_list = [c for c in design.getInSequentialOrder()]
    return [
        doc.getComponentDefinition(component.definition) for component in component_list
    ]


def extract_toplevel_definition(doc: sbol2.Document) -> sbol2.ComponentDefinition:
    return doc.componentDefinitions[0]


def construct_plasmid_dict(
    part_list: List[sbol2.ComponentDefinition], plasmid_collection: sbol2.Document
) -> Dict[str, List[MocloPlasmid]]:
    plasmid_dict = {}
    for part in part_list:
        for plasmid in plasmid_collection.componentDefinitions:
            if "http://identifiers.org/so/SO:0000637" in plasmid.roles:
                for component in plasmid.components:
                    if (
                        component.definition == str(part)
                    ):  # TODO make sure this is not a composite plasmid, i.e. plasmid just contains singular part of interest
                        fusion_sites = [
                            site.name
                            for site in extract_fusion_sites(
                                plasmid, plasmid_collection
                            )
                        ]
                        print(
                            f"found: {component.definition} in {plasmid} with {fusion_sites}"
                        )  # TODO switch to logger for backend tracing?
                        plasmid_dict.setdefault(part.displayId, [])

                        componentName = plasmid_collection.getComponentDefinition(
                            component.definition
                        ).name

                        plasmid_dict[part.displayId].append(
                            MocloPlasmid(componentName, plasmid, plasmid_collection)
                        )

    return plasmid_dict


def get_compatible_plasmids(
    plasmid_dict: Dict[str, List[MocloPlasmid]], backbone: MocloPlasmid
) -> List[MocloPlasmid]:
    """
    Returns a list of MocloPlasmid objects that can form a compatible assembly
    with the given backbone plasmid. The function selects one plasmid from each
    entry in the dictionary, ensuring that adjacent plasmids have matching fusion sites,
    and that the first and last plasmids are compatible with the backbone.

    Args:
        plasmid_dict: A dictionary mapping assembly positions or categories to lists
            of MocloPlasmid objects.
        backbone: The backbone MocloPlasmid whose fusion sites define compatibility.

    Returns:
        A list of compatible MocloPlasmid objects forming a sequential assembly.
    """
    selected_plasmids = []
    match_to = backbone
    match_idx = 0

    for i, key in enumerate(plasmid_dict):
        for plasmid in plasmid_dict[key]:
            if (
                i == len(plasmid_dict) - 1
                and plasmid.fusion_sites[0] == match_to.fusion_sites[match_idx]
                and plasmid.fusion_sites[1] == backbone.fusion_sites[1]
            ):
                print(
                    f"matched final component {plasmid.name} with {match_to.name} and {backbone.name} on fusion sites ({plasmid.fusion_sites[0]}, {plasmid.fusion_sites[1]})!"
                )
                selected_plasmids.append(plasmid)
                break
            elif (
                i < len(plasmid_dict) - 1
                and plasmid.fusion_sites[0] == match_to.fusion_sites[match_idx]
            ):  # TODO add error handling if no compatible plasmid found
                print(
                    f"matched {plasmid.name} with {match_to.name} on fusion site {plasmid.fusion_sites[0]}!"
                )
                selected_plasmids.append(plasmid)
                match_to = plasmid
                match_idx = 1
                break
            # TODO edge case where second fusion site does not match terminator fusion site will not be caught by current logic
            # 10/14: rethink implementation, will likely need to be different for combinatorial designs

    return selected_plasmids


# TODO potenitally replace each componentdefinition with a SBH URI, or extract definitions from SBH before calling
def translate_abstract_to_plasmids(
    abstract_design_doc: sbol2.Document,
    plasmid_collection: sbol2.Document,
    backbone_doc: sbol2.Document,
):
    abstract_design_def = extract_toplevel_definition(abstract_design_doc)
    backbone_def = extract_toplevel_definition(backbone_doc)

    ordered_part_definitions = extract_design_parts(
        abstract_design_def, abstract_design_doc
    )

    plasmid_dict = construct_plasmid_dict(ordered_part_definitions, plasmid_collection)
    backbone_plasmid = MocloPlasmid(backbone_def.displayId, backbone_def, backbone_doc)

    return get_compatible_plasmids(plasmid_dict, backbone_plasmid)
