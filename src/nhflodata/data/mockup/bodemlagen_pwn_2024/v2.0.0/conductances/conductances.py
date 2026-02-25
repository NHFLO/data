"""Clean up and merge layer conductance data from the NHDZ and Bergen models.

This script processes the raw Triwaco polygon data from two regional submodels
(NHDZ and Bergen) and produces three sets of conductance parameters as polygon
GeoDataFrames:

- ``kh``: horizontal conductivity [m/d] of the aquifer layers (W-layers).
- ``c``: vertical resistance [d] of the aquitard layers (S-layers).
- ``kd_nhdz``: horizontal transmissivity [m2/d] of the aquitard layers from
  the NHDZ model, computed from KD shapefiles and mask-based formulas.

Where the NHDZ and Bergen model boundaries overlap, NHDZ data takes priority.
The Bergen model only covers the shallower layers (W11-W21, S11-S21); deeper
layers use NHDZ data exclusively.

The remaining horizontal and vertical conductivities required by MODFLOW (e.g.
kv of aquifers, kh/kv of aquitards) are not produced here. They need to be
computed downstream by NHFLO/tools using an anisotropy factor and layer
thicknesses of the MODFLOW grid.
"""

import logging

import geopandas as gpd
import pandas as pd
from params_helper_functions import clip_to_mask_region, fill_boundary_with_polygons

from nhflodata.get_paths import get_abs_data_path

# logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

data_path = get_abs_data_path("bodemlagen_pwn_2024", "2.0.0")
data_path_bergen = get_abs_data_path("bodemlagen_pwn_bergen", "1.0.0")
data_path_nhdz = get_abs_data_path("bodemlagen_pwn_nhdz", "1.0.0")

layer_names = ["W11", "S11", "W12", "S12", "W13", "S13", "W21", "S21", "W22", "S22", "W31", "S31", "W32", "S32"]
c_nhdz_fill_values = {  # From bodemlagen_pwn_nhdz/v1.0.0/Ontleding_model_v2.xlsx
    "S11": 1.0,
    "S12": 10.0,
    "S13": 10.0,
    "S21": 10.0,
    "S22": 10.0,
    "S31": 10.0,
    "S32": 10.0,
}

kh_bergen_fill_values = {
    "W11": 7.0,  # Triwaco Excel uses 7.0, but prior nhflo implementations used 8.0.
    "W12": 7.0,
    "W13": 12.0,
    "W21": 15.0,
}
c_bergen_fill_values = {
    "S11": 1.0,
    "S12": 100.0,
    "S13": 100.0,
    "S21": 1.0,
}
bergen_name_mapping = {
    "11": "1A",
    "12": "1B",
    "13": "1C",
    "21": "2",
}

# Get boundaries that we need to fill up with the data from Bergen and NHDZ
gdf_bergen = gpd.read_file(data_path / "boundaries" / "triwaco_model_bergen.geojson")
gdf_nhdz = gpd.read_file(data_path / "boundaries" / "triwaco_model_nhdz.geojson")

# NHDZ
kh_nhdz = {}
for name in layer_names:
    if name.startswith("W"):
        fp = data_path_nhdz / "Bodemparams" / "Kwaarden_aquifers" / f"K{name}.shp"
        k = gpd.read_file(fp).set_crs("EPSG:28992")
        kh_nhdz[name], _, _ = fill_boundary_with_polygons(
            boundary_gdf=gdf_nhdz,
            source_gdf=k,
            value_col="VALUE",
            # fill_value=kh_bergen_fill_values[name],  # Not used as fill method is 'mean'
            fill_method="mean",
            overlap_priority="last",
            override_gdf=None,
        )

kd_nhdz = {}  # horizontal transmissivity of the aquitards from nhdz
folder = data_path_nhdz / "Bodemparams" / "KDwaarden_aquitards"
s12kd = gpd.read_file(folder / "s12kd.shp").set_crs("EPSG:28992")
s13kd = gpd.read_file(folder / "s13kd.shp").set_crs("EPSG:28992")
s21kd = gpd.read_file(folder / "s21kd.shp").set_crs("EPSG:28992")
s22kd = gpd.read_file(folder / "s22kd.shp").set_crs("EPSG:28992")
# src/nhflodata/data/mockup/bodemlagen_pwn_nhdz/v1.0.0/Bodemparams/Maskers_kdwaarden_aquitards/masker_aquitard12_kd.shp
folder = data_path_nhdz / "Bodemparams" / "Maskers_kdwaarden_aquitards"
ms12kd = gpd.read_file(folder / "masker_aquitard12_kd.shp").set_crs("EPSG:28992")
ms13kd = gpd.read_file(folder / "masker_aquitard13_kd.shp").set_crs("EPSG:28992")
ms21kd = gpd.read_file(folder / "masker_aquitard21_kd.shp").set_crs("EPSG:28992")
ms22kd = gpd.read_file(folder / "masker_aquitard22_kd.shp").set_crs("EPSG:28992")

