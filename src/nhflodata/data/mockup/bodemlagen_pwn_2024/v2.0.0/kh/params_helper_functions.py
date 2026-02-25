import logging

import geopandas as gpd
import numpy as np
from shapely import MultiPolygon, Polygon, make_valid

logger = logging.getLogger(__name__)


def _extract_polygons(geom):
    """Extract polygon parts from a geometry, discarding points and lines.

    Parameters
    ----------
    geom : shapely.Geometry
        Input geometry, possibly a GeometryCollection.

    Returns
    -------
    shapely.Polygon, shapely.MultiPolygon, or None
        The polygon parts, or None if no polygons are present.
    """
    if geom is None or geom.is_empty:
        return None
    geom = make_valid(geom)
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    # GeometryCollection: keep only polygon parts
    polys = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
    if not polys:
        return None
    if len(polys) == 1:
        return polys[0]
    return MultiPolygon(polys)


def _area_weighted_mean(gdf, value_col):
    """Compute area-weighted mean of a value column.

    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame with a geometry and value column.
    value_col : str
        Column name containing the values.

    Returns
    -------
    float
        Area-weighted mean, or np.nan if total area is zero or all values
        are NaN.
    """
    areas = gdf.geometry.area
    values = gdf[value_col].astype(float)
    mask = ~np.isnan(values)
    if mask.sum() == 0 or areas[mask].sum() == 0:
        return np.nan
    return float(np.average(values[mask], weights=areas[mask]))


def _area_weighted_median(gdf, value_col):
    """Compute area-weighted median of a value column.

    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame with a geometry and value column.
    value_col : str
        Column name containing the values.

    Returns
    -------
    float
        Area-weighted median, or np.nan if total area is zero or all values
        are NaN.
    """
    areas = gdf.geometry.area
    values = gdf[value_col].astype(float)
    mask = ~np.isnan(values)
    if mask.sum() == 0 or areas[mask].sum() == 0:
        return np.nan
    sorted_idx = np.argsort(values[mask].values)
    sorted_values = values[mask].values[sorted_idx]
    sorted_areas = areas[mask].values[sorted_idx]
    cumulative = np.cumsum(sorted_areas)
    halfway = cumulative[-1] / 2.0
    idx = np.searchsorted(cumulative, halfway)
    return float(sorted_values[min(idx, len(sorted_values) - 1)])


