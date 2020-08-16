from pathlib import Path
import subprocess
import sys
from typing import Any


def test_script(tmpdir: Any) -> Any:
    print(f"INSIDE TEST {tmpdir}")
    cmd = [
        sys.executable,
        "tests/test_scripts/myapp.py",
        "cpu",
        tmpdir
    ]
    result = subprocess.check_output(cmd)
    assert str(result.decode("utf-8")).strip().split()[-1] == "SUCCESS"
    assert Path(tmpdir/"impacttracker").exists()



