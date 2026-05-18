from .default import DefaultPointSurfaceReader


class SINCA(DefaultPointSurfaceReader):
    """SINCA (Sistema de Información Nacional de Calidad del Aire) reader.

    Currently a thin subclass of the default — kept distinct so SINCA-specific
    download/preprocessing (e.g. fetching from the SINCA API) can land here
    without touching DMC.
    """
