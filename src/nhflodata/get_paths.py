"""Functions to get paths to data sets."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import yaml
from yaml.loader import SafeLoader


def get_abs_data_path(name="", version="latest", location="get_from_env", local_parent_folder=""):
    """Return the absolute path to the data directory from data/repository.yaml.

    Sets the location of the data set. Can be "mockup", "local", "nhflo_server", or "get_from_env".
    - "get_from_env" is the default. The function will return the look for the value of the
        environment variable NHFLODATA_LOCATION. If not found, it will default to "mockup", if found
        it's value will be used as the `local_parent_folder` of the local data set.
    - "mockup" is a mockup of the data set. Format is correct but data is
        altered. It is packaged with the nhflodata package.
    - "local" is the path to the local data set. Format is correct and data is unaltered,
        but is not shipped with the nhflodata package. Please reach out to
        the data set owner listed in repository.yaml to obtain the data set.
        If local, defining parent folder is required.
    - "nhflo_server" is the data set on the nhflo server. Format is correct
        and the data is unaltered. Used for working on the nhflo.com server.

    Parameters
    ----------
    name : str
        Name of the data set.
    version : str
        Version of the data set. Can be "latest" or a specific version number. Version numbers
        must be a valid semantic version number: 1.0.0, 1.0.1, 1.1.0, etc.
        Corresponds to the verion_nhflo entry in repository.yaml.
    location : str, optional
        Location of the data set. Can be "mockup", "local", "nhflo_server", or "get_from_env".
        - "get_from_env" is the default. The function will return the look for the value of the
            environment variable NHFLODATA_LOCATION for the data path. mockup will be used if the
            variable is not found.
        - "mockup" is a mockup of the data set. Format is correct but data is
            altered. It is packaged with the nhflodata package.
        - "local" is the local data set. Format is correct and data is unaltered,
            but is not shipped with the nhflodata package. Please reach out to
            the data set owner listed in repository.yaml to obtain the data set.
            If local, defining parent folder is required.
        - "nhflo_server" is the data set on the nhflo server. Format is correct
            and the data is unaltered. Used for working on the nhflo server.
    local_parent_folder : str, optional
        Parent folder of the local data set. Required if location is "local".
        Must be left empty if location is "get_from_env".

    Returns
    -------
    str
        Absolute path to the data set.
    """
    if local_parent_folder and location != "local":
        msg = "local_parent_folder must be empty if location is 'get_from_env'"
        raise ValueError(msg)

    if location == "get_from_env":
        local_parent_folder = os.environ.get("NHFLODATA_LOCATION", "")

    if location not in {
        "get_from_env",  # "get_from_env" is the default
        "mockup",
        "local",
        "nhflo_server",
    }:
        msg = "Location must be 'get_from_env', 'mockup', 'local', or 'nhflo_server'"
        raise ValueError(msg)
    if not (is_valid_semver(version) or version == "latest"):
        msg = "Version must be a valid semantic version number or 'latest'"
        raise ValueError(msg)

    rep = get_repository_data()

    if version == "latest":
        version_index = 0

    else:
        versions_ordered = [item["version_nhflo"] for item in rep[name]]
        if version not in versions_ordered:
            msg = "Version not found in repository.yaml"
            raise ValueError(msg)

        version_index = versions_ordered.index(version)

    if location == "mockup" or (location == "get_from_env" and not local_parent_folder):
        rel_path = rep[name][version_index]["paths"]["mockup"]
        abs_path = os.path.join(get_data_dir(), rel_path)

    elif location == "local" or (location == "get_from_env" and local_parent_folder):
        rel_path = rep[name][version_index]["paths"]["local"]
        abs_path = os.path.join(local_parent_folder, rel_path)

    elif location == "nhflo_server":
        abs_path = rep[name][version_index]["paths"]["nhflo_server"]

    logging.info("Data path prompted is: %s", abs_path)

    if not os.path.exists(abs_path):
        logging.warning("Path does not exist: %s", abs_path)

    return abs_path


def get_data_dir():
    """Return the path to the data directory."""
    return os.path.join(os.path.dirname(__file__), "data")


def get_latest_data_paths() -> list[Path]:
    """
    Get paths to all latest data versions in the repository.

    Returns
    -------
    List[Path]
        List of Path objects representing all found directories

    Examples
    --------
    >>> folders = get_latest_data_paths()
    >>> print(folders[0])
    ./data/subfolder1/v1.2.3
    """
    dataset_names = sorted(get_repository_data().keys())
    dataset_paths = [get_abs_data_path(name, version="latest", location="mockup") for name in dataset_names]
    return [Path(path) for path in dataset_paths]


def get_repository_path():
    """Return the path to the repository.yaml file from data/repository.yaml."""
    # from importlib.resources import files
    # data_text = files('nhflodata.data').joinpath('repository.yaml')
    data_dir = get_data_dir()
    return os.path.join(data_dir, "repository.yaml")


def get_repository_data():
    """Return the data from the repository.yaml file."""
    with open(get_repository_path(), encoding="utf-8") as file:
        return yaml.load(file, Loader=SafeLoader)["data"]


def is_valid_semver(version):
    """Return True if the version is a valid semantic version number."""
    pattern = re.compile(r"^\d+\.\d+\.\d+$")
    return pattern.match(version) is not None


def bump_semver(version, level):
    """Bump the semver."""
    vstart = "v" if version[0] == "v" else ""
    major, minor, patch = map(int, version.split("."))

    if level == "major":
        return f"{vstart}{major + 1}.{minor}.{patch}"
    if level == "minor":
        return f"{vstart}{major}.{minor + 1}.{patch}"
    if level == "patch":
        return f"{vstart}{major}.{minor}.{patch + 1}"
    msg = "unsupported value for 'level'"
    raise ValueError(msg)
