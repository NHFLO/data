from nhflotools.geoconverter.geoconverter import GeoConverter, print_results
from pathlib import Path

converter = GeoConverter()

# Convert folder with all files
input_folder = Path("/Users/bdestombe/Downloads/daw_data_TS_DS")
output_folder = Path("/Users/bdestombe/Projects/NHFLO/data/src/nhflodata/data/mockup/bodemlagen_pwn_2024/v2.0.0/Koster_drilling_interpretations_geojson")
results = converter.convert_folder(
    input_folder=input_folder, output_folder=output_folder, coordinate_precision=0.01, overwrite_with_target_crs=True
)
print_results(results)