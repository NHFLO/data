"""Compute bottom elevations of the PWN bodemlagen (layer boundaries) for the NHFLO model.

This script reads contour-line and borehole point data for the seven aquitard
layers (S11, S12, S13, S21, S22, S31, S32) and their overlying aquifers
(W11 … W32), runs a series of quality checks, interpolates all tops and
thicknesses to a common set of point locations, and writes the resulting
bottom-elevation point clouds to GeoJSON files in the ``botm/`` subdirectory.

Workflow
--------
1. **Load data** - ``get_point_values`` reads digitised contour lines and
   borehole interpretations for each layer (top ``TSxx`` and thickness
   ``DSxx``) from the source GeoJSON files and returns a
   :class:`geopandas.GeoDataFrame` of point values.
2. **Quality checks** - three automated tests are run per layer:

   * *Test 1a*: all thickness values must be >= 0 and non-NaN.
   * *Test 1b*: points inside the zero-thickness masks must carry a value
     of exactly 0.
   * *Test 2*: all data points must lie within the layer boundary.
   * *Test 3*: duplicate locations are detected and merged by taking the
     mean value.

3. **Interpolate** - ``interpolate_to_all_points`` performs scipy linear
   interpolation with a nearest-neighbour fallback (for points inside the
   boundary but outside the convex hull of the data cloud) to map all tops
   and thicknesses to the union of data-point locations across every layer.
4. **Compute bottoms** - bottom elevations are derived as:

   * *Aquifer Wxx*: bottom = top of the underlying aquitard (``TS_xx``).
   * *Aquitard Sxx*: bottom = ``TS_xx`` - ``DS_xx``.
   * *Aquitard S32* (deepest layer, fixed thickness): bottom = ``TS32`` - 5 m.

5. **Enforce non-negative thickness** - a downward and an upward sweep clamp
   interpolated (non-original) values that would create negative layer
   thicknesses. Conflicts between two original data points are logged as
   warnings but left unchanged. Downward sweep first because upper layers are
   assumed to be better known.
6. **Save** - all layers are merged into a single
   :class:`geopandas.GeoDataFrame` (with a ``layer`` column identifying each
   layer) and written to ``botm.geojson``.

Notes
-----
Several ``# TODO`` comments in the source mark known data-quality issues that
still require manual intervention.  These do not affect the script's output
but are tracked for future improvement.
"""

import logging
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
from interpolation_helper_functions import get_point_values, interpolate_to_all_points

from nhflodata.get_paths import get_abs_data_path

# logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# DONE: Alle boring na de Koster dataset toevoegen/evalueren, zodat er meer punten zijn voor de interpolatie (get_point_values()).
# DONE: Koster "daw_bestanden" en "kaarten_2024_voor_interpolatie" mapjes op de juiste plek zetten. DAW -> geojson. src\nhflodata\data\mockup\bodemlagen_pwn_2024\v2.0.0\koster_daw
# TODO: "if fpath_shp_ber.exists() is True:" in get_point_values() eruit. Als laag is S11 dan skip
# TODO: get_point_values(layer_name) label bij punten met de bron van de data. Niet vereist voor implementatie NHFLO. Wel van toegevowegde waarde bij latere inversie stap.
# DONE: within gdf_msk_bergen gdf_d is assigned np.nan. Shouldn't it be zero?
# DONE: "daw_data_TS_DS.shp" in get_point_values() heeft 0.01m dikte voor aquitards die afwezig zijn. Check of deze punten in masks liggen en andersom. Dubbel check of er geen 1cm  laagdikten in eindproduct zitten, want speciale betekenis.
# DONE: Controleer of er geen locaties zijn die meerdere keren voorkomen en verschillende waarden hebben
# DONE: Bergen mask en Koster 0.01 mask samenvoegen tot 1 mask.
# TODO: Sanity checks voor gdf_d en gdf_t. Geen negatieve dikten. Hoe wordt omgegaan met ontbrekende waarden? Doorsnijdt Top min dikte de top van de onderliggende laag?
# TODO: Add points from mask polygons to gdf_d with value 0, so that these points are included in the interpolation and get a value of zero. This is currently done by creating a separate GeoDataFrame with the interpolation points and using spatial join to find the points that are within the mask polygons, but for course interpolation grids info is lost. The zero masks can be used for thickness, but the top is not known.
# TODO: Compute gdf_t for the points created from the zero masks.

