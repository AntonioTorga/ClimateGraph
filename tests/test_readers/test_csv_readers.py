"""Tests for the in-situ CSV/Excel point-surface readers (Chile, São Paulo,
Quito). These touch the sample files under ``test_data/data/DATOS-INSITU/`` so
they are marked ``slow``; the whole module skips when that directory is absent.
"""

import numpy as np
import pytest
import xarray as xr

from ClimateGraph.reader import Reader
from ClimateGraph.reader.reader.reader import ReadSpec

pytestmark = pytest.mark.slow


@pytest.fixture
def insitu_dir(test_data_dir):
    d = test_data_dir / "data" / "DATOS-INSITU"
    if not d.is_dir():
        pytest.skip("DATOS-INSITU sample files not present")
    return d


def _spec(paths, vars, extras, load_mode="safe"):
    return ReadSpec(paths=list(paths), vars=vars, load_mode=load_mode, extras=extras)


# --------------------------------------------------------------------------- #
# Chile (SINCACSV / CHILE) — one file per station                             #
# --------------------------------------------------------------------------- #


class TestSincaCsv:
    VARS = {
        "PM25": {"name": "PM25", "unit": "ug/m**3"},
        "PM10": {"name": "PM10", "unit": "ug/m**3"},
    }

    @pytest.fixture
    def chile_spec(self, insitu_dir):
        # A 2-3 station subset keeps the test fast (119 files in full).
        files = [insitu_dir / "CHILE" / f"{sid}.csv" for sid in ("104", "105", "118")]
        extras = {"metadata": str(insitu_dir / "CHILE" / "stations.csv")}
        return files, extras

    def test_contract(self, chile_spec):
        files, extras = chile_spec
        reader = Reader.get_reader_subclass("PointSurface", "CHILE")
        ds = reader.read(_spec(files, self.VARS, extras))

        assert isinstance(ds, xr.Dataset)
        assert set(ds.dims) == {"time", "site"}
        assert ds.sizes["site"] == 3
        # Canonical var present; site labelled by filename stem.
        assert "PM25" in ds.data_vars
        assert list(ds["site"].values) == ["104", "105", "118"]
        # Metadata join: lat/lon present and finite (int id ↔ str stem match).
        assert {"latitude", "longitude"}.issubset(ds.coords)
        assert np.isfinite(ds["latitude"].values).all()
        # Extra metadata columns ride along as site coords.
        assert "region" in ds.coords

    def test_safe_equals_unsafe(self, chile_spec):
        files, extras = chile_spec
        reader = Reader.get_reader_subclass("PointSurface", "CHILE")
        safe = reader.read(_spec(files, self.VARS, extras, "safe"))
        unsafe = reader.read(_spec(files, self.VARS, extras, "unsafe"))
        xr.testing.assert_equal(safe, unsafe)

    def test_missing_metadata_raises(self, chile_spec):
        files, _ = chile_spec
        reader = Reader.get_reader_subclass("PointSurface", "CHILE")
        with pytest.raises(ValueError, match="metadata"):
            reader.read(_spec(files, self.VARS, {}))


# --------------------------------------------------------------------------- #
# São Paulo (SAOPAULO) — one file, all stations                               #
# --------------------------------------------------------------------------- #


