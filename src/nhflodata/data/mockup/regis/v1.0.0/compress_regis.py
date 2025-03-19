"""
Compress the REGIS netcdf file using builtin compression.

All variables are compressed with {'zlib': True, 'complevel': 5, 'fletcher32': True, 'dtype': 'float32'}
"""
import datetime as dt

import nlmod
import xarray as xr

REGIS_URL = "REGIS.nc"

def get_regis(
    extent,
    botm_layer="AKc",
    variables=("top", "botm", "kh", "kv"),
    probabilities=False,
    nodata=-9999,
):
    """Get a regis dataset projected on the modelgrid.

    Parameters
    ----------
    extent : list, tuple or np.array
        desired model extent (xmin, xmax, ymin, ymax)
    botm_layer : str, optional
        regis layer that is used as the bottom of the model. This layer is
        included in the model. the Default is "AKc" which is the bottom
        layer of regis. call nlmod.read.regis.get_layer_names() to get a list
        of regis names.
    variables : tuple or list, optional
        The variables to keep from the regis Dataset. Possible entries in the list are
        'top', 'botm', 'kD', 'c', 'kh', 'kv', 'sdh' and 'sdv'. The default is
        ("top", "botm", "kh", "kv").
    remove_nan_layers : bool, optional
        When True, layers that do not occur in the requested extent (layers that contain
        only NaN values for the botm array) are removed. The default is True.
    drop_layer_dim_from_top : bool, optional
        When True, fill NaN values in top and botm and drop the layer dimension from
        top. This will transform top and botm to the data model in MODFLOW. An advantage
        of this data model is that the layer model is consistent by definition, with no
        possibilities of gaps between layers. The default is True.
    probabilities : bool, optional
        if True, also download probability data. The default is False.
    nodata : int or float, optional
        When nodata is not None, set values equal to nodata to nan. The default is
        -9999.

    Returns
    -------
    regis_ds : xarray dataset
        dataset with regis data projected on the modelgrid.
    """
    ds = xr.open_dataset(REGIS_URL, decode_times=False, decode_coords="all")
    if "crs" in ds.coords:
        # remove the crs coordinate, as rioxarray does not recognise the crs
        # and we set the crs at the end of this method by hand
        ds = ds.drop_vars("crs")

    # set x and y dimensions to cell center
    ds["x"] = ds.x_bounds.mean("bounds")
    ds["y"] = ds.y_bounds.mean("bounds")

    # slice extent
    ds = ds.sel(x=slice(extent[0], extent[1]), y=slice(extent[2], extent[3]))

    if len(ds.x) == 0 or len(ds.y) == 0:
        msg = "No data found. Please supply valid extent in the Netherlands in RD-coordinates"
        raise (ValueError(msg))

    # make sure layer names are regular strings
    ds["layer"] = ds["layer"].astype(str)

    # make sure y is descending
    if (ds["y"].diff("y") > 0).all():
        ds = ds.isel(y=slice(None, None, -1))

    # slice layers
    if botm_layer is not None:
        ds = ds.sel(layer=slice(botm_layer))

    # rename bottom to botm, as it is called in FloPy
    ds = ds.rename_vars({"bottom": "botm"})

    # slice data vars
    if variables is None:
        variables = list(ds.data_vars)
    else:
        if isinstance(variables, str):
            variables = [variables]
        if probabilities:
            variables = variables + ("sdh", "sdv")
        ds = ds[list(variables)]

    # since version REGIS v02r2s2 (22.07.2024) NaN values are replaced by -9999
    # we set these values to NaN again
    if nodata is not None:
        for var in variables:
            ds[var] = ds[var].where(ds[var] != nodata)

    ds.attrs["gridtype"] = "structured"
    ds.attrs["extent"] = extent
    for datavar in ds:
        ds[datavar].attrs["source"] = "REGIS"
        ds[datavar].attrs["url"] = REGIS_URL
        ds[datavar].attrs["date"] = dt.datetime.now().strftime("%Y%m%d")
        if datavar in ["top", "botm"]:
            ds[datavar].attrs["units"] = "mNAP"
        elif datavar in ["kh", "kv"]:
            ds[datavar].attrs["units"] = "m/day"
        elif datavar in ["c"]:
            ds[datavar].attrs["units"] = "day"
        elif datavar in ["kD"]:
            ds[datavar].attrs["units"] = "m2/day"

    # set the crs to dutch rd-coordinates
    ds.rio.write_crs(28992, inplace=True)

    return ds

# desired model extent (xmin, xmax, ymin, ymax)
ds_regis_full = xr.open_dataset(REGIS_URL, decode_times=False, decode_coords="all")
extent = (
    float(ds_regis_full.x_bounds.min()),
    float(ds_regis_full.x_bounds.max()),
    float(ds_regis_full.y_bounds.min()),
    float(ds_regis_full.y_bounds.max())
)
#extgent Province of NH
extent = (80000, 153000, 480000, 580000)
a = ds.isel(y=slice(None, None, -1)).sel(x=slice(extent[0], extent[1]), y=slice(extent[2], extent[3]))
for k, v in a.data_vars.items():
    vmin, vmax = v.min().values, v.max().values
    scale_factor, add_offset = nlmod.dims.attributes_encodings.compute_scale_and_offset(vmin, vmax)
    encoding = v.encoding
    encoding["dtype"] = "int16"
    encoding["scale_factor"] = scale_factor
    encoding["add_offset"] = add_offset
    encoding["_FillValue"] = -32767  # default for NC_SHORT
    v.to_netcdf(f"regis_nh_{k}2.nc")

ds.isel(y=slice(None, None, -1)).sel(x=slice(extent[0], extent[1]), y=slice(extent[2], extent[3])).to_netcdf("regis_nh.nc")
ds = get_regis(extent=extent)
# ds = xr.open_dataset("regis_rev.nc")
nlmod.dims.attributes_encodings.get_encodings(ds, set_encoding_inplace=True)
ds.to_netcdf("regis_rev_compressed.nc")
