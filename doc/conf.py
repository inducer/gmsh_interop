from urllib.request import urlopen

_conf_url = \
        "https://raw.githubusercontent.com/inducer/sphinxconfig/main/sphinxconfig.py"
with urlopen(_conf_url) as _inf:
    exec(compile(_inf.read(), _conf_url, "exec"), globals())

copyright = "2020-21, Andreas Klöckner"
author = "Andreas Klöckner"

ver_dic = {}
exec(compile(
    open("../gmsh_interop/version.py").read(),
    "../gmsh_interop/version.py", "exec"), ver_dic)
version = ".".join(str(x) for x in ver_dic["VERSION"])
release = ver_dic["VERSION_TEXT"]

intersphinx_mapping = {
        "python": ("https://docs.python.org/dev", None),
        "numpy":("https://numpy.org/doc/stable/", None),
        "meshpy": ("https://documen.tician.de/meshpy", None),
        }
