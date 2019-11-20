import atexit
import logging
import os
import pickle
import subprocess
import sys
import time
import traceback
from datetime import datetime
from queue import Empty as EmptyQueueException
from subprocess import PIPE, Popen
from sys import platform
from pathlib import Path


from pandas.io.json import json_normalize
import numpy as np
import pandas as pd
import ujson as json

import psutil
from experiment_impact_tracker.cpu import rapl
from experiment_impact_tracker.data_utils import *
from experiment_impact_tracker.cpu.common import get_my_cpu_info
from experiment_impact_tracker.cpu.intel import get_rapl_power
from experiment_impact_tracker.data_info_and_router import DATA_HEADERS, INITIAL_INFO
from experiment_impact_tracker.gpu.nvidia import (get_gpu_info,
                                                  get_nvidia_gpu_power)
from experiment_impact_tracker.utils import write_json_data_to_file, safe_file_path, processify, get_timestamp
from experiment_impact_tracker.emissions.common import is_capable_realtime_carbon_intensity
from experiment_impact_tracker.emissions.get_region_metrics import get_current_region_info_cached

SLEEP_TIME = 1

def read_latest_stats(log_dir):
    log_path = os.path.join(log_dir, DATAPATH)

    try:
        last_line = subprocess.check_output(["tail", "-1", log_path])
    except:
        return None

    if last_line:
        return json.loads(last_line)
    else:
        return None


def _sample_and_log_power(log_dir, initial_info, logger=None):
    current_process = psutil.Process(os.getppid())
    process_ids = [current_process.pid] + \
        [child.pid for child in current_process.children(recursive=True)]
    process_ids = list(set(process_ids)) # dedupe so that we don't double count by accident

    required_headers = _get_compatible_data_headers(get_current_region_info_cached()[0])

    header_information = {}

    # for all required headers make sure that we hit the corresponding function which gets that info
    # some functions return multiple values in one call (for example one RAPL reading could get multiple things)
    # so in that case we fill in information on multiple headers at once even though they have the same routing
    # information.
    for header in required_headers:
        if header["name"] in header_information.keys():
            # we already got that info from a multi-return function call
            continue

        start = time.time()
        results = header["routing"]["function"](process_ids, logger=logger, region=initial_info['region']['id'], log_dir=log_dir)
        end = time.time()
        logger.warn("Datapoint {} took {} seconds".format(header["name"], (end-start)))

        if isinstance(results, dict):
            # if we return a dict of results, could account for multiple headers
            for header_name, item in results.items():
                header_information[header_name] = item
        else:
            header_information[header["name"]] = results
    header_information["process_ids"] = process_ids
    # once we have gotten all the required info through routing calls for all headers, we log it
    log_path = safe_file_path(os.path.join(log_dir, DATAPATH))
    try:
        write_json_data_to_file(log_path, header_information)
    except:
        logger.error(header_information)
        raise
    return header_information


@processify
def launch_power_monitor(queue, log_dir, initial_info, logger=None):
    logger.warn("Starting process to monitor power")
    while True:
        try:
            message = queue.get(block=False)
            if isinstance(message, str):
                if message == "Stop":
                    return
            else:
                queue.put(message)
        except EmptyQueueException:
            pass

        try:
            _sample_and_log_power(log_dir, initial_info, logger=logger)
        except:
            ex_type, ex_value, tb = sys.exc_info()
            logger.error("Encountered exception within power monitor thread!")
            logger.error(''.join(traceback.format_tb(tb)))
            raise
        time.sleep(SLEEP_TIME)


def _get_compatible_data_headers(region=None):
    compatible_headers = []

    for header in DATA_HEADERS:
        compat = True
        for compatability_fn in header["compatability"]:
            if not compatability_fn(region=region):
                compat = False
                break
        if compat:
            compatible_headers.append(header)
            
    return compatible_headers

def _validate_compatabilities(compatabilities, *args, **kwargs):
    for compatability_fn in compatabilities:
        if not compatability_fn(*args, **kwargs):
            return False
    return True          



def gather_initial_info(log_dir):
    # TODO: log one time info: CPU/GPU info, version of this package, region, datetime for start of experiment, CO2 estimate data.
    # this will be used to build a latex table later.


    info_path = safe_file_path(os.path.join(log_dir, INFOPATH))

    data = {}

    # Gather all the one-time info specified by the appropriate router
    for info_ in INITIAL_INFO:
        key = info_["name"]
        compatabilities = info_["compatability"]
        if _validate_compatabilities(compatabilities):
            data[key] = info_["routing"]["function"]()

    with open(info_path, 'wb') as info_file:
        pickle.dump(data, info_file)

    # touch datafile to clear out any past cruft and write headers

    data_path = safe_file_path(os.path.join(log_dir, DATAPATH))
    if os.path.exists(data_path):
        os.remove(data_path)

    Path(data_path).touch()

    return data



class ImpactTracker(object):

    def __init__(self, logdir):
        self.logdir = logdir
        self._setup_logging()
        self.logger.warn("Gathering system info for reproducibility...")
        self.initial_info = gather_initial_info(logdir)
        self.logger.warn("Done initial setup and information gathering...")

    def _setup_logging(self):
        # Create a custom logger
        logger = logging.getLogger(
            "experiment_impact_tracker.compute_tracker.ImpactTracker")

        # Create handlers
        c_handler = logging.StreamHandler()
        f_handler = logging.FileHandler(safe_file_path(os.path.join(
            self.logdir, BASE_LOG_PATH, 'impact_tracker_log.log')))
        c_handler.setLevel(logging.WARNING)
        f_handler.setLevel(logging.ERROR)

        # Create formatters and add it to handlers
        c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        f_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)

        # Add handlers to the logger
        logger.addHandler(c_handler)
        logger.addHandler(f_handler)
        self.logger = logger

    def launch_impact_monitor(self):
        try:
            self.p, self.queue = launch_power_monitor(self.logdir, self.initial_info, self.logger)
            def _terminate_monitor_and_log_final_info(p):
                p.terminate(); log_final_info(self.logdir)
            atexit.register(_terminate_monitor_and_log_final_info, self.p)
        except:
            ex_type, ex_value, tb = sys.exc_info()
            self.logger.error(
                "Encountered exception when launching power monitor thread.")
            self.logger.error(ex_type, ex_value,
                              ''.join(traceback.format_tb(tb)))
            raise

    def get_latest_info_and_check_for_errors(self):
        try:
            message = self.queue.get(block=False)
            if isinstance(message, tuple):
                ret, error = message
            else:
                self.queue.put(message)
            if error:
                ex_type, ex_value, tb_str = error
                message = '%s (in subprocess)\n%s' % (str(ex_value), tb_str)
                raise ex_type(message)
        except EmptyQueueException:
            # Nothing in the message queue
            pass
        # TODO: make thread safe read/writes via multiprocessing lock.
        # There might be a case where we try to read a file that is currently being written to? possibly
        return read_latest_stats(self.logdir)
