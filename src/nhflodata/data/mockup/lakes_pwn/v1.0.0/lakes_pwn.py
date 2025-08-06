"""Create Lakes input file for dunes."""

from pathlib import Path

import geopandas as gpd
from nhflotools.geoconverter.utils import round_bounds, validate_crs, validate_geometry
from nlmod.gwf.lake import LAKE_KWDS, OUTLET_DEFAULT
import pandas as pd

from nhflodata.get_paths import get_abs_data_path

data_path_bergen_vijvers = get_abs_data_path(name="oppervlaktewater_bergen", version="latest", location="get_from_env")
data_path_vlotter_lakes = get_abs_data_path(name="Lakes_Vlotter", version="latest", location="get_from_env")
data_path_vlotter_bgt = get_abs_data_path(name="Oppervlaktewater_Vlotter", version="latest", location="get_from_env")
# %% Read Bergen vijvers
gdf_bergen_vijvers = gpd.read_file(data_path_bergen_vijvers / "oppervlaktewater_bergen.geojson")

# BGT identificatie - PWN identificatie koppeltabel
bgt_id = {
    # Bergen
    "vijver 1, 2 en 3": "W0651.865c8d7a2be84961826f052b681a7f63;W0651.be0fc7d4ecbd4459932a17fc38797f07;W0651.4422eb7cde924cfc9392959423afbcb5",
    "vijver 4": "W0651.729e81ab73374e9fa70abf139251f923",
    "libellenpoel": "G0373.9f930048a0ee488fabf6e822fdac4994",
    "boringkanaal B": "G0373.0ca7da473d004ccc84317497348b62f7;G0373.44d141555adc43498f67443c267694c6;G0373.dee82e56db11492eb475a822514bcec5;G0373.ee58e91c92b44316b7ab734d485a864d;G0373.3905b70fd5d24d888932edf1489f33d2;W0651.91036ab15e7d4dceb81dca0baf6760a3",
    "boringkanaal C": "G0373.e498c5cf32684b95a260151eb58e1fd1;G0373.dcecefc3ff6d4ddcb6951bf7c300f556;G0373.29b5a08aae3e48d6a2a39ae5a3a1faa3",
    "Guurtjeslaan": "G0373.3b8d111efde54846bf2f01152e176e74;G0373.bc1e0539b4ad4669912a452acae8a003",
}
strt = {
    # Bergen
    "vijver 1, 2 en 3": 2.85,
    "vijver 4": 3.30,
    "libellenpoel": 1.92,
    "boringkanaal_libell": 2.10,
    "boringkanaal B": 2.37,
    "boringkanaal C": 2.46,
    "Guurtjeslaan": 2.23,
}
botms = {
    # Bergen
    "vijver 1, 2 en 3": 0.85,
    "vijver 4": 1.30,
    "libellenpoel": 0.92,
    "boringkanaal_libell": 1.10,
    "boringkanaal B": 1.37,
    "boringkanaal C": 1.46,
    "Guurtjeslaan": 1.23,
}

# Create an empty GeoDataFrame for lakes. lakeno is the index
dtypes = {
    "identificatie": "str",
    "strt": "float",
    "clake": "float",
    "botm": "float",  # Lakes are located on top of the top cells. Adjust top cell elevation to the bathymetry.
    "bgt-identificatie": "str",
    **{kwd: "str" for kwd in LAKE_KWDS},
    "lakeout": "str",
    **{kwd: "float" for kwd in OUTLET_DEFAULT},
}
columns = list(dtypes.keys())
dtypes["couttype"] = "str"  # Special case for couttype, which is not in OUTLET_DEFAULT
dtypes["outlet_invert"] = "float"

gdf_bergen = gpd.GeoDataFrame(
    columns=columns,
    geometry=gdf_bergen_vijvers.geometry,
    crs=gdf_bergen_vijvers.crs,
    dtype=str,
).astype(dtype=dtypes)

# Fill the gdf with data from Bergen
gdf_bergen["identificatie"] = gdf_bergen_vijvers["naam"]
gdf_bergen.replace(
    {
        "identificatie": {
            "vijver 1": "vijver 1, 2 en 3",
            "vijver 2": "vijver 1, 2 en 3",
            "vijver 3": "vijver 1, 2 en 3",
            "Guurtjeslaan1": "Guurtjeslaan",
            "Guurtjeslaan2": "Guurtjeslaan",
        }
    },
    inplace=True,
)
gdf_bergen = gdf_bergen.dissolve("identificatie", as_index=False, aggfunc="first", sort=True)

gdf_bergen["bgt-identificatie"] = gdf_bergen.identificatie.map(bgt_id)
gdf_bergen["strt"] = gdf_bergen.identificatie.map(strt)
gdf_bergen["clake"] = 10.0  # days
gdf_bergen["botm"] = gdf_bergen.identificatie.map(botms)
gdf_bergen.loc[gdf_bergen.identificatie == "vijver 4", "lakeout"] = "Guurtjeslaan"
gdf_bergen.loc[gdf_bergen.identificatie == "vijver 4", "couttype"] = "WEIR"
gdf_bergen.loc[gdf_bergen.identificatie == "vijver 4", "outlet_invert"] = gdf_bergen.loc[
    gdf_bergen.identificatie == "vijver 4", "strt"
]
gdf_bergen.loc[gdf_bergen.identificatie == "vijver 4", "outlet_width"] = 1.0
gdf_bergen.loc[gdf_bergen.identificatie == "vijver 4", "outlet_rough"] = 0.0
gdf_bergen.loc[gdf_bergen.identificatie == "vijver 4", "outlet_slope"] = 0.0


