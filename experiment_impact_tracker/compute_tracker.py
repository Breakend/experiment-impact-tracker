import atexit
import logging
import os
import pickle
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from queue import Empty as EmptyQueueException
from subprocess import PIPE, Popen
from sys import platform

import numpy as np
import pandas as pd
import psutil
import ujson as json
from pandas.io.json import json_normalize

from experiment_impact_tracker.cpu import rapl
from experiment_impact_tracker.cpu.common import get_my_cpu_info
from experiment_impact_tracker.cpu.intel import get_rapl_power
from experiment_impact_tracker.data_info_and_router import (DATA_HEADERS,
                                                            INITIAL_INFO)
from experiment_impact_tracker.data_utils import *
from experiment_impact_tracker.emissions.common import \
    is_capable_realtime_carbon_intensity
from experiment_impact_tracker.emissions.get_region_metrics import \
    get_current_region_info_cached
from experiment_impact_tracker.gpu.nvidia import (get_gpu_info,
                                                  get_nvidia_gpu_power)
from experiment_impact_tracker.utils import (get_timestamp, processify,
                                             safe_file_path,
                                             write_json_data_to_file)

SLEEP_TIME = 1
STOP_MESSAGE = "Stop"
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

def read_latest_stats(log_dir):
    """
    Reads the latest last line of the jsonl file

    :param log_dir: log directory to read from
    :return: latest data
    """
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
    """
    Iterates over compatible metrics and logs the relevant information.

    :param log_dir: The log directory to use
    :param initial_info: Any initial information that was gathered
    :param logger: A logger to use
    :return: collected data
    """
    current_process = psutil.Process(os.getppid())
    process_ids = [current_process.pid] + [
        child.pid for child in current_process.children(recursive=True)
    ]
    process_ids = list(
        set(process_ids)
    )  # dedupe so that we don't double count by accident

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
        results = header["routing"]["function"](
            process_ids,
            logger=logger,
            region=initial_info["region"]["id"],
            log_dir=log_dir,
        )
        end = time.time()
        logger.info(
            "Datapoint {} took {} seconds".format(header["name"], (end - start))
        )

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
    """
    Launches a separate process which monitors metrics

    :param queue: A message queue to pass messages back and forth to the thread
    :param log_dir: The log directory to use
    :param initial_info: Any initial information that was gathered before the thread was launched.
    :param logger: A logger to use
    :return:
    """
    logger.info("Starting process to monitor power")
    while True:
        try:
            message = queue.get(block=False)
            if isinstance(message, str):
                if message == STOP_MESSAGE:
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
            logger.error("".join(traceback.format_tb(tb)))
            raise
        time.sleep(SLEEP_TIME)


def _get_compatible_data_headers(region=None):
    """
    Given all the data headers check for each one if it is compatible with the current system.

    :param region: The region we're in, required for some checks
    :return: which headers are compatible
    """
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
    """
    Given a list of compatability functions, run the checks

    :param compatabilities: a list of compatability functions to call
    :param args: any arguments to pass to compatability functions
    :param kwargs:  any arguments to pass to compatability functions
    :return: True if everything compatible, False otherwise
    """
    for compatability_fn in compatabilities:
        if not compatability_fn(*args, **kwargs):
            return False
    return True


def gather_initial_info(log_dir: str):
    """ Log one time info

    For example, CPU/GPU info, version of this package, region, datetime for start of experiment,
    CO2 estimate data.

    :param log_dir: the log directory to write to
    :return: gathered information
    """

    info_path = safe_file_path(os.path.join(log_dir, INFOPATH))

    data = {}

    # Gather all the one-time info specified by the appropriate router
    for info_ in INITIAL_INFO:
        key = info_["name"]
        compatabilities = info_["compatability"]
        if _validate_compatabilities(compatabilities):
            data[key] = info_["routing"]["function"]()

    with open(info_path, "wb") as info_file:
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
        self.logger.info("Gathering system info for reproducibility...")
        self.initial_info = gather_initial_info(logdir)
        self.logger.info("Done initial setup and information gathering...")
        self.launched = False

    def _setup_logging(self):
        """
        Private function to set up logging handlers

        :return:
        """
        # Create a custom logger
        logger = logging.getLogger(
            "experiment_impact_tracker.compute_tracker.ImpactTracker"
        )

        # Create handlers
        c_handler = logging.StreamHandler()
        f_handler = logging.FileHandler(
            safe_file_path(
                os.path.join(self.logdir, BASE_LOG_PATH, "impact_tracker_log.log")
            )
        )
        c_handler.setLevel(logging.WARNING)
        f_handler.setLevel(logging.ERROR)

        # Create formatters and add it to handlers
        c_format = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        f_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)

        # Add handlers to the logger
        logger.addHandler(c_handler)
        logger.addHandler(f_handler)
        self.logger = logger

    def launch_impact_monitor(self):
        """
        Launches the separate thread which starts polling for metrics

        :return:
        """
        try:
            self.p, self.queue = launch_power_monitor(
                self.logdir, self.initial_info, self.logger
            )

            def _terminate_monitor_and_log_final_info(p):
                p.terminate()
                log_final_info(self.logdir)

            atexit.register(_terminate_monitor_and_log_final_info, self.p)
            self.launched = True
        except:
            ex_type, ex_value, tb = sys.exc_info()
            self.logger.error(
                "Encountered exception when launching power monitor thread."
            )
            self.logger.error(ex_type, ex_value, "".join(traceback.format_tb(tb)))
            raise

    def get_latest_info_and_check_for_errors(self):
        """
        Reads the latest information from the log file and checks for errors that may have occured in the separate
        process

        :return: latest stats
        """
        try:
            message = self.queue.get(block=False)
            if isinstance(message, tuple):
                ret, error = message
            else:
                self.queue.put(message)
            if error:
                ex_type, ex_value, tb_str = error
                message = "%s (in subprocess)\n%s" % (str(ex_value), tb_str)
                raise ex_type(message)
        except EmptyQueueException:
            # Nothing in the message queue
            pass

        return read_latest_stats(self.logdir)

    def __enter__ (self):
        """
        Allows the object to function as a context and exit.

        For example,

        with ImpactTracker("./log1"):
            do_thing1()

        with ImpactTracker("./log2"):
            do_thing2()

        :return:
        """
        if launched:
            self.logger.error("Cannot enter an impact tracker after it has already been launched! Create a new "
                              "impact tracker object, please.")
            raise ValueError("Cannot enter an impact tracker after it has already been launched!")
        self.launch_impact_monitor()

    def __exit__ (self):
        """
        Allows the object to function as a context and exit.

        For example,

        with ImpactTracker("./log1"):
            do_thing1()

        with ImpactTracker("./log2"):
            do_thing2()

        :return:
        """
        # Code to start a new transaction
        self.stop()

    def stop(self):
        """
        Stops the monitoring thread

        :return:
        """
        self.queue.put(STOP_MESSAGE)