# Each formula is a list of (source_gdf, mask_gdf, mask_value, coefficient) terms
#   kd12s = s12kd*(ms12kd==1) + 0.5*s12kd*(ms12kd==2) + 3*s12kd*(ms12kd==3)
#   kd13s = (s13kd*(ms13kd==1) + 0.5*s12kd*(ms12kd==2)) * 1.04
#   kd21s = (s21kd*(ms21kd==1) + s13kd*(ms13kd==2)) * 0.6
#   kd22s = s22kd*(ms22kd==1) + s21kd*(ms21kd==2)
#   kd31s = s22kd*(ms22kd==2)
kd_formulas = {
    "S12": [
        (s12kd, ms12kd, 1, 1.0),
        (s12kd, ms12kd, 2, 0.5),
        (s12kd, ms12kd, 3, 3.0),
    ],
    "S13": [
        (s13kd, ms13kd, 1, 1.04),
        (s12kd, ms12kd, 2, 0.5 * 1.04),
    ],
    "S21": [
        (s21kd, ms21kd, 1, 0.6),
        (s13kd, ms13kd, 2, 0.6),
    ],
    "S22": [
        (s22kd, ms22kd, 1, 1.0),
        (s21kd, ms21kd, 2, 1.0),
    ],
    "S31": [
        (s22kd, ms22kd, 2, 1.0),
    ],
}

for name, terms in kd_formulas.items():
    parts = [clip_to_mask_region(src, mask, mask_value=val, coefficient=coeff) for src, mask, val, coeff in terms]
    kd_nhdz[name] = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs="EPSG:28992")
    kd_nhdz[name].to_file(data_path / "conductances" / f"KD{name}_NHDZ.geojson", driver="GeoJSON")

c_nhdz = {}
for name in layer_names:
    if name.startswith("S"):
        fp = data_path_nhdz / "Bodemparams" / "Cwaarden_aquitards" / f"C{name[1:]}AREA.shp"
        c = gpd.read_file(fp).set_crs("EPSG:28992")
        if name == "S22":
            c["VALUE"] *= 1.02  # From bodemlagen_pwn_nhdz/v1.0.0/Ontleding_model_v2.xlsx

        c_nhdz[name], overlaps_gdf, fill_gdf = fill_boundary_with_polygons(
            boundary_gdf=gdf_nhdz,
            source_gdf=c,
            value_col="VALUE",
            fill_value=c_nhdz_fill_values[name],
            fill_method="fill_value",
            overlap_priority="last",
            override_gdf=None,
        )
        # overlaps_gdf.to_file(data_path / "conductances" / f"C{name}_NHDZ_overlaps.geojson", driver="GeoJSON")
        # fill_gdf.to_file(data_path / "conductances" / f"C{name}_NHDZ_fill.geojson", driver="GeoJSON")

# Bergen
kh_bergen = {}
for name in bergen_name_mapping:
    kh_bergen[f"W{name}"], _, _ = fill_boundary_with_polygons(
        boundary_gdf=gdf_bergen,
        source_gdf=None,  # Are constants for Bergen, so use fill value only
        value_col="VALUE",  # Not used as source_gdf is None
        fill_value=kh_bergen_fill_values[f"W{name}"],
        fill_method="fill_value",
        overlap_priority="last",  # Not used as source_gdf is None
        override_gdf=None,
    )

c_bergen = {}
for name, bergen_name in bergen_name_mapping.items():
    fp = data_path_bergen / "Bodemparams" / f"C{bergen_name}.shp"
    c = gpd.read_file(fp).set_crs("EPSG:28992")
    c_bergen[f"S{name}"], overlaps_gdf, fill_gdf = fill_boundary_with_polygons(
        boundary_gdf=gdf_bergen,
        source_gdf=c,
        value_col="VALUE",  # Not used as source_gdf is None
        fill_value=c_bergen_fill_values[f"S{name}"],
        fill_method="fill_value",
        overlap_priority="last",  # Not used as source_gdf is None
        override_gdf=None,
    )
    # overlaps_gdf.to_file(data_path / "conductances" / f"C{bergen_name}_Bergen_overlaps.geojson", driver="GeoJSON")
    # fill_gdf.to_file(data_path / "conductances" / f"C{bergen_name}_Bergen_fill.geojson", driver="GeoJSON")

# Merge NHDZ and Bergen: NHDZ takes priority where they overlap.
# At deeper layers (W22, W31, W32, S22, S31, S32) only NHDZ data exists.
nhdz_boundary = gdf_nhdz.geometry.union_all()
bergen_minus_nhdz = gdf_bergen.geometry.union_all().difference(nhdz_boundary)

kh = {}
for name in layer_names:
    if not name.startswith("W"):
        continue
    if name in kh_nhdz and name in kh_bergen:
        bergen_part = gpd.clip(kh_bergen[name], bergen_minus_nhdz)
        bergen_part = bergen_part[~bergen_part.geometry.is_empty]
        kh[name] = gpd.GeoDataFrame(
            pd.concat([kh_nhdz[name], bergen_part], ignore_index=True),
            crs=kh_nhdz[name].crs,
        )
    elif name in kh_nhdz:
        kh[name] = kh_nhdz[name]

    kh[name].to_file(data_path / "conductances" / f"K{name}_combined.geojson", driver="GeoJSON")

c = {}
for name in layer_names:
    if not name.startswith("S"):
        continue
    if name in c_nhdz and name in c_bergen:
        bergen_part = gpd.clip(c_bergen[name], bergen_minus_nhdz)
        bergen_part = bergen_part[~bergen_part.geometry.is_empty]
        c[name] = gpd.GeoDataFrame(
            pd.concat([c_nhdz[name], bergen_part], ignore_index=True),
            crs=c_nhdz[name].crs,
        )
    elif name in c_nhdz:
        c[name] = c_nhdz[name]

    c[name].to_file(data_path / "conductances" / f"C{name}_combined.geojson", driver="GeoJSON")
