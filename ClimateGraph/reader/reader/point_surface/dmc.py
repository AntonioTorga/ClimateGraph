from .default import DefaultPointSurfaceReader


class DMC(DefaultPointSurfaceReader):
    """Dirección Meteorológica de Chile point-surface reader.

    Currently a thin subclass of the default — kept distinct so DMC-specific
    download/preprocessing (e.g. fetching from the DMC API) can land here
    without touching SINCA.
    """
