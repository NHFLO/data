import os

from nhflodata.get_paths import get_abs_data_path
from nhflodata.get_paths import get_repository_data
from nhflodata.get_paths import is_valid_semver


def test_repository_yaml():
    locations = ["mockup", "local", "nhflo_server", "get_from_env"]

    rep = get_repository_data()
    assert rep is not None, "Unable to load repository.yaml is None"

    for name, dataset in rep.items():
        for version in dataset:
            # iterating over the different versions of the data set
            assert is_valid_semver(
                version["version_nhflo"]
            ), f"Version {version['version_nhflo']} is not a valid semantic version number"

            # Check locations data
            local_parent_folder = "data_parent_folder"
            for location in locations:
                path = get_abs_data_path(
                    name=name,
                    version=version["version_nhflo"],
                    location=location,
                    local_parent_folder=local_parent_folder,
                )
                assert (
                    len(path) > len(local_parent_folder) + 4
                ), f"Path for {name} {version['version_nhflo']} {location} is None"

            # Check mockup data
            path = get_abs_data_path(
                name=name,
                version=version["version_nhflo"],
                location="mockup",
            )
            assert os.path.exists(path), f"Path {path} does not exist"
            assert os.listdir(path), f"Path {path} is empty"
