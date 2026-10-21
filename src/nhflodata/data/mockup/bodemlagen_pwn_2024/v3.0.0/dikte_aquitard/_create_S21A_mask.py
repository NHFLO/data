"""Generate mask for S21A, which was not mapped by Koster
but occurs in the Bergen area (Kreftenheye Fm. k1)
"""

import sys
from pathlib import Path

# Add src directory to path so nhflodata module can be found
src_path = Path(__file__).resolve().parents[6]
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import geopandas as gpd
import pandas as pd
from shapely import box

from nhflodata.get_paths import get_abs_data_path

data_dir = get_abs_data_path("bodemlagen_pwn_2024", "3.0.0")

name = "S21A"

koster_mask = box(100_000, 497_000, 109_000, 515_000)

fp_stuyfzand = data_dir / "dikte_aquitard" / f"D{name}" / f"D{name}_mask_bergen_area.geojson"
stuyfzand_mask = gpd.read_file(fp_stuyfzand, columns=["geometry", "value"])

# Use same field name and value as Koster did (for consistency, even though
# this might be confusing since Koster did not create this map himself but
# we're creating it here)
gdf = gpd.GeoDataFrame(
    data={"VALUE": [0.01]}, 
    geometry=[koster_mask],
    crs=28992,
)
gdf = gdf.difference(stuyfzand_mask)

fp_mask = data_dir / "dikte_aquitard" / f"D{name}" / f"D{name}_mask.geojson"
gdf.to_file(fp_mask)