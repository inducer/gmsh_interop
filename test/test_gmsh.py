__copyright__ = "Copyright (C) 2013 Andreas Kloeckner"

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


# {{{ gmsh

def search_on_path(filenames):
    """Find file on system path."""
    # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52224

    from os.path import exists, abspath, join
    from os import pathsep, environ

    search_path = environ["PATH"]

    paths = search_path.split(pathsep)
    for path in paths:
        for filename in filenames:
            if exists(join(path, filename)):
                return abspath(join(path, filename))


GMSH_SPHERE = """
x = 0; y = 1; z = 2; r = 3; lc = 0.3;

p1 = newp; Point(p1) = {x,  y,  z,  lc} ;
p2 = newp; Point(p2) = {x+r, y,  z,  lc} ;
p3 = newp; Point(p3) = {x,  y+r, z,  lc} ;
p4 = newp; Point(p4) = {x,  y,  z+r, lc} ;
p5 = newp; Point(p5) = {x-r, y,  z,  lc} ;
p6 = newp; Point(p6) = {x,  y-r, z,  lc} ;
p7 = newp; Point(p7) = {x,  y,  z-r, lc} ;

c1 = newreg; Circle(c1) = {p2, p1, p7};
c2 = newreg; Circle(c2) = {p7, p1, p5};
c3 = newreg; Circle(c3) = {p5, p1, p4};
c4 = newreg; Circle(c4) = {p4, p1, p2};
c5 = newreg; Circle(c5) = {p2, p1, p3};
c6 = newreg; Circle(c6) = {p3, p1, p5};
c7 = newreg; Circle(c7) = {p5, p1, p6};
c8 = newreg; Circle(c8) = {p6, p1, p2};
c9 = newreg; Circle(c9) = {p7, p1, p3};
c10 = newreg; Circle(c10) = {p3, p1, p4};
c11 = newreg; Circle(c11) = {p4, p1, p6};
c12 = newreg; Circle(c12) = {p6, p1, p7};

l1 = newreg; Line Loop(l1) = {c5, c10, c4};   Ruled Surface(newreg) = {l1};
l2 = newreg; Line Loop(l2) = {c9, -c5, c1};   Ruled Surface(newreg) = {l2};
l3 = newreg; Line Loop(l3) = {c12, -c8, -c1}; Ruled Surface(newreg) = {l3};
l4 = newreg; Line Loop(l4) = {c8, -c4, c11};  Ruled Surface(newreg) = {l4};
l5 = newreg; Line Loop(l5) = {-c10, c6, c3};  Ruled Surface(newreg) = {l5};
l6 = newreg; Line Loop(l6) = {-c11, -c3, c7}; Ruled Surface(newreg) = {l6};
l7 = newreg; Line Loop(l7) = {-c2, -c7, -c12};Ruled Surface(newreg) = {l7};
l8 = newreg; Line Loop(l8) = {-c6, -c9, c2};  Ruled Surface(newreg) = {l8};
"""


def test_gmsh():
    if search_on_path(["gmsh"]) is None:
        from pytest import skip
        skip("gmsh not found")

    from gmsh_interop.reader import generate_gmsh, GmshMeshReceiverBase
    from gmsh_interop.runner import ScriptSource

    mr = GmshMeshReceiverBase()
    source = ScriptSource(GMSH_SPHERE, "geo")
    generate_gmsh(mr, source, 3)

# }}}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        exec(sys.argv[1])
    else:
        from pytest import main
        main([__file__])

# vim: foldmethod=marker
