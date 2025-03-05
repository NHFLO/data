# Created by: bas.des.tombe@pwn.nl

import os

import nlmod
import xarray as xr

nhflo_data_dir = "/Users/bdestombe/Downloads"
fp_cl = os.path.join(nhflo_data_dir, "regis_prev.nc")
assert os.path.isfile(fp_cl), f"file {fp_cl} not found"
cl = xr.open_dataset(fp_cl)

for p in cl.percentile.values:
    conc = cl["3d-chloride"].sel(percentile=p).rename(f"chloride_{p}")
    vmin, vmax = conc.min().item(), conc.max().item()
    encoding = {
        "zlib": True,
        "complevel": 5,
        "fletcher32": True,  # Store checksums to detect corruption
    }
    dval_max = 5.0
    assert nlmod.dims.attributes_encodings.is_int16_allowed(vmin, vmax, dval_max), "Store as float instead"
    width = 32766 + 32767
    scale_factor = (vmax - vmin) / width
    add_offset = vmax - scale_factor * 32767

    encoding["dtype"] = "int16"
    encoding["scale_factor"] = scale_factor
    encoding["add_offset"] = add_offset
    encoding["_FillValue"] = -32767  # default for NC_SHORT

    fp_out = os.path.join(nhflo_data_dir, f"chloride_{p}.nc")
    conc.to_netcdf(fp_out, encoding={f"chloride_{p}": encoding})
    conc2 = xr.open_dataset(fp_out)[f"chloride_{p}"].compute()

    import numpy as np

    print(np.nanmax(np.abs(conc.values - conc2.values)))  # ~0.1 mg/l
