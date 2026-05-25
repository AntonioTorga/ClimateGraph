import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

chim = xr.open_mfdataset(
    "/home/cr2/nhuneeus/RESULTS/CHIMERE2023/FDCYT-STGOPTOMTT/chim_STGOPTOMTT_202106*out.nc",
    chunks="auto",
)
sinca = xr.open_dataset("test_data/data/SINCA-CAL-Daily-2000-2026.nc")

sinca = sinca.sel(time=slice("2021-6-1", "2021-6-4"))
chim = chim.sel(time_counter=slice("2021-6-1", "2021-6-4"))
chim = chim.resample(time_counter="D").mean()
sites = {
    "228": {"lat": -33.43307, "lon": -70.73206},
    "233": {"lat": -33.59136, "lon": -70.59443},
}

lat2d = chim["nav_lat"].values
lon2d = chim["nav_lon"].values


def nearest_index_2d(lat2d, lon2d, target_lat, target_lon):
    """Retorna (iy, ix) del punto más cercano en una grilla 2D."""
    # Distancia euclidiana en grados (suficiente para NN, sin necesidad de haversine)
    dist = np.sqrt((lat2d - target_lat) ** 2 + (lon2d - target_lon) ** 2)
    iy, ix = np.unravel_index(np.argmin(dist), dist.shape)
    return int(iy), int(ix)


results = {}
for name, coords in sites.items():
    iy, ix = nearest_index_2d(lat2d, lon2d, coords["lat"], coords["lon"])

    # Selección por índice entero — isel es siempre seguro con índices
    ts_model = chim["PM25"].isel(y=iy, x=ix)  # ajusta nombre de variable y dims

    results[name] = {
        "model": chim,
        "y": iy,
        "x": ix,
    }
    print(
        f"{name}: punto más cercano en ({lat2d[iy, ix]:.4f}, {lon2d[iy, ix]:.4f}), índice ({iy}, {ix})"
    )

ys = xr.DataArray([results["228"]["y"], results["233"]["y"]], dims="x")
xs = xr.DataArray([results["228"]["x"], results["233"]["x"]], dims="x")
sinca = sinca.sel(siteid=list(sites.keys()))[["PM25_ug|m3", "PM10_ug|m3"]]
sinca_ready = sinca.reduce(np.mean, ["x"])
chim = chim.isel(y=ys, x=xs, bottom_top=0)[["PM25", "PM10"]]
chim_ready = chim.reduce(np.mean, ["x"])

figure = plt.figure(figsize=[6, 6], layout="constrained")
ax = figure.add_subplot(1, 1, 1)

sinca_line = sinca_ready["PM25_ug|m3"].plot.line(ax=ax)
sinca_line[0].set_label("SINCA")

chim_line = chim_ready["PM25"].plot.line(ax=ax)
chim_line[0].set_label("CHIMERE")

ax.legend()

figure.savefig("./tests/test_results/PM25-SINCA-CHIMERE.jpg", dpi=1000)

figure = plt.figure(figsize=[6, 6], layout="constrained")
ax = figure.add_subplot(1, 1, 1)

sinca_line = sinca_ready["PM10_ug|m3"].plot.line(ax=ax)
sinca_line[0].set_label("SINCA")

chim_line = chim_ready["PM10"].plot.line(ax=ax)
chim_line[0].set_label("CHIMERE")

ax.legend()

figure.savefig("./tests/test_results/PM10-SINCA-CHIMERE.jpg", dpi=1000)
