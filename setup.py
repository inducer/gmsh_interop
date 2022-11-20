#! /usr/bin/env python

from setuptools import setup, find_packages

ver_dic = {}
version_file_name = "gmsh_interop/version.py"
with open(version_file_name) as version_file:
    version_file_contents = version_file.read()

exec(compile(version_file_contents, version_file_name, "exec"), ver_dic)

setup(name="gmsh_interop",
      version=ver_dic["VERSION_TEXT"],
      description="A parser for GMSH's .msh format",
      long_description=open("README.rst").read(),
      classifiers=[
          "Development Status :: 4 - Beta",
          "Intended Audience :: Developers",
          "Intended Audience :: Other Audience",
          "Intended Audience :: Science/Research",
          "License :: OSI Approved :: MIT License",
          "Natural Language :: English",
          "Programming Language :: Python",
          "Programming Language :: Python",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.3",
          "Programming Language :: Python :: 3.4",
          "Topic :: Scientific/Engineering",
          "Topic :: Scientific/Engineering :: Information Analysis",
          "Topic :: Scientific/Engineering :: Mathematics",
          "Topic :: Scientific/Engineering :: Visualization",
          "Topic :: Software Development :: Libraries",
          "Topic :: Utilities",
          ],

      python_requires="~=3.8",
      install_requires=[
          "numpy>=1.6.0",
          "pytools",
          "packaging>=20.0",
          ],

      author="Andreas Kloeckner",
      url="http://github.com/inducer/gmsh_interop",
      author_email="inform@tiker.net",
      license="MIT",
      packages=find_packages())
