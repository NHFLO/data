"""Test for forbidden file formats."""

from pathlib import Path

import pytest

from nhflodata.get_paths import get_latest_data_paths


def find_files_by_extension(folder: Path, extensions: set[str]) -> list[Path]:
    """
    Find all files with given extensions in a folder, case-insensitive.

    Parameters
    ----------
    folder : Path
        Path object representing the folder to search in
    extensions : Set[str]
        Set of file extensions to search for (with or without leading dot)

    Returns
    -------
    List[Path]
        List of Path objects representing found files

    Examples
    --------
    >>> files = find_files_by_extension(Path("./data"), {".csv", "txt"})
    >>> # Will find files like: example.csv, EXAMPLE.CSV, data.TXT
    >>> print(files[0])
    ./data/example.csv

    Notes
    -----
    The search is case-insensitive, so it will find both lowercase and uppercase
    extensions (e.g., both .shp and .SHP).
    """
    matched_files = []
    # Convert all extensions to lowercase and ensure they have a leading dot
    normalized_extensions = {(ext if ext.startswith(".") else f".{ext}").lower() for ext in extensions}

    # Get all files in the folder and its subfolders
    all_files = folder.glob("**/*")

    # Check each file's extension case-insensitively
    for file_path in all_files:
        if file_path.is_file():  # Ensure it's a file, not a directory
            file_ext = file_path.suffix.lower()  # Get lowercase extension
            if file_ext in normalized_extensions:
                matched_files.append(file_path)

    return matched_files


@pytest.mark.xfail(strict=False)
def test_no_shapefile_or_geopackage():
    """
    Test for absence of shapefile and geopackage formats.

    This test ensures that no shapefiles (.shp, .shx, .dbf, .prj) or
    geopackage (.gpkg) files are present in any subfolder of the project.
    The check is case-insensitive, so it will catch files like .SHP or .GPKG.

    Raises
    ------
    pytest.fail
        If any prohibited geographic files are found, with details about the files
        and recommendation to use GeoJSON format.

    Notes
    -----
    GeoJSON is preferred over shapefiles and geopackages because:
    - It's text-based and readable
    - Works better with version control
    - Single file format instead of multiple files (like shapefiles)
    """
    forbidden_geo_extensions = {".shp", ".shx", ".dbf", ".prj", ".gpkg"}
    folders = get_latest_data_paths()

    forbidden_files = []
    for folder in folders:
        files = find_files_by_extension(folder, forbidden_geo_extensions)
        forbidden_files.extend(files)

    if forbidden_files:
        files_str = "\n".join(str(f).split("mockup/")[-1] for f in forbidden_files)
        pytest.fail(
            f"Found prohibited geographic files:\n{files_str}\n\n"
            "Recommendation: Convert these files to GeoJSON format for better "
            "Git compatibility and readability."
        )


@pytest.mark.xfail(strict=False)
def test_no_excel_files():
    """
    Test for absence of Excel file formats.

    This test ensures that no Excel files (.xls, .xlsx, .xlsm) are present
    in any subfolder of the project. The check is case-insensitive, so it
    will catch files like .XLSX or .XLS.

    Raises
    ------
    pytest.fail
        If any Excel files are found, with details about the files and
        recommendation to use CSV format.

    Notes
    -----
    CSV is preferred over Excel because:
    - It's plain text and human-readable
    - Better version control capabilities
    - Simpler to process programmatically
    - More universal compatibility
    """
    excel_extensions = {".xls", ".xlsx", ".xlsm"}
    folders = get_latest_data_paths()

    excel_files = []
    for folder in folders:
        files = find_files_by_extension(folder, excel_extensions)
        excel_files.extend(files)

    if excel_files:
        files_str = "\n".join(str(f).split("mockup/")[-1] for f in excel_files)
        pytest.fail(
            f"Found Excel files:\n{files_str}\n\n"
            "Recommendation: Convert these files to CSV format for better "
            "Git compatibility and version control."
        )
