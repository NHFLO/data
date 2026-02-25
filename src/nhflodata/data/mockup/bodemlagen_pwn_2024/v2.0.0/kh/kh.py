import logging

import geopandas as gpd
import pandas as pd
from params_helper_functions import clip_polygons_to_mask, fill_boundary_with_polygons

from nhflodata.get_paths import get_abs_data_path

# logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

data_path = get_abs_data_path("bodemlagen_pwn_2024", "2.0.0")
data_path_bergen = get_abs_data_path("bodemlagen_pwn_bergen", "1.0.0")
data_path_nhdz = get_abs_data_path("bodemlagen_pwn_nhdz", "1.0.0")

layer_names = ["W11", "S11", "W12", "S12", "W13", "S13", "W21", "S21", "W22", "S22", "W31", "S31", "W32", "S32"]
c_nhdz_fill_values = {  # From bodemlagen_pwn_nhdz/v1.0.0/Ontleding_model_v2.xlsx
    "S11": 1.0,
    "S12": 10.0,
    "S13": 10.0,
    "S21": 10.0,
    "S22": 10.0,
    "S31": 10.0,
    "S32": 10.0,
}

kh_bergen_fill_values = {
    "W11": 7.0,  # Triwaco Excel uses 7.0, but prior nhflo implementations used 8.0.
    "W12": 7.0,
    "W13": 12.0,
    "W21": 15.0,
}
c_bergen_fill_values = {
    "S11": 1.0,
    "S12": 100.0,
    "S13": 100.0,
    "S21": 1.0,
}
bergen_name_mapping = {
    "11": "1A",
    "12": "1B",
    "13": "1C",
    "21": "2",
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
        kh_nhdz[name], _, _ = fill_boundary_with_polygons(
            boundary_gdf=gdf_nhdz,
            source_gdf=k,
            value_col="VALUE",
            # fill_value=kh_bergen_fill_values[name],  # Not used as fill method is 'mean'
            fill_method="mean",
            overlap_priority="last",
            override_gdf=None,
        )

kd_nhdz = {}  # horizontal transmissivity of the aquitards from nhdz
folder = data_path_nhdz / "Bodemparams" / "KDwaarden_aquitards"
s12kd = gpd.read_file(folder / "s12kd.shp").set_crs("EPSG:28992")
s13kd = gpd.read_file(folder / "s13kd.shp").set_crs("EPSG:28992")
s21kd = gpd.read_file(folder / "s21kd.shp").set_crs("EPSG:28992")
s22kd = gpd.read_file(folder / "s22kd.shp").set_crs("EPSG:28992")
folder = data_path_bergen / "Bodemparams" / "Masker_kdwaarden_aquitards"
ms12kd = gpd.read_file(folder / "masker_aquitard12_kd.shp").set_crs("EPSG:28992")
ms13kd = gpd.read_file(folder / "masker_aquitard13_kd.shp").set_crs("EPSG:28992")
ms21kd = gpd.read_file(folder / "masker_aquitard21_kd.shp").set_crs("EPSG:28992")
ms22kd = gpd.read_file(folder / "masker_aquitard22_kd.shp").set_crs("EPSG:28992")

# Each formula is a list of (source_gdf, mask_gdf, mask_value, coefficient) terms
#   kd12s = s12kd*(ms12kd==1) + 0.5*s12kd*(ms12kd==2) + 3*s12kd*(ms12kd==3)
#   kd13s = (s13kd*(ms13kd==1) + 0.5*s12kd*(ms12kd==2)) * 1.04
#   kd21s = (s21kd*(ms21kd==1) + s13kd*(ms13kd==2)) * 0.6
#   kd22s = s22kd*(ms22kd==1) + s21kd*(ms21kd==2)
#   kd31s = s22kd*(ms22kd==2)
kd_formulas = {
    "S12": [
        (s12kd, ms12kd, 1, 1.0),
        (s12kd, ms12kd, 2, 0.5),
        (s12kd, ms12kd, 3, 3.0),
    ],
    "S13": [
        (s13kd, ms13kd, 1, 1.04),
        (s12kd, ms12kd, 2, 0.5 * 1.04),
    ],
    "S21": [
        (s21kd, ms21kd, 1, 0.6),
        (s13kd, ms13kd, 2, 0.6),
    ],
    "S22": [
        (s22kd, ms22kd, 1, 1.0),
        (s21kd, ms21kd, 2, 1.0),
    ],
    "S31": [
        (s22kd, ms22kd, 2, 1.0),
    ],
}

for name, terms in kd_formulas.items():
    parts = [clip_polygons_to_mask(src, mask, mask_value=val, coefficient=coeff) for src, mask, val, coeff in terms]
    source = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs="EPSG:28992")
    kd_nhdz[name], _, _ = fill_boundary_with_polygons(
        boundary_gdf=gdf_nhdz,
        source_gdf=source,
        value_col="VALUE",
        fill_method="fill_value",
        fill_value=0.01,  # From bodemlagen_pwn_nhdz/v1.0.0/Ontleding_model_v2.xlsx 
        overlap_priority="sum",
    )