# %% Process Vlotter lakes
# Find removed bgt identifiers
# Visual inspection led to the conclusion that the open waters near the vlotter were removed.
# Manually downloaded the BGT data and selected the polygons near vlotter as centroids were all different and shapes have changed.

# extent = bgt_before.total_bounds[[0, 2, 1, 3]]
# bgt_now = nlmod.read.bgt.download_bgt(
#     extent=extent,
#     layer="waterdeel",
#     cut_by_extent=False,
#     make_valid=False,
#     fname=None,
#     geometry=None,
#     remove_expired=False,
#     add_bronhouder_names=False,
#     timeout=1200,
# )

bgt_before = gpd.read_file(data_path_vlotter_bgt / "Oppervlaktewater_Vlotter_voor_herinrichting.geojson")
bgt_after = gpd.read_file(data_path_vlotter_bgt / "Oppervlaktewater_Vlotter.geojson")
bgt_removed = gpd.read_file(Path(__file__).parent / "removed_bgt_vlotter.geojson")

bgt_removed_identifiers = ";".join(bgt_removed.identificatie)

gdf_vlotter_lakes_sweco = gpd.read_file(data_path_vlotter_lakes / "lakes_vlotter.geojson")

# Create an empty GeoDataFrame for vlotter lakes
gdf_vlotter = gpd.GeoDataFrame(
    columns=columns,
    geometry=gdf_vlotter_lakes_sweco.geometry,
    crs=gdf_vlotter_lakes_sweco.crs,
)
gdf_vlotter["clake"] = gdf_vlotter_lakes_sweco["clake"]
gdf_vlotter["identificatie"] = gdf_vlotter_lakes_sweco["lakeno"].map(lambda s: f"Vlotter {s}")
gdf_vlotter["botm"] = gdf_vlotter_lakes_sweco["Max stage"] - 0.5
gdf_vlotter["strt"] = gdf_vlotter_lakes_sweco["Max stage"]
gdf_vlotter.loc[gdf_vlotter_lakes_sweco["lakeno"] == 0, "lakeout"] = "-1"
gdf_vlotter.loc[gdf_vlotter_lakes_sweco["lakeno"] == 1, "lakeout"] = gdf_vlotter[gdf_vlotter_lakes_sweco["lakeno"] == 0]["identificatie"]
gdf_vlotter.loc[gdf_vlotter_lakes_sweco["lakeno"] == 2, "lakeout"] = gdf_vlotter[gdf_vlotter_lakes_sweco["lakeno"] == 0]["identificatie"]
gdf_vlotter.loc[gdf_vlotter_lakes_sweco["lakeno"] == 3, "lakeout"] = gdf_vlotter[gdf_vlotter_lakes_sweco["lakeno"] == 1]["identificatie"]
gdf_vlotter["couttype"] = gdf_vlotter_lakes_sweco.couttype
gdf_vlotter["outlet_invert"] = gdf_vlotter_lakes_sweco["Max stage"]
gdf_vlotter["outlet_width"] = gdf_vlotter_lakes_sweco["width"]
gdf_vlotter["outlet_rough"] = gdf_vlotter_lakes_sweco["rough"] / 5
gdf_vlotter["outlet_slope"] = gdf_vlotter_lakes_sweco["slope"]

# Relate all the removed bgt features to the largest lake (lakeno 1)
gdf_vlotter.loc[gdf_vlotter_lakes_sweco["lakeno"] == 1, "bgt-identificatie"] = bgt_removed_identifiers

# %% Checks and store
gdf = pd.concat([gdf_bergen, gdf_vlotter], ignore_index=True)

validate_crs(gdf)
for idx, geom in enumerate(gdf.geometry):
    is_valid, error = validate_geometry(geom)
    if not is_valid:
        msg = f"Geometry at index {idx} is invalid: {error}"
        raise ValueError(msg)

# Metadata
bounds = dict(zip(["minx", "miny", "maxx", "maxy"], gdf.total_bounds, strict=False))
print("extent:", round_bounds(bounds, rounding_interval=1000.0).values())  # noqa: T201

# Export to sanitized GeoJSON
gdf = gdf.astype(dtypes)
gdf[gdf.eq("nan")] = ""
gdf[gdf.eq("None")] = ""

# Checks
validate_crs(gdf)
for idx, geom in enumerate(gdf.geometry):
    is_valid, error = validate_geometry(geom)
    if not is_valid:
        msg = f"Geometry at index {idx} is invalid: {error}"
        raise ValueError(msg)

out_geojson = Path(__file__).parent / "lakes_pwn.geojson"
gdf.to_file(out_geojson, driver="GeoJSON", write_bbox=True, coordinate_precision=2)
