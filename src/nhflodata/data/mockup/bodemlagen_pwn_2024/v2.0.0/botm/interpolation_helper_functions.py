"""Helper functions for interpolating PWN aquitard layer boundaries.

Provides utilities to extract point values from contour-line and polygon
shapefiles, interpolate them to a target grid, and manipulate spatial data
for the NHFLO model layer construction.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.interpolate import griddata

# Default CRS, Amersfoort RD
CRS_RD = 28992

# Sentinel value in Koster (1997) shapefiles indicating layer absence (1 cm thickness)
KOSTER_ABSENT_VALUE = 0.01

# Expected number of polygons bordering a single contour line
N_BORDERING_POLYGONS = 2

# These dictonaries map the polygon values in the hnflo data
# version of the Koster shapefiles to values for the contour
# lines. The value that is assigned to the contour line is the
# value that occurs in both lists that correspond to a polygon
# value. So for example, a line that borders a polygon with
# -1.50 and 0 for TS11 will be assigned a value of -0.50 m.
LEGEND_DICTS = {
    "TS11": {
        -3.75: [-2.5],
        -1.50: [-2.50, -0.50],
        0: [-0.50, 0.50],
        1.50: [0.50, 2.50],
        3.75: [2.50, 5.00],
        5.50: [5.00],
    },
    "DS11": {
        0.13: [0.25],
        0.38: [0.25, 0.50],
        0.75: [0.50, 1.00],
        1.50: [1.00, 2.00],
        2.50: [2.00, 3.00],
        4.00: [3.00, 5.00],
        6.00: [5.00, 7.50],
        7.75: [7.50],
    },
    "TS12": {
        0.5: [0.00],
        -2.50: [-5.00, 0.00],
        -7.50: [-10.00, -5.00],
        -12.50: [-15.00, -10.00],
        -17.50: [-15.00],
    },
    "DS12": {
        0.75: [1.00],
        2.00: [1.00, 3.00],
        4.00: [3.00, 5.00],
        7.50: [5.00, 10.00],
        12.50: [10.00, 15.00],
        17.50: [15.00, 20.00],
        22.50: [20.00, 25.00],
        27.50: [25.00],
    },
    "TS13": {
        -12.50: [-15.00],
        -17.50: [-20.00, -15.00],
        -22.50: [-25.00, -20.00],
        -27.50: [-30.00, -25.00],
        -32.50: [-35.00, -30.00],
        -36.00: [-35.00],
    },
    "DS13": {
        0.25: [0.50],
        0.75: [0.50, 1.00],
        2.00: [1.00, 3.00],
        4.00: [3.00, 5.00],
        7.50: [5.00, 10.00],
        12.50: [10.00, 15.00],
        17.50: [15.00, 20.00],
        22.50: [20.00, 25.00],
        27.50: [25.00],
    },
    "TS21": {
        -25.00: [-30.00, -20.00],
        -35.00: [-40.00, -30.00],
        -45.00: [-50.00, -40.00],
        -55.00: [-60.00, -50.00],
        -65.00: [-60.00],
    },
    "DS21": {
        2.00: [3.00],
        4.00: [3.00, 5.00],
        7.50: [5.00, 10.00],
        12.50: [10.00, 15.00],
        17.50: [15.00, 20.00],
        22.50: [20.00, 25.00],
        27.50: [25.00, 30.00],
        32.50: [30.00, 35.00],
        37.50: [35.00, 40.00],
        42.50: [40.00],
    },
    "TS22": {
        -25.00: [-30.00],
        -35.00: [-40.00, -30.00],
        -45.00: [-50.00, -40.00],
        -55.00: [-60.00, -50.00],
        -65.00: [-70.00, -60.00],
        -75.00: [-80.00, -70.00],
        -85.00: [-90.00, -80.00],
        -95.00: [-90.00],
    },
    "DS22": {
        2.50: [5.00],
        7.50: [5.00, 10.00],
        12.50: [10.00, 15.00],
        17.50: [15.00, 20.00],
        22.50: [20.00, 25.00],
        27.50: [25.00, 30.00],
        32.50: [30.00, 35.00],
        37.50: [35.00, 40.00],
        42.50: [40.00, 45.00],
        47.50: [45.00, 50.00],
        52.50: [50.00],
    },
    "TS31": {
        -45.00: [-50.00],
        -55.00: [-60.00, -50.00],
        -65.00: [-70.00, -60.00],
        -75.00: [-80.00, -70.00],
        -85.00: [-90.00, -80.00],
        -95.00: [-100.0, -90.00],
        -105.0: [-100.0],
    },
    "DS31": {
        0.25: [0.50],
        0.75: [0.50, 1.00],
        2.00: [1.00, 3.00],
        4.00: [3.00, 5.00],
        7.50: [5.00, 10.00],
        12.50: [10.00, 15.00],
        17.50: [15.00],
    },
    "TS32": {
        -77.50: [-80.00],
        -82.50: [-85.00, -80.00],
        -87.50: [-90.00, -85.00],
        -92.50: [-95.00, -90.00],
        -97.50: [-100.0, -95.00],
        -102.5: [-105.0, -100.00],
        -107.5: [-110.0, -105.00],
        -112.5: [-110.0],
    },
    "DS32": {
        0.25: [0.50],
        0.75: [0.50, 1.00],
        2.00: [1.00, 3.00],
        4.00: [3.00, 5.00],
        7.50: [5.00, 10.00],
        12.50: [10.00, 15.00],
        17.50: [15.00],
    },
}


def get_internal_contour_lines(gdf_ln, gdf_pl):
    """Return linestrings that do not overlap with polygon boundaries.

    Separates the lines that represent a thickness from the lines
    that represent the limit of occurrence of a layer. Only used
    for thicknesses, not for the tops.

    Parameters
    ----------
    gdf_ln : GeoDataFrame
        GeoDataFrame containing the linestrings of the thickness
        contours
    gdf_pl : GeoDataFrame
        GeoDataFrame with the polygons of the thickness

    Returns
    -------
    GeoDataFrame
        Returns gdf_ln without the linestrings that overlap with the
        limit of occurrence
    """
    # Select only the polygons which indicate the regions where the layer does not occur
    idx = gdf_pl["VALUE"] == KOSTER_ABSENT_VALUE

    # Create a new GeoDataFrame containing the polygon boundaries as (Multi)LineStrings
    gdf_bnd = gpd.GeoDataFrame(
        geometry=gdf_pl.loc[idx, "geometry"].boundary,
        crs=CRS_RD,
    )
    # Explode so that MultiLineStrings become LineStrings
    gdf_bnd = gdf_bnd.explode()
    # Create a buffer around the polygon boundaries because in rare cases there
    # are minor differences between the line vertices and the polygon vertices
    gdf_bnd["geometry"] = gdf_bnd["geometry"].buffer(2.0)

    # Do a spatial join to find out which linestrings in gdf_ln are within
    # the polygons of gdf_bnd. Those that are, should not be returned by
    # the function.
    gdf_jn = gpd.sjoin(gdf_bnd, gdf_ln, how="left", predicate="contains")
    # Use the index of gdf_ln to create an GeoSeries to slice gdf_ln with
    idx = gdf_ln.index.isin(gdf_jn["index_right"])

    # Return gdf_ln without the linestrings that overlap with the 0.01 m
    # thickness polygon boundaries.
    return gdf_ln.loc[~idx]


def assign_poly_values_to_linestrings(
    gdf_ln,  # GeoDataFrame with contour lines
    gdf_pl,  # GeoDataFrame with the Koster (1997) polygons
    layer_name,  # Name of the layer
):
    """Identify which polygons in gdf_pl border a contour line and assign values.

    Ideally, a contour line forms the separation between two polygons but this
    is not always the case due to topology errors and the addition of polygons
    to the Koster (1997) shapefiles from other sources (occurs mostly in the
    southern part of the area).

    Note: [Edinsi report 3.1, p.12 and Section 5, p.38] Edinsi notes that the
    Python script cannot automatically determine values for all contour lines.
    Causes include: (a) overlapping polygons in original shapefiles, (b) minor
    digitization errors, (c) added polygons in the southern part that weren't in
    the original Koster (1997) data. These are flagged with remarks and resolved
    in a manual QGIS editing step (step 5 in the interpolation workflow).

    Parameters
    ----------
    gdf_ln : GeoDataFrame
        GeoDataFrame containing the linestrings of the thickness
        contours
    gdf_pl : GeoDataFrame
        GeoDataFrame with the polygons of the thickness
    layer_name : str
        Name of the layer being processed. This is needed to look up
        the dictionary in LEGEND_DICTS that maps the Koster (1997)
        legend entries to the top/thickness values assigned to the
        polygons.

    Returns
    -------
    GeoDataFrame
        A GeoDataFrame with for each linestring the assigned value,
        the number of bordering polygons found and any remarks.
    """
    # Get the legend_dict for the current layer
    legend_dict = LEGEND_DICTS[layer_name]

    # Check for polygons with VALUE attribute of 0.01 m, signals where layer is absent
    # Only returns rows for DS files, no effect for TS files
    idx = gdf_pl["VALUE"] == KOSTER_ABSENT_VALUE
    # Remove the 0.01 m polygons
    gdf_pl = gdf_pl.loc[~idx]
    # Renumber the index
    gdf_pl = gdf_pl.reindex(index=range(len(gdf_pl)))
    # Make geometries valid by using the buffer(0) trick
    gdf_pl["geometry"] = gdf_pl.buffer(0)

    # Determine which linestrings in gdf_ln intersect which polygons in gdf_pl
    gdf_int = gpd.sjoin(gdf_ln, gdf_pl, how="left", predicate="intersects")

    data = []
    # The index of gdf_int contains duplicates because most lines will
    # intersect multiple polygons.
    for i in gdf_int.index.unique():
        # Select the rows for the contour linestring and store in a separate
        # GeoDataFrame
        idx = gdf_int.index == i
        gdf_i = gdf_int.loc[idx]

        # Determine the length of the DataFrame, i.e. the number of polygons that intersect the linestring
        n = len(gdf_i)

        # Default remark for n == N_BORDERING_POLYGONS
        remark = "Value assigned automatically in Python script."

        # The linestring's geometry is the same for all rows of gdf_i. Only one is
        # needed to build the GeoDataFrame returned by the function.
        geom = gdf_i["geometry"].values[0]

        # Ideally each contour has a polygon to either side, so n == N_BORDERING_POLYGONS.
        # This is not always the case, hence the need for these conditional statements
        if n == N_BORDERING_POLYGONS:
            # Get the VALUE attribute of each polygon
            v0 = gdf_i["VALUE"].values[0]
            v1 = gdf_i["VALUE"].values[1]
            # Get the legend range from legend_dict
            list0 = legend_dict.get(v0)
            list1 = legend_dict.get(v1)
            # The value may not correspond to a range in the original Koster (1997)
            # as polygons from other sources were later added to the shapefiles. In
            # that case (one of) the list(s) will be None.
            if None in {list0, list1}:
                # Do not assign a value to the linestring and change the remark that will
                # appear in the shapefile attribute table.
                v = [None]
                remark = "Poly not in mapping dict. Assign value manually."
            else:
                # If both lists are not None then find the item they have in common.
                # Ideally this is a single value. When this is not the case, no value
                # is assigned and the remark is changed to reflect this problem.
                v = list({item0 for item0 in list0 if item0 in list1})
                if len(v) != 1:
                    v = [None]
                    remark = f"Ambiguous result {len(v)}. Assign value manually."
        # A linestring can intersect more than two polygons due to
        #  - overlapping polygons in the original shapefiles
        #  - the start- and end points of the contour lines touch (digitizing mistake)
        #  - when polygons from another data source were added to the original Koster (1997) polygons.
        # In these cases n is larger than 2 and it cannot be determined
        # automatically what the value for the linestring must be.
        elif n > N_BORDERING_POLYGONS:
            v = [None]
            remark = "Line intersects more than 2 polygons. Assign value manually."
        # A line can intersect no or a single polygon. This is most frequently the case for
        # the lines that were added to the Koster (1997) linestrings for the Bergen area
        # (based on the Stuyfzand figures).
        elif n < N_BORDERING_POLYGONS:
            v = [None]
            remark = "Line intersects less than 2 polygons. Assign value manually."

        # Append one line to the data for each linestring in gdf_ln
        data.append([*v, n, remark, geom])

    # Return a GeoDataFrame of linestrings
    return gpd.GeoDataFrame(
        data=data,
        columns=["value", "N", "remark", "geometry"],
        crs=CRS_RD,
    )


def combine_lists(lists):
    """Combine lists that share common items.

    Parameters
    ----------
    lists : list
        A list of lists to be analyzed

    Returns
    -------
    list
        A list in which the input lists with common items have
        been combined.
    """
    # Start by assuming each list is a separate group
    groups = [set(lst) for lst in lists]

    merged = True
    while merged:
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                # If two groups share any common elements, merge them
                if groups[i].intersection(groups[j]):
                    groups[i] = groups[i].union(groups[j])
                    groups.pop(j)
                    merged = True
                    break
            if merged:
                break

    # Convert sets back to lists for final output
    return [list(group) for group in groups]


def join_contour_line_segments(gdf_ln):
    """Combine individual Koster (1997) linestrings into larger contour lines.

    Parameters
    ----------
    gdf_ln : GeoDataFrame
        GeoDataFrame with individual linestrings.

    Returns
    -------
    GeoDataFrame
        GeoDataFrame with the comined linestrings.
    """
    # Use a spatial join to identify the linstrings with touching endpoints
    gdf_tch = gpd.sjoin(gdf_ln, gdf_ln, how="left", predicate="touches")

    # Create a dictionary for every line segment, which will store the
    # index numbers of the linestrings that it touches
    l_dict = {i: [] for i in gdf_ln.index}
    # Loop through the index items of gdf_tch
    for i0 in gdf_tch.index:
        # Get the rows for the current line segment
        idx = gdf_tch.index == i0
        # Get the index numbers of the touching linestrings
        irs = gdf_tch.loc[idx, "index_right"]
        irs = irs.dropna()
        # Combine the linestring index number with the
        # index numbers of the touchings linestrings into a single list
        i_list = [i0, *irs.astype(int).tolist()]
        # Update each item in the l_dict dictionary by adding i_list
        for i1 in i_list:
            l_dict[i1] += i_list

    # Combine the linestring segments that form a single contour line. This
    # will result in a nested list in which each item is a list containing
    # the index numbers of the line segments that together form a contour line
    unique_lines = combine_lists(list(l_dict.values()))

    # Loop through the list with the index numbers of the segments
    # and use these to create single contour lines
    lns = []
    ln_vals = []
    for idx in unique_lines:
        if len(idx) == 0:
            pass
        else:
            # Combine the line segments into a single linstring
            lns.append(gdf_ln.loc[idx, "geometry"].union_all())
            # Each line segment has a top/thickness value associated
            # with it. Ideally they are all the same but this is not
            # guaranteed. The next two lines select the most frequently
            # occurring value, which will be used as the value attribute
            # in the GeoDataFrame that will be returned.
            vals_lst = gdf_ln.loc[idx, "value"].to_list()
            v = max(vals_lst, key=vals_lst.count)
            ln_vals.append(v)

    # Return a GeoDataFrame with the combined linestrings and their
    # top/thickness value.
    return gpd.GeoDataFrame(
        geometry=lns,
        data={
            "script_value": ln_vals,
            "value": ln_vals,
        },
        crs=CRS_RD,
    )


def get_point_values(*, path, layer_name, dx_zero_vertices_interpolation=100.0):
    """Convert contour line segments to points and combine with borehole data.

    Converts line segments to points and combines them with point data from
    the geo_daw data (top/thickness values for boreholes interpreted by Koster,
    1997) and the point values for the Bergen area (digitized from the figures
    in the Stuyfzand, 1987 report).

    Parameters
    ----------
    path : str
        Path to the data.
    layer_name : str
        Name of the layer.
    dx_zero_vertices_interpolation : float, optional
        The distance between the vertices of the polygons with 0 thickness that
        will be added to the point data for interpolation. Only used for the
        thickness layers, not for the tops. Default is 100 m if CRS is in m.

    Returns
    -------
    GeoDataFrame
        GeoDataFrame with points and their corresponding top/thickness values
    """
    # Folder with the contour lines
    # src_dir = Path("..", "gis", "kaarten_2024_voor_interpolatie")
    # Set the paths to the files to be read
    if layer_name.find("T") == 0:
        fpath_shp = Path(path, "top_aquitard", layer_name, f"{layer_name}_union_with_values_edited.geojson")
        fpath_shp_ber = Path(path, "top_aquitard", layer_name, f"{layer_name}_bergen_points.geojson")
    elif layer_name.find("D") == 0:
        fpath_shp = Path(path, "dikte_aquitard", layer_name, f"{layer_name}_union_with_values_edited.geojson")
        fpath_shp_ber = Path(path, "dikte_aquitard", layer_name, f"{layer_name}_bergen_points.geojson")

    # Import the contour lines
    gdf_ln = gpd.read_file(fpath_shp)
    # Convert any multilinestrings to linestrings
    gdf_ln = gdf_ln.explode()
    # Add the line vertices as a list of coordinates to each row of the GeoDataFrame
    gdf_ln["points"] = gdf_ln.apply(lambda x: list(x["geometry"].coords), axis=1)

    # Convert the coordinates to points and assign values
    values = []
    pts = []
    # Loop through each row of gdf_ln
    for _index, row in gdf_ln.iterrows():
        # Skip NULL values that can occur for Bergen -999 polygons
        if np.isnan(row["value"]):
            continue
        # Get the coordinates created by the lambda function above and
        # convert them to Point objects
        xy_arr = np.array(row["points"])
        pts_i = list(gpd.points_from_xy(x=xy_arr[:, 0], y=xy_arr[:, 1]))
        # Add to the list of existing poins
        pts += pts_i
        # Expand the list with values
        values += [row["value"]] * len(pts_i)

    # Convert to a GeoDataFrame
    gdf_pts = gpd.GeoDataFrame(
        data=values,
        geometry=pts,
        columns=["value"],
        crs=CRS_RD,
    )

    gdf_pts.drop_duplicates(inplace=True)

    # Check if a shapefile with point data exists for the Bergen area
    if fpath_shp_ber.exists() is True:
        # Read the file
        gdf_pts_ber = gpd.read_file(fpath_shp_ber)
        # Discard columns other than 'VALUE' and 'geometry'
        gdf_pts_ber = gdf_pts_ber[["geometry", "VALUE"]]
        # Rename the 'VALUE' column to 'value' to be compatible with gdf_pts
        gdf_pts_ber = gdf_pts_ber.rename(columns={"VALUE": "value"})
        # Add the Bergen points to gdf_pts
        gdf_pts = pd.concat([gdf_pts, gdf_pts_ber])

    # Read the point data for the boreholes
    fpath_daw = Path(path, "koster_drilling_interpretations", "daw_data_TS_DS.geojson")
    gdf_daw = gpd.read_file(fpath_daw)
    # Select the column for the layer being processed
    gdf_daw = gdf_daw[[layer_name, "geometry"]].dropna()
    # Rename the column from layer name to 'value'
    gdf_daw = gdf_daw.rename(columns={layer_name: "value"})

    # Add the points to gdf_pts
    gdf_pts = pd.concat([gdf_pts, gdf_daw])

    if layer_name.find("D") == 0:
        fp_zero_masks = Path(path, "dikte_aquitard", layer_name, f"{layer_name}_mask_combined.geojson")
        gdf_zero_masks = gpd.read_file(fp_zero_masks)
        _gdf_zero_thickness = polygon_vertices_interpolated(gdf=gdf_zero_masks, dx=dx_zero_vertices_interpolation)
        _gdf_zero_thickness = gpd.GeoDataFrame(
            data={"value": len(_gdf_zero_thickness) * [0.0]},
            geometry=_gdf_zero_thickness.geometry,
            crs=CRS_RD,
        )

        # Locations that were already present in gdf_pts are overwritten with zero thickness values
        _gdf_pts = gdf_pts[~gdf_pts.geometry.isin(_gdf_zero_thickness.geometry)]
        gdf_pts = pd.concat([_gdf_pts, _gdf_zero_thickness])

    return gdf_pts


def interpolate_gdf(gdf_pt, gdf, gdf_ns=None):
    """Interpolate the point values of a layer to a (model) grid.

    Parameters
    ----------
    gdf_pt : GeoDataFrame
        GeoDataFrame with the points of the interpolation grid.
    gdf : GeoDataFrame
        GeoDataFrame with the values to be interpolated.
    gdf_ns : GeoDataFrame, optional
        GeoDataFrame with a polygon used to fill the grid below the North Sea
        with nearest-neighbour values after the interpolation. Not used
        if None is passed (default).

    Returns
    -------
    numpy.ndarray
        1-D array of interpolated values at the locations in ``gdf_pt``.
    """
    # Create 1D arrays for the interpolation points
    xi = gdf_pt["geometry"].x.to_numpy()
    yi = gdf_pt["geometry"].y.to_numpy()

    # Convert the data point coordinates and values to NumPy arrays
    x = gdf["geometry"].x.to_numpy()
    y = gdf["geometry"].y.to_numpy()
    z = gdf["value"].to_numpy()

    # Call SciPy's griddata to perform the interpolation. Note that zint
    # is assigned NaN outside the convex hull of the data point
    # cloud
    zint = griddata(
        points=(x, y),
        values=z,
        xi=(xi[None, :], yi[None, :]),
        method="linear",  # Note: cubic gives very poor results
        fill_value=np.nan,  # NaN outside the convex hull
    )

    # Repeat the interpolation for the interpolation points below
    # the North Sea if the polygon is supplied
    if gdf_ns is not None:
        # Take the existing interpolation result and make array 1D
        zint = zint.ravel()

        # Identify the points in the interpolaton grid that are within
        # the North Sea polygon
        gdf_within = gpd.sjoin(gdf_pt, gdf_ns, predicate="within")
        # Convert their indices to a list
        idx_ns = gdf_within.index.to_list()
        # Use the list to slice the arrays with interpolation point
        # x and y values
        xi_ns = xi[idx_ns]
        yi_ns = yi[idx_ns]

        # Find the points in the previous interpolation result that
        # have NaN values (these were outside the convex hull of the
        # data points)
        idx = np.isnan(zint)
        # Keep only the non-NaN values for the interpolation that will
        # assign the nearest neighbour value to the points below the
        # North Sea
        x = xi[~idx]
        y = yi[~idx]
        z = zint[~idx]

        # Perform interpolation
        zint_ns = griddata(
            points=(x, y),
            values=z,
            xi=(xi_ns[None, :], yi_ns[None, :]),
            method="nearest",
        )

        # Replace the values of the  points in zint that are below the
        # North Sea to the nearest neighbour values.
        zint[idx_ns] = zint_ns

    # Return the interpolated values
    return zint


def interpolate_to_all_points(*, gdf, all_xy, boundary_gdf):
    """Interpolate GeoDataFrame point values to all target locations.

    Uses scipy griddata with linear interpolation, with nearest-neighbor
    fallback for points inside the boundary but outside the convex hull.
    Clips results to the layer boundary.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Source points with 'value' column and point geometry.
    all_xy : np.ndarray
        Target locations as (N, 2) array of x, y coordinates.
    boundary_gdf : gpd.GeoDataFrame
        Boundary polygon(s) to clip interpolated results.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame with interpolated 'value' and 'is_original' columns
        at target locations, clipped to the boundary (NaN outside).
        'is_original' is True for points that coincide with source data.
    """
    src_xy = np.column_stack([gdf.geometry.x, gdf.geometry.y])
    src_values = gdf["value"].values

    # Linear interpolation
    interpolated = griddata(src_xy, src_values, all_xy, method="linear")

    # Identify points inside boundary
    gdf_result = gpd.GeoDataFrame(
        {"value": interpolated},
        geometry=gpd.points_from_xy(all_xy[:, 0], all_xy[:, 1]),
        crs=gdf.crs,
    )
    within = gpd.sjoin(gdf_result, boundary_gdf, predicate="intersects")
    mask_inside = gdf_result.index.isin(within.index)

    # Nearest-neighbor fallback for NaN points inside the boundary
    mask_nan_inside = mask_inside & np.isnan(interpolated)
    if mask_nan_inside.any():
        nearest = griddata(src_xy, src_values, all_xy[mask_nan_inside], method="nearest")
        interpolated[mask_nan_inside] = nearest

    gdf_result["value"] = interpolated

    # Clip: set values outside boundary to NaN
    gdf_result.loc[~mask_inside, "value"] = np.nan

    # Track which points are original (coincide with source data locations)
    # Build a set of (x, y) tuples from source for fast lookup
    src_set = set(map(tuple, np.round(src_xy, decimals=6)))
    all_rounded = np.round(all_xy, decimals=6)
    is_original = np.array([tuple(pt) in src_set for pt in all_rounded])
    gdf_result["is_original"] = is_original

    return gdf_result


def polygon_vertices_interpolated(*, gdf, dx):
    """
    Extract polygon vertices as points.

    Interpolating along edges so that no two consecutive points are more than dx apart.

    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame with Polygon or MultiPolygon geometries.
    dx : float
        Maximum distance between consecutive points, in CRS units.

    Returns
    -------
    GeoDataFrame
        One row per vertex/interpolated point, with all non-geometry
        columns from the input repeated for each point.
    """
    # Explode MultiPolygons to simple Polygons
    parts, part_idx = shapely.get_parts(gdf.geometry.values, return_index=True)

    # Get all rings (exterior + interior) per polygon
    rings, ring_idx = shapely.get_rings(parts, return_index=True)

    # Get all coordinates including closing coord
    coords, coord_idx = shapely.get_coordinates(rings, return_index=True)

    # Edges: consecutive coord pairs within the same ring (handles closing coord naturally)
    same_ring = coord_idx[:-1] == coord_idx[1:]
    edge_starts = coords[:-1][same_ring]
    edge_ends = coords[1:][same_ring]
    edge_ring_idx = coord_idx[:-1][same_ring]

    # Number of interpolation segments per edge
    diff = edge_ends - edge_starts
    lengths = np.hypot(diff[:, 0], diff[:, 1])
    n_segs = np.maximum(1, np.ceil(lengths / dx).astype(int))

    # t in [0, 1/n, ..., 1] — include end point; duplicates removed at the end
    n_pts = n_segs + 1
    offsets = np.empty(len(n_segs) + 1, dtype=np.intp)
    offsets[0] = 0
    np.cumsum(n_pts, out=offsets[1:])

    edge_of_point = np.repeat(np.arange(len(n_segs)), n_pts)
    local_t = (np.arange(offsets[-1]) - offsets[edge_of_point]) / n_segs[edge_of_point]
    interp_coords = edge_starts[edge_of_point] + local_t[:, np.newaxis] * diff[edge_of_point]

    # Chain index mappings: point -> edge -> ring -> part -> original row
    orig_idx = part_idx[ring_idx[edge_ring_idx[edge_of_point]]]

    return gpd.GeoDataFrame(
        gdf.drop(columns=gdf.geometry.name).iloc[orig_idx].reset_index(drop=True),
        geometry=gpd.points_from_xy(interp_coords[:, 0], interp_coords[:, 1]),
        crs=gdf.crs,
    ).drop_duplicates(ignore_index=True)
