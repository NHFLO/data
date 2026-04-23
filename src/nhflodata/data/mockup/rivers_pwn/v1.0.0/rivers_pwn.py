import logging
import os
import pathlib

import flopy
import geopandas as gpd
import matplotlib as mpl
import nlmod
import numpy as np
import pandas as pd
import xarray as xr
from nhflotools.major_surface_waters import (
    chd_ghb_from_major_surface_waters,
    get_chd_ghb_data_from_major_surface_waters,
)
from nhflotools.pwnlayers.layers import get_pwn_layer_model, get_top_from_ahn
from nhflotools.well import get_wells_pwn_dataframe
from overlap import create_overlap_matrix

from nhflodata.get_paths import get_abs_data_path

data_path_panden = get_abs_data_path(
    name="oppervlaktewater_pwn_shapes_panden", version="latest", location="get_from_env"
)

panden = gpd.read_file(data_path_panden / "Panden_ICAS_IKIEF.shp")

# panden.set_index("Naam", inplace=True)
extent = panden.total_bounds[[0, 2, 1, 3]]
bgt = nlmod.read.bgt.download_bgt(
    extent,
    layer="waterdeel",
    cut_by_extent=True,
    make_valid=False,
    fname=None,
    geometry=None,
    remove_expired=True,
    add_bronhouder_names=True,
    timeout=1200,
)
# bgt.set_index("identificatie", inplace=True)
out = create_overlap_matrix(bgt, panden, id_a="identificatie", id_b="Naam", as_pivot=True)
assert ((out > 0.5).sum(axis=1) == 1).all(), "Not all BGT features are uniquely matched to PANDEN features. Adjust the code below. Matrix is correct."
out = create_overlap_matrix(bgt, panden, id_a="identificatie", id_b="Naam", as_pivot=False)
bgt_mask = out["overlap_pct"] > 0.5
bgt_mask = bgt.identificatie.isin(out.identificatie)

gdf = bgt[bgt_mask].copy()
gdf["bgt-identificatie"] = gdf.identificatie
gdf["identificatie"] = out.set_index("identificatie").loc[gdf["bgt-identificatie"]].Naam.values
gdf.loc[gdf["identificatie"] == "VIJVER", "identificatie"] = "VIJVER PS Mensink"
gdf.loc[gdf["identificatie"].str.contains("ICAS"), "stage"] = 2.85
gdf.loc[gdf["identificatie"].str.contains("IKIEF"), "stage"] = 5.85
gdf.loc[gdf["identificatie"] == "VIJVER PS Mensink", "stage"] = 2.0  # Vijver PS Mensink
gdf["rbot"] = gdf.stage - 1.0
gdf["bed_resistance"] = 5.0  # days




fig, ax = nlmod.plot.get_map(extent)
# bgt[bgt_mask].plot(ax=ax, facecolor="blue", edgecolor="none", label="bgt is in pand")
# bgt[~bgt_mask].plot(ax=ax, facecolor="red", edgecolor="none", label="bgt is not in pand")
# panden.plot(ax=ax, facecolor="none", edgecolor="black")
gdf[gdf["identificatie"] == "VIJVER"].geometry.plot(ax=ax, color="red", label="VIJVER stage")
ax.legend()
