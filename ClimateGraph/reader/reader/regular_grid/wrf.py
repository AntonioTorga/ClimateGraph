from .default import DefaultRegularGridReader
from ClimateGraph.data import RegularGrid

from typing import Dict, Any
from pathlib import Path
import xarray as xr


class Wrf(DefaultRegularGridReader):
    main_type = RegularGrid
    rename = {
        "Time": "time",
        "south_north": "y",
        "west_east": "x",
        "XLONG": "longitude",
        "XLAT": "latitude",
    }

    variable_aggregation = {
        "noy_gas": {
            "hno3": 1,
            "no": 1,
            "no2": 1,
            "no3": 1,
            "pan": 1,
            "tpan": 1,
            "hono": 1,
            "hno4": 1,
            "onit": 1,
            "n2o5": 2,
            "ison": 1,
            "nald": 1,
            "mpan": 1,
        },
        "noy_aer": {"no3ai": 1, "no3aj": 1},
        "nox": {"no": 1, "no2": 1},
        "pm25_cl": {"clai": 1, "claj": 1},
        "pm25_ec": {"eci": 1, "ecj": 1},
        "pm25_na": {"naai": 1, "naaj": 1},
        "pm25_nh4": {"nh4ai": 1, "nh4aj": 1},
        "pm25_no3": {"no3ai": 1, "no3aj": 1},
        "pm25_so4": {"so4ai": 1, "so4aj": 1},
        "pm25_om": {
            "asoa1i": 1,
            "asoa1j": 1,
            "asoa2i": 1,
            "asoa2j": 1,
            "asoa3i": 1,
            "asoa3j": 1,
            "asoa4i": 1,
            "asoa4j": 1,
            "bsoa1i": 1,
            "bsoa1j": 1,
            "bsoa2i": 1,
            "bsoa2j": 1,
            "bsoa3i": 1,
            "bsoa3j": 1,
            "bsoa4i": 1,
            "bsoa4j": 1,
            "orgpai": 1,
            "orgpaj": 1,
        },
    }

    @staticmethod
    def open_mfdataset(
        files: Path | list[Path], vars: Dict[str, Any] = None, **kwargs
    ) -> xr.Dataset:
        return super().open_mfdataset(
            files,
            vars,
            rename=Wrf.rename,
        )
