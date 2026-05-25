import logging

import xarray as xr

from ..reader import ReadSpec
from .default import DefaultRegularGridReader

log = logging.getLogger(__name__)


class Chimere(DefaultRegularGridReader):
    rename = {
        "nav_lat": "latitude",
        "nav_lon": "longitude",
        "time_counter": "time",
        "bottom_top": "z",
    }

    @classmethod
    def _postprocess(cls, ds: xr.Dataset, spec: ReadSpec) -> xr.Dataset:
        # CHIMERE files carry a vertical 'z' axis. We pick a single level
        # via reader_kwargs['vertical_level'] (default 0 = surface). The
        # old reader silently always took z=0, which was ROADMAP issue 8;
        # now the choice is explicit and logged.
        if "z" in ds.dims:
            level = spec.extras.get("vertical_level", 0)
            log.info("Chimere: selecting vertical level z=%s", level)
            ds = ds.isel(z=level)
        return ds
