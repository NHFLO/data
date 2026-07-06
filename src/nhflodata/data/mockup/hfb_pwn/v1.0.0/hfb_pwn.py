from pathlib import Path

import geopandas as gpd
import numpy as np
from nhflotools.geoconverter.utils import round_bounds, validate_crs, validate_geometry

from nhflodata import get_abs_data_path

# Properties are those consumed by nlmod.gwf.hfb.get_hfb_spd(ds, linestrings, hydchr,
# depth=None, elevation=None), which places a horizontal flow barrier on the cell faces
# crossed by the line and spans the model layers vertically:
#   - hydchr:    hydraulic characteristic of the barrier [1/day]; 1/100 == resistance of 100 days.
#   - depth:     depth of the barrier below groundlevel [m, positive]; the top is at groundlevel.
#   - elevation: alternative to depth: absolute elevation of the barrier BOTTOM [m NAP].
# Use either depth or elevation (not both); here depth is populated and elevation left null.
columns_to_keep = [
    "name",
    "hydchr",
    "depth",
    "elevation",
    "comment",
    "geometry",
]

# %% Create horizontal flow barrier (sheet pile wall / "damwand") input
# The damwand features live in the same source dataset as the drains.
gdf_dir = get_abs_data_path("drains_en_damwand_bergen")
gdf = gpd.read_file(gdf_dir / "drains_en_damwand_bergen.geojson")
gdf = gdf.loc[gdf.naam.str.startswith("damwand")]
gdf = gdf.rename(columns={"naam": "name", "opmerking": "comment"})
gdf["comment"] = gdf["comment"].fillna("")

# diepte_van/diepte_tot are DEPTHS below groundlevel (negative = downward), so the barrier is
# defined by its construction depth, not by an absolute elevation. `depth` is the deepest extent
# below groundlevel as a POSITIVE number of metres -- exactly what nlmod.gwf.hfb.get_hfb_spd
# expects: the barrier top sits at groundlevel and extends `depth` metres straight down.
# `elevation` (absolute m NAP) is therefore left null; get_hfb_spd requires exactly one of the two.
#
# Deliberate modelling choice: representing the wall by construction depth (not an absolute tie-in)
# means that where the ground surface is high (dunes; AHN up to ~7.5 m NAP along this alignment)
# the wall bottom stays above the veen/SDL aquitard (0/-5 m NAP) and provides little cutoff there.
# This is intended -- the damwand is its physical 5 m of sheet pile, not forced down to the aquitard.
gdf["depth"] = -gdf[["diepte_van", "diepte_tot"]].min(axis=1)
gdf["elevation"] = np.nan

# Hydraulic characteristic [1/day]. Bergen model (04v2pwnbergenmodel) used 1/100,
# i.e. a resistance of 100 days for a unit gradient.
gdf["hydchr"] = 1.0 / 100.0

gdf = gdf[columns_to_keep]

# Checks
validate_crs(gdf)
for idx, geom in enumerate(gdf.geometry):
    is_valid, error = validate_geometry(geom)
    if not is_valid:
        msg = f"Geometry at index {idx} is invalid: {error}"
        raise ValueError(msg)

out_geojson = Path(__file__).parent / "hfb_pwn.geojson"
gdf[columns_to_keep].to_file(out_geojson, driver="GeoJSON", write_bbox=True, coordinate_precision=2)

bounds = dict(zip(["minx", "miny", "maxx", "maxy"], gdf.total_bounds, strict=False))
print("extent:", round_bounds(bounds, rounding_interval=1000.0).values())  # noqa: T201
