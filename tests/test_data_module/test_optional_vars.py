"""Data behavior when ``vars`` is omitted (None) or given as a bare list.

These are fast / no-IO: they build a ``RegularGrid`` over an in-memory dataset
with a stub reader (mirroring the conftest fixtures) and exercise the
list/None vars paths added when canonical names became optional.
"""

from __future__ import annotations

from pathlib import Path

import cartopy.crs as ccrs
import pytest

from ClimateGraph.data import RegularGrid


def _make(vars, ds) -> RegularGrid:
    class _StubReader:
        @staticmethod
        def read(spec):
            return ds

    inst = RegularGrid(
        name="grid",
        path=Path("memory://grid"),
        vars=vars,
        reader=_StubReader,
        crs=ccrs.PlateCarree(),
    )
    inst.obj = ds
    return inst


class TestVarsOmitted:
    def test_vars_stays_none(self, regular_grid_dataset):
        d = _make(None, regular_grid_dataset)
        assert d.vars is None

    def test_var_unit_is_none(self, regular_grid_dataset):
        d = _make(None, regular_grid_dataset)
        assert d.var_unit("Temperatura") is None

    def test_get_var_resolves_file_native_name(self, regular_grid_dataset):
        d = _make(None, regular_grid_dataset)
        xa = d.get_var("Temperatura")
        assert xa.name == "Temperatura"

    def test_get_var_missing_raises_clear_keyerror(self, regular_grid_dataset):
        d = _make(None, regular_grid_dataset)
        with pytest.raises(KeyError, match="not found in dataset"):
            d.get_var("DoesNotExist")


class TestVarsList:
    def test_list_normalized_to_identity_dict(self, regular_grid_dataset):
        d = _make(["Temperatura"], regular_grid_dataset)
        assert d.vars == {
            "Temperatura": {"name": "Temperatura", "unit": None, "operation": None}
        }

    def test_var_unit_is_none_without_declared_unit(self, regular_grid_dataset):
        d = _make(["Temperatura"], regular_grid_dataset)
        assert d.var_unit("Temperatura") is None

    def test_get_var_works(self, regular_grid_dataset):
        d = _make(["Temperatura"], regular_grid_dataset)
        xa = d.get_var("Temperatura")
        assert xa.name == "Temperatura"


class TestVarsDictStillWorks:
    def test_var_unit_returns_declared_unit(self, regular_grid_dataset):
        d = _make(
            {"Temperatura": {"name": "Temperatura", "unit": "kelvin"}},
            regular_grid_dataset,
        )
        assert d.var_unit("Temperatura") == "kelvin"
