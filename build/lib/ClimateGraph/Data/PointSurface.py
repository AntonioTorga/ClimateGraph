from ClimateGraph.Data.Data import Data
from pathlib import Path


class PointSurface(Data):
    def __init__(self, name: str, path: Path | list[Path], **kwargs):
        super().__init__(name, path)

    def load_obj(self, vars: list[str] | None = None):
        # TODO: code this
        pass

    def _set_geom(self):
        # TODO: code this
        pass
