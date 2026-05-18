import numpy as np
import pytest
import xarray as xr
from pyresample.geometry import SwathDefinition


class TestGetVar:
    def test_returns_dataarray(self, regular_grid_data):
        xa = regular_grid_data.get_var("Temperatura")
        assert isinstance(xa, xr.DataArray)
        assert set(xa.dims) == {"time", "y", "x"}

    def test_as_array(self, regular_grid_data):
        arr = regular_grid_data.get_var("Temperatura", as_array=True)
        assert isinstance(arr, np.ndarray)

    def test_in_unit_conversion(self, regular_grid_data):
        # Fixture's Temperatura is in kelvin (~285); convert to Celsius.
        xa = regular_grid_data.get_var("Temperatura", in_unit="degC")
        assert float(xa.mean()) < 50.0  # would be ~12 if conversion worked

    def test_missing_var_raises(self, regular_grid_data):
        with pytest.raises(KeyError):
            regular_grid_data.get_var("NotAVar")

    def test_reduction_with_keep_dims(self, regular_grid_data):
        xa = regular_grid_data.get_var(
            "Temperatura",
            reduction_func="mean",
            keep_dims=["time"],
        )
        assert set(xa.dims) == {"time"}


class TestGetCoordinates:
    def test_single_coord(self, regular_grid_data):
        lats = regular_grid_data.get_coordinates("latitude")
        assert isinstance(lats, xr.DataArray)

    def test_multiple_coords(self, regular_grid_data):
        lons, lats = regular_grid_data.get_coordinates(["longitude", "latitude"])
        assert lons.shape == lats.shape

    def test_as_array(self, regular_grid_data):
        lats = regular_grid_data.get_coordinates("latitude", as_array=True)
        assert isinstance(lats, np.ndarray)

    def test_missing_coord_raises(self, regular_grid_data):
        with pytest.raises(KeyError):
            regular_grid_data.get_coordinates("not-a-coord")


class TestBboxAndDims:
    def test_bbox_matches_fixture(self, regular_grid_data):
        minlon, minlat, maxlon, maxlat = regular_grid_data.bbox
        assert minlon == pytest.approx(-73.0)
        assert maxlon == pytest.approx(-69.0)
        assert minlat == pytest.approx(-36.0)
        assert maxlat == pytest.approx(-33.0)

    def test_dims(self, regular_grid_data):
        assert regular_grid_data.dims == {"time": 6, "y": 4, "x": 5}


class TestSetGeom:
    def test_regular_grid_geom_is_swath(self, regular_grid_data):
        # Hits the abstract method override on RegularGrid.
        regular_grid_data._set_geom()
        assert isinstance(regular_grid_data._geom, SwathDefinition)

    def test_point_surface_geom_is_swath(self, point_surface_data):
        point_surface_data._set_geom()
        assert isinstance(point_surface_data._geom, SwathDefinition)

    def test_geom_property_triggers_set(self, regular_grid_data):
        regular_grid_data._geom = None
        _ = regular_grid_data.geom
        assert regular_grid_data._geom is not None


class TestResampleVars:
    def test_resample_grid_to_point(self, regular_grid_data, point_surface_data):
        # Spatial overlap between the two fixtures by construction.
        result = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=500_000
        )
        assert isinstance(result, (xr.Dataset, xr.DataArray))
        new_var = f"Temperatura__{regular_grid_data.name}"
        assert new_var in result
        # Result should live on the destination (point) geometry.
        assert "site" in result.dims

    def test_resample_caches_resampled(self, regular_grid_data, point_surface_data):
        assert point_surface_data.resampled is None
        point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=500_000
        )
        assert point_surface_data.resampled is not None


class TestCopy:
    def test_returns_new_instance_same_class(self, regular_grid_data):
        copy = regular_grid_data.copy()
        assert copy is not regular_grid_data
        assert type(copy) is type(regular_grid_data)

    def test_user_facing_attrs_match(self, regular_grid_data):
        copy = regular_grid_data.copy()
        assert copy.name == regular_grid_data.name
        assert copy.path == regular_grid_data.path
        assert copy.vars == regular_grid_data.vars
        assert copy.reader is regular_grid_data.reader
        assert copy.crs == regular_grid_data.crs
        assert copy.reader_kwargs == regular_grid_data.reader_kwargs

    def test_obj_is_propagated(self, regular_grid_data):
        # Shallow on purpose: the cached dataset is shared so copy() doesn't
        # trigger another reader read.
        copy = regular_grid_data.copy()
        assert copy.obj is regular_grid_data.obj

    def test_cached_state_is_propagated(self, regular_grid_data):
        # Prime caches that the obj setter would otherwise reset.
        _ = regular_grid_data.bbox
        _ = regular_grid_data.dims
        regular_grid_data._set_geom()
        regular_grid_data.resampled = "sentinel"

        copy = regular_grid_data.copy()
        assert copy._bbox == regular_grid_data._bbox
        assert copy._dims == regular_grid_data._dims
        assert copy._geom is regular_grid_data._geom
        assert copy.resampled == "sentinel"

    def test_obj_setter_on_copy_does_not_mutate_original(
        self, regular_grid_data, make_regular_grid
    ):
        copy = regular_grid_data.copy()
        new_ds = make_regular_grid(n_time=3)
        copy.obj = new_ds
        assert copy.obj is new_ds
        assert regular_grid_data.obj is not new_ds

    def test_point_surface_copy(self, point_surface_data):
        copy = point_surface_data.copy()
        assert type(copy) is type(point_surface_data)
        assert copy.name == point_surface_data.name
        assert copy.obj is point_surface_data.obj


class TestObjLazyLoading:
    def test_obj_property_triggers_load(self, regular_grid_dataset):
        from pathlib import Path

        import cartopy.crs as ccrs

        from ClimateGraph.data import RegularGrid

        loaded = {"called": 0}

        class _Reader:
            @staticmethod
            def open_mfdataset(files, vars, **kwargs):
                loaded["called"] += 1
                return regular_grid_dataset

        instance = RegularGrid(
            name="lazy",
            path=Path("memory://x"),
            vars={"Temperatura": {"name": "Temperatura", "unit": "kelvin"}},
            reader=_Reader,
            crs=ccrs.PlateCarree(),
        )
        assert loaded["called"] == 0
        _ = instance.obj
        assert loaded["called"] == 1
        # Second access is cached.
        _ = instance.obj
        assert loaded["called"] == 1
