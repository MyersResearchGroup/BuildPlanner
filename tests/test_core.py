import sbol2
import filecmp
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from sbol2build import rebase_restriction_enzyme, backbone_digestion, part_digestion, ligation2

class Test_Core_Functions(unittest.TestCase):
    def test_part_digestion(self):
        doc = sbol2.Document()
        doc.read('test_files/pro_in_bb.xml')

        md = doc.getModuleDefinition('https://sbolcanvas.org/module1')
        assembly_plan = sbol2.ModuleDefinition('assembly_plan')

        parts_list, assembly_plan = part_digestion(md, [rebase_restriction_enzyme('BsaI')], assembly_plan, doc)

        product_doc = sbol2.Document()
        for extract, sequence in parts_list:
            product_doc.add(extract)
            product_doc.add(sequence)
        product_doc.add(assembly_plan)

        # ensure extracted part has 5prime, part from sbolcanvas, and 3prime
        for anno in parts_list[0][0].sequenceAnnotations:
            comp_uri = anno.component
            comp_obj = product_doc.find(comp_uri)
            comp_def = product_doc.find(comp_obj.definition)

            if 'three_prime_oh' in comp_obj.displayId:
                self.assertEqual(comp_def.roles, ['http://identifiers.org/so/SO:0001933'], 'Part digestion missing 3 prime role')
            elif 'five_prime_oh' in comp_obj.displayId:
                self.assertEqual(comp_def.roles, ['http://identifiers.org/so/SO:0001932'], 'Part digestion missing 5 prime role')
            else:
                self.assertTrue(comp_def.identity in doc.componentDefinitions, 'Digested part missing reference to part from original document') #check that old part has been transcribed to new doc, in extracted part

        # check that wasderivedfroms match, assembly plan records all interactions, 
        contains_restriction, contains_reactant, contains_product = False, False, False
        for participation in assembly_plan.interactions[0].participations:
            if participation.displayId == 'restriction':
                self.assertTrue('http://identifiers.org/biomodels.sbo/SBO:0000019' in participation.roles, "Restriction participation missing 'modifier' role")
                contains_restriction = True
            elif 'reactant' in participation.displayId:
                self.assertTrue('http://identifiers.org/biomodels.sbo/SBO:0000010' in participation.roles, "Restriction reactant participation missing 'reactant' role")
                contains_reactant = True
            elif 'product' in participation.displayId:
                self.assertTrue('http://identifiers.org/biomodels.sbo/SBO:0000011' in participation.roles, "Restriction product participation missing 'product' role")
                contains_product = True
        
        self.assertTrue(contains_product, 'Digestion Assembly plan missing product participation')
        self.assertTrue(contains_reactant, 'Digestion Assembly plan missing reactant participation')
        self.assertTrue(contains_restriction, 'Digestion Assembly plan missing restriction participation')

if __name__ == '__main__':
    unittest.main()