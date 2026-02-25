import logging

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from params_helper_functions import fill_boundary_with_polygons
from shapely import MultiPolygon, Polygon, make_valid

from nhflodata.get_paths import get_abs_data_path

# logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

data_path = get_abs_data_path("bodemlagen_pwn_2024", "2.0.0")
data_path_bergen = get_abs_data_path("bodemlagen_pwn_bergen", "1.0.0")
data_path_nhdz = get_abs_data_path("bodemlagen_pwn_nhdz", "1.0.0")

layer_names = ["W11", "S11", "W12", "S12", "W13", "S13", "W21", "S21", "W22", "S22", "W31", "S31", "W32", "S32"]
kh_bergen_fill_values = {
    "W11": 8.0,
    "S11": np.nan,
    "W12": 7.0,
    "S12": np.nan,
    "W13": 12.0,
    "S13": np.nan,
    "W21": 15.0,
    "S21": np.nan,
}


# Get boundaries that we need to fill up with the data from Bergen and NHDZ
gdf_bergen = gpd.read_file(data_path / "boundaries" / "triwaco_model_bergen.geojson")
gdf_nhdz = gpd.read_file(data_path / "boundaries" / "triwaco_model_nhdz.geojson")

# NHDZ
kh_nhdz = {}
for name in layer_names:
    if name.startswith("W"):
        fp = data_path_nhdz / "Bodemparams" / "Kwaarden_aquifers" / f"K{name}.shp"
        k = gpd.read_file(fp).set_crs("EPSG:28992")
        kh_nhdz[name], _ = fill_boundary_with_polygons(
            boundary_gdf=gdf_nhdz,
            source_gdf=k,
            value_col="VALUE",
            fill_value=kh_bergen_fill_values[name],  # Not used as fill method is 'mean'
            fill_method="mean",
            overlap_priority="smallest",
            override_gdf=None,
        )

# Bergen
kh_bergen = {}
for name in layer_names:
    if name.startswith("W"):
        kh_bergen[name], _ = fill_boundary_with_polygons(
            boundary_gdf=gdf_bergen,
            source_gdf=None,  # Are constants for Bergen, so use fill value only
            value_col="VALUE",  # Not used as source_gdf is None
            fill_value=kh_bergen_fill_values[name],
            fill_method="fill_value",
            overlap_priority="smallest",  # Not used as source_gdf is None
            override_gdf=None,
        )

"""
    kh[0] = 8.0
    kh[1] = thickness[1] / clist[0] / f_anisotropy
    kh[2] = 7.0
    kh[3] = thickness[3] / clist[1] / f_anisotropy
    kh[4] = 12.0
    kh[5] = thickness[5] / clist[2] / f_anisotropy
    kh[6] = 15.0
    kh[7] = thickness[7] / clist[3] / f_anisotropy
    kh[8] = 20.0

# Top
RL1=mv
RL2=BA1A
RL3=if(BA1B<TH2,BA1B,TH2-0.01)
RL4=if(BA1C<TH3,BA1C,TH3-0.01)
RL5=if(BA1D<TH4,BA1D,TH4-0.01)
RL6=if(BAQ2<TH5,BAQ2,TH5-0.01)
RL7=-105

# Bottom
TH1=BA1A+DI1A
TH2=if(BA1B+DI1B<RL2,BA1B+DI1B,RL2-0.01)
TH3=if(BA1C+DI1C<RL3,BA1C+DI1C,RL3-0.01)
TH4=if(BA1D+DI1D<RL4,BA1D+DI1D,RL4-0.01)
TH5=if(BAQ2+DI2<RL5,BAQ2+DI2,RL5-0.01)
TH6=-95
TH7=-129
out = xr.concat(
    (
        a[n("KW11")],  # Aquifer 11
        b.isel(layer=1) / a[n("C11AREA")] * anisotropy,  # Aquitard 11
        a[n("KW12")],  # Aquifer 12
        b.isel(layer=3) / a[n("C12AREA")] * anisotropy,  # Aquitard 12
        a[n("KW13")],  # Aquifer 13
        b.isel(layer=5) / a[n("C13AREA")] * anisotropy,  # Aquitard 13
        a[n("KW21")],  # Aquifer 21
        b.isel(layer=7) / a[n("C21AREA")] * anisotropy,  # Aquitard 21
        a[n("KW22")],  # Aquifer 22
        b.isel(layer=9) / a[n("C22AREA")] * anisotropy,  # Aquitard 22
        a[n("KW31")],  # Aquifer 31
        b.isel(layer=11) / a[n("C31AREA")] * anisotropy,  # Aquitard 31
        a[n("KW32")],  # Aquifer 32
        b.isel(layer=13) / a[n("C32AREA")] * anisotropy,  # Aquitard 32
    ),
    dim=layer_names,
)

s12k = (
    a[n("s12kd")] * (a[n("ms12kd")] == 1)
    + 0.5 * a[n("s12kd")] * (a[n("ms12kd")] == 2)
    + 3 * a[n("s12kd")] * (a[n("ms12kd")] == 3)
) / b.isel(layer=3)
s13k = a[n("s13kd")] * (a[n("ms13kd")] == 1) + 1.12 * a[n("s13kd")] * (a[n("ms13kd")] == 2) / b.isel(layer=5)
s21k = a[n("s21kd")] * (a[n("ms21kd")] == 1) + a[n("s21kd")] * (a[n("ms21kd")] == 2) / b.isel(layer=7)
s22k = 2 * a[n("s22kd")] * (a[n("ms22kd")] == 1) + a[n("s22kd")] * (a[n("ms22kd")] == 1) / b.isel(layer=9)

out.loc[{"layer": "S12"}] = out.loc[{"layer": "S12"}].where(np.isnan(s12k), other=s12k)
out.loc[{"layer": "S13"}] = out.loc[{"layer": "S13"}].where(np.isnan(s13k), other=s13k)
out.loc[{"layer": "S21"}] = out.loc[{"layer": "S21"}].where(np.isnan(s21k), other=s21k)
out.loc[{"layer": "S22"}] = out.loc[{"layer": "S22"}].where(np.isnan(s22k), other=s22k)
    
"""
