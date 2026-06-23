from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

import numpy as np
from pyresample import kd_tree


@runtime_checkable
class ResampleEngine(Protocol):
    """Protocol for spatial resampling backends.

    Two-step design: ``prepare`` computes reusable indices/weights from the
    source and destination geometries (expensive, done once per geometry pair),
    and ``make_resampler`` returns a callable that applies those to a single
    2-D array (cheap, called per variable per timestep via apply_ufunc).
    """

    def prepare(
        self,
        src_geom,
        dst_geom,
        radius_of_influence: int,
        **kwargs,
    ) -> Any:
        """Compute resampling info (indices, weights, etc.).

        The returned object is opaque — it is passed back into
        ``make_resampler`` without inspection by the caller.
        """
        ...

    def make_resampler(
        self,
        info: Any,
        dst_shape: tuple,
    ) -> Callable[[np.ndarray], np.ndarray]:
        """Return a function ``f(src_2d) -> dst_shaped`` using precomputed info."""
        ...


class PyresampleEngine:
    """Pyresample KD-tree backend. Supports nearest and gaussian methods."""

    def __init__(
        self,
        method: str = "nearest",
        sigmas: float = 10000,
        neighbours: int | None = None,
    ):
        self.method = method
        self.sigmas = sigmas
        self.neighbours = neighbours or (1 if method == "nearest" else 8)

    def prepare(self, src_geom, dst_geom, radius_of_influence: int, **kwargs) -> tuple:
        return kd_tree.get_neighbour_info(
            src_geom,
            dst_geom,
            radius_of_influence=radius_of_influence,
            neighbours=self.neighbours,
        )

    def make_resampler(self, info: tuple, dst_shape: tuple) -> Callable:
        valid_input, valid_output, index_array, dist_array = info

        if self.method == "nearest":

            def _resample(x: np.ndarray) -> np.ndarray:
                return kd_tree.get_sample_from_neighbour_info(
                    "nn",
                    dst_shape,
                    x,
                    valid_input,
                    valid_output,
                    index_array,
                    dist_array,
                    fill_value=np.nan,
                )

        elif self.method == "gaussian":
            sigma = self.sigmas
            n_neighbours = index_array.shape[1] if index_array.ndim > 1 else 1

            def _weight(dist):
                return np.exp(-(dist**2) / (2 * sigma**2))

            def _resample(x: np.ndarray) -> np.ndarray:
                return kd_tree.get_sample_from_neighbour_info(
                    "custom",
                    dst_shape,
                    x,
                    valid_input,
                    valid_output,
                    index_array,
                    dist_array,
                    weight_funcs=[_weight] * n_neighbours,
                    fill_value=np.nan,
                )

        else:
            raise ValueError(
                f"PyresampleEngine does not support method {self.method!r}. "
                f"Available: nearest, gaussian."
            )

        return _resample


ENGINES: dict[str, type] = {
    "pyresample": PyresampleEngine,
}


def get_engine(
    backend: str | ResampleEngine = "pyresample", **kwargs
) -> ResampleEngine:
    """Resolve an engine by backend name or return an already-instantiated one."""
    if isinstance(backend, str):
        cls = ENGINES.get(backend.lower())
        if cls is None:
            raise ValueError(
                f"Unknown resample backend {backend!r}. Available: {list(ENGINES)}"
            )
        return cls(**kwargs)
    return backend
