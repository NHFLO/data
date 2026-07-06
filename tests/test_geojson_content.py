"""Content contract for the committed GeoJSON artifacts of the drain/HFB datasets.

The registry test (test_repository_yaml) and the folder test (test_mockup_folder_structure)
verify metadata and folder structure but never open the GeoJSON files. This lightweight,
dependency-free (stdlib json) check verifies that the committed artifacts consumers rely on are
structurally sound: the expected file exists, has non-empty features, declares a CRS, and every
feature carries the property columns its model consumer reads. It deliberately does NOT assert
specific data values, which are allowed to change for a data repository.
"""

import json

import pytest

from nhflodata.get_paths import get_abs_data_path

# Required property columns per dataset, matching what the model consumers read.
REQUIRED_COLUMNS = {
    "drains_pwn": {
        "name",
        "elevation",
        "conductance_per_meter",
        "conductance_per_squared_meter",
        "bgt-identificatie",
        "mover_lake_name",
        "comment",
    },
    "hfb_pwn": {"name", "hydchr", "elevation", "depth", "comment"},
}


@pytest.mark.parametrize("name", sorted(REQUIRED_COLUMNS))
def test_geojson_content_contract(name):
    """Committed <name>.geojson has non-empty features, a CRS, and all required columns."""
    path = get_abs_data_path(name=name, version="latest", location="mockup")
    geojson_file = path / f"{name}.geojson"
    assert geojson_file.exists(), f"{geojson_file} is missing"

    with open(geojson_file, encoding="utf-8") as f:
        gj = json.load(f)

    features = gj.get("features", [])
    assert features, f"{name}.geojson has no features"
    assert gj.get("crs"), f"{name}.geojson has no CRS"

    required = REQUIRED_COLUMNS[name]
    for i, feat in enumerate(features):
        missing = required - set(feat.get("properties", {}))
        assert not missing, f"{name}.geojson feature {i} is missing columns: {sorted(missing)}"
