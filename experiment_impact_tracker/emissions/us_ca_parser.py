#!/usr/bin/env python3

import arrow
import pandas
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from functools import lru_cache
import time

FUEL_SOURCE_CSV = 'http://www.caiso.com/outlook/SP/History/{}/fuelsource.csv'

CARBON_INTENSITY_CSV = 'http://www.caiso.com/outlook/SP/History/{}/co2.csv'

def get_realtime_carbon_source():
    return CARBON_INTENSITY_CSV.format("<date>")

def get_ttl_hash(seconds=3600):
    """Return the same value withing `seconds` time period"""
    return round(time.time() / seconds)

def fetch_supply(*args, **kwargs):
    # Only query every 5 minutes since that's when the values are updated anyways
    # See example https://stackoverflow.com/questions/31771286/python-in-memory-cache-with-time-to-live
    return _fetch_supply(**kwargs, ttl_hash=get_ttl_hash(seconds=5*60))

@lru_cache(maxsize=32)
def _fetch_supply(target_datetime=None, latest_only=True, ttl_hash=None, **kwargs):
    """Requests the last known supply mix (in MW) of a given country
    Arguments:
    zone_key: used in case a parser is able to fetch multiple countries
    session: request session passed in order to re-use an existing session
    Return:
    A dictionary in the form:
    {
      'zoneKey': 'FR',
      'datetime': '2017-01-01T00:00:00Z',
      'supply': {
          'biomass': 0.0,
          'coal': 0.0,
          'gas': 0.0,
          'hydro': 0.0,
          'nuclear': null,
          'oil': 0.0,
          'solar': 0.0,
          'wind': 0.0,
          'geothermal': 0.0,
          'unknown': 0.0
      },
      'storage': {
          'hydro': -10.0,
      },
      'source': 'mysource.com'
    }
    """
    del ttl_hash # make sure this isn't actually used, also stop pylint errors
    # target_datetime = arrow.get(target_datetime)
    target_date = arrow.get(target_datetime).to('US/Pacific').replace(
        hour=0, minute=0, second=0, microsecond=0)
    
    formatted = target_date.format('YYYYMMDD')
    zone_key='US-CA'
    # Get the supply from the CSV
    fuel_source_csv = pandas.read_csv(FUEL_SOURCE_CSV.format(formatted))
    carbon_intensity_csv = pandas.read_csv(CARBON_INTENSITY_CSV.format(formatted))


    # there may be a timing issue where the carbon intensity csv will have one added time than the other, in this case truncate the carbon_intensity_csv
    if len(carbon_intensity_csv) > len(fuel_source_csv):
        carbon_intensity_csv = carbon_intensity_csv[:len(fuel_source_csv)]
    latest_index = len(carbon_intensity_csv) - 1

    supply_map = {
        'Solar': 'solar',
        'Wind': 'wind',
        'Geothermal': 'geothermal',
        'Biomass': 'biomass',
        'Biogas': 'biogas',
        'Small hydro': 'hydro',
        'Coal': 'coal',
        'Nuclear': 'nuclear',
        'Natural gas': 'gas',
        'Large hydro': 'hydro',
        'Imports' : 'imports',
        'Batteries' : 'battery',
        'Other': 'unknown'
    }

    co2_map = {
        'Biogas CO2' : 'biogas',
        'Biomass CO2' : 'biomass',
        'Natural Gas CO2' : 'gas',
        'Coal CO2' : 'coal',
        'Imports CO2' : 'imports',
        'Geothermal CO2' : 'geothermal'
    }


    daily_data = []
    if latest_only:
        start_index = latest_index
    else:
        start_index = 0

    for i in range(start_index, latest_index + 1):
        h, m = map(int, fuel_source_csv['Time'][i].split(':'))
        date = arrow.utcnow().to('US/Pacific').replace(hour=h, minute=m,
                                                       second=0, microsecond=0)
        data = {
            'zoneKey': zone_key,
            'supply': defaultdict(float),
            'carbon_intensity' :  defaultdict(float),
            'source': 'caiso.com',
            'datetime': date.datetime
        }

        # map items from names in CAISO CSV to names used in Electricity Map
        total_supply = 0.0
        for ca_gen_type, mapped_gen_type in supply_map.items():

            # ca reports in MW, but we standardize based on KW so multiply by 1000.0
            supply = float(fuel_source_csv[ca_gen_type][i]) * 1000.0

            # if another mean of supply created a value, sum them up
            data['supply'][mapped_gen_type] += supply
            total_supply += supply

        summed_carbon = 0.0
        for ca_gen_type, mapped_gen_type in co2_map.items():
            intensity = float(carbon_intensity_csv[ca_gen_type][i])
            summed_carbon += intensity

        summed_carbon_grams = 1000000 * summed_carbon
        # While CAISO says that carbon intensity is divided by demans, 
        # we can calculate carbon intensity from carbon divided by supply since this is 
        # what is being produced
        data['carbon_intensity'] = summed_carbon_grams / total_supply

        daily_data.append(data)

    return daily_data


