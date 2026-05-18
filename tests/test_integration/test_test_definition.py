"""End-to-end run of ``test_data/configs/test-definition.yaml``.

This is the canonical integration check: it loads the only YAML in
``test_data/configs/`` that points exclusively at on-disk samples (the
others reference paths on a CR2 NFS share). It rewrites the output path
to a tmp dir so the test is hermetic.

Figure sanity:
- Every plot block produces at least the expected output filenames.
- Each saved JPG is a non-trivial image (loads with PIL, > a few KB).

For pixel-level regression, see ``compare_to_baseline`` below: pass
``CLIMATEGRAPH_UPDATE_BASELINES=1`` to refresh the committed baselines in
``tests/baseline_images/``; otherwise every run compares saved JPGs against
those baselines via ``matplotlib.testing.compare.compare_images`` (RMS).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

from ClimateGraph.appkernel import AppKernel

pytestmark = [pytest.mark.slow, pytest.mark.integration]


BASELINE_DIR = (
    Path(__file__).resolve().parent.parent / "baseline_images" / "test_definition"
)
EXPECTED_FILES = {
    "ts": [
        "ts-Litoral-Temperatura-01-01-2019_01-02-2019.jpg",
        "ts-RM-Temperatura-01-01-2019_01-02-2019.jpg",
        "ts-Litoral-Presion-01-01-2019_01-02-2019.jpg",
        "ts-RM-Presion-01-01-2019_01-02-2019.jpg",
    ],
    "scatter": [
        # Scatter has no `domains:` key in the YAML → empty-domain default,
        # so the slot between the two `-` is blank.
        "scatter--Temperatura-01-01-2019_01-02-2019.jpg",
        "scatter--Presion-01-01-2019_01-02-2019.jpg",
    ],
    "so": [
        "spatial_overlay-Poly1-Temperatura-WRF_D02-DMC-01-01-2019_01-02-2019.jpg",
        "spatial_overlay-Poly1-Presion-WRF_D02-DMC-01-01-2019_01-02-2019.jpg",
    ],
}

# Per-pixel RMS over 0-255 channels. Empirically, identical figures rendered on
# the same machine come in at ~0; cross-machine drift from font hinting is
# usually < 5. Bump if CI starts complaining.
RMS_TOLERANCE = 5.0


def _rms_difference(a: Path, b: Path) -> float:
    with Image.open(a) as ia, Image.open(b) as ib:
        arr_a = np.asarray(ia.convert("RGB"), dtype=np.float64)
        arr_b = np.asarray(ib.convert("RGB"), dtype=np.float64)
    if arr_a.shape != arr_b.shape:
        return float("inf")
    return float(np.sqrt(np.mean((arr_a - arr_b) ** 2)))


@pytest.fixture
def rewritten_config(test_data_dir, tmp_output_dir, tmp_path):
    src = test_data_dir / "configs" / "test-definition.yaml"
    with open(src) as f:
        cfg = yaml.safe_load(f)

    cfg["analysis"]["output_path"] = str(tmp_output_dir)
    # Rewrite relative dataset paths to absolute, so the test is CWD-independent.
    for _, block in cfg["data"].items():
        block["path"] = str(test_data_dir / "data" / Path(block["path"]).name)

    out = tmp_path / "config.yaml"
    out.write_text(yaml.safe_dump(cfg))
    return out, tmp_output_dir


def test_test_definition_runs_end_to_end(rewritten_config):
    config_path, output_dir = rewritten_config
    AppKernel().run(config_path)

    for plot_name, files in EXPECTED_FILES.items():
        plot_dir = output_dir / plot_name
        assert plot_dir.is_dir(), f"missing plot dir {plot_dir}"
        for fname in files:
            target = plot_dir / fname
            assert target.exists(), f"missing output {target}"
            assert target.stat().st_size > 2_000, f"{target} looks empty"
            # PIL load = JPEG is at least minimally valid.
            with Image.open(target) as img:
                img.verify()


def _all_outputs(output_dir: Path):
    for plot_name, files in EXPECTED_FILES.items():
        for fname in files:
            yield output_dir / plot_name / fname


def test_test_definition_matches_baselines(rewritten_config):
    config_path, output_dir = rewritten_config

    update = os.environ.get("CLIMATEGRAPH_UPDATE_BASELINES") == "1"
    if not BASELINE_DIR.exists() and not update:
        pytest.skip(
            "No baselines committed; rerun with CLIMATEGRAPH_UPDATE_BASELINES=1 "
            f"to generate them under {BASELINE_DIR}"
        )

    AppKernel().run(config_path)

    if update:
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        for produced in _all_outputs(output_dir):
            rel = produced.relative_to(output_dir)
            dst = BASELINE_DIR / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(produced, dst)
        pytest.skip("Baselines refreshed; rerun without the env var to compare.")

    failures: list[str] = []
    for produced in _all_outputs(output_dir):
        rel = produced.relative_to(output_dir)
        baseline = BASELINE_DIR / rel
        if not baseline.exists():
            failures.append(f"no baseline for {rel}")
            continue
        rms = _rms_difference(baseline, produced)
        if rms > RMS_TOLERANCE:
            failures.append(f"{rel}: RMS {rms:.2f} > {RMS_TOLERANCE}")

    assert not failures, "\n".join(failures)
