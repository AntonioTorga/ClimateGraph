from pathlib import Path
import logging
import cartopy.crs as ccrs

logging.basicConfig(level=logging.INFO)

CRS_TYPES = {"platecarree": ccrs.PlateCarree}


def manage_path(paths: str | list[str]) -> list[Path]:

    if isinstance(paths, str):
        paths = [paths]

    result: list[Path] = []

    for raw in paths:
        p = Path(raw)

        # Detect glob pattern
        has_glob = any(char in raw for char in "*?[]")

        if has_glob:
            matches = list(Path().glob(raw))
            if not matches:
                logging.debug(f"No files match pattern: {raw}")
            result.extend(m.resolve() for m in matches if m.exists())
        else:
            if not p.exists():
                logging.debug(f"Path does not exist: {raw}")
            result.append(p.resolve())

    return result


def manage_crs(crs: str | None):
    if crs is None:
        crs = "platecarree"
    if crs not in CRS_TYPES:
        raise ValueError(f"CRS type {crs} not supported.")
    return CRS_TYPES[crs]
