from __future__ import annotations

from importlib import metadata
from urllib.request import urlopen


_conf_url = "https://raw.githubusercontent.com/inducer/sphinxconfig/main/sphinxconfig.py"
with urlopen(_conf_url) as _inf:
    exec(compile(_inf.read(), _conf_url, "exec"), globals())

author = "Andreas Klöckner"
copyright = "2020-24, Andreas Klöckner"
release = metadata.version("gmsh_interop")
version = ".".join(release.split(".")[:2])

intersphinx_mapping = {
    "python": ("https://docs.python.org/dev", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "meshpy": ("https://documen.tician.de/meshpy", None),
}

sphinxconfig_missing_reference_aliases = {
    "GmshSource": "obj:gmsh_interop.runner.GmshSource",
}


def setup(app):
    app.connect("missing-reference", process_autodoc_missing_reference)  # noqa: F821
