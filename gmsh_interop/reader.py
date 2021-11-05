"""Reader for the GMSH file format."""


__copyright__ = "Copyright (C) 2009 Xueyu Zhu, Andreas Kloeckner"

__license__ = """
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from functools import reduce

import numpy as np
#import numpy.linalg as la
from pytools import memoize_method, Record
from gmsh_interop.runner import (  # noqa
        ScriptSource, LiteralSource, FileSource, ScriptWithFilesSource)


__doc__ = """
.. exception:: GmshFileFormatError

Element types
-------------

.. autoclass:: GmshElementBase

Simplex Elements
^^^^^^^^^^^^^^^^

.. autoclass:: GmshSimplexElementBase
.. autoclass:: GmshPoint
.. autoclass:: GmshIntervalElement
.. autoclass:: GmshTriangularElement
.. autoclass:: GmshIncompleteTriangularElement
.. autoclass:: GmshTetrahedralElement

Tensor Product Elements
^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: GmshTensorProductElementBase
.. autoclass:: GmshQuadrilateralElement
.. autoclass:: GmshHexahedralElement

Receiver interface
------------------

.. autoclass:: GmshMeshReceiverBase

Receiver example implementation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: GmshMeshReceiverNumPy

Reader
------

.. autoclass:: ScriptSource
.. autoclass:: FileSource
.. autoclass:: ScriptWithFilesSource

.. autofunction:: read_gmsh
.. autofunction:: generate_gmsh

