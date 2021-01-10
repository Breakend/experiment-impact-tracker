import re
import subprocess
import sys
import timeit
from pathlib import Path
from typing import Any

import numpy as np


def exp(exp_dir: Path, epochs: int = 200, track: bool = True) -> None:
    exp_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "tests/scripts/myapp.py", "cpu", exp_dir, str(epochs)]
    if track:
        cmd += ["True", "False"]
    else:
        cmd += ["False", "False"]
    result = subprocess.check_output(cmd)
    assert str(result.decode("utf-8")).strip().split()[-1] == "SUCCESS"
    assert Path(exp_dir / "impacttracker").exists()


def test_overhead(tmpdir: Any) -> Any:
    exp1 = Path(tmpdir) / "exp1"

    exp2 = Path(tmpdir) / "exp2"

    from functools import partial

    times1 = timeit.timeit(lambda: exp(exp1), number=5)
    times2 = timeit.timeit(lambda: exp(exp2, track=False), number=5)

    first_diff = times2 / times1
    assert times2 / times1 > 0.99

    times1 = timeit.timeit(lambda: exp(exp1, epochs=500), number=5)
    times2 = timeit.timeit(lambda: exp(exp2, epochs=500, track=False), number=5)

    assert times2 / times1 > 0.99

    print(
        f"200 epochs without the tracker required {first_diff} of the time as with the tracker"
    )
    print(
        f"500 epochs without the tracker required {times2/times1} of the time as with the tracker"
    )
