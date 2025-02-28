import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

gdf_tata_zout = gpd.GeoDataFrame(
    pd.DataFrame(
        data=[
            ["A1", -180.0, -120.0, 1.0, 1.0, Point(0, 1)],
            ["A2", -180.0, -120.0, 1.0, 1.0, Point(0, 1)],
        ],
        columns=["Name", "botm", "top", "Q_Mm3/a", "Q_m3/d", "geometry"],
    ),
    crs="EPSG:28992",
)

# retreives top and botm from the model
gdf_tata_zoet = gpd.GeoDataFrame(
    pd.DataFrame(
        data=[
            ["B1", 1.0, 1.0, Point(0, 1)],
            ["B2", 1.0, 1.0, Point(0, 1)],
        ],
        columns=["Name", "Q_Mm3/a", "Q_m3/d", "geometry"],
    ),
    crs="EPSG:28992",
)

gdf_tata_zout.to_file("tata_zoutwaterbronnen.geojson", driver="GeoJSON")
gdf_tata_zoet.to_file("tata_zoetwaterbronnen.geojson", driver="GeoJSON")

zoet_fp = "/workspaces/NHFLO/models/modelscripts/09pwnmodel2/data/zoetwaterbronnen_tata.shp"
zout_fp = "/workspaces/NHFLO/models/modelscripts/09pwnmodel2/data/zoutwaterbronnen_tata.shp"

zout = gpd.read_file(zout_fp)[["Name", "botm", "top", "Q_Mm3/a", "Q_m3/d", "geometry"]]
zoet = gpd.read_file(zoet_fp)[["Name", "Q_Mm3/a", "Q_m3/d", "geometry"]]

zoetzout = pd.concat((zoet, zout))
print(f"Extent: {zoetzout.total_bounds}")

zout.to_file("tata_zoutwaterbronnen_unaltered.geojson", driver="GeoJSON")
zoet.to_file("tata_zoetwaterbronnen_unaltered.geojson", driver="GeoJSON")
