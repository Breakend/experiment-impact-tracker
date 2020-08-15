# coding: utf-8
# Scrapes wikipedia page for TDP of different cpus

import pandas as pd

url = "https://en.wikipedia.org/wiki/List_of_CPU_power_dissipation_figures"

df = pd.read_html(url)

power_dfs = [
    x
    for x in df
    if "Thermal Design Power" in x.columns or "TDP" in x.columns or "Power" in x.columns
]

for x in power_dfs:
    x.rename(columns={"Thermal Design Power": "TDP"}, inplace=True)
    x.rename(columns={"Power": "TDP"}, inplace=True)

power_dfs = [x.filter(["Model", "TDP"]) for x in power_dfs]

pd.concat(power_dfs).drop_duplicates("Model").reset_index().to_csv("cpu_tdp.csv")
