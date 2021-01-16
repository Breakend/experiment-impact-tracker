import tempfile
import time

import numpy as np
import psutil

from experiment_impact_tracker.compute_tracker import ImpactTracker
from experiment_impact_tracker.data_interface import DataInterface


def test_ram_attribution():
    p = psutil.Process()
    fname = tempfile.mkdtemp()

    with ImpactTracker(fname) as tracker:
        # Allocate 512Mb and chill for a bit
        x = bytearray(512000000)
        time.sleep(30)
        # Raises an errors in the main thread
        tracker.get_latest_info_and_check_for_errors()

    fname2 = tempfile.mkdtemp()
    del x

    with ImpactTracker(fname2) as tracker:
        # Allocate 1024Mb and chill for a bit
        y = bytearray(1024000000)
        time.sleep(30)
        # Raises an errors in the main thread
        tracker.get_latest_info_and_check_for_errors()

    del y

    di = DataInterface(fname)
    di2 = DataInterface(fname2)

    np.testing.assert_almost_equal(di.total_power * 2, di2.total_power, decimal=4)
