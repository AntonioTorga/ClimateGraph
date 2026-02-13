from ClimateGraph.Data.Data import Data
from pathlib import Path
from pyresample import AreaDefinition


class RegularGrid(Data):
    def __init__(self, name: str, path: Path | list[Path], **kwargs):
        super().__init__(name, path)

    def load_obj(self, vars: list[str] | None = None):
        pass

    def _set_geom(self):
        self.geom = AreaDefinition(area_id = f"area_{self.name}", 
                                   description= f"Regular grid area definition for {self.name} dataset.",
                                   projection= ,
                                   width= self.get_dim_length("x"),
                                   height = self.get_dim_length("y"),
                                   area_extent = self.get_bbox(),
                                   )
