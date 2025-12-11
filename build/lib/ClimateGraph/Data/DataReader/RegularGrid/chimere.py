from ClimateGraph.Data.DataReader.RegularGrid.DefaultRG import DefaultRegularGridReader


class Chimere(DefaultRegularGridReader):
    rename = {
        "nav_lat": "latitude",
        "nav_lon": "longitude",
        "time_counter": "time",
        "bottom_top": "z",
    }

    @staticmethod
    def open_mfdataset(files, var_list=None, **kwargs):
        return super().open_mfdataset(files, var_list, rename=Chimere.rename, **kwargs)
