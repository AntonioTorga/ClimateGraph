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

    @classmethod
    def _preprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        """Rename/drop/index, plus the two shapes raw wrfout differs in.

        1. Renaming ``XTIME`` does not carry an index across, so ``time`` comes
           out as a plain coordinate. Without a dimension coordinate
           ``open_mfdataset`` cannot order the files and fails with "Could not
           find any dimension coordinates to use to order the Dataset objects
           for concatenation".
        2. WRF writes ``XLAT``/``XLONG`` once per output time even though the
           grid is static, leaving them 3-D — which breaks the
           ``SwathDefinition`` that ``RegularGrid._set_geom`` builds for
           resampling.

        Both steps are no-ops on input that already has an indexed ``time`` and
        2-D lat/lon.
        """
        ds = super()._preprocess(ds, spec)

        # reset_coords() in the parent demotes a non-index `time` to a data
        # variable; promoting it back here is what actually builds the index.
        if "time" in ds.variables and "time" not in ds.indexes:
            ds = ds.set_index(time="time")

        for coord in ("latitude", "longitude"):
            if coord in ds.coords and "time" in ds[coord].dims:
                ds = ds.assign_coords({coord: ds[coord].isel(time=0, drop=True)})

        return ds
