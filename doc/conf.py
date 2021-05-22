# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------

project = "gmsh_interop"
copyright = "2020, Andreas Klöckner"
author = "Andreas Klöckner"

ver_dic = {}
exec(compile(
    open("../gmsh_interop/version.py").read(),
    "../gmsh_interop/version.py", "exec"), ver_dic)
version = ".".join(str(x) for x in ver_dic["VERSION"])
release = ver_dic["VERSION_TEXT"]

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
        "sphinx.ext.autodoc",
        "sphinx.ext.intersphinx",
        "sphinx_copybutton",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "furo"

autoclass_content = "class"

intersphinx_mapping = {
        "https://docs.python.org/dev": None,
        "https://numpy.org/doc/stable/": None,
        "https://documen.tician.de/meshpy": None,
        }
