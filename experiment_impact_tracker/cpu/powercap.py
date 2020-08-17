"""
Modified from https://github.com/mozilla/energia/blob/8bfc8e2cf774b702ea1085a164403356cc10086b/wrappers/PowerGadget.py
"""
import multiprocessing
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

import pandas as pd
from pandas import DataFrame

sys.path.append("..")


get_long_path = lambda x: x
try:
    import win32api

    get_long_path = win32api.GetLongPathName
except:
    pass


def is_powercap_compatible(*args, **kwargs):
    try:
        PowerGadget()
        return True
    except:
        return False


class PowerGadget(object):
    _osx_exec = "PowerLog"
    _osx_exec_backup = "/Applications/Intel Power Gadget/PowerLog"
    _win_exec = "PowerLog.exe"
    _lin_exec = "power_gadget"

    def __init__(self, duration=2, resolution=100):
        self._fields = [
            "Processor Joules",
            "Processor Watt",
            "IA Joules",
            "IA Watt",
            "GT Joules",
            "GT Watt",
        ]
        self._system = platform.system()
        self.duration = duration
        self.resolution = resolution

        if self._system == "Darwin":
            if shutil.which(PowerGadget._osx_exec):
                self._tool = PowerGadget._osx_exec
            elif shutil.which(PowerGadget._osx_exec_backup):
                self._tool = PowerGadget._osx_exec_backup
            else:
                raise Exception("Intel Power Gadget executable not found")
        elif self._system == "Linux":
            if shutil.which(PowerGadget._lin_exec):
                self._tool = PowerGadget._lin_exec
            else:
                raise Exception("Intel Power Gadget executable not found")
        elif self._system == "Windows":
            if shutil.which(PowerGadget._win_exec):
                self._tool = PowerGadget._win_exec
            else:
                raise Exception("Intel Power Gadget executable not found")
        else:
            raise Exception("Platform is not supported.")

    def start(self):
        directory = get_long_path(tempfile.mkdtemp())
        print(directory)
        self._logfile = os.path.join(directory, "PowerLog.csv")
        self._log_process = multiprocessing.Process(target=self._start)
        self._log_process.start()

    def _start(self):
        resolution = self.resolution
        duration = self.duration

        if self._system == "Darwin":
            os.system(
                '"{}" -resolution {} -duration {} -file {} > /dev/null'.format(
                    self._tool, str(resolution), str(duration), self._logfile
                )
            )
        elif self._system == "Linux":
            os.system(
                "{} -e {} -d {} > {}".format(
                    self._tool, str(resolution), str(duration), self._logfile
                )
            )
        else:
            os.system(
                "{} -resolution {} -duration {} -file {} > NUL 2>&1".format(
                    self._tool, str(resolution), str(duration), self._logfile
                )
            )

    def join(self):
        self._log_process.join()
        return self._parse()

    def _parse(self):
        """
        Note: IA is the power draw of the cores, DRAM is the power draw of the DRAM, GT is the GPU
        :return:
        """
        summary = {}

        try:
            data = pd.read_csv(self._logfile).dropna()
            for col in data.columns:
                if col in ["System Time", "Elapsed Time (sec)", "RDTSC"]:
                    continue

                if "Cumulative" in col:
                    data[col].iloc[-1]
                else:
                    summary[col] = data[col].mean()
        except FileNotFoundError:
            raise Exception("PowerLog failed to generate a valid logfile")

        assert summary["Processor Power_0(Watt)"] > 0

        shutil.rmtree(os.path.split(self._logfile)[0])
        return summary