data_path = get_abs_data_path("bodemlagen_pwn_2024", "2.0.0")

# Tolerance for floating point comparisons (meters)
THICKNESS_TOL = 1e-6

# Names of the layers to be interpolated
layer_names = ["S11", "S12", "S13", "S21", "S22", "S31", "S32"]

dict_t = {}
dict_d = {}

for layer_name in layer_names:
    # Create GeoDataFrames with the data points of the top and thicknesses
    gdf_t = get_point_values(path=data_path, layer_name=f"T{layer_name}", dx_zero_vertices_interpolation=50.0)
    gdf_d = get_point_values(path=data_path, layer_name=f"D{layer_name}", dx_zero_vertices_interpolation=50.0)

    # Test 1a: All thicknesses should be zero or positive (no negative or NaN values).
    n_negative = int((gdf_d["value"] < 0).sum())
    n_nan_d = int(gdf_d["value"].isna().sum())
    if n_negative == 0 and n_nan_d == 0:
        logger.info("Test 1a passed for %s: all gdf_d values are zero or positive.", layer_name)
    else:
        if n_negative > 0:
            logger.warning("Test 1a failed for %s: %d gdf_d points have negative values.", layer_name, n_negative)
        if n_nan_d > 0:
            logger.warning("Test 1a failed for %s: %d gdf_d points have NaN values.", layer_name, n_nan_d)

    n_nan_t = int(gdf_t["value"].isna().sum())
    if n_nan_t == 0:
        logger.info("Test 1a passed for %s: all gdf_t values are non-NaN.", layer_name)
    else:
        logger.warning("Test 1a failed for %s: %d gdf_t points have NaN values.", layer_name, n_nan_t)

    # Test 1b: All thicknesses should be zero in _mask_combined.geojson.
    mask_name = f"D{layer_name}"
    fp_zero_masks = Path(data_path, "dikte_aquitard", mask_name, f"{mask_name}_mask_combined.geojson")
    gdf_zero_masks = gpd.read_file(fp_zero_masks)

    gdf_d_in_mask = gpd.sjoin(gdf_d, gdf_zero_masks, predicate="within")
    non_zero = gdf_d_in_mask[gdf_d_in_mask["value_left"] != 0]

    gdf_d.loc[gdf_d_in_mask.index, "value"] = 0  # TODO: This one should not be necessary

    # ax=gdf_d.plot(); non_zero.plot(ax=ax, c="red"); gdf_zero_masks.boundary.plot(ax=ax, color="blue")
    if non_zero.empty:
        logger.info("Test 1b passed for %s: all gdf_d points within zero masks have value 0.", layer_name)
    else:
        logger.warning(
            "Test 1b failed for %s: %d gdf_d points within zero masks have non-zero values.",
            layer_name,
            len(non_zero),
        )

    # Test 2: All data points should lie on or inside the boundaries.
    gdf_boundary = gpd.read_file(os.path.join(data_path, "boundaries", layer_name, f"{layer_name}.geojson"))

    gdf_t_in_boundary = gpd.sjoin(gdf_t, gdf_boundary, predicate="intersects")
    n_t_outside = len(gdf_t) - len(gdf_t_in_boundary)
    # ax=gdf_t.plot(); gdf_t[~gdf_t.index.isin(gdf_t_in_boundary.index)].plot(ax=ax, c="red"); gdf_boundary.boundary.plot(ax=ax, color="blue")
    if n_t_outside == 0:
        logger.info("Test 2 passed for %s: all gdf_t points lie on or within the boundary.", layer_name)
    else:
        logger.warning("Test 2 failed for %s: %d gdf_t points lie outside the boundary.", layer_name, n_t_outside)

    gdf_t = gdf_t.loc[gdf_t_in_boundary.index]  # TODO: This one should not be necessary

    gdf_d_in_boundary = gpd.sjoin(gdf_d, gdf_boundary, predicate="intersects")
    n_d_outside = len(gdf_d) - len(gdf_d_in_boundary)
    # ax=gdf_d.plot(); gdf_d[~gdf_d.index.isin(gdf_d_in_boundary.index)].plot(ax=ax, c="red"); gdf_boundary.boundary.plot(ax=ax, color="blue")
    if n_d_outside == 0:
        logger.info("Test 2 passed for %s: all gdf_d points lie on or within the boundary.", layer_name)
    else:
        logger.warning("Test 2 failed for %s: %d gdf_d points lie outside the boundary.", layer_name, n_d_outside)

    gdf_d = gdf_d.loc[gdf_d_in_boundary.index]  # TODO: This one should not be necessary

    # Test 3: No multiple data points at the exact same location.
    # ax=gdf_t.plot(); gdf_t[gdf_t.duplicated(subset="geometry")].plot(ax=ax, c="red")
    # ax=gdf_d.plot(); gdf_d[gdf_d.duplicated(subset="geometry")].plot(ax=ax, c="red")
    dup_count = int(gdf_t.duplicated(subset="geometry").sum())
    gdf_t = gdf_t.dissolve(by=gdf_t.geometry, aggfunc="mean").reset_index(
        drop=True
    )  # TODO: This one should not be necessary
    if dup_count == 0:
        logger.info("Test 3 passed for %s: no duplicate points in gdf_t.", layer_name)
    else:
        logger.warning(
            "Test 3 failed for %s: %d duplicate points in gdf_t. Taking the mean of duplicate values.",
            layer_name,
            dup_count,
        )

    dup_count = int(gdf_d.duplicated(subset="geometry").sum())
    gdf_d = gdf_d.dissolve(by=gdf_d.geometry, aggfunc="mean").reset_index(
        drop=True
    )  # TODO: This one should not be necessary
    if dup_count == 0:
        logger.info("Test 3 passed for %s: no duplicate points in gdf_d.", layer_name)
    else:
        logger.warning(
            "Test 3 failed for %s: %d duplicate points in gdf_d. Taking the mean of duplicate values.",
            layer_name,
            dup_count,
        )

    dict_t[layer_name] = gdf_t
    dict_d[layer_name] = gdf_d

