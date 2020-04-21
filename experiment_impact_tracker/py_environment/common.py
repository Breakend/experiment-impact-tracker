import copyreg
import zipimport

import pkg_resources

copyreg.pickle(zipimport.zipimporter, lambda x: (x.__class__, (x.archive,)))


def get_python_packages_and_versions(*args, **kwargs):
    return list(pkg_resources.working_set)
