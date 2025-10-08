import sbol2
from typing import Dict, List
from .constants import FUSION_SITES

class MocloPlasmid:
    def __init__(self, name: str, definition: sbol2.ComponentDefinition, doc: sbol2.document):
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
    
def extract_fusion_sites(plasmid: sbol2.ComponentDefinition, doc: sbol2.Document) -> List[sbol2.ComponentDefinition]:
    fusion_sites = []
    for component in plasmid.components:
        definition = doc.getComponentDefinition(component.definition)
        if ("http://identifiers.org/so/SO:0001953" in definition.roles):
            fusion_sites.append(definition)

    return fusion_sites

def extract_design_parts(design: sbol2.ComponentDefinition, doc: sbol2.Document) -> List[sbol2.ComponentDefinition]:
    component_list = [c for c in design.getInSequentialOrder()]
    return [doc.getComponentDefinition(component.definition) for component in component_list]

def extract_toplevel_definition(doc: sbol2.Document) -> sbol2.ComponentDefinition:
    module = doc.moduleDefinitions[0]
    functional_component = module.functionalComponents[0]

    return doc.getComponentDefinition(functional_component.definition)

def construct_plasmid_dict(part_list: List[sbol2.ComponentDefinition], plasmid_collection: sbol2.Document) -> Dict[str, List[MocloPlasmid]]: 
    plasmid_dict = {}
    for part in part_list:
        for plasmid in plasmid_collection.moduleDefinitions:
            toplevel_URI = plasmid.functionalComponents[0].definition
            toplevel_definition = plasmid_collection.getComponentDefinition(toplevel_URI)

            for component in toplevel_definition.components:
                if component.definition == str(part):
                    fusion_sites = [site.name for site in extract_fusion_sites(toplevel_definition, plasmid_collection)]
                    print(f"found: {component.definition} in {plasmid} with {fusion_sites}") #TODO switch to logger for backend tracing?
                    plasmid_dict.setdefault(part.displayId, [])

                    componentName = plasmid_collection.getComponentDefinition(component.definition).name


                    plasmid_dict[part.displayId].append(
                        MocloPlasmid(componentName, toplevel_definition, plasmid_collection)
                    )

    return plasmid_dict
    
def get_compatibile_plasmids(plasmid_dict: Dict[str, List[MocloPlasmid]], backbone: MocloPlasmid):
    selected_plasmids = []
    match_to = backbone
    match_idx = 0

    for i, key in enumerate(plasmid_dict):
        for plasmid in plasmid_dict[key]:
            if plasmid.fusion_sites[0] == match_to.fusion_sites[match_idx]:
                print(f"matched {plasmid.name} with {match_to.name} on fusion site {plasmid.fusion_sites[0]}!")
                selected_plasmids.append(plasmid)
                match_to = plasmid
                match_idx = 1
                break

    return selected_plasmids

# TODO potenitally replace each componentdefinition with a SBH URI, or extract definitions from SBH before calling
def translate_abstract_to_plasmids(abstract_design_doc: sbol2.Document, plasmid_collection: sbol2.Document, backbone_doc: sbol2.Document):
    abstract_design_def = extract_toplevel_definition(abstract_design_doc)
    backbone_def = extract_toplevel_definition(backbone_doc)

    ordered_part_definitions = extract_design_parts(abstract_design_def, abstract_design_doc)
    
    plasmid_dict = construct_plasmid_dict(ordered_part_definitions, plasmid_collection)
    backbone_plasmid = MocloPlasmid(backbone_def.displayId, backbone_def, backbone_doc)

    return get_compatibile_plasmids(plasmid_dict, backbone_plasmid)