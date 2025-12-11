from .data import Data
from pathlib import Path
from pyresample import AreaDefinition


class RegularGrid(Data):
    def __init__(self, name: str, path: Path | list[Path], **kwargs):
        super().__init__(name, path)

    def _set_geom(self):
        self.geom = AreaDefinition(
            area_id=f"area_{self.name}",
            description=f"Regular grid area definition for {self.name} dataset.",
            projection=self.projection,
            area_extent=self.bbox,
            width=self.get_dim_length("x"),
            height=self.get_dim_length("y"),
        )
