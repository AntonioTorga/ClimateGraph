from ClimateGraph.data import Data, PointSurface, RegularGrid, SatelliteSwath

import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

AVAILABLE_PLOTS = {}


def register(name: str | list[str]):
    names = [name] if isinstance(name, str) else name

    def decorator(func):
        for alias in names:
            AVAILABLE_PLOTS[alias] = func
        return func

    return decorator


@register("contourf")
def contourf(
    data: RegularGrid, var: str, dims: tuple[str, str], reduction_func=None, **kwargs
):
    print(f"Creating countourf based on {data.name}.")

    fig = plt.figure(figsize=(6, 6), layout="constrained")
    ## AQUI QUEDE PLOTTING # TODO: manage reduction_func as a Callable for DataArrays
    ax = fig.add_subplot(
        1, 1, 1, projection=kwargs.get("projection", ccrs.PlateCarree())
    )

    lons, lats = data.get_coords(["longitude", "latitude"], as_numpy=True)
    plot_data = data.get_var(var, reduction_func=reduction_func)

    ax.contourf(
        lons, lats, plot_data, levels=kwargs.get("levels", 10), transform=data.crs
    )

    ax.coastlines()
    ax.add_feature(cfeature.BORDERS)

    fig.show()


@register("scatter")
def scatter(
    data: PointSurface,
    var: str | list[str],
    coords: tuple[str, str] = ("latitude", "longitude"),
):
    pass


@register(["spatial_overlay", "spatial-overlay"])
def spatial_overlay(over: PointSurface, under: RegularGrid, vars: str | list[str]):
    pass


def timeseries(data: Data):
    print(f"Creating timeseries based on {data.name}")
