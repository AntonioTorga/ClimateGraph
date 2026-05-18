from .default import DefaultRegularGridReader


class Wrf(DefaultRegularGridReader):
    rename = {
        "Time": "time",
        "south_north": "y",
        "west_east": "x",
        "bottom_top": "z",
        "XLONG": "longitude",
        "XLAT": "latitude",
    }
