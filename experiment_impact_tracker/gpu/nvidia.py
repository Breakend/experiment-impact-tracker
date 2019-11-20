import atexit
import subprocess
import time
from collections import OrderedDict
from subprocess import PIPE, Popen
from xml.etree.ElementTree import fromstring

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

import cpuinfo
import psutil
from experiment_impact_tracker.utils import *

from .exceptions import GPUAttributeAssertionError

_timer = getattr(time, 'monotonic', time.time)


def is_nvidia_compatible(*args, **kwargs):
    from shutil import which

    if which("nvidia-smi") is None:
        return False

    # make sure that nvidia-smi doesn't just return no devices
    p = Popen(['nvidia-smi'], stdout=PIPE)
    stdout, stderror = p.communicate()
    output = stdout.decode('UTF-8')
    if "no devices" in output.lower():
        return False

    return True


def get_gpu_info(*args, **kwargs):
    p = Popen(['nvidia-smi', '-q', '-x'], stdout=PIPE)
    outs, errors = p.communicate()
    xml = fromstring(outs)
    datas = []
    driver_version = xml.findall('driver_version')[0].text
    cuda_version = xml.findall('cuda_version')[0].text

    for gpu_id, gpu in enumerate(xml.getiterator('gpu')):
        gpu_data = {}
        name = [x for x in gpu.getiterator('product_name')][0].text
        memory_usage = gpu.findall('fb_memory_usage')[0]
        total_memory = memory_usage.findall('total')[0].text

        gpu_data['name'] = name
        gpu_data['total_memory'] = total_memory
        gpu_data['driver_version'] = driver_version
        gpu_data['cuda_version'] = cuda_version
        datas.append(gpu_data)
    return datas


def assert_gpus_by_attributes(attributes_set):
    """Assert that you're running on GPUs with a certain set of attributes.

    This helps when running jobs in a cluster setting with heterogeneous GPUs
    to filter out sets of GPUs that you'd rather avoid. Current NVIDIA attributes,
    include product_name (e.g., GeForce GTX TITAN X, Titan xp, Tesla k40m, etc.),
    must be an exact match based on string seen in nvidia-smi -q -x. 

    Args:
        attributes_set (dict): set of attribute key pairs

    Raises:
        GPUAttributeAssertionError on encountered asserted attribute mismatch
    """
    gpu_info = get_gpu_info()
    for gpu in gpu_info:
        for attribute, value in attributes_set.items():
            try:
                if gpu[attribute] != value:
                    raise GPUAttributeAssertionError("Attribute {} asserted to be {}, but found {} instead.".format(
                        attribute, value, gpu[attribute]))
            except KeyError:
                raise GPUAttributeAssertionError("Attribute {} does not exist. Available attributes: {}.".format(
                    attribute, ",".join(list(gpu.keys()))))


def _stringify_performance_states(state_dict):
    """ Stringifies performance states across multiple gpus

    Args:
        state_dict (dict(str)): a dictionary of gpu_id performance state values

    Returns:
        str: a stringified version of the dictionary with gpu_id::performance state|gpu_id2::performance_state2 format
    """
    return "|".join("::".join(map(lambda x: str(x), z)) for z in state_dict.items())


