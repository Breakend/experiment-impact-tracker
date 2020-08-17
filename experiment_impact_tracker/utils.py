import atexit
import csv
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from functools import wraps
from multiprocessing import Process, Queue

import numpy as np
import pandas as pd
import psutil
import pytest
import ujson

from experiment_impact_tracker.data_utils import *
from experiment_impact_tracker.data_utils import load_data_into_frame
from experiment_impact_tracker.emissions.constants import PUE

_timer = getattr(time, "monotonic", time.time)

log = logging.getLogger(__name__)


def get_timestamp(*args, **kwargs):
    now = datetime.now()
    timestamp = datetime.timestamp(now)
    return timestamp


def get_flop_count_tensorflow(graph=None, session=None):
    import tensorflow as tf  # import within function so as not to require tf for package
    from tensorflow.python.framework import graph_util

    def load_pb(pb):
        with tf.gfile.GFile(pb, "rb") as f:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(f.read())
        with tf.Graph().as_default() as graph:
            tf.import_graph_def(graph_def, name="")
            return graph

    if graph is None and session is None:
        graph = tf.get_default_graph()
    if session is not None:
        graph = session.graph

    run_meta = tf.RunMetadata()
    opts = tf.profiler.ProfileOptionBuilder.float_operation()

    # We use the Keras session graph in the call to the profiler.
    flops = tf.profiler.profile(graph=graph, run_meta=run_meta, cmd="op", options=opts)

    return flops.total_float_ops  # Prints the "flops" of the model.


