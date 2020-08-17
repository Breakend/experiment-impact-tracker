import subprocess
import sys
from pathlib import Path
from typing import Any


def exp(exp_dir: Path) -> None:
    exp_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "tests/scripts/myapp.py", "cpu", exp_dir]
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
    # pytest.set_trace()
    # for now make sure the script runs.
    subprocess.check_output(cmd)
