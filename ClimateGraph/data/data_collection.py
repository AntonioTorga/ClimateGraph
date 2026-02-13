from .data import Data

class DataCollection:
    def __init__(self, main_data: Data, vars:list[str]):
        self.name = main_data.name + "_collection"
        self.obj = Data.obj
        self.geom = Data.geom
        self.others = []
    
    def add_dataset(self, other: Data, vars: str | list[str], resample_method):
        if not isinstance(vars, list): vars = [vars]
        vars = {name:da for name, da in zip(vars, other.get_var(vars))}
        other_geom = other.geom

        #TODO: Manage resampling methods.