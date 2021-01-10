import atexit
import os
import time

import cpuinfo
import numpy as np
import pandas as pd
import psutil
import requests
from bs4 import BeautifulSoup

from experiment_impact_tracker.cpu.common import get_my_cpu_info
from experiment_impact_tracker.utils import *

from . import powercap, rapl


def get_and_cache_cpu_max_tdp_from_intel():
    """ Goes to Intel's website and pulls information about TDP.
    """
    cpu_brand = cpuinfo.get_cpu_info()["brand"].split(" ")[2]
    if os.path.exists(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "cpuinfocache/{}".format(cpu_brand),
        )
    ):
        with open(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "cpuinfocache/{}".format(cpu_brand),
            ),
            "r",
        ) as f:
            return int(f.readline())
    s = requests.Session()
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.131 Safari/537.36"
    s.headers["User-Agent"] = user_agent
    r = s.get(
        "https://ark.intel.com/content/www/us/en/ark/search.html?_charset_=UTF-8&q={}".format(
            cpu_brand
        ),
        allow_redirects=True,
    )
    soup = BeautifulSoup(r.content, "lxml")
    results = soup.find_all("span", attrs={"data-key": "MaxTDP"})

    if len(results) == 0:
        redirect_url = soup.find(id="FormRedirectUrl").attrs["value"]
        if redirect_url:
            r = s.get("https://ark.intel.com/" + redirect_url, allow_redirects=True)
            soup = BeautifulSoup(r.content, "lxml")
            results = soup.find_all("span", attrs={"data-key": "MaxTDP"})

    with open(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "cpuinfocache/{}".format(cpu_brand),
        ),
        "w",
    ) as f:
        f.write((results[0].text.strip().replace("W", "")))
    return int(results[0].text.strip().replace("W", ""))


_timer = getattr(time, "monotonic", time.time)


def is_intel_compatible(*args, **kwargs):
    return powercap.is_powercap_compatible() or rapl._is_rapl_compatible()


def get_intel_power(pid_list, logger=None, **kwargs):
    """ Gathers CPU information from RAPL.

    Args:
        pid_list ([int]): List of process IDs to attribute power to.
        logger (optional): Logger to use when logging information. Defaults to None.

    Raises:
        NotImplementedError: If an unexpected top-level domain is encountered in RAPL information.
        ValueError: If no memory is used by the processes. This seems highly unlikely if not impossible and is probably a bug.
        ValueError: If RAPL power estimates are coming back 0. This is unlikely if not impossible so is probably an error.

    Returns:
        dict: Information about CPU
    """
    if rapl._is_rapl_compatible():
        return get_rapl_power(pid_list, logger, **kwargs)
    elif powercap.is_powercap_compatible():
        return get_powercap_power(pid_list, logger, **kwargs)
    else:
        raise ValueError("Not compatible with any power interface")


