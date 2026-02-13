import pkgutil
import importlib

for module in pkgutil.iter_modules(__path__):
    print(f"Importing {__name__}.{module.name}")
    importlib.import_module(f"{__name__}.{module.name}")

from .reader import Reader
# from .downloader import Downloader

# TODO: enable Downloader when it is implemented

__all__ = ["Reader",
        #    "Downloader",
           ]