def processify(func):
    """Decorator to run a function as a process.
    Be sure that every argument and the return value
    is *pickable*.
    The created process is joined, so the code does not
    run in parallel.
    """

    def process_func(q, *args, **kwargs):
        try:
            ret = func(q, *args, **kwargs)
        except Exception as e:
            ex_type, ex_value, tb = sys.exc_info()
            error = ex_type, ex_value, "".join(traceback.format_tb(tb))
            ret = None
            q.put((ret, error))
            raise e
        else:
            error = None
        q.put((ret, error))

    # register original function with different name
    # in sys.modules so it is pickable
    process_func.__name__ = func.__name__ + "processify_func"
    setattr(sys.modules[__name__], process_func.__name__, process_func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        queue = Queue()  # not the same as a Queue.Queue()
        p = Process(target=process_func, args=[queue] + list(args), kwargs=kwargs)
        p.start()
        return p, queue

    return wrapper


def _get_cpu_hours_from_per_process_data(json_array):
    latest_per_pid = {}
    for datapoint in json_array:
        cpu_point = datapoint.get("cpu_time_seconds", {})
        for pid, value in cpu_point.items():
            latest_per_pid[pid] = value["user"] + value["system"]
    return sum(latest_per_pid.values())


def gather_additional_info(info, logdir):
    df, json_array = load_data_into_frame(logdir)
    cpu_seconds = _get_cpu_hours_from_per_process_data(json_array)
    exp_len = datetime.timestamp(info["experiment_end"]) - datetime.timestamp(
        info["experiment_start"]
    )
    exp_len_hours = exp_len / 3600.0
    # integrate power
    # https://electronics.stackexchange.com/questions/237025/converting-watt-values-over-time-to-kwh
    # multiply by carbon intensity to get Kg Carbon eq
    time_differences = df["timestamp"].diff()
    time_differences[0] = df["timestamp"][0] - datetime.timestamp(
        info["experiment_start"]
    )

    # Add final timestamp and extrapolate last row of power estimates
    time_differences.loc[len(time_differences)] = (
        datetime.timestamp(info["experiment_end"])
        - df["timestamp"][len(df["timestamp"]) - 1]
    )

    # elementwise multiplication and sum
    time_differences_in_hours = time_differences / 3600.0
    power_draw_rapl_kw = None

    if "rapl_estimated_attributable_power_draw" in df:
        power_draw_rapl_kw = df["rapl_estimated_attributable_power_draw"] / 1000.0
        power_draw_rapl_kw.loc[len(power_draw_rapl_kw)] = power_draw_rapl_kw.loc[
            len(power_draw_rapl_kw) - 1
        ]
    has_gpu = False

    if "gpu_info" in info.keys():
        has_gpu = True
        num_gpus = len(info["gpu_info"])
        nvidia_power_draw_kw = df["nvidia_estimated_attributable_power_draw"] / 1000.0
        nvidia_power_draw_kw.loc[len(nvidia_power_draw_kw)] = nvidia_power_draw_kw.loc[
            len(nvidia_power_draw_kw) - 1
        ]
        gpu_absolute_util = df["average_gpu_estimated_utilization_absolute"]
        gpu_absolute_util.loc[len(gpu_absolute_util)] = gpu_absolute_util.loc[
            len(gpu_absolute_util) - 1
        ]

        # elementwise multiplication and sum
        kw_hr_nvidia = np.multiply(time_differences_in_hours, nvidia_power_draw_kw)

    kw_hr_rapl = (
        np.multiply(time_differences_in_hours, power_draw_rapl_kw)
        if power_draw_rapl_kw is not None
        else None
    )

    total_power_per_timestep = None
    if has_gpu:
        total_power_per_timestep = PUE * (kw_hr_nvidia + kw_hr_rapl)
    elif kw_hr_rapl is not None:
        total_power_per_timestep = PUE * (kw_hr_rapl)

    realtime_carbon = None
    total_power = (
        total_power_per_timestep.sum() if total_power_per_timestep is not None else None
    )

    estimated_carbon_impact_grams = None
    if "realtime_carbon_intensity" in df:
        realtime_carbon = df["realtime_carbon_intensity"]
        realtime_carbon.loc[len(realtime_carbon)] = realtime_carbon.loc[
            len(realtime_carbon) - 1
        ]
        # If we lost some values due to network errors, forward fill the last available value.
        # Backfill in a second pass to get any values that haven't been picked up.
        # Then finally, if any values remain, replace with the region average.
        realtime_carbon = (
            pd.to_numeric(realtime_carbon, errors="coerce")
            .fillna(method="ffill")
            .fillna(method="bfill")
            .fillna(value=info["region_carbon_intensity_estimate"]["carbonIntensity"])
        )
        try:
            estimated_carbon_impact_grams_per_timestep = (
                np.multiply(total_power_per_timestep, realtime_carbon)
                if total_power_per_timestep
                else None
            )
        except:
            import pdb

            pdb.set_trace()
        estimated_carbon_impact_grams = (
            estimated_carbon_impact_grams_per_timestep.sum()
            if estimated_carbon_impact_grams_per_timestep
            else None
        )
    else:
        if total_power is not None:
            estimated_carbon_impact_grams = (
                total_power
                * info["region_carbon_intensity_estimate"]["carbonIntensity"]
            )

    estimated_carbon_impact_kg = (
        estimated_carbon_impact_grams / 1000.0
        if estimated_carbon_impact_grams is not None
        else None
    )

    cpu_hours = cpu_seconds / 3600.0

    data = {}

    if cpu_hours is not None:
        data["cpu_hours"] = cpu_hours
    if estimated_carbon_impact_kg is not None:
        data["estimated_carbon_impact_kg"] = estimated_carbon_impact_kg
    if total_power is not None:
        data["total_power"] = total_power
    if kw_hr_rapl is not None:
        data["kw_hr_cpu"] = kw_hr_rapl.sum()
    if exp_len_hours is not None:
        data["exp_len_hours"] = exp_len_hours

    if has_gpu:
        # GPU-hours percent utilization * length of time utilized (assumes absolute utliziation)
        gpu_hours = (
            np.multiply(time_differences_in_hours, gpu_absolute_util).sum() * num_gpus
        )
        data.update({"gpu_hours": gpu_hours, "kw_hr_gpu": kw_hr_nvidia.sum()})

    if realtime_carbon is not None:
        data["average_realtime_carbon_intensity"] = realtime_carbon.mean()

    return data
