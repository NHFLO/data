"""Test that the folder structure in the mockup folder matches the repository.yaml."""

import os
from pathlib import Path

import pytest

from nhflodata.get_paths import (
    get_abs_data_path,
    get_data_dir,
    get_repository_data,
)


def test_mockup_folder_structure():
    """Test that all folders in muckup data folder are present in repository.yaml."""
    rep = get_repository_data()
    assert rep is not None, "Unable to load repository.yaml is None"

    # Test if all paths listed in repository.yaml are present in the mockup folder
    for name, dataset in rep.items():
        for version in dataset:
            if version["paths"]["local"] != f"{name}/v{version['version_nhflo']}":
                pytest.fail(f"Path in repository.yaml does not match the expected path: {version['paths']['local']}")

            if version["paths"]["nhflo_server"] != f"/data/{name}/v{version['version_nhflo']}":
                pytest.fail(
                    f"Path in repository.yaml does not match the expected path: {version['paths']['nhflo_server']}"
                )

            if version["paths"]["mockup"] != f"mockup/{name}/v{version['version_nhflo']}":
                pytest.fail(f"Path in repository.yaml does not match the expected path: {version['paths']['mockup']}")

            path = get_abs_data_path(
                name=name,
                version=version["version_nhflo"],
                location="mockup",
            )
            if not path.endswith(version["paths"]["mockup"]):
                pytest.fail(f"Path in repository.yaml does not match the expected path: {version['paths']['mockup']}")

            assert os.path.exists(path), f"Path {path} does not exist"
            assert os.listdir(path), f"Path {path} is empty"

    # Test if all folders in the mockup folder are listed in repository.yaml
    mockup_path = Path(get_data_dir()) / "mockup"

    skip_folders = {".gitkeep", "README.md", ".DS_Store", "Thumbs.db", "license_by-nc-sa-40.txt"}

    for dataset_name in os.listdir(mockup_path):
        if dataset_name in skip_folders:
            continue

        if dataset_name not in rep:
            pytest.fail(f"Folder {dataset_name} in mockup is not listed in repository.yaml")

        sort_versions = sorted(
            [i for i in os.listdir(mockup_path / dataset_name) if i not in skip_folders], reverse=True
        )
        rep_version = [f"v{version['version_nhflo']}" for version in rep[dataset_name]]

        if sort_versions != rep_version:
            pytest.fail(f"Versions of {dataset_name} in mockup folder do not match versions in repository.yaml")
