"""Merges the masks of the aquitard thickness layers from Koster (1997) and Stuyfzand (1970) into a single file.

These masks indicate the absence of an aquitard layer.

Open concerns from Edinsi Groundwater report (Vincent Post, Aug 2024):
- [Edinsi 3.1, p.12] Edinsi notes DS21.shp: the 0.01m polygon (indicating layer
  absence) is inaccurate — it sometimes has gaps or overlaps with other polygons.
- [Edinsi 3.1, p.12] Edinsi notes DS22.shp: the 7.5m thickness contour has a
  strange shape and overlaps with the area where the layer doesn't exist.
- [Edinsi 3.1, p.13] Edinsi notes DS11.shp: duplicate polygons in the north —
  two polygons (0.13 and 0.38m) are covered by 0.01m polygons suggesting layer
  absence according to Koster (1997).
"""

import geopandas as gpd
import pandas as pd

from nhflodata.get_paths import get_abs_data_path

data_dir = get_abs_data_path("bodemlagen_pwn_2024", "1.0.0")
layer_names = ["S11", "S12", "S13", "S21", "S22", "S31", "S32"]

# Load the masks
for name in layer_names:
    # dikte aquitard
    fp_koster = data_dir / "dikte_aquitard" / f"D{name}" / f"D{name}_mask.geojson"
    koster_mask = gpd.read_file(fp_koster, columns=["geometry", "VALUE"])
    koster_mask["source"] = "Koster (1997)"
    koster_mask = koster_mask.rename(columns={"VALUE": "value"})

    fp_out = data_dir / "dikte_aquitard" / f"D{name}" / f"D{name}_mask_combined.geojson"
    fp_stuyfzand = data_dir / "dikte_aquitard" / f"D{name}" / f"D{name}_mask_bergen_area.geojson"
    if fp_stuyfzand.exists():
        stuyfzand_mask = gpd.read_file(fp_stuyfzand, columns=["geometry", "value"])
        stuyfzand_mask["source"] = "Stuyfzand (1970)"

        # Combine the masks
        pd.concat((koster_mask, stuyfzand_mask)).to_file(
            data_dir / "dikte_aquitard" / f"D{name}" / f"D{name}_mask_combined.geojson",
            driver="GeoJSON",
        )

    else:
        koster_mask.to_file(
            fp_out,
            driver="GeoJSON",
        )
