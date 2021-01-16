#!/usr/bin/env python3

from __future__ import print_function

import argparse
import json
import os
import re
import sys
from datetime import datetime
from importlib import import_module
from itertools import combinations
from pprint import pprint
from shutil import copyfile

import numpy as np
import pandas as pd
import scipy
from deepdiff import DeepDiff  # For Deep Difference of 2 objects
from jinja2 import Environment, FileSystemLoader

import experiment_impact_tracker
from experiment_impact_tracker.create_graph_appendix import (
    create_graphs, create_scatterplot_from_df)
from experiment_impact_tracker.data_utils import (load_data_into_frame,
                                                  load_initial_info,
                                                  zip_data_and_info)
from experiment_impact_tracker.emissions.common import \
    get_realtime_carbon_source
from experiment_impact_tracker.emissions.constants import PUE
from experiment_impact_tracker.emissions.get_region_metrics import \
    get_zone_name_by_id
from experiment_impact_tracker.stats import (get_average_treatment_effect,
                                             run_test)
from experiment_impact_tracker.utils import gather_additional_info

pd.set_option("display.max_colwidth", -1)


def _gather_executive_summary(
    aggregated_info, executive_summary_variables, experiment_set_names, all_points=False
):
    # Gather variables to generate executive summary for
    executive_summary = [["Experiment"] + executive_summary_variables]
    for exp_name in experiment_set_names:
        if not all_points:
            data = [exp_name]
            for variable in executive_summary_variables:
                values = aggregated_info[exp_name][variable]
                values_mean = np.mean(values)
                values_stdder = scipy.stats.sem(values)
                data.append("{:.3f} +/- {:.2f}".format(values_mean, values_stdder))
            executive_summary.append(data)
        else:
            for j in range(
                len(aggregated_info[exp_name][executive_summary_variables[0]])
            ):
                data = [exp_name]
                for variable in executive_summary_variables:
                    values = aggregated_info[exp_name][variable]
                    data.append(values[j])
                executive_summary.append(data)

    executive_summary = pd.DataFrame(np.vstack(executive_summary))

    new_header = executive_summary.iloc[0]  # grab the first row for the header
    # take the data less the header row
    executive_summary = executive_summary[1:]
    executive_summary.columns = new_header  # set the header row as the df header

    return executive_summary


def _format_setname(setname):
    return setname.lower().replace(" ", "_").replace("(", "").replace(")", "")


def _get_carbon_infos(info, extended_info):
    vals = {}
    if "average_realtime_carbon_intensity" in extended_info:
        vals["Realtime Carbon Intensity Data Source"] = [
            get_realtime_carbon_source(info["region"]["id"])
        ]
        vals["Realtime Carbon Intensity Average During Exp"] = [
            extended_info["average_realtime_carbon_intensity"]
        ]

    vals["Region Average Carbon Intensity"] = [
        info["region_carbon_intensity_estimate"]["carbonIntensity"]
    ]
    vals["Region Average Carbon Intensity Source"] = [
        info["region_carbon_intensity_estimate"]["_source"]
    ]
    vals["Assumed PUE"] = [PUE]
    vals["Compute Region"] = [get_zone_name_by_id(info["region"]["id"])]
    vals["Experiment Impact Tracker Version"] = [
        info["experiment_impact_tracker_version"]
    ]
    return pd.DataFrame.from_dict(vals)


def _construct_index_page(
    output_directory,
    aggregated_info,
    experiment_set_names,
    experiment_set_filters,
    executive_summary_variables,
    description,
    title,
    base_dir,
    plot_paths=[],
    executive_summary_ordering_variable=None,
):
    os.makedirs(output_directory, exist_ok=True)
    template_directory = os.path.join(
        os.path.dirname(experiment_impact_tracker.__file__), "html_templates"
    )
    file_loader = FileSystemLoader(template_directory)
    env = Environment(loader=file_loader)

    template = env.get_template("index.html")

    # Gather variables to generate executive summary for
    executive_summary = _gather_executive_summary(
        aggregated_info,
        executive_summary_variables,
        experiment_set_names,
        all_points=False,
    )
    if executive_summary_ordering_variable is not None:
        executive_summary["sort"] = (
            executive_summary[executive_summary_ordering_variable]
            .str.extract("([-+]?\d*\.\d+|\d+)", expand=False)
            .astype(float)
        )
        executive_summary.sort_values(by="sort", inplace=True, ascending=False)
        executive_summary = executive_summary.drop("sort", axis=1)
    plot_paths = [
        os.path.relpath(plot_path, output_directory) for plot_path in plot_paths
    ]

    output = template.render(
        exp_set_names_titles=[
            (
                _format_setname(experiment_set_names[exp_set]),
                experiment_set_names[exp_set],
            )
            for exp_set in range(len(experiment_set_filters))
        ],
        executive_summary=executive_summary,
        title=title,
        description=description,
        relative_base_dir=os.path.relpath(base_dir, output_directory),
        plot_paths=plot_paths,
    )

    with open(os.path.join(output_directory, "index.html"), "w") as f:
        f.write(output)


def _filter_dirs(all_log_dirs, _filter):
    if _filter is None:
        return all_log_dirs

    # Allow for a sort of regex filter
    def check(x):
        return bool(re.search(_filter, x))

    filtered_dirs = list(filter(check, all_log_dirs))
    print("Filtered dirs: {}".format(",".join(filtered_dirs)))
    return filtered_dirs


def _method_from_string(function_string):
    p, m = function_string.rsplit(".", 1)
    mod = import_module(p)
    return getattr(mod, m)


class DataInterface(object):
    def __init__(self, logdirs):

        if isinstance(logdirs, str):
            logdirs = [logdirs]

        all_log_dirs = []

        for log_dir in logdirs:
            for path, subdirs, files in os.walk(log_dir):
                if "impacttracker" in path:
                    all_log_dirs.append(
                        path.replace("impacttracker", "").replace("//", "/")
                    )

        all_log_dirs = list(set(all_log_dirs))
        kg_carbon = 0
        total_power = 0.0
        exp_len_hours = 0

        for log_dir in all_log_dirs:
            info = load_initial_info(log_dir)
            extracted_info = gather_additional_info(info, log_dir)
            kg_carbon += float(extracted_info["estimated_carbon_impact_kg"])
            total_power += float(extracted_info["total_power"])
            exp_len_hours += float(extracted_info["exp_len_hours"])

        self.kg_carbon = kg_carbon
        self.total_power = total_power
        self.PUE = PUE
        self.exp_len_hours = exp_len_hours
