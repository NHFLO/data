"""
Boundaries geven aan waar geldige data voor bodemlage_pwn_2024 aanwezig is.

Binnen de boundaries zou je geldige waarden moeten vinden voor de top en dikte van de aquitards.
Aan cell nodes buiten de boundaries moeten nan waarden worden toegekend.

De samenvoeging is gedaan voor de slechtdoorlatende lagen S2.1, S1.3, S1.2 en S1.1. Voor de dieper
gelegen lagen (S3.2, S3.1 en S2.2) bevatten de shapefiles van het Bergen model geen informatie (zie
paragraaf 3.3.6 van report).
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
from nhflotools.geoconverter.geoconverter import GeoConverter, print_results

converter = GeoConverter()

# Convert folder with all files
input_folder = Path("/Users/bdestombe/Downloads/boundaries")
output_folder = Path("/Users/bdestombe/Projects/NHFLO/data/src/nhflodata/data/mockup/bodemlagen_pwn_2024/v2.0.0/boundaries")
results = converter.convert_folder(
    input_folder=input_folder, output_folder=output_folder, coordinate_precision=2, overwrite_with_target_crs=True
)
print_results(results)
bounds_koster = gpd.read_file(output_folder / "triwaco_model_nhdz.geojson", columns=[])
bounds_bergen = gpd.read_file(output_folder / "triwaco_model_bergen.geojson", columns=[])
bounds_koster_bergen = gpd.GeoDataFrame(
    geometry=[gpd.GeoDataFrame(pd.concat([bounds_koster, bounds_bergen], ignore_index=True)).union_all()],
    crs=bounds_koster.crs,
)  # into single polygon geometry

bounds = {
    "S11": bounds_koster_bergen,
    "S12": bounds_koster_bergen,
    "S13": bounds_koster_bergen,
    "S21": bounds_koster_bergen,
    "S22": bounds_koster,
    "S31": bounds_koster,
    "S32": bounds_koster,
}

for layer_name, gdf in bounds.items():
    fpath_out = output_folder / layer_name / f"{layer_name}.geojson"
    fpath_out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(fpath_out, driver="GeoJSON")
