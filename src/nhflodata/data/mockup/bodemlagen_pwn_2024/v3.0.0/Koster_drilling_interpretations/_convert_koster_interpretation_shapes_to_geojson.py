"""Convert Koster drilling interpretation shapefiles (DAW) to GeoJSON.

Reads the Dawaco-exported shapefile archive containing top (TS) and thickness
(DS) interpretations per aquitard layer from Koster (1997), and converts them
to GeoJSON format with coordinate precision of 0.01 m.

This is a one-time conversion script. The source shapefiles are archived in
koster_drilling_interpretations/daw_data_TS_DS.zip within the data directory.
"""

from nhflotools.geoconverter.geoconverter import GeoConverter, print_results

from nhflodata.get_paths import get_abs_data_path

converter = GeoConverter()

data_path = get_abs_data_path("bodemlagen_pwn_2024", "2.0.0")

# Convert folder with all files.
# Source shapefiles are archived in koster_drilling_interpretations/daw_data_TS_DS.zip.
input_folder = data_path / "koster_drilling_interpretations" / "daw_data_TS_DS.zip"
output_folder = data_path / "koster_drilling_interpretations" / "geojson"
results = converter.convert_folder(
    input_folder=input_folder, output_folder=output_folder, coordinate_precision=0.01, overwrite_with_target_crs=True
)
print_results(results)
