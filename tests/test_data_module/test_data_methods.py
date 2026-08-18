from pathlib import Path

import cartopy.crs as ccrs
import numpy as np
import pandas as pd
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

    def test_resample_caches_identical_calls(
        self, regular_grid_data, point_surface_data
    ):
        # The result is memoized on the SOURCE, keyed by (target, vars, params), so a
        # second identical call returns the same Dataset without recomputing. The
        # target is never mutated.
        target_before = point_surface_data.obj
        r1 = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=500_000
        )
        r2 = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=500_000
        )
        assert point_surface_data.obj is target_before  # target untouched
        assert r1 is r2  # cache hit returns the same object

    def test_resample_cache_keyed_per_target_no_clobber(
        self, regular_grid_data, point_surface_data, make_regular_grid
    ):
        # Different source grids onto one target land in separate cache entries and
        # keep their own results (guards the old flat-cache clobber bug). A different
        # radius must not return a stale hit either.
        other_grid = regular_grid_data.copy()
        other_grid.name = "other_grid"
        other_grid.obj = make_regular_grid(n_time=3)

        r_a = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=500_000
        )
        r_b = point_surface_data.resample_vars(
            other_grid, "Temperatura", radius_of_influence=500_000
        )
        assert r_a is not r_b
        assert r_a.sizes["time"] != r_b.sizes["time"]  # each kept its own time axis
        # Cache lives on the source, one entry per (target, vars, params).
        assert len(regular_grid_data._resample_cache) == 1
        assert len(other_grid._resample_cache) == 1

        # Different radius -> different key -> not the cached object.
        r_a2 = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=250_000
        )
        assert r_a2 is not r_a
        assert len(regular_grid_data._resample_cache) == 2

    def test_resample_cache_invalidated_on_source_obj_change(
        self, regular_grid_data, point_surface_data, make_regular_grid
    ):
        # Reassigning the source's obj means the values changed, so the memoized
        # projection is stale and must be recomputed.
        r1 = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=500_000
        )
        regular_grid_data.obj = make_regular_grid(n_time=3)
        r2 = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=500_000
        )
        assert r1 is not r2

    def test_resample_keeps_source_time_and_inherits_target_coords(
        self, regular_grid_data, point_surface_data
    ):
        # The source keeps its OWN time axis (no snapping onto the target), and
        # inherits the target's spatial coords (site + region), which is what makes
        # region/site attribute filtering on a resampled grid possible.
        result = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=500_000
        )
        src_time = regular_grid_data.obj["time"]
        assert result.sizes["time"] == src_time.sizes["time"]
        assert result["time"].equals(src_time)
        assert "region" in result.coords  # inherited from the point target
        assert result.sizes["site"] == point_surface_data.obj.sizes["site"]

    def test_resample_4d_grid_preserves_z(self, point_surface_data):
        """Resampling a 4D (time, z, y, x) RegularGrid should broadcast across z
        and produce (time, z, site) output without crashing."""
        from ClimateGraph.data import RegularGrid

        n_time, n_z, n_y, n_x = 3, 4, 4, 5
        times = pd.date_range("2019-01-01", periods=n_time, freq="D")
        lat_1d = np.linspace(-36.0, -33.0, n_y)
        lon_1d = np.linspace(-73.0, -69.0, n_x)
        lat2d, lon2d = np.meshgrid(lat_1d, lon_1d, indexing="ij")
        rng = np.random.default_rng(seed=42)
        data_4d = rng.normal(size=(n_time, n_z, n_y, n_x))

        ds_4d = xr.Dataset(
            data_vars={"Temperatura": (("time", "z", "y", "x"), data_4d)},
            coords={
                "time": times,
                "z": np.arange(n_z),
                "latitude": (("y", "x"), lat2d),
                "longitude": (("y", "x"), lon2d),
            },
        )

        class _StubReader:
            @staticmethod
            def read(spec):
                return ds_4d

        grid_4d = RegularGrid(
            name="grid_4d",
            path=Path("memory://grid4d"),
            vars={"Temperatura": {"name": "Temperatura", "unit": "kelvin"}},
            reader=_StubReader,
            crs=ccrs.PlateCarree(),
        )
        grid_4d.obj = ds_4d

        result = point_surface_data.resample_vars(
            grid_4d, "Temperatura", radius_of_influence=500_000
        )
        assert "z" in result.dims
        assert "site" in result.dims
        assert "time" in result.dims
        assert result.sizes["z"] == n_z

    def test_block_resample_matches_per_slice(
        self, regular_grid_data, point_surface_data
    ):
        # The batched (channel-axis) resample must be numerically identical to
        # resampling each timestep's 2-D slice separately with the same neighbour
        # info — the safety net for dropping vectorize=True.
        from pyresample import kd_tree

        radius = 500_000
        src, dst = regular_grid_data.geom, point_surface_data.geom
        vi, vo, ia, da = kd_tree.get_neighbour_info(
            src, dst, radius_of_influence=radius, neighbours=1
        )
        var = regular_grid_data.get_var("Temperatura")  # (time, y, x)
        reference = np.stack(
            [
                kd_tree.get_sample_from_neighbour_info(
                    "nn",
                    dst.shape,
                    var.isel(time=t).values,
                    vi,
                    vo,
                    ia,
                    da,
                    fill_value=np.nan,
                )
                for t in range(var.sizes["time"])
            ]
        )

        result = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=radius
        )
        new_var = f"Temperatura__{regular_grid_data.name}"
        np.testing.assert_allclose(result[new_var].values, reference, equal_nan=True)

    def test_resample_result_is_materialized(
        self, regular_grid_data, point_surface_data
    ):
        # The resample result is loaded (concrete numpy) before caching, even from a
        # dask-chunked source, so downstream ops don't re-execute the graph on every
        # render. The cache then returns the same materialized object.
        regular_grid_data.obj = regular_grid_data.obj.chunk({"time": 1})
        r1 = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=500_000
        )
        new_var = f"Temperatura__{regular_grid_data.name}"
        assert r1[new_var].chunks is None  # materialized, not lazy
        r2 = point_surface_data.resample_vars(
            regular_grid_data, "Temperatura", radius_of_influence=500_000
        )
        assert r1 is r2  # cache hit, no recompute


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

        copy = regular_grid_data.copy()
        assert copy._bbox == regular_grid_data._bbox
        assert copy._dims == regular_grid_data._dims
        assert copy._geom is regular_grid_data._geom

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
            def read(spec):
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
