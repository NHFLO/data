"""Tests for YAML schema validation and linting.

This module validates both schema compliance using yamale and style rules using yamllint.
"""

from pathlib import Path

import pytest
import yamale
import yaml
from yamllint import config as lint_config
from yamllint import linter

from nhflodata.get_paths import get_repository_data, get_repository_path


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

    schema = yamale.make_schema(fp_schema_repository_yaml)
    data = yamale.make_data(content=yaml_content)
    result = yamale.validate(schema, data, _raise_error=False)[0]
    if result.errors:
        error_msg = "\nSchema validation problems found:\n"
        for error in result.errors:
            error_msg += error
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
