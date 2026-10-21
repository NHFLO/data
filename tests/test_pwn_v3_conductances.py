"""Check v3 layer mapping and hydraulic parameter generation."""

import ast
import csv
import importlib.util
import runpy
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from geopandas.testing import assert_geodataframe_equal
from pandas.api.types import is_numeric_dtype

from nhflodata import get_paths

DATA_ROOT = Path(get_paths.get_data_dir()) / "mockup"
PWN_ROOT = DATA_ROOT / "bodemlagen_pwn_2024"
V3_ROOT = PWN_ROOT / "v3.0.0"
LAYER_NAMES = [
    "W11",
    "S11",
    "W12",
    "S12",
    "W13",
    "S13",
    "W21A",
    "S21A",
    "W21B",
    "S21",
    "W22",
    "S22",
    "W31",
    "S31",
    "W32",
    "S32",
]


def load_helper(version):
    """Load a version's preparation helper without executing its generator."""
    path = PWN_ROOT / version / "conductances" / "params_helper_functions.py"
    spec = importlib.util.spec_from_file_location("conductance_helper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def helper():
    """Return the v3 polygon preparation helper."""
    return load_helper("v3.0.0")


@pytest.fixture(scope="module")
def generated():
    """Execute both generators using mockup inputs and intercept every write."""
    return {version: run_generator(version) for version in ["v2.0.0", "v3.0.0"]}


def run_generator(version):
    """Run one generator with isolated path resolution and captured output."""
    writes = {}
    reads = []
    real_get_path = get_paths.get_abs_data_path
    real_read_file = gpd.read_file

    def resolve_path(name, version):
        return real_get_path(name, version, location="mockup")

    def read_file(path):
        reads.append(Path(path))
        return real_read_file(path)

    def capture_write(frame, filename, driver):
        assert driver == "GeoJSON"
        writes[Path(filename)] = frame.copy()

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(get_paths, "get_abs_data_path", resolve_path)
        patch.setattr(gpd, "read_file", read_file)
        patch.setattr(gpd.GeoDataFrame, "to_file", capture_write)
        patch.setitem(sys.modules, "params_helper_functions", load_helper(version))
        namespace = runpy.run_path(str(PWN_ROOT / version / "conductances" / "conductances.py"))
    return {"namespace": namespace, "writes": writes, "reads": reads}


def test_v3_translation_table():
    """Ensure table names and zero-based indices match the complete v3 stack."""
    with (V3_ROOT / "bodemlagenvertaaltabel.csv").open(newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 136
    assert {row["ASSUMPTION1"] for row in rows if row["ASSUMPTION1"]} == set(LAYER_NAMES)
    for row in rows:
        assert None not in row
        name = row["ASSUMPTION1"]
        assert row["ASSUMPTION1_index"] == (f"{LAYER_NAMES.index(name):.1f}" if name else "")
        assert not row["Triwaco"] or row["Triwaco"] in LAYER_NAMES
    krk1 = next(row for row in rows if row["Regis II v2.2"] == "KRk1")
    assert krk1["Triwaco"] == krk1["ASSUMPTION1"] == "S21A"

    tree = ast.parse((V3_ROOT / "botm" / "botm.py").read_text(encoding="utf-8"))
    output_layers = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "output_layers" for target in node.targets)
    )
    assert [name for name, _, _ in output_layers] == LAYER_NAMES


def test_v3_generator_sources_and_outputs(generated):
    """Require all v3 parameter names without reads or writes in the v2 dataset."""
    result = generated["v3.0.0"]
    namespace = result["namespace"]
    assert namespace["layer_names"] == LAYER_NAMES
    assert set(namespace["kh"]) == {name for name in LAYER_NAMES if name.startswith("W")}
    assert set(namespace["c"]) == {name for name in LAYER_NAMES if name.startswith("S")}
    expected_files = (
        {f"K{name}_combined.geojson" for name in namespace["kh"]}
        | {f"C{name}_combined.geojson" for name in namespace["c"]}
        | {f"KD{name}_NHDZ.geojson" for name in namespace["kd_nhdz"]}
    )
    assert {path.name for path in result["writes"]} == expected_files
    assert all(path.parent == V3_ROOT / "conductances" for path in result["writes"])
    assert not any("v2.0.0" in path.parts for path in result["reads"])
    assert any(path.name == "C1D.shp" for path in result["reads"])
    assert not any(path.name in {"KW21A.shp", "KW21B.shp", "C21AAREA.shp"} for path in result["reads"])
    assert any(path.name == "S21A.geojson" for path in result["reads"])
    assert not any(path.name == "DS21A_mask_combined.geojson" for path in result["reads"])


def test_v3_hydraulic_polygons_cover_revised_layer_boundaries(generated):
    """Every active layer area needs K or c, including areas outside both old models."""
    new = generated["v3.0.0"]["namespace"]
    for parameter, prefix in [("kh", "K"), ("c", "C")]:
        for name, frame in new[parameter].items():
            unit = "21" if name == "W21B" else name[1:]
            boundary = gpd.read_file(V3_ROOT / "boundaries" / f"S{unit}" / f"S{unit}.geojson")
            target = boundary.geometry.union_all()
            support = frame.geometry.union_all()
            assert target.difference(support).area < 1e-4, f"{prefix}{name} leaves revised layer areas uncovered"
            assert frame.geometry.is_valid.all()
            assert frame.geometry.area.sum() - support.area < 1e-4, name
            assert (np.isfinite(frame["VALUE"]) & (frame["VALUE"] > 0.0)).all(), name


