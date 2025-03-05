"""
Compress the REGIS netcdf file using builtin compression.

All variables are compressed with {'zlib': True, 'complevel': 5, 'fletcher32': True, 'dtype': 'float32'}
"""
import nlmod
import xarray as xr

ds = xr.open_dataset("regis_rev.nc")
nlmod.dims.attributes_encodings.get_encodings(ds, set_encoding_inplace=True)
ds.to_netcdf("regis_rev_compressed.nc")
