import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


def exp(exp_dir: Path, track: bool = True) -> None:
    exp_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "tests/scripts/myapp.py", "cpu", exp_dir, "200"]
    if track:
        cmd += ["True", "False"]

    result = subprocess.Popen(cmd)

    time.sleep(30)

    result.kill()

    assert Path(exp_dir / "impacttracker").exists()
    assert Path(exp_dir / "impacttracker").exists()


def test_generate_carbon_impact_statement(tmpdir: Any) -> Any:
    exp1 = Path(tmpdir) / "exp1"
    exp(exp1)

    # test create-compute-appendix
    cmd = [
        sys.executable,
        "scripts/generate-carbon-impact-statement",
        str(tmpdir),
        "USA",
    ]
    # for now make sure the script runs.
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, stderr = p.communicate()

    assert ("looks like your experiment ended abruptly" in stderr.decode("utf-8").lower())

    numbers = re.findall(
        "wall-clock time of all experiments was [+-]?\d+(\.\d+)?",
        output.decode("utf-8").lower(),
    )
    exp_time = float(numbers[0])
    np.testing.assert_allclose(exp_time, 0.005, atol=2e-03)