def fill_boundary_with_polygons(
    *,
    boundary_gdf,
    source_gdf=None,
    value_col="VALUE",
    fill_value=np.nan,
    fill_method="fill_value",
    overlap_priority="largest",
    override_gdf=None,
):
    """Fill a boundary polygon with values from source polygons.

    Covers the entire boundary with non-overlapping polygons. Where source
    polygons overlap, the overlap_priority determines which value is used.
    Gaps within the boundary that are not covered by any source polygon are
    filled according to fill_method.

    Parameters
    ----------
    boundary_gdf : GeoDataFrame
        Single polygon defining the boundary to fill.
    source_gdf : GeoDataFrame or None, optional
        Polygons with a value attribute to fill the boundary. Can be None or
        empty, in which case only override_gdf and the fill value are used.
        Default is None.
    value_col : str, optional
        Column name in source_gdf containing the values. Default is "VALUE".
    fill_value : float, optional
        Value for areas not covered by any source polygon when
        ``fill_method="fill_value"``. Default is np.nan.
    fill_method : str, optional
        How to determine the value for uncovered areas:

        - ``'fill_value'``: use the ``fill_value`` parameter (default).
        - ``'mean'``: area-weighted mean of source polygon values within the
          boundary. Does not consider override_gdf polygons.
        - ``'median'``: area-weighted median of source polygon values within
          the boundary. Does not consider override_gdf polygons.
    overlap_priority : str, optional
        How to resolve overlapping source polygons:

        - ``'first'``: polygon with lowest index in source_gdf wins.
        - ``'last'``: polygon with highest index wins.
        - ``'largest'``: polygon with largest area wins (default).
        - ``'smallest'``: polygon with smallest area wins.
    override_gdf : GeoDataFrame or None, optional
        Polygons whose parts within the boundary always take precedence over
        both source_gdf and the fill value. Must contain a ``value_col``
        column. These are carved out of the boundary first, before any source
        polygon processing. Default is None.

    Returns
    -------
    result : GeoDataFrame
        Non-overlapping polygons covering the entire boundary, with value_col
        attribute set.
    has_overlaps : bool
        True if overlapping polygons were detected in source_gdf (within the
        boundary). A warning is logged when True.
    """
    boundary_geom = boundary_gdf.geometry.iloc[0]

    # Clip source to boundary (handle None / empty source_gdf)
    has_overlaps = False
    if source_gdf is not None and not source_gdf.empty:
        source = source_gdf[["geometry", value_col]].copy().to_crs(boundary_gdf.crs)
        source_clipped = gpd.clip(source, boundary_geom).reset_index(drop=True)

        # Check for overlaps: if sum of areas > union area, polygons overlap
        if len(source_clipped) >= 2:
            union_area = source_clipped.geometry.union_all().area
            sum_area = source_clipped.geometry.area.sum()
            has_overlaps = (sum_area - union_area) > 1.0  # 1 m² absolute tolerance
            if has_overlaps:
                logger.warning(
                    "Overlapping polygons detected in source_gdf "
                    "(overlap area ~%.1f m2). "
                    "Using overlap_priority='%s' to resolve.",
                    sum_area - union_area,
                    overlap_priority,
                )
    else:
        source_clipped = gpd.GeoDataFrame(columns=["geometry", value_col])

    # Determine fill value for uncovered areas
    if fill_method == "fill_value":
        computed_fill = fill_value
    elif fill_method == "mean":
        computed_fill = _area_weighted_mean(source_clipped, value_col)
    elif fill_method == "median":
        computed_fill = _area_weighted_median(source_clipped, value_col)
    else:
        msg = f"Unknown fill_method '{fill_method}'. Choose from 'fill_value', 'mean', 'median'."
        raise ValueError(msg)

    # Clip and prepare override polygons (highest priority)
    if override_gdf is not None:
        override = override_gdf[["geometry", value_col]].copy().to_crs(boundary_gdf.crs)
        override_clipped = gpd.clip(override, boundary_geom).reset_index(drop=True)
        if len(override_clipped) >= 2:
            ov_union_area = override_clipped.geometry.union_all().area
            ov_sum_area = override_clipped.geometry.area.sum()
            if (ov_sum_area - ov_union_area) > 1.0:
                msg = (
                    "Polygons in override_gdf must not overlap. "
                    f"Detected ~{ov_sum_area - ov_union_area:.1f} m2 of overlap."
                )
                raise ValueError(msg)
    else:
        override_clipped = None

    # Sort to determine processing order — first processed wins overlapping area
    if not source_clipped.empty:
        source_clipped["_area"] = source_clipped.geometry.area
        if overlap_priority == "first":
            ordered = source_clipped
        elif overlap_priority == "last":
            ordered = source_clipped.sort_index(ascending=False)
        elif overlap_priority == "largest":
            ordered = source_clipped.sort_values("_area", ascending=False)
        elif overlap_priority == "smallest":
            ordered = source_clipped.sort_values("_area", ascending=True)
        else:
            msg = f"Unknown overlap_priority '{overlap_priority}'. Choose from 'first', 'last', 'largest', 'smallest'."
            raise ValueError(msg)
    else:
        ordered = source_clipped

    # Start with override polygons — they always take precedence
    result_parts = []
    remaining = boundary_geom

    if override_clipped is not None and not override_clipped.empty:
        for _, row in override_clipped.iterrows():
            if remaining.is_empty:
                break
            covered = _extract_polygons(remaining.intersection(row.geometry))
            if covered is not None:
                result_parts.append({"geometry": covered, value_col: row[value_col]})
            remaining = remaining.difference(row.geometry)

    # Then fill with source polygons according to overlap priority
    for _, row in ordered.iterrows():
        if remaining.is_empty:
            break
        covered = _extract_polygons(remaining.intersection(row.geometry))
        if covered is not None:
            result_parts.append({"geometry": covered, value_col: row[value_col]})
        remaining = remaining.difference(row.geometry)

    # Fill any uncovered remainder
    remainder = _extract_polygons(remaining)
    if remainder is not None:
        result_parts.append({"geometry": remainder, value_col: computed_fill})

    result = gpd.GeoDataFrame(result_parts, crs=boundary_gdf.crs)
    return result, has_overlaps
