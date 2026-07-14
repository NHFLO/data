from pathlib import Path

from geopandas import read_file
from nhflotools.geoconverter import geoconverter


# Round point coordinates to nearest 100
def round_coords_to_100(geom):
    factor = 100
    coords = [(round(x / factor) * factor, round(y / factor) * factor) for x, y in geom.coords]
    return geom.__class__(coords)

converter = geoconverter.GeoConverter()

output_folder = Path(__file__).parent
# # Convert folder with all files
# input_folder = Path(r"C:\Users\tombb\OneDrive - PWN\Vincent PWN inhuur\Opgeleverd\lagenmodel\data\gis\profielen")
# results = converter.convert_folder(
#     input_folder=input_folder, output_folder=output_folder, coordinate_precision=1, overwrite_with_target_crs=True
# )
# geoconverter.print_results(results)

for file in output_folder.glob("**/*.geojson"):
    print(file)



    gdf = read_file(file)
    gdf["geometry"] = gdf["geometry"].apply(round_coords_to_100)

    gdf.to_file(file, driver="GeoJSON")