class TestSaoPaulo:
    VARS = {
        "O3": {"name": "o3", "unit": "ug/m**3"},
        "PM10": {"name": "pm10", "unit": "ug/m**3"},
    }

    @pytest.fixture
    def sp_spec(self, insitu_dir):
        files = [insitu_dir / "SAOPAULO" / "obs_sp_aug_sep_2024.csv"]
        extras = {"metadata": str(insitu_dir / "SAOPAULO" / "stations.csv")}
        return files, extras

    def test_contract(self, sp_spec):
        files, extras = sp_spec
        reader = Reader.get_reader_subclass("PointSurface", "saopaulo")
        ds = reader.read(_spec(files, self.VARS, extras))

        assert set(ds.dims) == {"time", "site"}
        # Renamed to canonical; native lowercase name gone.
        assert "O3" in ds.data_vars
        assert "o3" not in ds.data_vars
        # The non-numeric ``type`` is metadata, not a data variable.
        assert "type" not in ds.data_vars
        assert "type" in ds.coords
        assert {"latitude", "longitude"}.issubset(ds.coords)
        assert np.isfinite(ds["latitude"].values).all()

    def test_timestamps_are_naive(self, sp_spec):
        files, extras = sp_spec
        reader = Reader.get_reader_subclass("PointSurface", "saopaulo")
        ds = reader.read(_spec(files, self.VARS, extras))
        # tz stripped to naive local wall-clock (resolution-agnostic compare).
        assert np.issubdtype(ds["time"].dtype, np.datetime64)
        assert ds["time"].values[0] == np.datetime64("2024-08-01T00:00:00")

    def test_boundary_duplicates_collapsed(self, sp_spec):
        # The export overlaps at the Aug/Sep boundary; the reader must yield a
        # unique time axis rather than erroring on the duplicate rows.
        files, extras = sp_spec
        reader = Reader.get_reader_subclass("PointSurface", "saopaulo")
        ds = reader.read(_spec(files, self.VARS, extras))
        assert ds.indexes["time"].is_unique


# --------------------------------------------------------------------------- #
# Quito (QUITO) — one file per variable                                       #
# --------------------------------------------------------------------------- #


class TestQuito:
    VARS = {
        "CO": {"name": "CO", "unit": "mg/m**3"},
        "NO2": {"name": "NO2", "unit": "ug/m**3"},
    }

    @pytest.fixture
    def quito_spec(self, insitu_dir):
        files = [
            insitu_dir / "QUITO" / "CO_Sep22.csv",
            insitu_dir / "QUITO" / "NO2_Sep22.csv",
        ]
        extras = {
            "metadata": str(insitu_dir / "QUITO" / "EstacionesCoordenadas.xlsx"),
            "var_files": {"CO": "CO_Sep22.csv", "NO2": "NO2_Sep22.csv"},
        }
        return files, extras

    def test_contract(self, quito_spec):
        files, extras = quito_spec
        reader = Reader.get_reader_subclass("PointSurface", "quito")
        ds = reader.read(_spec(files, self.VARS, extras))

        assert set(ds.dims) == {"time", "site"}
        # Variable-per-file merged onto shared time/site.
        assert {"CO", "NO2"}.issubset(ds.data_vars)
        assert ds.sizes["site"] == 9
        assert {"latitude", "longitude"}.issubset(ds.coords)
        # 8 of 9 stations have Excel metadata; EMAUSFQ has none → NaN.
        finite = np.isfinite(ds["latitude"].values)
        assert finite.sum() == 8
        emaus = list(ds["site"].values).index("EMAUSFQ")
        assert not finite[emaus]

    def test_accented_metadata_join(self, quito_spec):
        # "Guamaní"/"El Camal" in the Excel must match the "GUAMANI"/"ELCAMAL"
        # CSV headers via accent/space normalisation.
        files, extras = quito_spec
        reader = Reader.get_reader_subclass("PointSurface", "quito")
        ds = reader.read(_spec(files, self.VARS, extras))
        for site in ("GUAMANI", "ELCAMAL"):
            lat = ds["latitude"].sel(site=site).item()
            assert np.isfinite(lat)

    def test_safe_equals_unsafe(self, quito_spec):
        files, extras = quito_spec
        reader = Reader.get_reader_subclass("PointSurface", "quito")
        safe = reader.read(_spec(files, self.VARS, extras, "safe"))
        unsafe = reader.read(_spec(files, self.VARS, extras, "unsafe"))
        xr.testing.assert_equal(safe, unsafe)

    def test_missing_var_files_raises(self, quito_spec):
        files, extras = quito_spec
        extras = {k: v for k, v in extras.items() if k != "var_files"}
        reader = Reader.get_reader_subclass("PointSurface", "quito")
        with pytest.raises(ValueError, match="var_files"):
            reader.read(_spec(files, self.VARS, extras))
