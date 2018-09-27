from __future__ import division, absolute_import

__copyright__ = """
Copyright (C) 2017 Andreas Kloeckner
Copyright (C) 2018 Alexandru Fikl
"""

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

from pytools import memoize_method

import logging
logger = logging.getLogger(__name__)


__doc__ = """

.. exception:: GmshError
.. autoclass:: ScriptSource
.. autoclass:: FileSource
.. autoclass:: ScriptWithFilesSource

.. autoclass:: GmshRunner
"""


class GmshError(RuntimeError):
    pass


# {{{ tools

def _erase_dir(dir):
    from os import listdir, unlink, rmdir
    from os.path import join
    for name in listdir(dir):
        unlink(join(dir, name))
    rmdir(dir)


class _TempDirManager(object):
    def __init__(self):
        from tempfile import mkdtemp
        self.path = mkdtemp()

    def sub(self, n):
        from os.path import join
        return join(self.path, n)

    def clean_up(self):
        _erase_dir(self.path)

    def error_clean_up(self):
        _erase_dir(self.path)


class ScriptSource(object):
    """
    .. versionadded:: 2016.1
    """
    def __init__(self, source, extension):
        self.source = source
        self.extension = extension


class LiteralSource(ScriptSource):
    """
    .. versionadded:: 2014.1
    """
    def __init__(self, source, extension):
        super(LiteralSource, self).__init__(source, extension)

        from warnings import warn
        warn("LiteralSource is deprecated, use ScriptSource instead",
                DeprecationWarning, stacklevel=2)


class FileSource(object):
    """
    .. versionadded:: 2014.1
    """
    def __init__(self, filename):
        self.filename = filename


class ScriptWithFilesSource(object):
    """
    .. versionadded:: 2016.1

    .. attribute:: source

        The script code to be fed to gmsh.

    .. attribute:: filenames

        The names of files to be copied to the temporary directory where
        gmsh is run.
    """
    def __init__(self, source, filenames, source_name="temp.geo"):
        self.source = source
        self.source_name = source_name
        self.filenames = filenames


class GmshRunner(object):
    def __init__(self, source, dimensions=None, order=None,
            incomplete_elements=None, other_options=[],
            extension="geo", gmsh_executable="gmsh",
            output_file_name="output.msh",
            target_unit=None):
        if isinstance(source, str):
            from warnings import warn
            warn("passing a string as 'source' is deprecated--use "
                    "one of the *Source classes",
                    DeprecationWarning)

            source = ScriptSource(source, extension)

        if target_unit is None:
            target_unit = "MM"
            from warnings import warn
            warn("Not specifying target_unit is deprecated. Set target_unit='MM' "
                "to retain prior behavior.", DeprecationWarning, stacklevel=2)

        self.source = source
        self.dimensions = dimensions
        self.order = order
        self.incomplete_elements = incomplete_elements
        self.other_options = other_options
        self.gmsh_executable = gmsh_executable
        self.output_file_name = output_file_name
        self.target_unit = target_unit.upper()

        if self.dimensions not in [1, 2, 3, None]:
            raise RuntimeError("dimensions must be one of 1,2,3 or None")

        if self.target_unit not in ['M', 'MM']:
            raise RuntimeError("units must be 'M' (meters) or 'MM' (millimeters)")

    @property
    @memoize_method
    def version(self):
        from distutils.version import LooseVersion
        cmdline = [
                self.gmsh_executable,
                '-version'
                ]

        from pytools.prefork import call_capture_output
        retcode, stdout, stderr = call_capture_output(cmdline)

        version = stderr.decode().strip()
        return LooseVersion(version)

    def __enter__(self):
        self.temp_dir_mgr = None
        temp_dir_mgr = _TempDirManager()
        try:
            working_dir = temp_dir_mgr.path
            from os.path import join, abspath, exists

            if isinstance(self.source, ScriptSource):
                source_file_name = join(
                        working_dir, "temp."+self.source.extension)
                with open(source_file_name, "w") as source_file:
                    source_file.write(self.source.source)

            elif isinstance(self.source, FileSource):
                source_file_name = abspath(self.source.filename)
                if not exists(source_file_name):
                    raise IOError("'%s' does not exist" % source_file_name)

            elif isinstance(self.source, ScriptWithFilesSource):
                source_file_name = join(
                        working_dir, self.source.source_name)
                with open(source_file_name, "w") as source_file:
                    source_file.write(self.source.source)

                from os.path import basename
                from shutil import copyfile
                for f in self.source.filenames:
                    copyfile(f, join(working_dir, basename(f)))

            else:
                raise RuntimeError("'source' type unrecognized")

            output_file_name = join(working_dir, self.output_file_name)
            cmdline = [
                    self.gmsh_executable,
                    "-o", self.output_file_name,
                    "-nopopup",
                    "-format", "msh2"]

            # NOTE: handle unit incompatibility introduced in GMSH4
            # https://gitlab.onelab.info/gmsh/gmsh/issues/397
            if self.version < '4.0.0':
                if self.target_unit == 'M':
                    cmdline.extend(["-string", "Geometry.OCCScaling=1000;"])
            else:
                cmdline.extend(["-string",
                    "Geometry.OCCTargetUnit='{}';".format(self.target_unit)])

            if self.dimensions is not None:
                cmdline.append("-%d" % self.dimensions)

            if self.order is not None:
                cmdline.extend(["-order", str(self.order)])

            if self.incomplete_elements is not None:
                cmdline.extend(["-string",
                    "Mesh.SecondOrderIncomplete = %d;"
                    % int(self.incomplete_elements)])

            cmdline.extend(self.other_options)
            cmdline.append(source_file_name)

            if self.dimensions is None:
                cmdline.append("-")

            logger.info("invoking gmsh: '%s'" % " ".join(cmdline))
            from pytools.prefork import call_capture_output
            retcode, stdout, stderr = call_capture_output(
                    cmdline, working_dir)
            logger.info("return from gmsh")

            stdout = stdout.decode("utf-8")
            stderr = stderr.decode("utf-8")

            import re
            error_match = re.match(r"([0-9]+)\s+error", stdout)
            warning_match = re.match(r"([0-9]+)\s+warning", stdout)

            if error_match is not None or warning_match is not None:
                # if we have one, we expect to see both
                assert error_match is not None or warning_match is not None

                num_warnings = int(warning_match.group(1))
                num_errors = int(error_match.group(1))
            else:
                num_warnings = 0
                num_errors = 0

            if num_errors:
                msg = "gmsh execution failed with message:\n\n"
                if stdout:
                    msg += stdout+"\n"
                msg += stderr+"\n"
                raise GmshError(msg)

            if num_warnings:
                from warnings import warn

                msg = "gmsh issued the following warning messages:\n\n"
                if stdout:
                    msg += stdout+"\n"
                msg += stderr+"\n"
                warn(msg)

            self.output_file = open(output_file_name, "r")

            self.temp_dir_mgr = temp_dir_mgr
            return self
        except Exception:
            temp_dir_mgr.clean_up()
            raise

    def __exit__(self, type, value, traceback):
        self.output_file.close()
        if self.temp_dir_mgr is not None:
            self.temp_dir_mgr.clean_up()