def test_existing_parameters_are_unchanged(generated):
    """Keep all original polygons and values; only append new layer coverage."""
    old = generated["v2.0.0"]["namespace"]
    new = generated["v3.0.0"]["namespace"]
    for parameter in ["c", "kd_nhdz", "kh"]:
        for name, frame in old[parameter].items():
            if name != "W21":
                assert_geodataframe_equal(
                    new[parameter][name].iloc[: len(frame)], frame, check_dtype=parameter != "kd_nhdz"
                )
    for name in ["W21A", "W21B"]:
        assert_geodataframe_equal(new["kh_nhdz"][name], old["kh_nhdz"]["W21"])
    assert_geodataframe_equal(new["kh"]["W21A"].iloc[: len(old["kh"]["W21"])], old["kh"]["W21"])
    assert (new["kh_bergen"]["W21A"]["VALUE"] == 15.0).all()
    assert (new["kh_bergen"]["W21B"]["VALUE"] == 20.0).all()
    nhdz = new["gdf_nhdz"].geometry.union_all()
    final_nhdz = gpd.clip(new["kh"]["W21B"], nhdz, keep_geom_type=True)
    assert nhdz.difference(final_nhdz.geometry.union_all()).area < 1e-4
    assert set(final_nhdz["VALUE"]) == set(old["kh_nhdz"]["W21"]["VALUE"])
    for value in final_nhdz["VALUE"].unique():
        actual = final_nhdz.loc[final_nhdz["VALUE"] == value].geometry.union_all()
        expected = old["kh_nhdz"]["W21"].loc[old["kh_nhdz"]["W21"]["VALUE"] == value].geometry.union_all()
        assert actual.symmetric_difference(expected).area < 1e-4
    final_bergen = gpd.clip(new["kh"]["W21B"], new["bergen_minus_nhdz"], keep_geom_type=True)
    assert (final_bergen["VALUE"] == 20.0).all()
    assert final_bergen.geometry.union_all().symmetric_difference(new["bergen_minus_nhdz"]).area < 1e-4


def test_added_coverage_uses_existing_regional_defaults(generated):
    """Extensions use documented layer defaults, not arbitrary conductivity replacements."""
    old = generated["v2.0.0"]["namespace"]
    new = generated["v3.0.0"]["namespace"]
    shallow_k = {"W11": 7.0, "W12": 7.0, "W13": 12.0, "W21A": 15.0, "W21B": 20.0}
    shallow_c = {"S11": 1.0, "S12": 100.0, "S13": 100.0, "S21A": 1000.0, "S21": 1.0}
    for parameter, defaults in [("kh", shallow_k), ("c", shallow_c)]:
        for name, frame in new[parameter].items():
            original_name = "W21" if name in {"W21A", "W21B"} else name
            original = new["c_bergen"]["S21A"] if name == "S21A" else old[parameter][original_name]
            additions = frame.iloc[len(original) :]
            assert len(additions) == 1, name
            if name in defaults:
                expected = defaults[name]
            elif parameter == "c":
                expected = 10.0
            else:
                expected = np.average(original["VALUE"], weights=original.geometry.area)
            np.testing.assert_allclose(additions["VALUE"], expected, rtol=1e-12)


def test_generated_geojson_round_trip(generated, tmp_path):
    """Verify every emitted parameter retains its values and geometry on disk."""
    result = generated["v3.0.0"]
    for path, frame in result["writes"].items():
        output = tmp_path / path.name
        frame.to_file(output, driver="GeoJSON")
        stored = gpd.read_file(output)
        assert is_numeric_dtype(stored["VALUE"]), path.name
        expected = frame.reset_index(drop=True)[stored.columns].astype({"VALUE": "float64"})
        assert_geodataframe_equal(stored, expected)
        if path.name.endswith("_combined.geojson"):
            assert_geodataframe_equal(gpd.read_file(path), expected)


def test_s21a_resistance_uses_standard_source(generated, helper):
    """Process S21A through the same source/default filling as other aquitards."""
    new = generated["v3.0.0"]["namespace"]
    source_path = DATA_ROOT / "bodemlagen_pwn_bergen" / "v1.0.0" / "Bodemparams" / "C1D.shp"
    source = gpd.read_file(source_path).set_crs("EPSG:28992")
    expected, _, _ = helper.fill_boundary_with_polygons(
        boundary_gdf=new["gdf_bergen"],
        source_gdf=source,
        fill_value=1000.0,
        overlap_priority="last",
    )
    assert "S21A" not in new["c_nhdz"]
    assert_geodataframe_equal(new["c_bergen"]["S21A"], expected)
    resistance = new["c"]["S21A"]
    assert_geodataframe_equal(resistance.iloc[: len(expected)], expected)
    assert resistance.geometry.is_valid.all()
    assert set(resistance["VALUE"]) == {1000.0}
    assert 1000.0 in resistance["VALUE"].values
    boundary = gpd.read_file(V3_ROOT / "boundaries" / "S21A" / "S21A.geojson").geometry.union_all()
    expected_coverage = new["gdf_bergen"].geometry.union_all().union(boundary)
    assert resistance.geometry.union_all().symmetric_difference(expected_coverage).area < 1e-4
    assert resistance.geometry.area.sum() - resistance.geometry.union_all().area < 1e-4
