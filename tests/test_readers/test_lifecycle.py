"""Unit tests for the Reader template-method lifecycle.

These tests do not touch disk: they install a fake reader subclass with
instrumented hooks and assert the orchestration walks them in the documented
order, both for safe and unsafe load modes.
"""

from pathlib import Path

import pytest
import xarray as xr

from ClimateGraph.reader.reader.reader import Reader, ReadSpec


def _ds(value: int) -> xr.Dataset:
    return xr.Dataset({"v": ("t", [value])}, coords={"t": [value]})


@pytest.fixture
def tracked_reader():
    """A throwaway Reader subclass that records each hook invocation."""
    calls: list[str] = []

    class _Tracked(Reader):
        topology = f"_track_{id(calls)}"  # unique per-fixture, avoid registry clash

        @classmethod
        def _resolve_paths(cls, spec):
            calls.append("resolve")
            return spec.paths

        @classmethod
        def _open_many(cls, paths, spec):
            calls.append("open_many")
            return _ds(0)

        @classmethod
        def _open_one(cls, path, spec):
            calls.append(f"open_one:{path.name}")
            return _ds(int(path.stem))

        @classmethod
        def _to_xarray(cls, raw, spec):
            calls.append("to_xarray")
            return raw

        @classmethod
        def _preprocess(cls, ds, spec):
            calls.append("preprocess")
            return ds

        @classmethod
        def _join(cls, pieces, spec):
            calls.append("join")
            return xr.concat(pieces, dim="t")

        @classmethod
        def _postprocess(cls, ds, spec):
            calls.append("postprocess")
            return ds

    yield _Tracked, calls

    # Clean up registry so the throwaway topology doesn't leak between tests.
    Reader.registry.pop(_Tracked.topology.lower(), None)


def test_safe_mode_call_order(tracked_reader):
    cls, calls = tracked_reader
    cls.read(ReadSpec(paths=[Path("a.nc"), Path("b.nc")], load_mode="safe"))
    # In safe mode the orchestrator trusts _open_many to return a
    # fully-preprocessed Dataset (the default implementation invokes
    # _to_xarray + _preprocess per file via xr.open_mfdataset's
    # `preprocess=` kwarg). Our mock _open_many here just returns a
    # canned Dataset and never fires those callbacks, so the visible
    # call order is the short one.
    assert calls == ["resolve", "open_many", "postprocess"]


def test_unsafe_mode_iterates_and_joins(tracked_reader):
    cls, calls = tracked_reader
    cls.read(ReadSpec(paths=[Path("1.nc"), Path("2.nc")], load_mode="unsafe"))
    assert calls == [
        "resolve",
        "open_one:1.nc",
        "to_xarray",
        "preprocess",
        "open_one:2.nc",
        "to_xarray",
        "preprocess",
        "join",
        "postprocess",
    ]


def test_unknown_load_mode_raises(tracked_reader):
    cls, _ = tracked_reader
    with pytest.raises(ValueError, match="Unknown load_mode"):
        cls.read(ReadSpec(paths=[Path("a.nc")], load_mode="nope"))


def test_default_open_many_wires_per_file_pipeline(monkeypatch):
    """The default _open_many should pass a per-file callback as the
    `preprocess=` kwarg to xr.open_mfdataset and request parallel opens.
    Without this wiring the safe path would skip _to_xarray and
    _preprocess entirely. End-to-end behaviour (the callback actually
    renaming and dropping) is covered by the slow safe-vs-unsafe
    equivalence tests on real files.
    """
    import xarray as xr

    from ClimateGraph.reader.reader.regular_grid.default import (
        DefaultRegularGridReader,
    )

    captured = {}

    def fake_open_mfdataset(paths, **kwargs):
        captured["paths"] = list(paths)
        captured["kwargs"] = kwargs
        return xr.Dataset()

    monkeypatch.setattr(xr, "open_mfdataset", fake_open_mfdataset)

    spec = ReadSpec(paths=[Path("a.nc")], vars=None)
    DefaultRegularGridReader._open_many([Path("a.nc")], spec)

    assert captured["kwargs"]["parallel"] is True
    assert captured["kwargs"]["chunks"] == "auto"
    assert callable(captured["kwargs"]["preprocess"])


def test_resolve_paths_returning_empty_raises(tracked_reader):
    cls, _ = tracked_reader

    class _Empty(cls):
        topology = f"_empty_{id(cls)}"

        @classmethod
        def _resolve_paths(cls, spec):
            return []

    try:
        with pytest.raises(ValueError, match="returned no paths"):
            _Empty.read(ReadSpec(paths=[Path("x.nc")]))
    finally:
        Reader.registry.pop(_Empty.topology.lower(), None)
