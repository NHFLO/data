from pathlib import Path

import geopandas as gpd
from nhflotools.geoconverter.utils import round_bounds, validate_crs, validate_geometry

from nhflodata import get_abs_data_path

gdf_dir = get_abs_data_path("drains_en_damwand_bergen")
gdf = gpd.read_file(gdf_dir / "drains_en_damwand_bergen.geojson")
gdf = gdf.loc[gdf.naam.str.startswith("drain")]
gdf["elevation"] = gdf[["diepte_van", "diepte_tot"]].min(axis=1)
gdf = gdf.rename(columns={"naam": "name", "opmerking": "comment"})
columns_to_keep = [
    "name",
    "elevation",  # Elevation of the bottom of the drain
    "comment",
    "geometry",
]
gdf = gdf[columns_to_keep]

# Add conductances
# m3/day per meter head difference per meter drain length
gdf["conductance_per_meter"] = 1.0  # Default conductance

# Checks
validate_crs(gdf)
for idx, geom in enumerate(gdf.geometry):
    is_valid, error = validate_geometry(geom)
    if not is_valid:
        msg = f"Geometry at index {idx} is invalid: {error}"
        raise ValueError(msg)

out_geojson = Path(__file__).parent / "drains_pwn.geojson"
gdf[columns_to_keep].to_file(out_geojson, driver="GeoJSON", write_bbox=True, coordinate_precision=2)

bounds = dict(zip(["minx", "miny", "maxx", "maxy"], gdf.total_bounds, strict=False))
print("extent:", round_bounds(bounds, rounding_interval=1000.0).values())  # noqa: T201