def get_powercap_power(pid_list, logger=None, **kwargs):
    """ Gathers CPU information from RAPL.

    Args:
        pid_list ([int]): List of process IDs to attribute power to.
        logger (optional): Logger to use when logging information. Defaults to None.

    Raises:
        NotImplementedError: If an unexpected top-level domain is encountered in RAPL information.
        ValueError: If no memory is used by the processes. This seems highly unlikely if not impossible and is probably a bug.
        ValueError: If RAPL power estimates are coming back 0. This is unlikely if not impossible so is probably an error.

    Returns:
        dict: Information about CPU
    """
    # start an initial sample to maximize time between samples without artificial waits
    powercap_interface = powercap.PowerGadget()
    powercap_interface.start()

    cpu_percent = 0
    absolute_cpu_percent = 0
    cpu_times = 0

    infos1 = []
    infos2 = []

    process_list = []
    mem_info_per_process = {}
    cpu_times_per_process = {}

    # gather processes as process objects
    for process in pid_list:
        try:
            p = psutil.Process(process)
            process_list.append(p)
        except psutil.NoSuchProcess:
            if logger is not None:
                logger.warn(
                    "Process with pid {} used to be part of this process chain, but was shut down. Skipping."
                )
            continue

    # Get initial times and cpu info
    zombies = []
    for i, p in enumerate(process_list):
        # Modifying code https://github.com/giampaolo/psutil/blob/c10df5aa04e1ced58d19501fa42f08c1b909b83d/psutil/__init__.py#L1102-L1107
        # We want relative percentage of CPU used so we ignore the multiplier by number of CPUs, we want a number from 0-1.0 to give
        # power credits accordingly
        st11 = _timer()
        # units in terms of cpu-time, so we need the cpu in the last time period that are for the process only
        system_wide_pt1 = psutil.cpu_times()
        st12 = _timer()
        try:
            pt1 = p.cpu_times()
            infos1.append((st11, st12, system_wide_pt1, pt1))
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            zombies.append(i)

    time.sleep(2.0)

    for p in process_list:
        st21 = _timer()
        try:
            pt2 = p.cpu_times()
            st22 = _timer()
            system_wide_pt2 = psutil.cpu_times()
            infos2.append((st21, st22, system_wide_pt2, pt2))
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            zombies.append(i)
    # now is a good time to get the power samples that we got the process times for
    powercap_results = powercap_interface.join()
    total_intel_power = powercap_results.get("Processor Power_0(Watt)", 0)
    total_dram_power = powercap_results.get("DRAM Power_0(Watt)", 0)
    total_cpu_power = powercap_results.get("IA Power_0(Watt)", 0)
    total_gpu_power = powercap_results.get("GT Power_0(Watt)", 0)

    if total_gpu_power != 0:
        raise ValueError("Don't support credit assignment to Intel RAPL GPU yet.")

    for i, p in enumerate(process_list):
        if i in zombies:
            continue
        st1, st12, system_wide_pt1, pt1 = infos1[i]
        st2, st22, system_wide_pt2, pt2 = infos2[i]

        # change in cpu-hours process
        delta_proc = (pt2.user - pt1.user) + (pt2.system - pt1.system)
        cpu_util_process = delta_proc / float(st2 - st1)
        # change in cpu-hours system
        delta_proc2 = (system_wide_pt2.user - system_wide_pt1.user) + (
            system_wide_pt2.system - system_wide_pt1.system
        )
        cpu_util_system = delta_proc2 / float(st22 - st12)

        # percent of cpu-hours in time frame attributable to this process (e.g., attributable compute)
        attributable_compute = cpu_util_process / cpu_util_system

        delta_time = st2 - st1

        # cpu-seconds / seconds = cpu util
        # NOTE: WE DO NOT MULTIPLY BY THE NUMBER OF CORES LIKE HTOP, WE WANT 100% to be the max
        # since we want a percentage of the total packages.
        # TODO: I'm not sure if this will get that in all configurations of hardware.
        absolute_cpu_percent += delta_proc / float(delta_time)

        cpu_percent += attributable_compute

        # only care about cpu_times for latest number
        cpu_times += (pt2.user) + (pt2.system)
        cpu_times_per_process[pid_list[i]] = pt2._asdict()
        try:
            try:
                mem_info = p.memory_full_info()
            except psutil.AccessDenied:
                mem_info = p.memory_info()
            mem_info_per_process[pid_list[i]] = mem_info._asdict()
        except (psutil.ZombieProcess, psutil.NoSuchProcess):
            pass

    total_physical_memory = psutil.virtual_memory()
    # what percentage of used memory can be attributed to this process
    # pss (Linux): aka “Proportional Set Size”, is the amount of memory shared with other processes, accounted in a
    # way  that the amount is divided evenly between the processes that share it. I.e. if a process has 10 MBs all to
    # itself and 10 MBs shared with another process its PSS will be 15 MBs.
    # summing these two gets us a nice fair metric for the actual memory used in the RAM hardware. The unique bits
    # are directly attributable to the process
    # and the shared bits we give credit based on how many processes share those bits
    pss_avail = all(["pss" in x.keys() for x in mem_info_per_process.values()])

    if pss_avail:
        system_wide_mem_percent = np.sum(
            [
                float(x["pss"])
                / float(total_physical_memory.total - total_physical_memory.available)
                for x in mem_info_per_process.values()
            ]
        )
    else:
        # Sometimes we don't have access to PSS so just need to make due with Rss
        system_wide_mem_percent = np.sum(
            [
                float(x["rss"])
                / float(total_physical_memory.total - total_physical_memory.available)
                for x in mem_info_per_process.values()
            ]
        )
    power_credit_cpu = cpu_percent
    power_credit_mem = system_wide_mem_percent
    if power_credit_cpu == 0:
        logger.warn(
            "Problem retrieving CPU usage percentage to assign power credit, not using any CPU. This is possibly "
            "true, but seems unlikely! See if there's a problem! "
        )
    if power_credit_mem == 0:
        raise ValueError(
            "Problem retrieving Mem usage percentage to assign power credit"
        )

    total_attributable_power = 0
    if total_cpu_power != 0:
        total_attributable_power += total_cpu_power * power_credit_cpu
    if total_dram_power != 0:
        total_attributable_power += total_dram_power * power_credit_mem

    # assign the rest of the power to the CPU percentage even if this is a bit innacurate
    total_attributable_power += (
        total_intel_power - total_dram_power - total_cpu_power
    ) * power_credit_cpu

    if total_intel_power == 0:
        raise ValueError(
            "It seems that power estimates from Intel RAPL are coming back 0, this indicates a problem."
        )

    if pss_avail:
        abs_mem_usage = np.sum(
            [float(x["pss"]) for x in mem_info_per_process.values()]
        )

        abs_mem_percent_usage = np.sum(
            [
                float(x["pss"]) / float(total_physical_memory.total)
                for x in mem_info_per_process.values()
            ]
        )
    else:
        abs_mem_usage = np.sum([float(x["rss"]) for x in mem_info_per_process.values()])

        abs_mem_percent_usage = np.sum(
            [
                float(x["rss"]) / float(total_physical_memory.total)
                for x in mem_info_per_process.values()
            ]
        )

    if total_intel_power < total_attributable_power:
        raise ValueError("For some reason the total intel estimated power is less than the attributable power. This "
                         "means there is an error in computing the attribution. Please re-open "
                         "https://github.com/Breakend/experiment-impact-tracker/issues/38 and add the trace for this "
                         "warning.")

    data_return_values_with_headers = {
        "rapl_power_draw_absolute": total_intel_power,
        "rapl_estimated_attributable_power_draw": total_attributable_power,
        "cpu_time_seconds": cpu_times_per_process,
        "average_relative_cpu_utilization": cpu_percent,
        "absolute_cpu_utilization": absolute_cpu_percent,
        "relative_mem_usage": system_wide_mem_percent,
        "absolute_mem_usage": abs_mem_usage,
        "absolute_mem_percent_usage": abs_mem_percent_usage,
        "mem_info_per_process": mem_info_per_process,
    }

    return data_return_values_with_headers


