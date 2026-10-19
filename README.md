# NHFLO-data
Metadata of data owned by HHNK and PWN

Note that the content of this repository is available under a not-so-permissive open-source licence: GNU AGPLv3. Please have a look at [choose a license](https://choosealicense.com/licenses/agpl-3.0/) for the key conditions and limitations of this license before getting started.

## PWN layer translation table

For `bodemlagen_pwn_2024` version `3.0.0`, read `bodemlagenvertaaltabel.csv`
from the directory returned by
`nhflodata.get_paths.get_abs_data_path("bodemlagen_pwn_2024", "3.0.0")`.
It is based on the proposed KRk1 mapping previously stored in
`bodemlagen_pwn_regis_koppeltabel` version `1.1.0`. The existing geological
assumptions are retained; moving the table does not validate them.

The v3 table uses `W21A`, `S21A`, and `W21B`, matching the layer names in
`botm.py`. `ASSUMPTION1_index` gives the zero-based index in its 16-layer stack;
unmapped REGIS layers have an empty name and index. The published standard
table in `bodemlagen_pwn_regis_koppeltabel` remains available for older consumers.
The two datasets have independent version numbers.

The accompanying report (`rapportage_lagenmodel_pwn_concept_20261007.pdf`,
sections 4.1.3 and 5.2.3) identifies S21A as the former S21_0, interpreted
as the first Kreftenheye clay unit (KRk1), with an assumed thickness of 2 m.
It retains the name W21 for the aquifer below S21A; the v3 code and this
table use W21B for that aquifer. S21 remains the Eem aquitard.

### V3 hydraulic parameters

Run `conductances.py` in the v3 `conductances` directory with `nhflodata`,
`geopandas`, and `pandas` available. It resolves all inputs through
`get_abs_data_path`, respecting `NHFLODATA_LOCATION`. Confirm that this points
to the intended unaltered data before generating production parameters.

The regional Triwaco footprint files in v3 are unchanged copies of the v2
footprints. The generator already used them to fill gaps within each source
model and give NHDZ priority where both regions provide data. They are not
the per-layer interpolation boundaries: replacing the regional footprints
with layer convex hulls would change the coverage of every hydraulic
parameter. The generator reads the Bergen and NHDZ source datasets at
version `1.0.0`; it neither reads nor writes the v2 combined dataset.

For NHDZ, both `W21A` and `W21B` use the original `KW21.shp` conductivity.
For Bergen, the original model specifies 15 m/d above its 1D aquitard and
20 m/d below it (`basismodel_MODEL.INI`, TX4 and TX5). `S21A` uses `C1D.shp`
as an additional, independently defined resistance (CL4); the existing
`S13`/`S21` resistance inputs are not reduced.

S21A follows the same resistance processing as the other aquitards:
`C1D.shp` supplies the polygon values and the original CL4 default of 1 day
fills source gaps within the Bergen footprint. There is no NHDZ resistance
source for S21A, so its combined output contains only the Bergen data.
There is no layer-specific resistance helper or use of top/thickness masks
in this step. Layer presence and zero thickness remain encoded in the
layer-geometry data and must be handled consistently downstream for all
layers. No NHDZ transmissivity source is invented for S21A; existing KD
formulas are unchanged. Resistance `c` is in days, not MODFLOW conductance.