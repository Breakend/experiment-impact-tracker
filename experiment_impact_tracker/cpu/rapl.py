import os
import os.path
import re
from datetime import datetime

UJOULES = 1
JOULES = 2
WATT_HOURS = 3


def _read_sysfs_file(path):
    with open(path, "r") as f:
        contents = f.read().strip()
        return contents


def _get_domain_info(path):
    name = _read_sysfs_file("%s/name" % path)
    energy_uj = int(_read_sysfs_file("%s/energy_uj" % path))
    max_energy_range_uj = int(_read_sysfs_file(
        "%s/max_energy_range_uj" % path))

    return name, energy_uj, max_energy_range_uj


def _is_rapl_compatible(*args, **kwargs):
    # TODO: for future methods can add an if-else statement here for different rapl variations
    return os.path.exists("/sys/class/powercap/intel-rapl")


def _walk_rapl_dir(path):
    if not os.path.exists(path):
        raise ValueError("No RAPL directory exists to read from, RAPL CPU power readings may not be supported on this machine. If you discover a way to read rapl readings, please submit a pull request to update compatibility for your system!")
    regex = re.compile("intel-rapl")

    for dirpath, dirnames, filenames in os.walk(path, topdown=True):
        for d in dirnames:
            if not regex.search(d):
                dirnames.remove(d)
        yield dirpath, dirnames, filenames


class RAPLDomain(object):

    @classmethod
    def construct(cls, id, path):
        name, energy_uj, max_energy_range_uj = _get_domain_info(path)

        domain = RAPLDomain()
        domain.name = name
        domain.id = id
        domain.values = {}
        domain.values["energy_uj"] = energy_uj
        domain.max_values = {}
        domain.max_values["energy_uj"] = max_energy_range_uj
        domain.subdomains = {}
        domain.parent = None

        return domain

    def is_subdomain(self):
        splits = self.id.split(":")
        return len(splits) > 2

    def parent_id(self):
        splits = self.id.split(":")
        return ":".join(splits[0:2])

    # take the difference of two domain samples
    def __sub__(self, other):
        assert self.name == other.name and self.id == other.id

        domain = RAPLDomain()
        domain.name = self.name
        domain.id = self.id
        domain.values = {}
        for v in self.values:
            diff = self.values[v] - other.values[v]
            # if there was a rollover
            if diff < 0:
                diff = self.max_values[v] + diff
            domain.values[v] = diff

        domain.subdomains = {}
        domain.parent = None

        return domain

    def __str__(self):
        values = ""
        for v in self.values:
            values += " %s=%s" % (v, self.values[v])

        values = values.strip()

        return "%s: %s" % (self.name, values)

    def __repr__(self):
        return self.__str__()


class RAPLSample(object):

    @classmethod
    def take_sample(cls):
        sample = RAPLSample()
        sample.domains = {}
        sample.domains_by_id = {}
        sample.timestamp = datetime.now()

        for dirpath, dirnames, filenames in _walk_rapl_dir("/sys/class/powercap/intel-rapl"):
            current = dirpath.split("/")[-1]
            splits = current.split(":")

            # base of RAPL tree
            if len(splits) == 1:
                continue

            # package
            elif len(splits) >= 2:
                domain = RAPLDomain.construct(current, dirpath)
                # catalog all domains here
                sample.domains_by_id[domain.id] = domain
                sample._link_tree(domain)

        return sample

    def _link_tree(self, domain):
        if domain.is_subdomain():
            parent = self.domains_by_id[domain.parent_id()]
            parent.subdomains[domain.name] = domain
        else:
            self.domains[domain.name] = domain

    def __sub__(self, other):
        diff = RAPLDifference()
        diff.domains = {}
        diff.domains_by_id = {}
        diff.duration = (self.timestamp - other.timestamp).total_seconds()

        for id in self.domains_by_id:
            assert id in other.domains_by_id

        for id in self.domains_by_id:
            selfDomain = self.domains_by_id[id]
            otherDomain = other.domains_by_id[id]
            diffDomain = selfDomain - otherDomain

            diff.domains_by_id[id] = diffDomain
            diff._link_tree(diffDomain)

        return diff

    def energy(self, package, domain=None, unit=UJOULES):
        if not domain:
            e = self.domains[package].values["energy_uj"]
        else:
            e = self.domains[package].subdomains[domain].values["energy_uj"]

        if unit == UJOULES:
            return e
        elif unit == JOULES:
            return e / 1000000
        elif unit == WATT_HOURS:
            return e / (1000000*3600)


class RAPLDifference(RAPLSample):
    def average_power(self, package, domain=None):
        return self.energy(package, domain, unit=JOULES) / self.duration


class RAPLMonitor(object):
    @classmethod
    def sample(cls):
        return RAPLSample.take_sample()
