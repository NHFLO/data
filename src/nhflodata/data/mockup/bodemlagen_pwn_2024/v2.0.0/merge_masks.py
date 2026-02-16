"""Merges the masks of the aquitard thickness layers from Koster (1997) and Stuyfzand (1970) into a single file."""

from pathlib import Path

import geopandas as gpd
import pandas as pd

data_dir = Path("/Users/bdestombe/Projects/NHFLO/data/src/nhflodata/data/mockup/bodemlagen_pwn_2024/v1.0.0")
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
