"""Clean up and merge layer conductance data from the NHDZ and Bergen models.

This script processes the raw Triwaco polygon data from two regional submodels
(NHDZ and Bergen) and produces three sets of conductance parameters as polygon
GeoDataFrames:

- ``kh``: horizontal conductivity [m/d] of the aquifer layers (W-layers).
- ``c``: vertical resistance [d] of the aquitard layers (S-layers).
- ``kd_nhdz``: horizontal transmissivity [m2/d] of the aquitard layers from
  the NHDZ model, computed from KD shapefiles and mask-based formulas.

Where both regions provide data and their boundaries overlap, NHDZ takes priority.
The Bergen model only covers the shallower layers (W11-W21B, S11-S21); deeper
layers use NHDZ data exclusively. W21 is split into W21A and W21B. NHDZ uses
the original KW21 source for both, while Bergen uses 15 and 20 m/d respectively.
S21A uses Bergen C1D as a separate resistance, not subtracted from S13 or S21.
It is filled and merged like the other aquitards, using the available regional
sources. There is no NHDZ resistance source for S21A.

After merging, K and c polygons are extended to each revised v3 layer boundary.
Existing polygons are retained; only uncovered areas are added. Shallow layers
use the existing Bergen layer defaults for these additions, and deeper layers
use the NHDZ resistance defaults or the area-weighted mean K of the merged source.
The original regional coverage and NHDZ overlap priority are unchanged.

The remaining horizontal and vertical conductivities required by MODFLOW (e.g.
kv of aquifers, kh/kv of aquitards) are not produced here. They need to be
computed downstream by NHFLO/tools using an anisotropy factor and layer
thicknesses of the MODFLOW grid.
"""

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
from params_helper_functions import clip_to_mask_region, fill_boundary_with_polygons

from nhflodata.get_paths import get_abs_data_path

# logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def extend_to_layer_boundary(source, boundary, *, fill_value, parameter_name):
    """Add hydraulic coverage inside a layer boundary without changing source values.

    Parameters
    ----------
    source : gpd.GeoDataFrame
        Merged K [m/d] or c [d] polygons in EPSG:28992, with a ``VALUE`` column.
    boundary : shapely.Geometry
        Revised layer footprint in the same CRS.
    fill_value : float
        Existing regional layer default, or area-weighted mean source K.
    parameter_name : str
        Hydraulic parameter identifier for warnings and errors.

    Returns
    -------
    gpd.GeoDataFrame
        Original polygons plus a non-overlapping polygon covering any gaps.
    """
    if not (np.isfinite(source["VALUE"]) & (source["VALUE"] > 0.0)).all():
        msg = f"{parameter_name}: source hydraulic values must be positive and finite"
        raise ValueError(msg)
    uncovered = boundary.difference(source.geometry.union_all())
    if uncovered.is_empty:
        return source
    if not np.isfinite(fill_value) or fill_value <= 0.0:
        msg = f"{parameter_name}: cannot extend hydraulic coverage without a positive, finite fill value"
        raise ValueError(msg)
    logger.warning(
        "%s: extending hydraulic coverage by %.3f km2 using fill value %.6g.",
        parameter_name,
        uncovered.area / 1e6,
        fill_value,
    )
    addition = gpd.GeoDataFrame({"VALUE": [fill_value]}, geometry=[uncovered], crs=source.crs)
    return gpd.GeoDataFrame(pd.concat([source, addition], ignore_index=True), crs=source.crs)


data_path = get_abs_data_path(name="bodemlagen_pwn_2024", version="3.0.0")
data_path_bergen = get_abs_data_path(name="bodemlagen_pwn_bergen", version="1.0.0")
data_path_nhdz = get_abs_data_path(name="bodemlagen_pwn_nhdz", version="1.0.0")

layer_names = [
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
# TODO: [Edinsi report 3.2, p.24] Edinsi notes that C12AREA (S12 vertical resistance from
#   NHDZ) has an extremely high resistance of 37800 days for a small area west of Castricum.
#   Edinsi flags this as an item that still needs to be processed/verified.
# TODO: [Edinsi report 3.2, p.22] Edinsi notes that S1.2 at boring 19CZW643 has 7.5m
#   thickness and 430 day resistance (only 0.02 m/d vertical conductivity) despite sand
#   material and no piezometric head difference. This may indicate the conductance data is
#   unreliable for this layer in some locations.
# TODO: [Edinsi report 3.2, p.24] Edinsi flags: S12 mapped as 17.5m thick at 19CNPCS 10
#   but this doesn't match the boring data.
# TODO: [Edinsi report 3.2, p.24] Edinsi flags: Profile GG shows thick clay at 19CZW718
#   with negligible head difference between filters 2 and 3. Possible density effects?
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
    "W12": 7.0,  # Ontleding_model.xlsx Aquifer 2
    "W13": 12.0,  # Ontleding_model.xlsx Aquifer 3
    "W21A": 15.0,  # Ontleding_model.xlsx Aquifer 4
    "W21B": 20.0,  # Ontleding_model.xlsx Aquifer 5
}
c_bergen_fill_values = {
    "S11": 1.0,
    "S12": 100.0,
    "S13": 100.0,
    "S21A": 1000.0,  # SPD1H SWE 87.001 Tabel 3.1 p27.
    "S21": 1.0,
}
bergen_name_mapping = {
    "11": "1A",
    "12": "1B",
    "13": "1C",
    "21A": "1D",  # SPD 1D is Kreftenheye.
    "21": "2",
}

