"""Creates a convex hull around the interpolation points of each layer. This 
prevents extrapolation outside the area with data.

"""

import sys
from pathlib import Path

# Add src directory to path so nhflodata module can be found
src_path = Path(__file__).resolve().parents[6]
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import geopandas as gpd
import pandas as pd

from nhflodata.get_paths import get_abs_data_path

buffer_width = 10. # m

data_dir = get_abs_data_path("bodemlagen_pwn_2024", "3.0.0")
layer_names = ["S11", "S12", "S13", "S21A", "S21", "S22", "S31", "S32"]

for name in layer_names:
    fpath = data_dir / "dikte_aquitard" / f"D{name}" / f"D{name}_union_with_values_edited.geojson"
    gdf_thk = gpd.read_file(fpath)

    fpath = data_dir / "top_aquitard" / f"T{name}" / f"T{name}_union_with_values_edited.geojson"
    gdf_top = gpd.read_file(fpath)

    gdf = pd.concat([gdf_thk, gdf_top])
    gdf = gdf.dissolve().buffer(buffer_width)

    gdf_out = gpd.GeoDataFrame(
        geometry=gdf.convex_hull.values,
        data={"layer": [name]},
        crs="EPSG:28992"
    )

    fpath = data_dir / "boundaries" / name / f"{name}.geojson"
    gdf_out.to_file(fpath, driver="GeoJSON")
