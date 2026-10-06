"""Render the example figures used in the documentation.

Runs every control file in ``configs/`` exactly as the command line would, and
copies the resulting figures into ``docs/source/_static/examples/``.

The configs and the figures are both committed, so the documentation page can
show the real file that produced each image, and neither CI nor ReadTheDocs has
to render anything. Run this by hand after changing an example:

    python docs/examples/generate_figures.py

Each config can also be run on its own, from the repository root:

    ClimateGraph run docs/examples/configs/timeseries.yaml
"""

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

from ClimateGraph.appkernel import AppKernel  # noqa: E402

CONFIGS = HERE / "configs"
OUTPUT = HERE / "output"
STATIC = HERE.parent / "source" / "_static" / "examples"


def main() -> int:
    if not (HERE / "data" / "model.nc").exists():
        print("Missing example data. Run: python docs/examples/make_data.py")
        return 1

    STATIC.mkdir(parents=True, exist_ok=True)
    failed: list[tuple[str, str]] = []

    for config in sorted(CONFIGS.glob("*.yaml")):
        name = config.stem
        try:
            AppKernel().run(config)
        except Exception as err:
            failed.append((name, f"{type(err).__name__}: {err}"))
            continue

        produced = sorted((OUTPUT / name).glob("*"))
        if not produced:
            failed.append((name, "ran, but produced no figure"))
            continue

        target = STATIC / f"{name}.png"
        shutil.copyfile(produced[0], target)
        size = target.stat().st_size // 1024
        print(f"  {name:16s} -> {target.relative_to(REPO)} ({size} KB)")

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)

    for name, why in failed:
        print(f"  FAILED {name}: {why}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
