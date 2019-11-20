import os

import numpy as np
from progiter import ProgIter

import ujson as json
from shapely.geometry import shape


def read_terrible_json(path):
    """ Reads a slightly malformed json file 
    where each line is a different json dict.
    
    Args:
        path (string): the filepath to read from
    
    Returns:
        [dict]: list of dictionaries
    """
    with open(path, 'rt') as f:
        lines = []
        test_read_lines = [x for x in f.readlines()]
        for x in ProgIter(test_read_lines):
            if x:
                x = x.replace("/", "\/")
                x = json.loads(x)
                lines.append(x)
    return lines


def _load_zone_info():
    """Loads zone information from the json file in the package.
    
    Returns:
        dict : the loaded json file
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(dir_path, 'data/co2eq_parameters.json'), 'rt') as f:
        x = json.load(f)
    return x

def _load_zone_names():
    """Loads zone name info from the json file in the package.
    
    Returns:
        dict : the loaded json file
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(dir_path, 'data/zone_names.json'), 'rt') as f:
        x = json.load(f)
    return x


def load_regions_with_bounding_boxes():
    """Loads bounding boxes as shapely objects.
    
    Returns:
        list: list of shapely objects containing regional geometries
    """
    print("loading region bounding boxes for computing carbon emissions region, this may take a moment...")

    dir_path = os.path.dirname(os.path.realpath(__file__))
    all_geoms = []
    # with open('data/zone_geometries.json') as f:
    all_geoms = read_terrible_json(os.path.join(
        dir_path, 'data/zonegeometries.json'))

    for i, geom in enumerate(all_geoms):
        all_geoms[i]["geometry"] = shape(geom["geometry"])
    print("Done!")
    return all_geoms


PUE = 1.58
REGIONS_WITH_BOUNDING_BOXES = load_regions_with_bounding_boxes()
ZONE_INFO = _load_zone_info()["fallbackZoneMixes"]
ZONE_NAMES = _load_zone_names()