# Get boundaries that we need to fill up with the data from Bergen and NHDZ
gdf_bergen = gpd.read_file(data_path / "boundaries" / "triwaco_model_bergen.geojson")
gdf_nhdz = gpd.read_file(data_path / "boundaries" / "triwaco_model_nhdz.geojson")

layer_boundaries = {}
for name in layer_names:
    if name.startswith("S"):
        boundary = gpd.read_file(data_path / "boundaries" / name / f"{name}.geojson").to_crs(gdf_nhdz.crs)
        layer_boundaries[name[1:]] = boundary.geometry.union_all()

# NHDZ
kh_nhdz = {}
for name in layer_names:
    if name.startswith("W"):
        source_name = "W21" if name in {"W21A", "W21B"} else name
        fp = data_path_nhdz / "Bodemparams" / "Kwaarden_aquifers" / f"K{source_name}.shp"
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

# Obtains the transmissivity of the aquitards from the NHDZ data. `sXXkd` contains the values,
# `msXXkd` contains the corresponding mask polygons. The mask gdfs contain several polygons with
# mask_value referring to regions that were calibrated separately. The mask masks the source data.
# The source data is multiplied by the coefficients listed here in kd_formulas, derived from ontledingstabel.xlsx
for name, terms in kd_formulas.items():
    parts = [clip_to_mask_region(src, mask, mask_value=val, coefficient=coeff) for src, mask, val, coeff in terms]
    kd_nhdz[name] = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs="EPSG:28992").astype({"VALUE": "float64"})
    kd_nhdz[name].to_file(data_path / "conductances" / f"KD{name}_NHDZ.geojson", driver="GeoJSON")

c_nhdz = {}
for name, fill_value in c_nhdz_fill_values.items():
    fp = data_path_nhdz / "Bodemparams" / "Cwaarden_aquitards" / f"C{name[1:]}AREA.shp"
    c = gpd.read_file(fp).set_crs("EPSG:28992")
    if name == "S22":
        c["VALUE"] *= 1.02  # From bodemlagen_pwn_nhdz/v1.0.0/Ontleding_model_v2.xlsx

    c_nhdz[name], overlaps_gdf, fill_gdf = fill_boundary_with_polygons(
        boundary_gdf=gdf_nhdz,
        source_gdf=c,
        value_col="VALUE",
        fill_value=fill_value,
        fill_method="fill_value",
        overlap_priority="last",
        override_gdf=None,
    )
    # overlaps_gdf.to_file(data_path / "conductances" / f"C{name}_NHDZ_overlaps.geojson", driver="GeoJSON")
    # fill_gdf.to_file(data_path / "conductances" / f"C{name}_NHDZ_fill.geojson", driver="GeoJSON")

# Bergen
kh_bergen = {}
for name, fill_value in kh_bergen_fill_values.items():
    kh_bergen[name], _, _ = fill_boundary_with_polygons(
        boundary_gdf=gdf_bergen,
        source_gdf=None,  # Are constants for Bergen, so use fill value only
        value_col="VALUE",  # Not used as source_gdf is None
        fill_value=fill_value,
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
    else:
        msg = f"No conductance data available for layer {name}"
        raise ValueError(msg)

    unit = "21" if name == "W21B" else name[1:]
    fill_value = (
        kh_bergen_fill_values[name]
        if name in kh_bergen
        else np.average(kh[name]["VALUE"], weights=kh[name].geometry.area)
    )
    kh[name] = extend_to_layer_boundary(
        kh[name], layer_boundaries[unit], fill_value=fill_value, parameter_name=f"K{name}"
    )
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
    elif name in c_bergen:
        c[name] = c_bergen[name]
    else:
        msg = f"No conductance data available for layer {name}"
        raise ValueError(msg)

    fill_value = c_bergen_fill_values[name] if name in c_bergen else c_nhdz_fill_values[name]
    c[name] = extend_to_layer_boundary(
        c[name], layer_boundaries[name[1:]], fill_value=fill_value, parameter_name=f"C{name}"
    )
    c[name].to_file(data_path / "conductances" / f"C{name}_combined.geojson", driver="GeoJSON")
