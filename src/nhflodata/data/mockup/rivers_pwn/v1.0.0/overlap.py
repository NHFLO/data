import geopandas as gpd
import pandas as pd
import warnings


def create_overlap_matrix(
    gdf_a: gpd.GeoDataFrame,
    gdf_b: gpd.GeoDataFrame,
    id_a: str | None = None,
    id_b: str | None = None,
    *,
    as_pivot: bool = True,
) -> pd.DataFrame:
    """
    Calculate a matrix showing the percentage of overlap of geometries from a source GeoDataFrame (gdf_a) into a target GeoDataFrame (gdf_b).

    This version is robust to non-unique identifiers in the input dataframes
    by dissolving the target dataframe before calculating overlaps.

    Parameters
    ----------
    gdf_a : gpd.GeoDataFrame
        The "source" GeoDataFrame for the matrix rows.
    gdf_b : gpd.GeoDataFrame
        The "target" GeoDataFrame for the matrix columns.
    id_a : str or None, optional
        A unique identifier column in gdf_a. If None, the index is used.
    id_b : str or None, optional
        An identifier column in gdf_b (does not need to be unique).
        If None, the index is used.
    as_pivot : bool, default True
        If True, returns a pivoted DataFrame (a matrix).
        If False, returns a long-format DataFrame.

    Returns
    -------
    pd.DataFrame
        The overlap matrix or a long-format DataFrame of overlaps.
    """
    # --- Input Validation ---
    if gdf_a.crs != gdf_b.crs:
        msg = "Input GeoDataFrames must have the same CRS."
        raise ValueError(msg)
    if gdf_a.crs is None or not gdf_a.crs.is_projected:
        warnings.warn("CRS is not projected. Area calculations may be inaccurate.", stacklevel=2)

    # --- Prepare DataFrames ---
    g1 = gdf_a.copy()
    g2 = gdf_b.copy()
    geom_col_a = g1.geometry.name
    geom_col_b = g2.geometry.name

    # Assign temporary IDs if none are provided
    id_col_a = id_a or "_id_a"
    id_col_b = id_b or "_id_b"

    g1[id_col_a] = g1.index
    g2[id_col_b] = g2.index

    if not g1[id_col_a].is_unique:
        msg = f"The identifier column '{id_col_a}' for gdf_a must contain unique values."
        raise ValueError(msg)

    # --- FIX: Dissolve gdf_b by its identifier to handle non-unique IDs ---
    # This creates a new GeoDataFrame where each row corresponds to a unique id_b,
    # and the geometry is the union of all original geometries with that id.
    g2_dissolved = g2.dissolve(by=id_col_b)
    # The index of g2_dissolved is now the unique values of id_col_b.

    # --- Core Logic ---
    g1["area_a"] = g1.geometry.area

    # Spatial join to find all intersecting pairs.
    intersecting_pairs = gpd.sjoin(
        g1[[id_col_a, "area_a", geom_col_a]],
        g2_dissolved,  # Use the dissolved dataframe
        how="inner",
        predicate="intersects",
    )

    # The 'index_right' column from sjoin now holds the unique id_b values.
    intersecting_pairs.rename(columns={"index_right": id_col_b}, inplace=True)

    # Calculate intersection area
    geom_b_map = g2_dissolved[geom_col_b]
    geom_b = intersecting_pairs[id_col_b].map(geom_b_map)

    intersection_area = intersecting_pairs.geometry.intersection(geom_b, align=False).area
    intersecting_pairs["overlap_pct"] = (intersection_area / intersecting_pairs["area_a"]).fillna(0)

    # --- Format Output ---
    # Aggregation is no longer needed due to the upfront dissolve.
    result_long = intersecting_pairs[[id_col_a, id_col_b, "overlap_pct"]]

    if as_pivot:
        overlap_matrix = result_long.pivot_table(index=id_col_a, columns=id_col_b, values="overlap_pct", fill_value=0)
        return overlap_matrix
    else:
        return result_long.sort_values([id_col_a, id_col_b]).reset_index(drop=True)
