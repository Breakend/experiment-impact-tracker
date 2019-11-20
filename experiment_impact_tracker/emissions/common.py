import experiment_impact_tracker.emissions.us_ca_parser as us_ca_parser
import numpy

REALTIME_REGIONS = {
    "US-CA" : us_ca_parser
}

def is_capable_realtime_carbon_intensity(*args, region=None, **kwargs):
    return region in list(REALTIME_REGIONS.keys())
    
def get_realtime_carbon_source(region):
    return REALTIME_REGIONS[region].get_realtime_carbon_source()

def get_realtime_carbon(*args, **kwargs):
    if 'region' not in kwargs:
        raise ValueError("region was not passed to function")
    try:
        carbon_intensity = REALTIME_REGIONS[kwargs['region']].fetch_supply()[0]['carbon_intensity']
        if numpy.isnan(carbon_intensity):
            return {
                "realtime_carbon_intensity" : "n/a"
            }
    except:
        return {
            "realtime_carbon_intensity" : "n/a"
        }

    return {
        "realtime_carbon_intensity" : carbon_intensity 
    }
