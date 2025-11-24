from .Data import Data
from pathlib import Path


class PointSurface(Data):
    def __init__(self, name: str, path: Path | list[Path], **kwargs):
        super().__init__(name, path)

    def read_obj(self, vars: list[str] | None = None):
        pass

    def _set_geom(self):
        pass
