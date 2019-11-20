from sys import platform


def is_linux(*args, **kwargs):
    return (platform == "linux" or platform == "linux2")