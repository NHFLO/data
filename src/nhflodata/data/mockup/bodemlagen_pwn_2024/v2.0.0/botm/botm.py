"""Compute bottom elevations of the PWN bodemlagen (layer boundaries) for the NHFLO model.

This script reads contour-line and borehole point data for the seven aquitard
layers (S11, S12, S13, S21, S22, S31, S32) and their overlying aquifers
(W11 … W32), runs a series of quality checks, interpolates all tops and
thicknesses to a common set of point locations, and writes the resulting
bottom-elevation point clouds to a single GeoJSON file ``botm.geojson`` in
``data_path``.

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
   :class:`geopandas.GeoDataFrame` and written as two GeoJSON files:

   * ``botm.geojson``: per-layer ``{layer}`` value columns only, kept
     lean for downstream consumers that just need bottom elevations.
   * ``botm_incl_source.geojson``: the same values plus, for each layer,
     a boolean ``{layer}_is_original`` column (``True`` when the point
     coincides with a source data point — borehole, contour, or synthetic
     zero-thickness mask vertex — and ``False`` when the value comes from
     interpolation) and a ``{layer}_source`` column with the relative
     source file path (or ``"interp"``).

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
from interpolation_helper_functions import (
    combine_sources,
    get_point_values,
    interpolate_to_all_points,
    report_duplicate_geometries,
    report_points_outside_boundary,
    report_unresolved_monotonicity,
    report_value_validity,
    report_zero_mask_violations,
)

from nhflodata.get_paths import get_abs_data_path

if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
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
#
# --- Open concerns from Edinsi Groundwater report ---
# (rapportage_lagenmodel_pwn_concept.pdf, Vincent Post, Aug 2024)
# All recommendations below are from the Edinsi report unless stated otherwise.
#
# TODO: [Edinsi report 2.1, p.6-7] Borehole location differences between Dawaco and Dinoloket
#   (up to 200m, esp. near Castricum). Erroneous registrations for B19C0239 and B19C0806.
#   Systematic coordinate inversion west of Bergen (Uilenvangersweg). Current assumption is
#   that Dawaco locations are correct, but this has not been verified. Edinsi recommends
#   investigating whether these differences have consequences for REGIS.
# TODO: [Edinsi report 3.1, p.12] Depth shapefiles extend west of the coastline (North Sea)
#   because the old Triwaco model assumed layers continue there. Thickness contours for S1.1,
#   S1.3, S3.2 are NOT extended that far, suggesting layers may be absent under the seabed.
#   Edinsi recommends investigating whether layers truly exist under the North Sea and what
#   consequences this has for the groundwater model.
# TODO: [Edinsi report 3.2, p.22-24] Profile analysis shows interpreted borehole thicknesses
#   are often much less than shapefile polygon values. In the deep eastern part (below -40m
#   NAP), piezometric data is limited and layer positions are uncertain.
# TODO: [Edinsi report 4.1, p.32] S2.1 (Eem clay): Edinsi recommends remapping the occurrence
#   of this layer in the eastern part of the Bergen area because REGIS and Dinoloket indicate
#   a much larger extent than Stuyfzand (1989) assumed. Koster (1997) northern boundary is a
#   study area limit, not a geological boundary.
# TODO: [Edinsi report 4.2, p.34-35] S1.3 (Holocene base): The northern boundary w.r.t.
#   Bergen is NOT processed in the new shapefile. Edinsi recommends further investigation.
#   Also, the boundary near Bergen was shifted eastward based on Dinoloket data.
# TODO: [Edinsi report 4.3, p.35] S1.2 (Holocene): SDP 1B was NOT included because the depth
#   polygon for BA1A.shp was missing. Edinsi recommends investigating the extent of the
#   Holocene aquitard in this area. The DI1B polygon with 0.4m thickness was also excluded
#   because its origin is unclear. Also recommends refining geological mapping here.
# TODO: [Edinsi report 4.4, p.36-37] S1.1 (Duinveen): DI2A.shp thickness is 0.2m, lower than
#   Koster's (1997) 1-2m. This causes a thickness jump from 1.5m to 0.2m at the
#   Koster/Bergen boundary. Edinsi recommends a borehole study to connect layers properly.
# TODO: [Edinsi report 6, p.40] Edinsi recommends investigating whether Eem clay splitting
#   into two layers (as in REGIS) is needed instead of the single-unit approach of Koster.
# TODO: [Edinsi report 6, p.40] Edinsi recommends extending maps of S3.2, S3.1, and S2.2
#   northward into the Bergen area. Currently only NHDZ data exists for the deeper layers.

data_path = get_abs_data_path("bodemlagen_pwn_2024", "2.0.0")

# Tolerance for floating point comparisons (meters)
THICKNESS_TOL = 1e-6

# Fixed thickness of S32 (deepest aquitard), meters
S32_FIXED_THICKNESS_M = 5.0

# Names of the layers to be interpolated
layer_names = ["S11", "S12", "S13", "S21", "S22", "S31", "S32"]

dict_t = {}
dict_d = {}
boundaries = {}

for layer_name in layer_names:
    # Create GeoDataFrames with the data points of the top and thicknesses
    gdf_t = get_point_values(path=data_path, layer_name=f"T{layer_name}", dx_zero_vertices_interpolation=50.0)
    gdf_d = get_point_values(path=data_path, layer_name=f"D{layer_name}", dx_zero_vertices_interpolation=50.0)

    # get_point_values concatenates frames without resetting, so the returned index
    # can contain duplicate labels. Reset so later ``.loc[label, ...]`` assignments
    # don't silently mutate unrelated rows that happen to share a label.
    gdf_t = gdf_t.reset_index(drop=True)
    gdf_d = gdf_d.reset_index(drop=True)

    # Test 1a: gdf_t values non-NaN; gdf_d values non-NaN and non-negative.
    report_value_validity(gdf=gdf_t, layer_name=layer_name, is_thickness=False, logger=logger)
    report_value_validity(gdf=gdf_d, layer_name=layer_name, is_thickness=True, logger=logger)

    # Test 1b: All thicknesses should be zero in _mask_combined.geojson.
    mask_name = f"D{layer_name}"
    fp_zero_masks = Path(data_path, "dikte_aquitard", mask_name, f"{mask_name}_mask_combined.geojson")
    gdf_zero_masks = gpd.read_file(fp_zero_masks)

    gdf_d_in_mask = report_zero_mask_violations(
        gdf=gdf_d, gdf_mask=gdf_zero_masks, layer_name=layer_name, logger=logger
    )
    # Clamp values AND overwrite source: these points now reflect the zero-mask
    # polygon, not their original file of origin.
    mask_src = f"dikte_aquitard/D{layer_name}/D{layer_name}_mask_combined.geojson"
    gdf_d.loc[gdf_d_in_mask.index, "value"] = 0  # TODO: This one should not be necessary
    gdf_d.loc[gdf_d_in_mask.index, "source"] = mask_src

    # Test 2: All data points should lie on or inside the boundaries.
    gdf_boundary = gpd.read_file(os.path.join(data_path, "boundaries", layer_name, f"{layer_name}.geojson"))
    boundaries[layer_name] = gdf_boundary

    gdf_t_in_boundary = report_points_outside_boundary(
        gdf=gdf_t, boundary=gdf_boundary, layer_name=layer_name, is_thickness=False, logger=logger
    )
    gdf_t = gdf_t.loc[gdf_t_in_boundary.index.unique()]  # TODO: This one should not be necessary

    gdf_d_in_boundary = report_points_outside_boundary(
        gdf=gdf_d, boundary=gdf_boundary, layer_name=layer_name, is_thickness=True, logger=logger
    )
    gdf_d = gdf_d.loc[gdf_d_in_boundary.index.unique()]  # TODO: This one should not be necessary

    # Test 3: No multiple data points at the exact same location.
    # Dissolve averages the value and pipe-joins unique sources so provenance
    # from every file that contributed to the location is preserved.
    dissolve_agg = {"value": "mean", "source": combine_sources}

    report_duplicate_geometries(gdf=gdf_t, layer_name=layer_name, is_thickness=False, logger=logger)
    gdf_t = gdf_t.dissolve(by=gdf_t.geometry, aggfunc=dissolve_agg).reset_index(
        drop=True
    )  # TODO: This one should not be necessary

    report_duplicate_geometries(gdf=gdf_d, layer_name=layer_name, is_thickness=True, logger=logger)
    gdf_d = gdf_d.dissolve(by=gdf_d.geometry, aggfunc=dissolve_agg).reset_index(
        drop=True
    )  # TODO: This one should not be necessary

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
    gdf_boundary = boundaries[layer_name]
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
source_arrays = {}


def _combine_ts_ds_sources(ts_src, ds_src):
    """Element-wise combine TS and DS source arrays for aquitard Sxx bottoms.

    NaN on either side → NaN (outside boundary); both ``"interp"`` collapse to
    ``"interp"``; otherwise pipe-join the two strings.
    """
    out = np.empty(len(ts_src), dtype=object)
    for i in range(len(ts_src)):
        t = ts_src[i]
        d = ds_src[i]
        t_nan = not isinstance(t, str)
        d_nan = not isinstance(d, str)
        if t_nan or d_nan:
            out[i] = np.nan
        elif t == "interp" and d == "interp":
            out[i] = "interp"
        elif t == d:
            out[i] = t
        else:
            out[i] = f"{t} | {d}"
    return out


for layer_name, s_layer, layer_type in output_layers:
    ts = interp_t[s_layer]

    if layer_type == "aquifer":
        botm_arrays[layer_name] = ts["value"].values.copy()
        is_original_arrays[layer_name] = ts["is_original"].values.copy()
        source_arrays[layer_name] = ts["source"].values.copy()
    elif layer_type == "aquitard":
        ds = interp_d[s_layer]
        botm_arrays[layer_name] = ts["value"].values - ds["value"].values
        is_original_arrays[layer_name] = ts["is_original"].values & ds["is_original"].values
        source_arrays[layer_name] = _combine_ts_ds_sources(ts["source"].values, ds["source"].values)
    elif layer_type == "aquitard_fixed":
        botm_arrays[layer_name] = ts["value"].values.copy() - S32_FIXED_THICKNESS_M
        is_original_arrays[layer_name] = ts["is_original"].values.copy()
        source_arrays[layer_name] = ts["source"].values.copy()

# --- Enforce non-negative thickness ---
# Two sweeps ensure interpolated values respect original data from both sides.
# NaN (= outside boundary) is handled transparently: np.fmin/fmax skip NaN,
# and NaN comparisons are False so no spurious violations are detected.
# Zero-thickness mask points are flagged ``is_original=True`` upstream, so the
# sweeps will never push a "layer absent" point back to a non-zero thickness.
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

# Report remaining violations (both layers original, cannot be resolved).
report_unresolved_monotonicity(
    botm_arrays=botm_arrays,
    is_original_arrays=is_original_arrays,
    layer_order=layer_order,
    tol=THICKNESS_TOL,
    logger=logger,
)

# --- Filter to boundary and collect all layers ---
crs = interp_t[layer_names[0]].crs

# Build the output directly from botm_arrays to preserve spatial alignment.
# Each botm_arrays[layer] is indexed against all_points_unique and already
# contains NaN for points outside the layer boundary (set by
# interpolate_to_all_points).  Per-layer boundary filtering with
# reset_index would destroy the positional correspondence between layers
# (different boundaries exclude different subsets of points, so reset
# indices no longer refer to the same physical location).
gdf_data = {layer: botm_arrays[layer] for layer in layer_order}
gdf_data.update({f"{layer}_is_original": is_original_arrays[layer] for layer in layer_order})
gdf_data.update({f"{layer}_source": source_arrays[layer] for layer in layer_order})
gdf_all = gpd.GeoDataFrame(
    gdf_data,
    geometry=gpd.points_from_xy(all_points_unique[:, 0], all_points_unique[:, 1]),
    crs=crs,
)

# Sanity check: a point flagged ``is_original`` must have a non-NaN value.
# If this fires, a source point ended up outside its layer boundary (or the
# aquitard combination of ts/ds original flags is inconsistent with their
# values), and the invariant underpinning the sweeps no longer holds.
for layer_name in layer_order:
    bad = int((gdf_all[f"{layer_name}_is_original"] & gdf_all[layer_name].isna()).sum())
    if bad:
        msg = f"is_original/value inconsistency for {layer_name}: {bad} row(s) flagged original but value is NaN."
        raise AssertionError(msg)

# Remove points that are outside every layer boundary (all values NaN).
# ``dropna`` is restricted to the value columns — the ``_is_original`` flag
# columns must not influence which rows are dropped.
gdf_all = gdf_all.dropna(subset=layer_order, how="all").reset_index(drop=True)

# Drop interpolation-only rows: points where no output layer is flagged
# ``is_original``. These come from source points that contribute to the union
# of locations but never produce an original botm value — e.g. a DSxx-only
# source point (no paired TSxx original), which makes neither Wxx (needs
# TSxx original) nor Sxx (needs both TSxx and DSxx original) original at
# that location. Such rows carry only interpolated data and would spuriously
# inflate the point cloud.
n_before = len(gdf_all)
original_cols = [f"{layer}_is_original" for layer in layer_order]
is_original_any = np.asarray(gdf_all[original_cols].to_numpy(dtype=bool).any(axis=1), dtype=bool)
gdf_all = gdf_all.loc[is_original_any].reset_index(drop=True)
logger.info(
    "Dropped %d interpolation-only points (kept %d with original data in at least one layer).",
    n_before - len(gdf_all),
    len(gdf_all),
)

for layer_name in layer_order:
    n_valid = int(gdf_all[layer_name].notna().sum())
    n_original = int((gdf_all[layer_name].notna() & gdf_all[f"{layer_name}_is_original"]).sum())
    logger.info(
        "Layer %s: %d valid points in output, of which %d original.",
        layer_name,
        n_valid,
        n_original,
    )

# --- Merge and save as GeoJSON files ---
# ``botm.geojson`` holds only the per-layer value columns to keep the file
# small. The companion ``botm_incl_source.geojson`` carries the full metadata
# (``_is_original`` flags and ``_source`` provenance strings) for consumers
# that need it.
#
# Values are rounded to millimetre precision (3 decimals): it shrinks the
# GeoJSON substantially and honestly communicates that sub-mm digits from
# interpolation are not physically meaningful.
source_cols = [f"{layer}_source" for layer in layer_order]
metadata_cols = original_cols + source_cols

gdf_all[layer_order] = gdf_all[layer_order].round(3)

fpath_out = Path(data_path, "botm.geojson")
gdf_all.drop(columns=metadata_cols).to_file(fpath_out, driver="GeoJSON")
logger.info("Saved all %d bottom points (%d layers) to %s.", len(gdf_all), len(output_layers), fpath_out)

fpath_out_src = Path(data_path, "botm_incl_source.geojson")
gdf_all.to_file(fpath_out_src, driver="GeoJSON")
logger.info(
    "Saved all %d bottom points (%d layers) with source provenance to %s.",
    len(gdf_all),
    len(output_layers),
    fpath_out_src,
)
