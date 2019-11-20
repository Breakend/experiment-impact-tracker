import pkg_resources

def get_python_packages_and_versions(*args, **kwargs):
    return list(pkg_resources.working_set)