"""Tests for YAML schema validation and linting.

This module validates both schema compliance using yamale and style rules using yamllint.
"""
import os
from pathlib import Path
import yaml

import pytest
import yamale
from yamale.validators import DefaultValidators, Validator
from yamllint import config as lint_config
from yamllint import linter

from nhflodata.get_paths import get_abs_data_path, get_repository_path, get_repository_data, is_valid_semver


class PathsMatchVersion(Validator):
    """Ensure all paths end with version_nhflo."""

    def _is_valid(self, value):
        version_nhflo = self.value_context.get("version_nhflo")
        if not version_nhflo:
            return False

        return (
            value["local"].endswith(version_nhflo)
            and value["nhflo_server"].endswith(version_nhflo)
            and value["mockup"].endswith(version_nhflo)
        )


def test_repository_yaml_file_validation():
    """Test both schema validation and linting rules."""
    # Read YAML content
    fp_repository_yaml = get_repository_path()
    fp_schema_repository_yaml = Path(__file__).parent / "schema_repository.yaml"

    try:
        # try opening using yaml.save_load() to catch yaml.YAMLError
        get_repository_data()
    except yaml.YAMLError as exc:
        pytest.fail(f"Error in repository.yaml: {exc}")

    with open(fp_repository_yaml, encoding="utf-8") as f:
        yaml_content = f.read()

    # Schema validation
    validators = DefaultValidators.copy()
    validators["paths_match_version"] = PathsMatchVersion

    schema = yamale.make_schema(fp_schema_repository_yaml, validators=validators)
    data = yamale.make_data(content=yaml_content)
    result = yamale.validate(schema, data)[0]
    if result.errors:
        error_msg = "\nSchema validation problems found:\n"
        for error in result.errors:
            error_msg += f"Line {error.line}: {error.message}\n"
        pytest.fail(error_msg)



def test_repository_yaml_file_lint():
    """Test both schema validation and linting rules."""
    # Read YAML content
    fp_repository_yaml = get_repository_path()

    try:
        # try opening using yaml.save_load() to catch yaml.YAMLError
        get_repository_data()
    except yaml.YAMLError as exc:
        pytest.fail(f"Error in repository.yaml: {exc}")

    with open(fp_repository_yaml, encoding="utf-8") as f:
        yaml_content = f.read()

    # Lint validation
    lint_conf = lint_config.YamlLintConfig("""
        extends: default
        rules:
            document-start: disable
            line-length: disable
            empty-lines:
                max: 1
                max-start: 1
                max-end: 1
            indentation:
                spaces: 2
                indent-sequences: true
            braces:
                min-spaces-inside: 0
                max-spaces-inside: 0
            brackets:
                min-spaces-inside: 0
                max-spaces-inside: 0
            comments:
                min-spaces-from-content: 2
    """)

    problems = list(linter.run(yaml_content, lint_conf))

    # Format lint problems into readable message if any exist
    if problems:
        error_msg = "\nLinting problems found:\n"
        for problem in problems:
            error_msg += f"Line {problem.line}: {problem.message}\n"
        pytest.fail(error_msg)


def test_repository_yaml():
    """Test that the repository.yaml file is correctly formatted."""
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
            for location in locations:
                local_parent_folder = "data_parent_folder" if location == "local" else ""
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
