import pkg_resources

def get_python_packages_and_versions():
    return list(pkg_resources.working_set)