"""Create Lakes input file for dunes."""

import geopandas as gpd
from nhflotools.geoconverter.geoconverter import GeoConverter
from nhflotools.geoconverter.utils import round_bounds, validate_crs, validate_geometry
from nlmod.gwf.lake import LAKE_KWDS, OUTLET_DEFAULT

from nhflodata.get_paths import get_abs_data_path

data_path_bergen_vijvers = get_abs_data_path(name="oppervlaktewater_bergen", version="latest", location="get_from_env")
gdf_bergen_vijvers = gpd.read_file(data_path_bergen_vijvers / "oppervlaktewater_bergen.geojson")

# Create an empty GeoDataFrame for lakes. lakeno is the index
columns = ["identificatie", "strt", "clake", *LAKE_KWDS, "lakeout", *list(OUTLET_DEFAULT)]
dtypes = {
    "identificatie": "str",
    "strt": "float",
    "clake": "float",
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
gdf_lake["strt"] = gdf_bergen_vijvers["peil_circa"]
gdf_lake["clake"] = 10.0  # days
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