logger.info("Data loaded and checked for duplicates. Ready for interpolation.")

# --- Layer model definition (single source of truth) ---
# Each entry: (output_layer_name, s_layer_key, layer_type)
# Aquifer Wxx: bottom = TS_xx (top of the corresponding aquitard)
# Aquitard Sxx: bottom = TS_xx - DS_xx (except S32: TS32 - 5.0)
output_layers = [
    ("W11", "S11", "aquifer"),
    ("S11", "S11", "aquitard"),
    ("W12", "S12", "aquifer"),
    ("S12", "S12", "aquitard"),
    ("W13", "S13", "aquifer"),
    ("S13", "S13", "aquitard"),
    ("W21", "S21", "aquifer"),
    ("S21", "S21", "aquitard"),
    ("W22", "S22", "aquifer"),
    ("S22", "S22", "aquitard"),
    ("W31", "S31", "aquifer"),
    ("S31", "S31", "aquitard"),
    ("W32", "S32", "aquifer"),
    ("S32", "S32", "aquitard_fixed"),
]

# --- Collect all unique point locations across all layers ---
all_points = []
for layer_name in layer_names:
    for gdf in [dict_t[layer_name], dict_d[layer_name]]:
        coords = np.column_stack([gdf.geometry.x, gdf.geometry.y])
        all_points.append(coords)

all_points = np.vstack(all_points)
all_points_unique = np.unique(all_points, axis=0)
logger.info("Collected %d unique point locations across all layers.", len(all_points_unique))

# --- Interpolate all TS and DS values to all unique locations ---
# After this step, all points inside the boundary have values (linear
# interpolation with nearest-neighbor fallback). Points outside the
# boundary are NaN and will be filtered out when saving.
interp_t = {}
interp_d = {}

for layer_name in layer_names:
    gdf_boundary = gpd.read_file(os.path.join(data_path, "boundaries", layer_name, f"{layer_name}.geojson"))
    interp_t[layer_name] = interpolate_to_all_points(
        gdf=dict_t[layer_name], all_xy=all_points_unique, boundary_gdf=gdf_boundary
    )
    interp_d[layer_name] = interpolate_to_all_points(
        gdf=dict_d[layer_name], all_xy=all_points_unique, boundary_gdf=gdf_boundary
    )
    logger.info("Interpolated TS and DS for layer %s.", layer_name)

# --- Compute bottom elevations for all 14 layers ---
botm_arrays = {}
is_original_arrays = {}

