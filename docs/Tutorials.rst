Tutorials
======================================
Let's get started with creating DNA assembly plans. First we will demonstrate a workflow using plasmid files from `SBOLCanvas <https://sbolcanvas.org/>`_:

.. code:: ipython3

    import sbol2build as s2b
    import sbol2

First, read your plasmid SBOL files into documents.

.. code:: ipython3
    
    promoter = sbol2.Document()
    promoter.read('pro_in_bb.xml')

    rbs = sbol2.Document()
    rbs.read('rbs_in_bb.xml')

    cds = sbol2.Document()
    cds.read('cds_in_bb.xml')

    terminator = sbol2.Document()
    terminator.read('terminator_in_bb.xml')

    backbone = sbol2.Document()
    backbone.read('backbone.xml')

Create golden gate assembly plan object with all the parts, the acceptor backbone, and restriction enzyme.

.. code:: ipython3

    assembly_doc = sbol2.Document()
    
    assembly_plan = s2b.golden_gate_assembly_plan('tutorial_assembly_plan', [promoter, rbs, cds, terminator], backbone, 'BsaI', assembly_doc)
    
    composites = assembly_plan.run()