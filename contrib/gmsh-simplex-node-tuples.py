import os
import subprocess

import numpy as np
import gmsh


OUTPUT_TEMPLATE = """
tri_node_tuples = %s

tet_node_tuples = %s
"""


def generate_triangle_node_tuples(tmpdir, order):
    # {{{ create mesh

    gmsh.model.add(f"Triangle{order}")
    gmsh.option.setNumber("Mesh.MeshSizeMin", 2*order)
    gmsh.option.setNumber("Mesh.MeshSizeMax", 2*order)

    gmsh.model.occ.addRectangle(0, 0, 0, order, order)
    gmsh.model.occ.synchronize()

    gmsh.model.mesh.generate(2)
    gmsh.model.mesh.setOrder(order)

    # this generates an X triangle mesh like
    #
    #        +-----+
    #        |\   /|
    #        | \ / |
    #        |  +  |
    #        | / \ |
    #        |/ 0 \|
    #        +-----+
    #
    # and we'll work on the bottom 0 element
    # FIXME: would be nice to just generate two triangles there

    # }}}

    # {{{ get element

    el_types, _, node_tags = gmsh.model.mesh.getElements(2)
    assert len(el_types) == 1

    # get node indices for the first element
    nnodes = gmsh.model.mesh.getElementProperties(el_types[0])[3]
    node_tags = node_tags[0].reshape(-1, nnodes) - 1
    assert node_tags[0].size == (order + 1) * (order + 2) // 2

    _, nodes, _ = gmsh.model.mesh.getNodes()
    nodes = nodes.reshape(-1, 3)

    # transform element nodes to match the unit triangle
    mat = np.array([[1, -1], [0, 2]])
    nodes = (mat @ nodes[node_tags[0, :], :-1].T).T

    # }}}

    return [tuple(node) for node in nodes.astype(int)]


def generate_tetrahedron_node_tuples(tmpdir, order):
    raise NotImplementedError


def generate_node_tuples(filename, max_order=10):
    tri_node_tuples = {}
    tet_node_tuples = {}

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 1)

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        for order in range(1, max_order + 1):
            tri_node_tuples[order] = generate_triangle_node_tuples(".", order)
            # tet_node_tuples[order] = generate_tetrahedron_node_tuples(tmp, order)

    gmsh.finalize()

    from pprint import pformat
    txt = (OUTPUT_TEMPLATE % (
        pformat(tri_node_tuples, width=80),
        pformat(tet_node_tuples, width=80)
        )).replace('"', "")

    if filename is None:
        print(txt)
    else:
        with open(filename, "w") as fd:
            fd.write(txt)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("filename", nargs="?", default=None)
    args = parser.parse_args()

    generate_node_tuples(args.filename)