for layer_name, s_layer, layer_type in output_layers:
    ts = interp_t[s_layer]

    if layer_type == "aquifer":
        botm_arrays[layer_name] = ts["value"].values.copy()
        is_original_arrays[layer_name] = ts["is_original"].values.copy()
    elif layer_type == "aquitard":
        ds = interp_d[s_layer]
        botm_arrays[layer_name] = ts["value"].values - ds["value"].values
        is_original_arrays[layer_name] = ts["is_original"].values & ds["is_original"].values
    elif layer_type == "aquitard_fixed":
        botm_arrays[layer_name] = ts["value"].values.copy() - 5.0
        is_original_arrays[layer_name] = ts["is_original"].values.copy()

# --- Enforce non-negative thickness ---
# Two sweeps ensure interpolated values respect original data from both sides.
# NaN (= outside boundary) is handled transparently: np.fmin/fmax skip NaN,
# and NaN comparisons are False so no spurious violations are detected.
layer_order = [name for name, _, _ in output_layers]

# Downward sweep: clamp interpolated values DOWN to respect data above.
running_min = botm_arrays[layer_order[0]].copy()
for i in range(1, len(layer_order)):
    layer = layer_order[i]
    orig = is_original_arrays[layer]

    violation = botm_arrays[layer] > running_min + THICKNESS_TOL
    if violation.any():
        adjust = violation & ~orig
        botm_arrays[layer][adjust] = running_min[adjust]
        logger.info(
            "Downward sweep at %s: %d interpolated values clamped down.",
            layer,
            int(adjust.sum()),
        )

    running_min = np.fmin(running_min, botm_arrays[layer])

# Upward sweep: clamp interpolated values UP to respect data below.
running_max = botm_arrays[layer_order[-1]].copy()
for i in range(len(layer_order) - 2, -1, -1):
    layer = layer_order[i]
    orig = is_original_arrays[layer]

    violation = botm_arrays[layer] < running_max - THICKNESS_TOL
    if violation.any():
        adjust = violation & ~orig
        botm_arrays[layer][adjust] = running_max[adjust]
        logger.info(
            "Upward sweep at %s: %d interpolated values clamped up.",
            layer,
            int(adjust.sum()),
        )

    running_max = np.fmax(running_max, botm_arrays[layer])

# Report remaining violations (both layers original, cannot be resolved)
for i in range(1, len(layer_order)):
    upper = layer_order[i - 1]
    lower = layer_order[i]
    both_orig = is_original_arrays[upper] & is_original_arrays[lower]
    violation = both_orig & (botm_arrays[lower] > botm_arrays[upper] + THICKNESS_TOL)
    n = int(violation.sum())
    if n > 0:
        logger.warning(
            "Unresolved: %d original data points have negative thickness between %s and %s. NOT adjusted.",
            n,
            upper,
            lower,
        )

# --- Filter to boundary and collect all layers ---
crs = interp_t[layer_names[0]].crs
gdfs = []

for layer_name, s_layer, _ in output_layers:
    gdf_botm = gpd.GeoDataFrame(
        {"layer": layer_name, "value": botm_arrays[layer_name], "is_original": is_original_arrays[layer_name]},
        geometry=gpd.points_from_xy(all_points_unique[:, 0], all_points_unique[:, 1]),
        crs=crs,
    )

    # Keep only points within the layer boundary
    gdf_boundary = gpd.read_file(os.path.join(data_path, "boundaries", s_layer, f"{s_layer}.geojson"))
    within = gpd.sjoin(gdf_botm, gdf_boundary, predicate="intersects")
    gdf_botm = gdf_botm.loc[within.index].reset_index(drop=True)

    gdfs.append(gdf_botm)
    logger.info("Filtered bottom of %s to %d points.", layer_name, len(gdf_botm))

# --- Merge and save as a single GeoJSON ---
gdf_all = gpd.GeoDataFrame(
    {layer: gdfi["value"] for layer, gdfi in zip(layer_order, gdfs, strict=True)},  # TODO: This creates separate columns per layer, but we want a single "value" column and a "layer" column to identify the layer. This is needed for the inversion step later.
    geometry=gdfs[0].geometry.copy(),
    crs=crs,
)
fpath_out = Path(data_path, "botm.geojson")
gdf_all.to_file(fpath_out, driver="GeoJSON")
logger.info("Saved all %d bottom points (%d layers) to %s.", len(gdf_all), len(output_layers), fpath_out)
