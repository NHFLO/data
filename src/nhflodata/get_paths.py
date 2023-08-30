import os

import yaml


def get_abs_data_path(
    name="", version="latest", location="get_from_env", local_parent_folder=""
):
    """Returns the absolute path to the data directory from data/repository.yaml


    Parameters
    ----------
    name : str
        Name of the data set.
    version : str
        Version of the data set. Can be "latest" or a specific version number.
        Corresponds to the verion_nhflo entry in repository.yaml.
    location : str, optional
        Location of the data set. Can be "mockup", "local", "nhflo_server", or "get_from_env".
        - "get_from_env" is the default. The function will return the look for the value of the
            environment variable NHFLODATA_LOCATION.
        - "mockup" is a mockup of the data set. Format is correct but data is
            altered. It is packaged with the nhflodata package.
        - "local" is the local data set. Format is correct and data is unaltered,
            but is not shipped with the nhflodata package. Please reach out to
            the data set owner listed in repository.yaml to obtain the data set.
            If local, defining parent folder is required.
        - "nhflo_server" is the data set on the nhflo server. Format is correct
            and the data is unaltered. Used for working on the nhflo server.
    """
    if location == "get_from_env":
        if "NHFLODATA_LOCATION" not in os.environ:
            print(
                "NHFLODATA_LOCATION environment variable not found. Setting to 'mockup'"
            )

        location = os.environ.get("NHFLODATA_LOCATION", "mockup")

    assert location in [
        "mockup",
        "local",
        "nhflo_server",
    ], "Location must be 'mockup', 'local', or 'nhflo_server'"
    assert (
        is_valid_semver(version) or version == "latest"
    ), "Version must be a valid semantic version number or 'latest'"

    rep = get_repository_data()

    if version == "latest":
        version_index = 0

    else:
        versions_ordered = [item["version_nhflo"] for item in rep[name]]
        assert version in versions_ordered, "Version not found in repository.yaml"

        version_index = versions_ordered.index(version)

    if location == "mockup":
        rel_path = rep[name][version_index]["paths"][location]
        abs_path = os.path.join(get_data_dir(), rel_path)

    elif location == "local":
        assert local_parent_folder != "", "Local parent folder must be defined"
        rel_path = rep[name][version_index]["paths"][location]
        abs_path = os.path.join(local_parent_folder, rel_path)

    elif location == "nhflo_server":
        abs_path = rep[name][version_index]["paths"][location]

    return abs_path


def get_data_dir():
    """Returns the path to the data directory"""
    return os.path.join(os.path.dirname(__file__), "data")


def get_repository_path():
    """Returns the path to the repository.yaml file from data/repository.yaml"""
    # from importlib.resources import files
    # data_text = files('nhflodata.data').joinpath('repository.yaml')
    data_dir = get_data_dir()
    return os.path.join(data_dir, "repository.yaml")


def get_repository_data():
    """Returns the data from the repository.yaml file"""
    with open(get_repository_path(), "r") as file:
        data = yaml.load(file, Loader=yaml.FullLoader)["data"]
    return data


def is_valid_semver(version):
    """Returns True if the version is a valid semantic version number"""
    import re

    pattern = re.compile(r"^\d+\.\d+\.\d+$")
    return pattern.match(version) is not None
