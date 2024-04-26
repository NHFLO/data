import os

import nlmod
import xarray as xr
from nhflodata.get_paths import get_abs_data_path

nhflo_data_dir = r"C:\Users\oebbe\02_python\nhflo_data"
#fp_gt = os.path.join(nhflo_data_dir, 'modelbestanden_nhflozz', "geotop.nc")
geotop_path = get_abs_data_path(name="geotop", version="latest", location="get_from_env")
geotop_ds = xr.open_dataset(os.path.join(geotop_path, 'geotop.nc'), mask_and_scale=False)


# gt_ds = xr.open_dataset(fp_gt)

geotop_ds.to_netcdf(os.path.join(geotop_path, 'geotop_zip.nc'), 
                    encoding={'strat': {'zlib': True, 'complevel': 5, 'fletcher32': True},
                              'lithok': {'zlib': True, 'complevel': 5, 'fletcher32': True}})