"""


# {{{ tools

def generate_triangle_vertex_tuples(order):
    yield (0, 0)
    yield (order, 0)
    yield (0, order)


def generate_triangle_edge_tuples(order):
    for i in range(1, order):
        yield (i, 0)
    for i in range(1, order):
        yield (order-i, i)
    for i in range(1, order):
        yield (0, order-i)


def generate_triangle_volume_tuples(order):
    for i in range(1, order):
        for j in range(1, order-i):
            yield (j, i)


def generate_quad_vertex_tuples(dim, order):
    from pytools import \
            generate_nonnegative_integer_tuples_below
    for tup in generate_nonnegative_integer_tuples_below(2, dim):
        yield tuple(order * i for i in tup)


class LineFeeder:
    def __init__(self, line_iterable):
        self.line_iterable = iter(line_iterable)
        self.next_line = None

    def has_next_line(self):
        if self.next_line is not None:
            return True

        try:
            self.next_line = next(self.line_iterable)
        except StopIteration:
            return False
        else:
            return True

    def get_next_line(self):
        if self.next_line is not None:
            nl = self.next_line
            self.next_line = None
            return nl.strip()

        try:
            nl = next(self.line_iterable)
        except StopIteration:
            raise GmshFileFormatError("unexpected end of file")
        else:
            return nl.strip()

# }}}


# {{{ element info

class GmshElementBase:
    """
    .. automethod:: vertex_count
    .. automethod:: node_count
    .. automethod:: lexicographic_node_tuples

        Generate tuples enumerating the node indices present
        in this element. Each tuple has a length equal to the dimension
        of the element. The tuples constituents are non-negative integers
        whose sum is less than or equal to the order of the element.

    .. automethod:: get_lexicographic_gmsh_node_indices

      (Implemented by subclasses)
    """
    def __init__(self, order):
        self.order = order

    @property
    def element_type(self):
        raise NotImplementedError

    def vertex_count(self):
        raise NotImplementedError

    def node_count(self):
        raise NotImplementedError

    def lexicographic_node_tuples(self):
        raise NotImplementedError

    @memoize_method
    def get_lexicographic_gmsh_node_indices(self):
        gmsh_tup_to_index = {
                tup: i
                for i, tup in enumerate(self.gmsh_node_tuples())}

        return np.array([
            gmsh_tup_to_index[tup] for tup in self.lexicographic_node_tuples()],
            dtype=np.intp)


# {{{ simplices

class GmshSimplexElementBase(GmshElementBase):
    def vertex_count(self):
        return self.dimensions + 1

    @memoize_method
    def node_count(self):
        """Return the number of interpolation nodes in this element."""
        d = self.dimensions
        o = self.order
        from operator import mul
        from pytools import factorial
        return int(reduce(mul, (o + 1 + i for i in range(d)), 1) / factorial(d))

    @memoize_method
    def lexicographic_node_tuples(self):
        from pytools import \
                generate_nonnegative_integer_tuples_summing_to_at_most as gnitstam
        result = list(gnitstam(self.order, self.dimensions))

        assert len(result) == self.node_count()
        return result


class GmshPoint(GmshSimplexElementBase):
    dimensions = 0

    @property
    def element_type(self):
        return 15

    @memoize_method
    def gmsh_node_tuples(self):
        return [()]


class GmshIntervalElement(GmshSimplexElementBase):
    dimensions = 1

    @property
    @memoize_method
    def element_type(self):
        return [1, 8, 26, 27, 28, 62, 63, 64, 65, 66][self.order - 1]

    @memoize_method
    def gmsh_node_tuples(self):
        return [(0,), (self.order,), ] + [
                (i,) for i in range(1, self.order)]


class GmshIncompleteTriangularElement(GmshSimplexElementBase):
    dimensions = 2

    def __init__(self, order):
        self.order = order

    @property
    @memoize_method
    def element_type(self):
        return {3: 20, 4: 22, 5: 24}[self.order]

    @memoize_method
    def gmsh_node_tuples(self):
        result = []
        for tup in generate_triangle_vertex_tuples(self.order):
            result.append(tup)
        for tup in generate_triangle_edge_tuples(self.order):
            result.append(tup)
        return result


class GmshTriangularElement(GmshSimplexElementBase):
    dimensions = 2

    @property
    @memoize_method
    def element_type(self):
        from gmsh_interop.node_tuples import triangle_data
        return triangle_data[self.order]["element_type"]

    @memoize_method
    def gmsh_node_tuples(self):
        from gmsh_interop.node_tuples import triangle_data
        return triangle_data[self.order]["node_tuples"]


class GmshTetrahedralElement(GmshSimplexElementBase):
    dimensions = 3

    @property
    @memoize_method
    def element_type(self):
        from gmsh_interop.node_tuples import tetrahedron_data
        return tetrahedron_data[self.order]["element_type"]

    @memoize_method
    def gmsh_node_tuples(self):
        from gmsh_interop.node_tuples import tetrahedron_data
        return tetrahedron_data[self.order]["node_tuples"]

# }}}


# {{{ tensor product elements

class GmshTensorProductElementBase(GmshElementBase):
    def vertex_count(self):
        return 2**self.dimensions

    @memoize_method
    def node_count(self):
        return (self.order+1) ** self.dimensions

    @memoize_method
    def lexicographic_node_tuples(self):
        """Generate tuples enumerating the node indices present
        in this element. Each tuple has a length equal to the dimension
        of the element. The tuples constituents are non-negative integers
        whose sum is less than or equal to the order of the element.
        """
        from pytools import generate_nonnegative_integer_tuples_below as gnitb
        result = list(gnitb(self.order + 1, self.dimensions))

        assert len(result) == self.node_count()
        return result


class GmshQuadrilateralElement(GmshTensorProductElementBase):
    dimensions = 2

    @property
    @memoize_method
    def element_type(self):
        from gmsh_interop.node_tuples import quadrangle_data
        return quadrangle_data[self.order]["element_type"]

    @memoize_method
    def gmsh_node_tuples(self):
        from gmsh_interop.node_tuples import quadrangle_data
        return quadrangle_data[self.order]["node_tuples"]


class GmshHexahedralElement(GmshTensorProductElementBase):
    dimensions = 3

    @property
    @memoize_method
    def element_type(self):
        from gmsh_interop.node_tuples import hexahedron_data
        return hexahedron_data[self.order]["element_type"]

    @memoize_method
    def gmsh_node_tuples(self):
        from gmsh_interop.node_tuples import hexahedron_data
        return hexahedron_data[self.order]["node_tuples"]

# }}}

# }}}


# {{{ receiver interface

def _gmsh_supported_element_type_map():
    supported_elements = (
            [GmshPoint(0)]
            + [GmshIntervalElement(n + 1) for n in range(10)]
            + [GmshIncompleteTriangularElement(n) for n in [3, 4, 5]]
            + [GmshTriangularElement(n + 1) for n in range(10)]
            + [GmshTetrahedralElement(n + 1) for n in range(10)]
            + [GmshQuadrilateralElement(n + 1) for n in range(10)]
            + [GmshHexahedralElement(n + 1) for n in range(9)]
            )

    return {el.element_type: el for el in supported_elements}


class GmshMeshReceiverBase:
    """
    .. attribute:: gmsh_element_type_to_info_map
    .. automethod:: set_up_nodes
    .. automethod:: add_node
    .. automethod:: finalize_nodes
    .. automethod:: set_up_elements
    .. automethod:: add_element
    .. automethod:: finalize_elements
    .. automethod:: add_tag
    .. automethod:: finalize_tags
    """

    gmsh_element_type_to_info_map = _gmsh_supported_element_type_map()

    def set_up_nodes(self, count):
        pass

    def add_node(self, node_nr, point):
        pass

    def finalize_nodes(self):
        pass

    def set_up_elements(self, count):
        pass

    def add_element(self, element_nr, element_type, vertex_nrs,
            lexicographic_nodes, tag_numbers):
        pass

    def finalize_elements(self):
        pass

    def add_tag(self, name, index, dimension):
        pass

    def finalize_tags(self):
        pass

# }}}


# {{{ receiver example

class GmshMeshReceiverNumPy(GmshMeshReceiverBase):
    """GmshReceiver that emulates the semantics of
    :class:`meshpy.triangle.MeshInfo` and :class:`meshpy.tet.MeshInfo` by using
    similar fields, but instead of loading data into ForeignArrays, load into
    NumPy arrays. Since this class is not wrapping any libraries in other
    languages -- the Gmsh data is obtained via parsing text -- use :mod:`numpy`
    arrays as the base array data structure for convenience.

    .. versionadded:: 2014.1
    """

    def __init__(self):
        # Use data fields similar to meshpy.triangle.MeshInfo and
        # meshpy.tet.MeshInfo
        self.points = None
        self.elements = None
        self.element_types = None
        self.element_markers = None
        self.tags = None

    # Gmsh has no explicit concept of facets or faces; certain faces are a type
    # of element.  Consequently, there are no face markers, but elements can be
    # grouped together in physical groups that serve as markers.

    def set_up_nodes(self, count):
        # Preallocate array of nodes within list; treat None as sentinel value.
        # Preallocation not done for performance, but to assign values at indices
        # in random order.
        self.points = [None] * count

    def add_node(self, node_nr, point):
        self.points[node_nr] = point

    def finalize_nodes(self):
        pass

    def set_up_elements(self, count):
        # Preallocation of arrays for assignment elements in random order.
        self.elements = [None] * count
        self.element_types = [None] * count
        self.element_markers = [None] * count
        self.tags = []

    def add_element(self, element_nr, element_type, vertex_nrs,
            lexicographic_nodes, tag_numbers):
        self.elements[element_nr] = vertex_nrs
        self.element_types[element_nr] = element_type
        self.element_markers[element_nr] = tag_numbers
        # TODO: Add lexicographic node information

    def finalize_elements(self):
        pass

    def add_tag(self, name, index, dimension):
        self.tags.append((name, index, dimension))

    def finalize_tags(self):
        pass

# }}}


# {{{ file reader

class GmshFileFormatError(RuntimeError):
    pass


def read_gmsh(receiver, filename, force_dimension=None):
    """Read a gmsh mesh file from *filename* and feed it to *receiver*.

    :param receiver: Implements the :class:`GmshMeshReceiverBase` interface.
    :param force_dimension: if not None, truncate point coordinates to
        this many dimensions.
    """
    mesh_file = open(filename)
    try:
        result = parse_gmsh(receiver, mesh_file, force_dimension=force_dimension)
    finally:
        mesh_file.close()

    return result


def generate_gmsh(receiver, source, dimensions=None, order=None, other_options=(),
            extension="geo", gmsh_executable="gmsh", force_dimension=None,
            output_file_name=None, save_tmp_files_in=None):
    """Run gmsh and feed the output to *receiver*.

    :arg receiver: a class that implements the :class:`GmshMeshReceiverBase`
        interface.
    :arg source: an instance of :class:`ScriptSource` or :class:`FileSource`.
    """
    from gmsh_interop.runner import GmshRunner
    runner = GmshRunner(source, dimensions, order=order,
            other_options=other_options, extension=extension,
            gmsh_executable=gmsh_executable,
            output_file_name=output_file_name,
            save_tmp_files_in=save_tmp_files_in)

    runner.__enter__()
    try:
        result = parse_gmsh(receiver, runner.output_file,
                force_dimension=force_dimension)
    finally:
        runner.__exit__(None, None, None)

    return result


def parse_gmsh(receiver, line_iterable, force_dimension=None):
    """
    :arg receiver: this object will be fed the entities encountered in
        reading the GMSH file. See :class:`GmshMeshReceiverBase` for the
        interface this object needs to conform to.
    :arg line_iterable: an iterable that generates the lines of the GMSH file.
    :arg force_dimension: if not *None*, truncate point coordinates to this
        many dimensions.
    """

    feeder = LineFeeder(line_iterable)

    # collect the mesh information

    class ElementInfo(Record):
        pass

    while feeder.has_next_line():
        next_line = feeder.get_next_line()
        if not next_line.startswith("$"):
            raise GmshFileFormatError(
                    f"expected start of section, '{next_line}' found instead")

        section_name = next_line[1:]

        if section_name == "MeshFormat":
            line_count = 0
            while True:
                next_line = feeder.get_next_line()
                if next_line == "$End"+section_name:
                    break

                if line_count == 0:
                    version_number, file_type, data_size = next_line.split()

                if line_count > 0:
                    raise GmshFileFormatError(
                            "more than one line found in MeshFormat section")

                if not version_number.startswith("2."):
                    # https://github.com/inducer/gmsh_interop/issues/18
                    raise NotImplementedError(
                        f"Unsupported mesh version number '{version_number}' "
                        "found. Convert your mesh to a v2.x mesh using "
                        "'gmsh your_msh.msh -save -format msh2 -o your_msh-v2.msh'")

                if version_number not in ["2.1", "2.2"]:
                    from warnings import warn
                    warn(
                            f"unexpected mesh version number '{version_number}' "
                            "found, continuing")

                if file_type != "0":
                    raise GmshFileFormatError(
                            "only ASCII gmsh file type is supported")

                line_count += 1

        elif section_name == "Nodes":
            node_count = int(feeder.get_next_line())
            receiver.set_up_nodes(node_count)

            node_idx = 1

            while True:
                next_line = feeder.get_next_line()
                if next_line == "$End"+section_name:
                    break

                parts = next_line.split()
                if len(parts) != 4:
                    raise GmshFileFormatError(
                            "expected four-component line in $Nodes section")

                read_node_idx = int(parts[0])
                if read_node_idx != node_idx:
                    raise GmshFileFormatError("out-of-order node index found")

                if force_dimension is not None:
                    point = [float(x) for x in parts[1:force_dimension+1]]
                else:
                    point = [float(x) for x in parts[1:]]

                receiver.add_node(
                        node_idx-1,
                        np.array(point, dtype=np.float64))

                node_idx += 1

            if node_count+1 != node_idx:
                raise GmshFileFormatError("unexpected number of nodes found")

            receiver.finalize_nodes()

        elif section_name == "Elements":
            element_count = int(feeder.get_next_line())
            receiver.set_up_elements(element_count)

            element_idx = 1
            while True:
                next_line = feeder.get_next_line()
                if next_line == "$End"+section_name:
                    break

                parts = [int(x) for x in next_line.split()]

                if len(parts) < 4:
                    raise GmshFileFormatError("too few entries in element line")

                read_element_idx = parts[0]
                if read_element_idx != element_idx:
                    raise GmshFileFormatError("out-of-order node index found")

                el_type_num = parts[1]
                try:
                    element_type = \
                            receiver.gmsh_element_type_to_info_map[el_type_num]
                except KeyError:
                    raise GmshFileFormatError(
                            f"unexpected element type: {el_type_num}")

                tag_count = parts[2]
                tags = parts[3:3+tag_count]

                # convert to zero-based
                node_indices = np.array(
                        [x-1 for x in parts[3+tag_count:]], dtype=np.intp)

                if element_type.node_count() != len(node_indices):
                    raise GmshFileFormatError(
                            "unexpected number of nodes in element")

                gmsh_vertex_nrs = node_indices[:element_type.vertex_count()]
                zero_based_idx = element_idx - 1

                tag_numbers = [tag for tag in tags[:1] if tag != 0]

                receiver.add_element(element_nr=zero_based_idx,
                        element_type=element_type, vertex_nrs=gmsh_vertex_nrs,
                        lexicographic_nodes=node_indices[
                            element_type.get_lexicographic_gmsh_node_indices()],
                        tag_numbers=tag_numbers)

                element_idx += 1

            if element_count+1 != element_idx:
                raise GmshFileFormatError("unexpected number of elements found")

            receiver.finalize_elements()

        elif section_name == "PhysicalNames":
            name_count = int(feeder.get_next_line())
            name_idx = 1

            while True:
                next_line = feeder.get_next_line()
                if next_line == "$End"+section_name:
                    break

                dimension, number, name = next_line.split(" ", 2)
                dimension = int(dimension)
                number = int(number)

                if not name[0] == '"' or not name[-1] == '"':
                    raise GmshFileFormatError("expected quotes around physical name")

                receiver.add_tag(name[1:-1], number, dimension)

                name_idx += 1

            if name_count+1 != name_idx:
                raise GmshFileFormatError(
                        "unexpected number of physical names found")

            receiver.finalize_tags()
        else:
            # unrecognized section, skip
            from warnings import warn
            warn(f"unrecognized section '{section_name}' in gmsh file")
            while True:
                next_line = feeder.get_next_line()
                if next_line == "$End"+section_name:
                    break

# }}}

# vim: fdm=marker
