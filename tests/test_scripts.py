import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np


def exp(exp_dir: Path, track: bool = True) -> None:
    exp_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "tests/scripts/myapp.py", "cpu", exp_dir, "200"]
    if track:
        cmd += ["True", "False"]
    result = subprocess.check_output(cmd)
    assert str(result.decode("utf-8")).strip().split()[-1] == "SUCCESS"
    assert Path(exp_dir / "impacttracker").exists()


def test_script(tmpdir: Any) -> Any:
    exp1 = Path(tmpdir) / "exp1"
    exp(exp1)

    exp2 = Path(tmpdir) / "exp2"
    exp(exp2)

    # test create-compute-appendix
    cmd = [
        sys.executable,
        "scripts/create-compute-appendix",
        str(tmpdir),
        "--site_spec",
        "tests/scripts/leaderboard_generation_format.json",
        "--output_dir",
        str(tmpdir / "output"),
    ]
    # for now make sure the script runs.
    subprocess.check_output(cmd)


def test_generate_carbon_impact_statement(tmpdir: Any) -> Any:
    exp1 = Path(tmpdir) / "exp1"
    exp(exp1)

    exp2 = Path(tmpdir) / "exp2"
    exp(exp2)

    # test create-compute-appendix
    cmd = [
        sys.executable,
        "scripts/generate-carbon-impact-statement",
        str(tmpdir),
        "USA",
    ]
    # for now make sure the script runs.
    output = subprocess.check_output(cmd)

    numbers = re.findall("[+-]?\d+(\.\d+)? kg of", output.decode("utf-8").lower())
    kgcarbon = float(numbers[0])
    numbers = re.findall("[+-]?\d+(\.\d+)? kwh of", output.decode("utf-8").lower())
    kwh = float(numbers[0])

    output = subprocess.check_output(cmd, env={"OVERRIDE_PUE": "1.11"})
    numbers = re.findall("[+-]?\d+(\.\d+)? kg of", output.decode("utf-8").lower())
    kgcarbon2 = float(numbers[0])
    numbers = re.findall("[+-]?\d+(\.\d+)? kwh of", output.decode("utf-8").lower())
    kwh2 = float(numbers[0])

    np.testing.assert_allclose(kgcarbon2 / kgcarbon, 1.11 / 1.58, rtol=1e-02)
    np.testing.assert_allclose(kwh2 / kwh, 1.11 / 1.58, rtol=1e-02)
