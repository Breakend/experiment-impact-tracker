import argparse
import os
import sys
from pprint import pprint

import country_converter as coco
import geocoder
import numpy as np
import pandas as pd
from geopy.geocoders import Nominatim

import experiment_impact_tracker
from experiment_impact_tracker.emissions.get_region_metrics import (
    get_current_region_info, get_sorted_region_infos,
    get_zone_information_by_coords)

gpu_data = pd.read_csv(os.path.join(os.path.dirname(experiment_impact_tracker.__file__), 'gpu/data/tdp.csv'))
cpu_data = pd.read_csv(os.path.join(os.path.dirname(experiment_impact_tracker.__file__), 'cpu/data/cpu_tdp.csv'))

class RoughEmissionsEstimator(object):

    def __init__(self, gpu, cpu, gpu_utilization_factor, cpu_utilization_factor, location, experiment_length_seconds):
        self.gpu = gpu
        self.cpu = cpu
        self.gpu_utilization_factor = gpu_utilization_factor
        self.cpu_utilization_factor = cpu_utilization_factor
        self.location = location
        self.experiment_length_seconds = experiment_length_seconds

        self.gpu_vals = gpu_data.loc[gpu_data['name'] == self.gpu]

        if self.location is not None:
            geolocator = Nominatim(user_agent="experiment_impact_tracker")
            location = geolocator.geocode(self.location, addressdetails=True)
            country_code = location.raw["address"]["country_code"]
            zone_name, zone_info = get_zone_information_by_coords((location.latitude, location.longitude))
        else:
            raise ValueError("Must provide location.")

        self.zone_name = zone_name["properties"]["zoneName"]
        carbonIntensity = zone_info['carbonIntensity']
        carbonIntensity_source = zone_info['_source']

        gpu_kWh = kWh = float(self.gpu_vals['tdp']) * self.gpu_utilization_factor * (self.experiment_length_seconds /
                                                                                 3600.)\
                 / \
              1000.

        if self.cpu is not None:
            if self.cpu not in cpu_data["Model"].tolist():
                raise ValueError(f"CPU {self.cpu} not in available CPUs: {cpu_data['Model']}")

            tdp = cpu_data[cpu_data["Model"] == self.cpu]["TDP"].tolist()[0].replace("W", "").strip()
            cpu_kWh = float(tdp) * self.cpu_utilization_factor * (self.experiment_length_seconds / 3600.) / 1000.
            kWh += cpu_kWh

        kg_carbon = (carbonIntensity * kWh) / 1000.0

        self.kg_carbon = kg_carbon
        self.cpu_kWh = cpu_kWh
        self.gpu_kWh = gpu_kWh
        self.kWh = kWh
        self.carbon_intensity = carbonIntensity
        self.carbon_intensity_zone = zone_name

        ssc = pd.read_csv(
            "https://raw.githubusercontent.com/country-level-scc/cscc-database-2018/master/cscc_db_v2.csv")
        ISO3_COUNTRY_CODE = coco.convert(names=[country_code], to='ISO3')
        # only use short-run model
        ssc = ssc[ssc["run"] == "bhm_sr"]
        ssc = ssc[ssc["SSP"] == "SSP2"]
        ssc = ssc[ssc["ISO3"] == ISO3_COUNTRY_CODE]
        ssc = ssc[np.isnan(ssc["dr"])]  # use only growth adjusted models
        ssc = ssc[ssc["prtp"] == 2]  # a growth adjusted discount rate with 2% pure rate of time preference
        ssc = ssc[ssc["eta"] == "1p5"]  # IES of 1.5
        ssc = ssc[ssc["RCP"] == "rcp60"]  # rcp 6, middle of the road
        ssc = ssc[ssc["dmgfuncpar"] == "bootstrap"]
        ssc = ssc[ssc["climate"] == "uncertain"]

        median = ssc["50%"]
        lower = ssc["16.7%"]
        upper = ssc["83.3%"]

        median_carbon_cost = (kg_carbon / 1000.) * float(median)
        upper_carbon_cost = (kg_carbon / 1000.) * float(upper)
        lower_carbon_cost = (kg_carbon / 1000.) * float(lower)

        bibtex_nature = """
        @article{ricke2018country,
            title={Country-level social cost of carbon},
            author={Ricke, Katharine and Drouet, Laurent and Caldeira, Ken and Tavoni, Massimo},
            journal={Nature Climate Change},
            volume={8},
            number={10},
            pages={895},
            year={2018},
            publisher={Nature Publishing Group}
            }
            """

        bibtex_experiment_impact_tracker = """
            @misc{henderson2020systematic,
                title={Towards the Systematic Reporting of the Energy and Carbon Footprints of Machine Learning},
                author={Peter Henderson and Jieru Hu and Joshua Romoff and Emma Brunskill and Dan Jurafsky and Joelle Pineau},
                year={2020},
                eprint={2002.05651},
                archivePrefix={arXiv},
                primaryClass={cs.CY}
            }
            """

        statement = (
                "This work contributed a rough estimate of {:.3f} kg of $\\text{{CO}}_{{2eq}}$ to the atmosphere and used {:.3f} "
                "kWh of electricity, having a {}-specific social cost of carbon of \${:.2f} (\${:.2f}, \${:.2f}). This assumes "
                "{runtime:.3f} hours of runtime, a region-specific carbon intensity of {carbon_intensity:.3f} g CO2eq "
                "per kWh (see {carbonIntensity_source}) in {location} (assuming electricity grid Zone {zone_name}), "
                "a {gpu} GPU, a {cpu} CPU, a CPU utilization of {cpu_util}, a GPU utilization of {gpu_util}. The "
                "social cost of carbon uses models from \\citep{{ricke2018country}} and this statement and carbon "
                "emissions information was generated using the \emph{{get-rough-emissions-estimate}} script of the "
                "\\emph{{experiment-impact-tracker}}\\citep{{henderson2019climate}}"
                ".\n\n{}\n\n{}".format(
                    kg_carbon, kWh, ISO3_COUNTRY_CODE, median_carbon_cost, lower_carbon_cost, upper_carbon_cost,
                    bibtex_nature, bibtex_experiment_impact_tracker, location=self.location, zone_name=self.zone_name,
                    gpu=self.gpu, cpu=self.cpu,
                    runtime=self.experiment_length_seconds / 60 / 60, cpu_util=self.cpu_utilization_factor,
                    gpu_util=self.gpu_utilization_factor, carbon_intensity=carbonIntensity,
                    carbonIntensity_source=carbonIntensity_source)
            )

        if median_carbon_cost < 0 or lower_carbon_cost < 0 or upper_carbon_cost < 0:
                statement += (
                    "Note: the Canada-specific social cost of carbon is negative in this case as explained by \citet{{ricke2018country}}: "
                    "``The CSCC captures the amount of marginal damage (or, if negative, the benefit) expected to occurin an individual country "
                    "as a consequence of additional CO2 emission... Northern Europe, Canada and the Former Soviet Union have negative CSCC values "
                    "because their current temperatures are below the economic optimum.''")
        self.statement = statement

    @property
    def carbon_impact_statement(self):
        return self.statement

    @classmethod
    def get_available_gpus(self):
        return gpu_data["name"].tolist()

    @classmethod
    def get_available_cpus(self):
        return cpu_data["Model"].tolist()