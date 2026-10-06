"""Write the synthetic datasets the example configs read.

The files are small and tracked in the repository, so this normally only needs
running if the generator changes:

    python docs/examples/make_data.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _synthetic import make_grid, make_stations  # noqa: E402


def main() -> None:
    data = HERE / "data"
    print(make_grid(data / "model.nc"))
    print(make_stations(data / "stations.nc"))


if __name__ == "__main__":
    main()
