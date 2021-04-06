import time
from functools import lru_cache

from shapely.geometry import Point

from .constants import REGIONS_WITH_BOUNDING_BOXES, ZONE_INFO, ZONE_NAMES


def get_zone_information_by_coords(coords):
    region = get_region_by_coords(coords)
    return region, ZONE_INFO[region["id"]]


def get_region_by_coords(coords):
    # TODO: automatically narrow down possibilities
    lat, lon = coords
    point = Point(lon, lat)
    zone_possibilities = []
    for zone in REGIONS_WITH_BOUNDING_BOXES:
        try:
            if zone["geometry"].contains(point):
                zone_possibilities.append(zone)
        except:
            import pdb

            pdb.set_trace()
    if len(zone_possibilities) == 0:
        raise ValueError("No possibilities found, may need to add a zone.")

    z = min(zone_possibilities, key=lambda x: x["geometry"].area)
    return z


def get_current_location():
    import geocoder

    g = geocoder.ip("me")
    return g.y, g.x


@lru_cache(maxsize=32)
def get_current_region_info(*args, **kwargs):
    return get_zone_information_by_coords(get_current_location())

### Added by nikhil153 to avoid error in get_current_region_info_cached on CC
def get_region_info(region_coords=None):
    ''' Wrapper func to grab zone info based on either specific lat-long coordinates or default current region
    '''
    print('Emissions region coords: {}'.format(region_coords))
    if region_coords == None:
        return get_current_region_info_cached()
    else:
        return get_zone_information_by_coords(region_coords)

def get_zone_name_by_id(zone_id):
    zone = ZONE_NAMES["zoneShortName"][zone_id]
    name = zone["zoneName"]
    if "countryName" in zone:
        name += ", {}".format(zone["countryName"])
    return name


def get_sorted_region_infos():
    zone_infos = [(key, value["carbonIntensity"]) for key, value in ZONE_INFO.items()]
    return sorted(zone_infos, key=lambda x: x[1])


def get_ttl_hash(seconds=3600):
    """Return the same value withing `seconds` time period"""
    return round(time.time() / seconds)


def get_current_region_info_cached():
    return get_current_region_info(ttl_hash=get_ttl_hash(seconds=60 * 60))