def get_nvidia_gpu_power(pid_list, logger=None, **kwargs):
    # Find per process per gpu usage info
    sp = subprocess.Popen(['nvidia-smi', 'pmon', '-c', '5'],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out_str = sp.communicate()
    out_str_split = out_str[0].decode('utf-8').split('\n')
    # sometimes with too many processess on the machine or too many gpus, this command will reprint the headers
    # to avoid that we just remove duplicate lines
    out_str_split = list(OrderedDict.fromkeys(out_str_split))
    out_str_pruned = [x for x in out_str_split if 'Idx' not in x] # [out_str_split[0], ] + out_str_split[2:]
    
    # For some weird reason the header position sometimes gets jumbled so we need to re-order it to the front 
    position = -1

    for i, x in enumerate(out_str_pruned):
        if 'gpu' in x:
            position = i
    if position == -1:
        raise ValueError('Problem with output in nvidia-smi pmon -c 10')
    out_str_pruned.insert(0, out_str_pruned.pop(position))
    out_str_final = "\n".join(out_str_pruned)
    out_str_final = out_str_final.replace("-", "0")
    out_str_final = out_str_final.replace("#", "")

    df = pd.read_csv(pd.compat.StringIO(
        out_str_final), engine='python', delim_whitespace=True)
    process_percentage_used_gpu = df.groupby(
        ['gpu', 'pid']).mean().reset_index()

    p = Popen(['nvidia-smi', '-q', '-x'], stdout=PIPE)
    outs, errors = p.communicate()
    xml = fromstring(outs)
    num_gpus = int(xml.findall('attached_gpus')[0].text)
    results = []
    power = 0
    per_gpu_absolute_percent_usage = {}
    per_gpu_relative_percent_usage = {}
    absolute_power = 0
    per_gpu_performance_states = {}

    for gpu_id, gpu in enumerate(xml.findall('gpu')):
        gpu_data = {}

        name = gpu.findall('product_name')[0].text
        gpu_data['name'] = name

        # get memory
        memory_usage = gpu.findall('fb_memory_usage')[0]
        total_memory = memory_usage.findall('total')[0].text
        used_memory = memory_usage.findall('used')[0].text
        free_memory = memory_usage.findall('free')[0].text
        gpu_data['memory'] = {
            'total': total_memory,
            'used_memory': used_memory,
            'free_memory': free_memory
        }

        # get utilization
        utilization = gpu.findall('utilization')[0]
        gpu_util = utilization.findall('gpu_util')[0].text
        memory_util = utilization.findall('memory_util')[0].text
        gpu_data['utilization'] = {
            'gpu_util': gpu_util,
            'memory_util': memory_util
        }

        # get power
        power_readings = gpu.findall('power_readings')[0]
        power_draw = power_readings.findall('power_draw')[0].text

        gpu_data['power_readings'] = {
            'power_draw': power_draw
        }
        absolute_power += float(power_draw.replace("W", ""))

        # processes
        processes = gpu.findall('processes')[0]

        infos = []
        # all the info for processes on this particular gpu that we're on
        gpu_based_processes = process_percentage_used_gpu[process_percentage_used_gpu['gpu'] == gpu_id]
        # what's the total absolute SM for this gpu across all accessible processes
        percentage_of_gpu_used_by_all_processes = float(
            gpu_based_processes['sm'].sum())
        per_gpu_power_draw = {}
        for info in processes.findall('process_info'):
            pid = info.findall('pid')[0].text
            process_name = info.findall('process_name')[0].text
            used_memory = info.findall('used_memory')[0].text
            sm_absolute_percent = gpu_based_processes[gpu_based_processes['pid'] == int(
                pid)]['sm'].sum()
            if percentage_of_gpu_used_by_all_processes == 0:
                # avoid divide by zero, sometimes nothing is used so 0/0 should = 0 in this case
                sm_relative_percent = 0
            else:
                sm_relative_percent = sm_absolute_percent / \
                    percentage_of_gpu_used_by_all_processes
            infos.append({
                'pid': pid,
                'process_name': process_name,
                'used_memory': used_memory,
                'sm_relative_percent': sm_relative_percent,
                'sm_absolute_percent': sm_absolute_percent
            })

            if int(pid) in pid_list:
                # only add a gpu to the list if it's being used by one of the processes. sometimes nvidia-smi seems to list all gpus available
                # even if they're not being used by our application, this is a problem in a slurm setting
                if gpu_id not in per_gpu_absolute_percent_usage:
                    # percentage_of_gpu_used_by_all_processes
                    per_gpu_absolute_percent_usage[gpu_id] = 0
                if gpu_id not in per_gpu_relative_percent_usage:
                    # percentage_of_gpu_used_by_all_processes
                    per_gpu_relative_percent_usage[gpu_id] = 0

                if gpu_id not in per_gpu_performance_states:
                    # we only log information for gpus that we're using, we've noticed that nvidia-smi will sometimes return information
                    # about all gpu's on a slurm cluster even if they're not assigned to a worker
                    performance_state = gpu.findall(
                        'performance_state')[0].text
                    per_gpu_performance_states[gpu_id] = performance_state

                power += sm_relative_percent * \
                    float(power_draw.replace("W", ""))
                per_gpu_power_draw[gpu_id] = float(power_draw.replace("W", ""))
                # want a proportion value rather than percentage
                per_gpu_absolute_percent_usage[gpu_id] += (
                    sm_absolute_percent / 100.0)
                per_gpu_relative_percent_usage[gpu_id] += sm_relative_percent

        gpu_data['processes'] = infos

        results.append(gpu_data)

    if len(per_gpu_absolute_percent_usage.values()) == 0:
        average_gpu_utilization = 0
        average_gpu_relative_utilization = 0
    else:
        average_gpu_utilization = np.mean(
            list(per_gpu_absolute_percent_usage.values()))
        average_gpu_relative_utilization = np.mean(
            list(per_gpu_relative_percent_usage.values()))

    data_return_values_with_headers = {
        "nvidia_draw_absolute": absolute_power,
        "nvidia_estimated_attributable_power_draw": power,
        "average_gpu_estimated_utilization_absolute": average_gpu_utilization,
        "per_gpu_average_estimated_utilization_absolute": process_percentage_used_gpu.set_index(['gpu', 'pid']).to_dict(orient='index'),
        "average_gpu_estimated_utilization_relative": average_gpu_relative_utilization,
        "per_gpu_performance_state": per_gpu_performance_states,
        "per_gpu_power_draw" : per_gpu_power_draw
    }

    return data_return_values_with_headers
