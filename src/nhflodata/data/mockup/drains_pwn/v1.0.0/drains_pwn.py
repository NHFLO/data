from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from nhflotools.geoconverter.utils import round_bounds, validate_crs, validate_geometry

from nhflodata import get_abs_data_path

columns_to_keep = [
    "name",
    "elevation",  # Elevation of the bottom of the drain
    "conductance_per_meter",
    "conductance_per_squared_meter",
    "bgt-identificatie",
    "mover_lake_name",
    "comment",
    "geometry",
]

# %% Create line drains input
gdf_dir = get_abs_data_path("drains_en_damwand_bergen")
gdf = gpd.read_file(gdf_dir / "drains_en_damwand_bergen.geojson")
gdf = gdf.loc[gdf.naam.str.startswith("drain")]
gdf["elevation"] = gdf[["diepte_van", "diepte_tot"]].min(axis=1)
gdf = gdf.rename(columns={"naam": "name", "opmerking": "comment"})

# Add conductances
# m3/day per meter head difference per meter drain length
gdf["conductance_per_meter"] = 1.0  # Default conductance
gdf["conductance_per_squared_meter"] = np.nan  # Default conductance for open water
gdf["bgt-identificatie"] = ""  # Placeholder for BGT identification
gdf["mover_lake_name"] = ""  # Placeholder for mover lake boundary name, to move drained water to.
gdf = gdf[columns_to_keep]

# %% Add open water drainage
# m3/day per meter head difference  per squaredd meter
bergen_oppwater_path = get_abs_data_path("oppervlaktewater_bergen")
oppwater = gpd.read_file(bergen_oppwater_path / "oppervlaktewater_bergen.geojson")

open_water_drainage = oppwater.loc[oppwater["naam"].eq("bassin")]
gdf = pd.concat(
    (
        gdf,
        gpd.GeoDataFrame(
            data={
                "name": open_water_drainage["naam"],
                "elevation": open_water_drainage["peil_circa"],
                "comment": "",
                "geometry": open_water_drainage["geometry"],
                "conductance_per_meter": np.nan,  # Default conductance for open water
                "conductance_per_squared_meter": 1.0,  # Default conductance for open water
                "bgt-identificatie": "",
                "mover_lake_name": "vijver 4",
            }
        ),
    ),
    axis=0,
    ignore_index=True,
)

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
