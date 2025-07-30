"""Create Lakes input file for dunes."""

import geopandas as gpd
import pandas as pd
from nhflotools.geoconverter.geoconverter import GeoConverter
from nhflotools.geoconverter.utils import round_bounds, validate_crs, validate_geometry
from nlmod.gwf.lake import LAKE_KWDS, OUTLET_DEFAULT

from nhflodata.get_paths import get_abs_data_path

data_path_bergen_vijvers = get_abs_data_path(name="oppervlaktewater_bergen", version="latest", location="get_from_env")
gdf_bergen_vijvers = gpd.read_file(data_path_bergen_vijvers / "oppervlaktewater_bergen.geojson")
mask = ~gdf_bergen_vijvers["naam"].str.contains("bassin|droge stort", case=False, na=False)
gdf_bergen_vijvers = gdf_bergen_vijvers[mask]  # Bassin is moddeled as drainage cell, not lake. Droge stort modeled as WEL.

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
columns = ["identificatie", "strt", "clake", "botm", "bgt-identificatie", *LAKE_KWDS, "lakeout", *list(OUTLET_DEFAULT)]
dtypes = {
    "identificatie": "str",
    "strt": "float",
    "clake": "float",
    "botm": "float",  # Lakes are located on top of the top cells. Adjust top cell elevation to the bathymetry.
    "bgt-identificatie": "str",
    "lakeout": "str",
    **{kwd: "str" for kwd in LAKE_KWDS},
    **{kwd: "float" for kwd in OUTLET_DEFAULT},
}
dtypes["couttype"] = "str"  # Special case for couttype, which is not in OUTLET_DEFAULT
dtypes["outlet_invert"] = "float"

gdf_lake = gpd.GeoDataFrame(
    columns=columns,
    geometry=gdf_bergen_vijvers.geometry,
    crs=gdf_bergen_vijvers.crs,
)

# Fill the gdf with data from Bergen
gdf_lake["identificatie"] = gdf_bergen_vijvers["naam"]
gdf_lake["bgt-identificatie"] = gdf_lake.identificatie.map(bgt_id)
gdf_lake["strt"] = gdf_bergen_vijvers["peil_circa"].replace(-9999.0, pd.NA)
gdf_lake["clake"] = 10.0  # days
gdf_lake["botm"] = gdf_lake.identificatie.map(botms)
gdf_lake.loc[gdf_lake.identificatie == "vijver 4", "lakeout"] = "Guurtjeslaan"
gdf_lake.loc[gdf_lake.identificatie == "vijver 4", "couttype"] = "WEIR"
gdf_lake.loc[gdf_lake.identificatie == "vijver 4", "outlet_invert"] = gdf_lake.loc[
    gdf_lake.identificatie == "vijver 4", "strt"
]
gdf_lake.loc[gdf_lake.identificatie == "vijver 4", "outlet_width"] = 1.0
gdf_lake.loc[gdf_lake.identificatie == "vijver 4", "outlet_rough"] = 0.0
gdf_lake.loc[gdf_lake.identificatie == "vijver 4", "outlet_slope"] = 0.0

gdf_lake.replace(
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
gdf_lake = gdf_lake.dissolve("identificatie", as_index=False, aggfunc="first", sort=True)

# Checks
validate_crs(gdf_lake)
for idx, geom in enumerate(gdf_lake.geometry):
    is_valid, error = validate_geometry(geom)
    if not is_valid:
        msg = f"Geometry at index {idx} is invalid: {error}"
        raise ValueError(msg)

# Metadata
bounds = dict(zip(["minx", "miny", "maxx", "maxy"], gdf_lake.total_bounds, strict=False))
print("extent:", round_bounds(bounds, rounding_interval=1000.0).values())  # noqa: T201

# Export to sanitized GeoJSON
gdf_lake = gdf_lake.astype(dtypes)
gdf_lake.to_file("lakes_pwn.geojson", driver="GeoJSON", write_bbox=True, coordinate_precision=2)
