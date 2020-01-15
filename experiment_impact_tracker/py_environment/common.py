import pkg_resources
import copyreg
import zipimport

copyreg.pickle(zipimport.zipimporter, lambda x: (x.__class__, (x.archive, )))

def get_python_packages_and_versions(*args, **kwargs):
    return list(pkg_resources.working_set)