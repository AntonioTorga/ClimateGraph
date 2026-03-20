import pkgutil
import importlib

from .reader import Reader

__all__ = [
    "Reader",
    #    "Downloader",
]

for module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{module.name}")
