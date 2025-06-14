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

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, MutableSequence, Sequence
from typing import ClassVar, Literal, cast

import numpy as np
from typing_extensions import override

from pytools import memoize_method

from gmsh_interop.runner import (  # noqa: F401
    FileSource,
    LiteralSource,  # pyright: ignore[reportUnusedImport]
    ScriptSource,
    ScriptWithFilesSource,
)


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

def generate_triangle_vertex_tuples(order: int) -> Iterator[tuple[int, int]]:
    yield (0, 0)
    yield (order, 0)
    yield (0, order)


def generate_triangle_edge_tuples(order: int) -> Iterator[tuple[int, int]]:
    for i in range(1, order):
        yield (i, 0)
    for i in range(1, order):
        yield (order-i, i)
    for i in range(1, order):
        yield (0, order-i)


def generate_triangle_volume_tuples(order: int) -> Iterator[tuple[int, int]]:
    for i in range(1, order):
        for j in range(1, order-i):
            yield (j, i)


def generate_quad_vertex_tuples(dim: int, order: int) -> Iterator[tuple[int, ...]]:
    from pytools import generate_nonnegative_integer_tuples_below

    for tup in generate_nonnegative_integer_tuples_below(2, dim):
        yield tuple(order * i for i in tup)


class LineFeeder:
    def __init__(self, line_iterable: Iterable[str]) -> None:
        self.line_iterable: Iterator[str] = iter(line_iterable)
        self.next_line: str | None = None

    def has_next_line(self) -> bool:
        if self.next_line is not None:
            return True

        try:
            self.next_line = next(self.line_iterable)
        except StopIteration:
            return False
        else:
            return True

    def get_next_line(self) -> str:
        if self.next_line is not None:
            nl = self.next_line
            self.next_line = None
            return nl.strip()

        try:
            nl = next(self.line_iterable)
        except StopIteration:
            raise GmshFileFormatError("Unexpected end of file") from None
        else:
            return nl.strip()

# }}}


# {{{ element info

IndexArray = np.typing.NDArray[np.integer]
NodeTuples = Sequence[tuple[int, ...]]


class GmshElementBase(ABC):
    """
    .. automethod:: vertex_count
    .. automethod:: node_count
    .. automethod:: lexicographic_node_tuples

        Generate tuples enumerating the node indices present
        in this element. Each tuple has a length equal to the dimension
        of the element. The tuples constituents are non-negative integers
        whose sum is less than or equal to the order of the element.

    .. automethod:: get_lexicographic_gmsh_node_indices
    """

    order: int

    def __init__(self, order: int) -> None:
        self.order = order

    @property
    @abstractmethod
    def dimensions(self) -> int:
        pass

    @property
    @abstractmethod
    def element_type(self) -> int:
        pass

    @abstractmethod
    def vertex_count(self) -> int:
        pass

    @abstractmethod
    def node_count(self) -> int:
        pass

    @abstractmethod
    def gmsh_node_tuples(self) -> NodeTuples:
        pass

    @abstractmethod
    def lexicographic_node_tuples(self) -> NodeTuples:
        pass

    @memoize_method
    def get_lexicographic_gmsh_node_indices(self) -> IndexArray:
        gmsh_tup_to_index = {
            tup: i for i, tup in enumerate(self.gmsh_node_tuples())
        }

        return np.array([
            gmsh_tup_to_index[tup] for tup in self.lexicographic_node_tuples()],
            dtype=np.intp)


# {{{ simplices

