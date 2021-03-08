Interoperability between Python and Gmsh
========================================

.. image:: https://gitlab.tiker.net/inducer/gmsh_interop/badges/main/pipeline.svg
    :alt: Gitlab Build Status
    :target: https://gitlab.tiker.net/inducer/gmsh_interop/commits/main
.. image:: https://github.com/inducer/gmsh_interop/workflows/CI/badge.svg
    :alt: Github Build Status
    :target: https://github.com/inducer/gmsh_interop/actions?query=branch%3Amain+workflow%3ACI
.. image:: https://badge.fury.io/py/gmsh_interop.png
    :alt: Python Package Index Release Page
    :target: https://pypi.org/project/gmsh_interop/

This package allows Python to interoperate with the `gmsh <http://gmsh.info/>`_
mesh generator.

This package contains:

* ``gmsh_interop.reader`` to read gmsh's ``.msh`` file format.
* ``gmsh_interop.runner`` to run gmsh under program control and process its output.

Its contents was extracted from `meshpy <https://github.com/inducer/meshpy>`__
to escape its obnoxious licensing.

Links:

* `Github <https://github.com/inducer/gmsh_interop>`_
* `Python package index <https://pypi.org/project/gmsh_interop/>`_
* `Documentation <https://documen.tician.de/gmsh_interop>`_
