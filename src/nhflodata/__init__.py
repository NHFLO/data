"""Utilities for working with NHFLO data."""

# ruff: noqa: F401
from importlib.metadata import version

from nhflodata.get_paths import create_new_dataset, get_abs_data_path

__version__ = version("nhflodata")
