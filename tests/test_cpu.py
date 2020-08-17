from unittest.mock import patch

import pytest

from experiment_impact_tracker.compute_tracker import _get_compatible_data_headers
from experiment_impact_tracker.cpu.common import is_cpu_freq_compatible


def test_cpu_freq_is_avail():
    with patch("psutil.cpu_freq", side_effect=NotImplementedError("mocked error")):
        assert is_cpu_freq_compatible() == False
        headers = _get_compatible_data_headers()
        assert "cpu_freq" not in headers