def get_rapl_power(pid_list, logger=None, **kwargs):
    """ Gathers CPU information from RAPL.

    Args:
        pid_list ([int]): List of process IDs to attribute power to.
        logger (optional): Logger to use when logging information. Defaults to None.

    Raises:
        NotImplementedError: If an unexpected top-level domain is encountered in RAPL information.
        ValueError: If no memory is used by the processes. This seems highly unlikely if not impossible and is probably a bug.
        ValueError: If RAPL power estimates are coming back 0. This is unlikely if not impossible so is probably an error.

    Returns:
        dict: Information about CPU
    """
    # start an initial sample to maximize time between samples without artificial waits
    s1 = rapl.RAPLMonitor.sample()

    cpu_percent = 0
    absolute_cpu_percent = 0
    cpu_times = 0

    infos1 = []
    infos2 = []

    process_list = []
    mem_info_per_process = {}
    cpu_times_per_process = {}

    # gather processes as process objects
    for process in pid_list:
        try:
            p = psutil.Process(process)
            process_list.append(p)
        except psutil.NoSuchProcess:
            if logger is not None:
                logger.warn(
                    "Process with pid {} used to be part of this process chain, but was shut down. Skipping."
                )
            continue

    # Get initial times and cpu info
    zombies = []
    for i, p in enumerate(process_list):
        # Modifying code https://github.com/giampaolo/psutil/blob/c10df5aa04e1ced58d19501fa42f08c1b909b83d/psutil/__init__.py#L1102-L1107
        # We want relative percentage of CPU used so we ignore the multiplier by number of CPUs, we want a number from 0-1.0 to give
        # power credits accordingly
        st11 = _timer()
        # units in terms of cpu-time, so we need the cpu in the last time period that are for the process only
        system_wide_pt1 = psutil.cpu_times()
        st12 = _timer()
        try:
            pt1 = p.cpu_times()
            infos1.append((st11, st12, system_wide_pt1, pt1))
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            zombies.append(i)

    time.sleep(2.0)

    for p in process_list:
        st21 = _timer()
        try:
            pt2 = p.cpu_times()
            st22 = _timer()
            system_wide_pt2 = psutil.cpu_times()
            infos2.append((st21, st22, system_wide_pt2, pt2))
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            zombies.append(i)

    # now is a good time to get the power samples that we got the process times for
    s2 = rapl.RAPLMonitor.sample()
    diff = s2 - s1
    total_intel_power = 0
    total_dram_power = 0
    total_cpu_power = 0
    total_gpu_power = 0
    for d in diff.domains:
        domain = diff.domains[d]
        power = diff.average_power(package=domain.name)
        # this should get the power per package (e.g., total rapl power)
        # see images/power-planes.png for example
        # Downloaded from: https://blog.chih.me/images/power-planes.jpg
        #  Recent (Sandy Bridge and later) Intel processors that implement the RAPL (Running Average Power Limit)
        # interface that provides MSRs containing energy consumption estimates for up to four power planes or
        # domains of a machine, as seen in the diagram above.
        # PKG: The entire package.
        # PP0: The cores.
        # PP1: An uncore device, usually the GPU (not available on all processor models.)
        # DRAM: main memory (not available on all processor models.)
        # PSys: Skylake mobile SoC total energy
        # The following relationship holds: PP0 + PP1 <= PKG. DRAM is independent of the other three domains.
        # Most processors come in two packages so top level domains shold be package-1 and package-0

        if domain.name == "psys":  # skip SoC aggregate reporting
            continue

        if "package" not in domain.name:
            raise NotImplementedError(
                "Unexpected top level domain for RAPL package. Not yet supported."
            )

        total_intel_power += power

        for sd in domain.subdomains:
            subdomain = domain.subdomains[sd]
            power = diff.average_power(package=domain.name, domain=subdomain.name)
            subdomain = subdomain.name.lower()
            if subdomain == "ram" or subdomain == "dram":
                total_dram_power += power
            elif subdomain == "cores" or subdomain == "cpu":
                total_cpu_power += power
            elif subdomain == "gpu":
                total_gpu_power += power
            # other domains get don't have relevant readouts to give power attribution, therefore
            # will get assigned the same amount of credit as the CPU

    if total_gpu_power != 0:
        raise ValueError("Don't support credit assignment to Intel RAPL GPU yet.")

    for i, p in enumerate(process_list):
        if i in zombies:
            continue

        st1, st12, system_wide_pt1, pt1 = infos1[i]
        st2, st22, system_wide_pt2, pt2 = infos2[i]

        # change in cpu-hours process
        delta_proc = (pt2.user - pt1.user) + (pt2.system - pt1.system)
        cpu_util_process = delta_proc / float(st2 - st1)
        # change in cpu-hours system
        delta_proc2 = (system_wide_pt2.user - system_wide_pt1.user) + (
            system_wide_pt2.system - system_wide_pt1.system
        )
        cpu_util_system = delta_proc2 / float(st22 - st12)

        # percent of cpu-hours in time frame attributable to this process (e.g., attributable compute)
        attributable_compute = cpu_util_process / cpu_util_system

        delta_time = st2 - st1

        # cpu-seconds / seconds = cpu util
        # NOTE: WE DO NOT MULTIPLY BY THE NUMBER OF CORES LIKE HTOP, WE WANT 100% to be the max
        # since we want a percentage of the total packages.
        # TODO: I'm not sure if this will get that in all configurations of hardware.
        absolute_cpu_percent += delta_proc / float(delta_time)

        cpu_percent += attributable_compute

        # only care about cpu_times for latest number
        cpu_times += (pt2.user) + (pt2.system)
        cpu_times_per_process[pid_list[i]] = pt2._asdict()
        try:
            try:
                mem_info = p.memory_full_info()
            except psutil.AccessDenied:
                mem_info = p.memory_info()
            mem_info_per_process[pid_list[i]] = mem_info._asdict()
        except (psutil.ZombieProcess, psutil.NoSuchProcess):
            pass

    total_physical_memory = psutil.virtual_memory()
    # what percentage of used memory can be attributed to this process
    # pss (Linux): aka “Proportional Set Size”, is the amount of memory shared with other processes, accounted in a way
    # that the amount is divided evenly between the processes that share it. I.e. if a process has 10 MBs all to itself
    # and 10 MBs shared with another process its PSS will be 15 MBs.
    # summing these two gets us a nice fair metric for the actual memory used in the RAM hardware.
    # The unique bits are directly attributable to the process
    # and the shared bits we give credit based on how many processes share those bits
    pss_avail = all(["pss" in x for x in mem_info_per_process.values()])
    if pss_avail:
        system_wide_mem_percent = np.sum(
            [
                float(x["pss"])
                / float(total_physical_memory.total - total_physical_memory.available)
                for x in mem_info_per_process.values()
            ]
        )
    else:
        # Sometimes we don't have access to PSS so just need to make due with rss
        system_wide_mem_percent = np.sum(
            [
                float(x["rss"])
                / float(total_physical_memory.total - total_physical_memory.available)
                for x in mem_info_per_process.values()
            ]
        )
    power_credit_cpu = cpu_percent
    power_credit_mem = system_wide_mem_percent
    if power_credit_cpu == 0:
        logger.warn(
            "Problem retrieving CPU usage percentage to assign power credit, not using any CPU. This is possibly true, but seems unlikely! See if there's a problem!"
        )
    if power_credit_mem == 0:
        raise ValueError(
            "Problem retrieving Mem usage percentage to assign power credit"
        )

    total_attributable_power = 0
    if total_cpu_power != 0:
        total_attributable_power += total_cpu_power * power_credit_cpu
    if total_dram_power != 0:
        total_attributable_power += total_dram_power * power_credit_mem

    # assign the rest of the power to the CPU percentage even if this is a bit innacurate
    total_attributable_power += (
        total_intel_power - total_dram_power - total_cpu_power
    ) * power_credit_cpu

    if total_intel_power == 0:
        raise ValueError(
            "It seems that power estimates from Intel RAPL are coming back 0, this indicates a problem."
        )

    if pss_avail:
        abs_mem_usage = np.sum(
            [float(x["pss"]) for x in mem_info_per_process.values()]
        )

        abs_mem_percent_usage = np.sum(
            [
                float(x["pss"]) / float(total_physical_memory.total)
                for x in mem_info_per_process.values()
            ]
        )
    else:
        abs_mem_usage = np.sum([float(x["rss"]) for x in mem_info_per_process.values()])

        abs_mem_percent_usage = np.sum(
            [
                float(x["rss"]) / float(total_physical_memory.total)
                for x in mem_info_per_process.values()
            ]
        )

    if total_intel_power < total_attributable_power:
        raise ValueError("For some reason the total intel estimated power is less than the attributable power. This "
                         "means there is an error in computing the attribution. Please re-open "
                         "https://github.com/Breakend/experiment-impact-tracker/issues/38 and add the trace for this "
                         "warning.")

    data_return_values_with_headers = {
        "rapl_power_draw_absolute": total_intel_power,
        "rapl_estimated_attributable_power_draw": total_attributable_power,
        "cpu_time_seconds": cpu_times_per_process,
        "average_relative_cpu_utilization": cpu_percent,
        "absolute_cpu_utilization": absolute_cpu_percent,
        "relative_mem_usage": system_wide_mem_percent,
        "absolute_mem_usage": abs_mem_usage,
        "absolute_mem_percent_usage": abs_mem_percent_usage,
        "mem_info_per_process": mem_info_per_process,
    }

    return data_return_values_with_headers