class GmshSimplexElementBase(GmshElementBase, ABC):
    @override
    def vertex_count(self) -> int:
        return self.dimensions + 1

    @memoize_method
    def node_count(self) -> int:
        """Return the number of interpolation nodes in this element."""
        import math
        from functools import reduce
        from operator import mul
        return (
                reduce(mul, (self.order + 1 + i for i in range(self.dimensions)), 1)
                // math.factorial(self.dimensions))

    @memoize_method
    def lexicographic_node_tuples(self) -> NodeTuples:
        from pytools import (
            generate_nonnegative_integer_tuples_summing_to_at_most as gnitstam,
        )
        result = list(gnitstam(self.order, self.dimensions))

        assert len(result) == self.node_count()
        return result


class GmshPoint(GmshSimplexElementBase):
    @property
    @override
    def dimensions(self) -> int:
        return 0

    @property
    @override
    def element_type(self) -> int:
        return 15

    @memoize_method
    def gmsh_node_tuples(self) -> NodeTuples:
        return [()]


class GmshIntervalElement(GmshSimplexElementBase):
    @property
    @override
    def dimensions(self) -> int:
        return 1

    @property
    @memoize_method
    def element_type(self) -> int:
        return [1, 8, 26, 27, 28, 62, 63, 64, 65, 66][self.order - 1]

    @memoize_method
    def gmsh_node_tuples(self) -> NodeTuples:
        return [(0,), (self.order,), ] + [(i,) for i in range(1, self.order)]


class GmshIncompleteTriangularElement(GmshSimplexElementBase):
    @property
    @override
    def dimensions(self) -> int:
        return 2

    @property
    @memoize_method
    def element_type(self) -> int:
        return {3: 20, 4: 22, 5: 24}[self.order]

    @memoize_method
    def gmsh_node_tuples(self) -> NodeTuples:
        result: list[tuple[int, ...]] = []
        for tup in generate_triangle_vertex_tuples(self.order):
            result.append(tup)
        for tup in generate_triangle_edge_tuples(self.order):
            result.append(tup)
        return result


class GmshTriangularElement(GmshSimplexElementBase):
    @property
    @override
    def dimensions(self) -> int:
        return 2

    @property
    @memoize_method
    def element_type(self) -> int:
        from gmsh_interop.node_tuples import triangle_data
        return triangle_data[self.order]["element_type"]

    @memoize_method
    def gmsh_node_tuples(self) -> NodeTuples:
        from gmsh_interop.node_tuples import triangle_data
        return triangle_data[self.order]["node_tuples"]


class GmshTetrahedralElement(GmshSimplexElementBase):
    @property
    @override
    def dimensions(self) -> int:
        return 3

    @property
    @memoize_method
    def element_type(self) -> int:
        from gmsh_interop.node_tuples import tetrahedron_data
        return tetrahedron_data[self.order]["element_type"]

    @memoize_method
    def gmsh_node_tuples(self) -> NodeTuples:
        from gmsh_interop.node_tuples import tetrahedron_data
        return tetrahedron_data[self.order]["node_tuples"]

# }}}


# {{{ tensor product elements

class GmshTensorProductElementBase(GmshElementBase, ABC):
    @override
    def vertex_count(self) -> int:
        return int(2**self.dimensions)

    @memoize_method
    def node_count(self) -> int:
        return int((self.order+1) ** self.dimensions)

    @memoize_method
    def lexicographic_node_tuples(self) -> NodeTuples:
        """Generate tuples enumerating the node indices present in this element.

        Each tuple has a length equal to the dimension of the element. The
        tuples constituents are non-negative integers whose sum is less than or
        equal to the order of the element.
        """
        from pytools import generate_nonnegative_integer_tuples_below as gnitb

        # gnitb(2, 2) gives [(0, 0), (0, 1), (1, 0), (1, 1)]
        # We want the x-coordinate to increase first, so reverse.
        # (This is also consistent with gnitstam.)
        result = [tup[::-1] for tup in gnitb(self.order + 1, self.dimensions)]

        assert len(result) == self.node_count()
        return result


class GmshQuadrilateralElement(GmshTensorProductElementBase):
    @property
    @override
    def dimensions(self) -> int:
        return 2

    @property
    @memoize_method
    def element_type(self) -> int:
        from gmsh_interop.node_tuples import quadrangle_data
        return quadrangle_data[self.order]["element_type"]

    @memoize_method
    def gmsh_node_tuples(self) -> NodeTuples:
        from gmsh_interop.node_tuples import quadrangle_data
        return quadrangle_data[self.order]["node_tuples"]


class GmshHexahedralElement(GmshTensorProductElementBase):
    @property
    @override
    def dimensions(self) -> int:
        return 3

    @property
    @memoize_method
    def element_type(self) -> int:
        from gmsh_interop.node_tuples import hexahedron_data
        return hexahedron_data[self.order]["element_type"]

    @memoize_method
    def gmsh_node_tuples(self) -> NodeTuples:
        from gmsh_interop.node_tuples import hexahedron_data
        return hexahedron_data[self.order]["node_tuples"]

# }}}

# }}}


# {{{ receiver interface

Point = np.typing.NDArray[np.floating]
Nodes = np.typing.NDArray[np.floating]


def _gmsh_supported_element_type_map() -> dict[int, GmshElementBase]:
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


class GmshMeshReceiverBase(ABC):
    """
    .. autoattribute:: gmsh_element_type_to_info_map

    .. automethod:: set_up_nodes
    .. automethod:: add_node
    .. automethod:: finalize_nodes
    .. automethod:: set_up_elements
    .. automethod:: add_element
    .. automethod:: finalize_elements
    .. automethod:: add_tag
    .. automethod:: finalize_tags
    """

    gmsh_element_type_to_info_map: ClassVar[dict[int, GmshElementBase]] = (
        _gmsh_supported_element_type_map())

    @abstractmethod
    def set_up_nodes(self, count: int) -> None:
        pass

    @abstractmethod
    def add_node(self, node_nr: int, point: Point) -> None:
        pass

    @abstractmethod
    def finalize_nodes(self) -> None:
        pass

    @abstractmethod
    def set_up_elements(self, count: int) -> None:
        pass

    @abstractmethod
    def add_element(self,
                    element_nr: int,
                    element_type: GmshElementBase,
                    vertex_nrs: IndexArray,
                    lexicographic_nodes: IndexArray,
                    tag_numbers: Sequence[int]) -> None:
        pass

    @abstractmethod
    def finalize_elements(self) -> None:
        pass

    @abstractmethod
    def add_tag(self, name: str, index: int, dimension: int) -> None:
        pass

    @abstractmethod
    def finalize_tags(self) -> None:
        pass

# }}}


# {{{ receiver example

class GmshMeshReceiverNumPy(GmshMeshReceiverBase):
    r"""GmshReceiver that loads fields into :mod:`numpy` arrays.

    This class emulates the semantics of :class:`meshpy.triangle.MeshInfo` and
    :class:`meshpy.tet.MeshInfo` by using similar field names. However, instead
    of loading data into ``ForeignArray``\ s, it loads it into :mod:`numpy` arrays.

    This class is not wrapping any libraries -- the Gmsh data is obtained
    via parsing text.

    .. versionadded:: 2014.1
    """

    def __init__(self) -> None:
        # Use data fields similar to meshpy.triangle.MeshInfo and meshpy.tet.MeshInfo
        self.points: MutableSequence[Point | None] | None = None
        self.elements: MutableSequence[IndexArray | None] | None = None
        self.element_types: MutableSequence[GmshElementBase | None] | None = None
        self.element_markers: MutableSequence[Sequence[int] | None] | None = None
        self.tags: MutableSequence[tuple[str, int, int]] | None = None

    # Gmsh has no explicit concept of facets or faces; certain faces are a type
    # of element.  Consequently, there are no face markers, but elements can be
    # grouped together in physical groups that serve as markers.

    @override
    def set_up_nodes(self, count: int) -> None:
        # Preallocate array of nodes within list; treat None as sentinel value.
        # Preallocation not done for performance, but to assign values at indices
        # in random order.
        self.points = cast(MutableSequence[Point | None], [None] * count)

    @override
    def add_node(self, node_nr: int, point: Point) -> None:
        assert self.points is not None
        self.points[node_nr] = point

    @override
    def finalize_nodes(self) -> None:
        pass

    @override
    def set_up_elements(self, count: int) -> None:
        # Preallocation of arrays for assignment elements in random order.
        self.elements = cast(MutableSequence[IndexArray | None], [None] * count)
        self.element_types = (
            cast(MutableSequence[GmshElementBase | None], [None] * count))
        self.element_markers = (
            cast(MutableSequence[Sequence[int] | None], [None] * count))
        self.tags = []

    @override
    def add_element(self,
                    element_nr: int,
                    element_type: GmshElementBase,
                    vertex_nrs: IndexArray,
                    lexicographic_nodes: IndexArray,
                    tag_numbers: Sequence[int]) -> None:
        assert self.elements is not None
        self.elements[element_nr] = vertex_nrs
        assert self.element_types is not None
        self.element_types[element_nr] = element_type
        assert self.element_markers is not None
        self.element_markers[element_nr] = tag_numbers
        # TODO: Add lexicographic node information

    @override
    def finalize_elements(self) -> None:
        pass

    @override
    def add_tag(self, name: str, index: int, dimension: int) -> None:
        assert self.tags is not None
        self.tags.append((name, index, dimension))

    @override
    def finalize_tags(self) -> None:
        pass

# }}}


# {{{ file reader

class GmshFileFormatError(RuntimeError):
    pass


def read_gmsh(
        receiver: GmshMeshReceiverBase,
        filename: str,
        force_dimension: int | None = None) -> None:
    """Read a gmsh mesh file from *filename* and feed it to *receiver*.

    :param receiver: Implements the :class:`GmshMeshReceiverBase` interface.
    :param force_dimension: if not None, truncate point coordinates to
        this many dimensions.
    """
    with open(filename) as mesh_file:
        parse_gmsh(receiver, mesh_file, force_dimension=force_dimension)


def generate_gmsh(
        receiver: GmshMeshReceiverBase,
        source: str | ScriptSource | FileSource | ScriptWithFilesSource,
        dimensions: int | None = None,
        order: int | None = None,
        other_options: tuple[str, ...] = (),
        extension: str = "geo",
        gmsh_executable: str = "gmsh",
        force_dimension: int | None = None,
        target_unit: Literal["M", "MM"] | None = None,
        output_file_name: str | None = None,
        save_tmp_files_in: str | None = None) -> None:
    """Run gmsh and feed the output to *receiver*.

    :arg receiver: a class that implements the :class:`GmshMeshReceiverBase`
        interface.
    :arg source: an instance of :class:`ScriptSource` or :class:`FileSource`.
    """
    from gmsh_interop.runner import GmshRunner

    runner = GmshRunner(source, dimensions, order=order,
            other_options=other_options, extension=extension,
            gmsh_executable=gmsh_executable,
            target_unit=target_unit,
            output_file_name=output_file_name,
            save_tmp_files_in=save_tmp_files_in)

    with runner:
        output_file = runner.output_file
        assert output_file is not None

        parse_gmsh(
            receiver,
            output_file,
            force_dimension=force_dimension)


def parse_gmsh(receiver: GmshMeshReceiverBase,
               line_iterable: Iterable[str],
               force_dimension: int | None = None) -> None:
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

    while feeder.has_next_line():
        next_line = feeder.get_next_line()
        if not next_line.startswith("$"):
            raise GmshFileFormatError(
                f"Expected start of section: found '{next_line}'")

        section_name = next_line[1:]

        if section_name == "MeshFormat":
            line_count = 0
            while True:
                next_line = feeder.get_next_line()
                if next_line == f"$End{section_name}":
                    break

                if line_count > 0:
                    raise GmshFileFormatError(
                            "More than one line found in 'MeshFormat' section")

                version_number, file_type, _data_size = next_line.split()

                if not version_number.startswith("2."):
                    # https://github.com/inducer/gmsh_interop/issues/18
                    raise NotImplementedError(
                        f"Unsupported mesh version number '{version_number}' "
                        "found. Convert your mesh to a v2.x mesh using "
                        "'gmsh your_msh.msh -save -format msh2 -o your_msh-v2.msh'")

                if version_number not in ["2.1", "2.2"]:
                    from warnings import warn
                    warn(f"Unexpected mesh version number '{version_number}' "
                         "found. Continuing anyway!", stacklevel=2)

                if file_type != "0":
                    raise GmshFileFormatError(
                        f"Only ASCII Gmsh file type is supported: '{file_type}'")

                line_count += 1

        elif section_name == "Nodes":
            node_count = int(feeder.get_next_line())
            receiver.set_up_nodes(node_count)

            node_idx = 1

            while True:
                next_line = feeder.get_next_line()
                if next_line == f"$End{section_name}":
                    break

                node_parts = next_line.split()
                if len(node_parts) != 4:
                    raise GmshFileFormatError(
                        "Expected four-component line in $Nodes section: "
                        f"got {node_parts} nodes")

                read_node_idx = int(node_parts[0])
                if read_node_idx != node_idx:
                    raise GmshFileFormatError(
                        f"Out-of-order node index found: got node {read_node_idx} "
                        f"but expected node {node_idx}")

                if force_dimension is not None:
                    point = [float(x) for x in node_parts[1:force_dimension+1]]
                else:
                    point = [float(x) for x in node_parts[1:]]

                receiver.add_node(
                        node_idx-1,
                        np.array(point, dtype=np.float64))

                node_idx += 1

            if node_count+1 != node_idx:
                raise GmshFileFormatError(
                    f"Unexpected number of nodes found: got {node_idx} nodes "
                    f"but expected {node_count + 1} nodes")

            receiver.finalize_nodes()

        elif section_name == "Elements":
            element_count = int(feeder.get_next_line())
            receiver.set_up_elements(element_count)

            element_idx = 1
            while True:
                next_line = feeder.get_next_line()
                if next_line == f"$End{section_name}":
                    break

                elem_parts = [int(x) for x in next_line.split()]

                if len(elem_parts) < 4:
                    raise GmshFileFormatError(
                        f"Too few entries in element line: got {elem_parts} "
                        "but expected a list of at least 4 entries")

                read_element_idx = elem_parts[0]
                if read_element_idx != element_idx:
                    raise GmshFileFormatError(
                        "Out-of-order element index found: got element "
                        f"{read_element_idx} but expected element {element_idx}")

                el_type_num = elem_parts[1]
                try:
                    element_type = receiver.gmsh_element_type_to_info_map[el_type_num]
                except KeyError:
                    raise GmshFileFormatError(
                            f"Unexpected element type: {el_type_num}"
                            ) from None

                tag_count = elem_parts[2]
                tags = elem_parts[3:3+tag_count]

                # convert to zero-based
                node_indices = np.array(elem_parts[3+tag_count:], dtype=np.intp) - 1

                if element_type.node_count() != len(node_indices):
                    raise GmshFileFormatError(
                        "Unexpected number of nodes in element: got "
                        f"{len(node_indices)} nodes but expected "
                        f"{element_type.node_count()} nodes")

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
                raise GmshFileFormatError(
                    f"Unexpected number of elements found: got {element_idx} "
                    f"elements but expected {element_count + 1}")

            receiver.finalize_elements()

        elif section_name == "PhysicalNames":
            name_count = int(feeder.get_next_line())
            name_idx = 1

            while True:
                next_line = feeder.get_next_line()
                if next_line == f"$End{section_name}":
                    break

                dimension_, number_, name = next_line.split(" ", 2)
                dimension = int(dimension_)
                number = int(number_)

                if not name[0] == '"' or not name[-1] == '"':
                    raise GmshFileFormatError(
                        f"Expected quotes around physical name: <{name}>")

                receiver.add_tag(name[1:-1], number, dimension)

                name_idx += 1

            if name_count+1 != name_idx:
                raise GmshFileFormatError(
                    f"Unexpected number of physical names found: got {name_idx} "
                    f"names but expected {name_count + 1} names")

            receiver.finalize_tags()
        else:
            # unrecognized section, skip
            from warnings import warn
            warn(f"Unrecognized section '{section_name}' in Gmsh file",
                 stacklevel=2)

            while True:
                next_line = feeder.get_next_line()
                if next_line == f"$End{section_name}":
                    break

# }}}

# vim: fdm=marker
