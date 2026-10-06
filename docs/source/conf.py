"""Sphinx configuration for the ClimateGraph documentation.
"""

import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

project = "ClimateGraph"
author = "Antonio Andrés Torga Mellado"
copyright = f"2026, {author}"

try:
    release = _package_version("ClimateGraph")
except PackageNotFoundError:
    release = "0.0.0+unknown"


extensions = [
    "sphinx.ext.autodoc",  
    "sphinx.ext.autosummary",  
    "sphinx.ext.napoleon",  
    "sphinx.ext.viewcode",  
    "sphinx.ext.intersphinx",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


autosummary_generate = True

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "ignore-module-all": True,
}

autodoc_typehints = "description"
autodoc_member_order = "bysource"
autodoc_class_signature = "separated"

napoleon_google_docstring = False
napoleon_numpy_docstring = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "xarray": ("https://docs.xarray.dev/en/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
}

html_theme = "furo"
html_static_path = ["_static"]
html_title = f"ClimateGraph {release}"
html_theme_options = {
    "source_repository": "https://github.com/AntonioTorga/ClimateGraph/",
    "source_branch": "main",
    "source_directory": "docs/source/",
}