c_nhdz = {}
for name in layer_names:
    if name.startswith("S"):
        fp = data_path_nhdz / "Bodemparams" / "Cwaarden_aquitards" / f"C{name}.shp"
        c = gpd.read_file(fp).set_crs("EPSG:28992")
        if name == "S22":
            c["VALUE"] *= 1.02  # From bodemlagen_pwn_nhdz/v1.0.0/Ontleding_model_v2.xlsx

        c_nhdz[name], overlaps_gdf, fill_gdf = fill_boundary_with_polygons(
            boundary_gdf=gdf_nhdz,
            source_gdf=c,
            value_col="VALUE",
            fill_value=c_nhdz_fill_values[name],
            fill_method="fill_value",
            overlap_priority="last",
            override_gdf=None,
        )
        overlaps_gdf.to_file(data_path / "kh" / f"C{name}_NHDZ_overlaps.geojson", driver="GeoJSON")
        fill_gdf.to_file(data_path / "kh" / f"C{name}_NHDZ_fill.geojson", driver="GeoJSON")

# Bergen
kh_bergen = {}
for name in bergen_name_mapping:
    kh_bergen[f"W{name}"], _, _ = fill_boundary_with_polygons(
        boundary_gdf=gdf_bergen,
        source_gdf=None,  # Are constants for Bergen, so use fill value only
        value_col="VALUE",  # Not used as source_gdf is None
        fill_value=kh_bergen_fill_values[f"W{name}"],
        fill_method="fill_value",
        overlap_priority="last",  # Not used as source_gdf is None
        override_gdf=None,
    )

c_bergen = {}
for name, bergen_name in bergen_name_mapping.items():
    fp = data_path_bergen / "Bodemparams" / f"C{bergen_name}.shp"
    c = gpd.read_file(fp).set_crs("EPSG:28992")
    c_bergen[f"S{name}"], overlaps_gdf, fill_gdf = fill_boundary_with_polygons(
        boundary_gdf=gdf_bergen,
        source_gdf=c,
        value_col="VALUE",  # Not used as source_gdf is None
        fill_value=c_bergen_fill_values[f"S{name}"],
        fill_method="fill_value",
        overlap_priority="last",  # Not used as source_gdf is None
        override_gdf=None,
    )
    overlaps_gdf.to_file(data_path / "kh" / f"C{bergen_name}_Bergen_overlaps.geojson", driver="GeoJSON")
    fill_gdf.to_file(data_path / "kh" / f"C{bergen_name}_Bergen_fill.geojson", driver="GeoJSON")

"""
# NHDZ Bergen
S21 S2
S13 S1C
S12 S1B
S11 S1A



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
