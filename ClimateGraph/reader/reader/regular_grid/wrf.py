"""Reader for WRF model output."""

import xarray as xr

from ..reader import ReadSpec
from .default import DefaultRegularGridReader


class Wrf(DefaultRegularGridReader):
    # `Time` and `XTIME` are alternatives, never both: cleaned NetCDF carries an
    # indexed `Time` coordinate, while raw wrfout leaves `Time` a bare dimension
    # and puts the valid times in `XTIME`. restrict_rename_to_present keeps
    # whichever the file actually has.
    rename = {
        "Time": "time",
        "XTIME": "time",
        "south_north": "y",
        "west_east": "x",
        "bottom_top": "z",
        "XLONG": "longitude",
        "XLAT": "latitude",
    }
    restrict_rename_to_present = True
    # Raw wrfout has no time index until `_postprocess` builds one, so the lazy
    # combine orders files by path instead of by coordinate.
    combine_kwargs = {"combine": "nested", "concat_dim": "time"}

    @classmethod
    def _preprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Rename/drop, plus the lat/lon shape raw wrfout differs in.

        WRF writes ``XLAT``/``XLONG`` once per output time even though the grid
        is static, leaving them 3-D — which breaks the ``SwathDefinition`` that
        ``RegularGrid._set_geom`` builds for resampling.

        A no-op on input that already has 2-D lat/lon. Reads no values, so the
        lazy path does not touch all 1825 files while opening them.
        """
        ds = super()._preprocess(ds, spec)

        for coord in ("latitude", "longitude"):
            if coord in ds.coords and "time" in ds[coord].dims:
                ds = ds.assign_coords({coord: ds[coord].isel(time=0, drop=True)})

        return ds

    @classmethod
    def _postprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Promote ``time`` to an index, once, after the files are combined.

        Renaming ``XTIME`` does not carry an index across, and ``reset_coords()``
        in the parent demotes a non-index ``time`` to a data variable. A no-op
        for ``_open_many``, which gets its index from the gathered timestamps;
        it serves the lazy and unsafe paths, which concat in path order.
        """
        ds = super()._postprocess(ds, spec)

        if "time" in ds.variables and "time" not in ds.indexes:
            ds = ds.set_index(time="time")

        return ds
