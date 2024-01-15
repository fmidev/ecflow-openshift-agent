from setuptools import setup, find_packages
import os


def get_requirements(filename="requirements.txt"):
    """Extract requirements from a pip formatted requirements file."""

    with open(filename, "r") as requirements_file:
        return requirements_file.read().splitlines()


def get_version(rel_path):
    """Returns the semantic version for the openshift-client module."""
    for line in read(rel_path).splitlines():
        if line.startswith("__VERSION__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


def read(rel_path):
    """Returns the contents of the file at the specified relative path."""
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, rel_path), "r") as fp:
        return fp.read()


DESCRIPTION = "My first Python package"
LONG_DESCRIPTION = "My first Python package with a slightly longer description"

# Setting up
setup(
    # the name must match the folder name 'verysimplemodule'
    name="ecflow-openshift-agent",
    version=get_version("packages/ecflow_openshift_agent/__init__.py"),
    author="Mikko Partio",
    author_email="<mikko.partio@fmi.fi>",
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    packages=find_packages(where="packages"),
    package_dir={"": "packages"},
    install_requires=get_requirements(),
    keywords=["ecflow", "openshift"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Education",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
    ],
)
