"""Convert boundary shapefiles and produce per-layer boundary GeoJSON files.

Boundaries indicate where valid data for bodemlagen_pwn_2024 is available.
Within the boundaries, valid values for the top and thickness of the aquitards
should be found. Grid cells outside the boundaries are assigned NaN values.

The merge was done for the aquitard layers S2.1, S1.3, S1.2, and S1.1. For the
deeper layers (S3.2, S3.1, and S2.2), the Bergen model shapefiles contain no
information (see report section 3.3.6).

This is a one-time conversion script. The source shapefiles are archived in
boundaries.zip within the boundaries/ data directory.
"""

import geopandas as gpd
import pandas as pd
from nhflotools.geoconverter.geoconverter import GeoConverter, print_results

from nhflodata.get_paths import get_abs_data_path

converter = GeoConverter()

data_path = get_abs_data_path("bodemlagen_pwn_2024", "2.0.0")

# Convert folder with all files.
# Source shapefiles are archived in boundaries/boundaries.zip.
input_folder = data_path / "boundaries" / "boundaries.zip"
output_folder = data_path / "boundaries"
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

# TODO: [Edinsi report 6, p.40] Edinsi recommends extending S3.2, S3.1, and S2.2 maps
#   northward into the Bergen area. Currently these layers only use the Koster (NHDZ)
#   boundary because the Bergen model shapefiles contain no information for layers deeper
#   than S2.1 (see Edinsi report 3.3.6, p.30).
# TODO: [Edinsi report 3.1.1, p.21] Edinsi notes large differences between Koster S2.1 and
#   REGIS for the Eem clay extent. REGIS distinguishes two clay layers (eek1, eek2) while
#   Koster treats it as a single unit. Edinsi recommends investigating whether this splitting
#   is necessary for the groundwater model (see also Edinsi report 6, p.40).
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
