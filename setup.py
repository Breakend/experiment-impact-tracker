import sys
import subprocess
from setuptools import setup, find_packages
from distutils.version import LooseVersion


from distutils.util import convert_path

main_ns = {}
ver_path = convert_path('experiment_impact_tracker/version.py')
with open(ver_path) as ver_file:
    exec(ver_file.read(), main_ns)

if sys.version_info.major != 3:
    print('This Python is only compatible with Python 3, but you are running '
          'Python {}. The installation will likely fail.'.format(sys.version_info.major))

setup(name='experiment_impact_tracker',
      packages= find_packages(),
      include_package_data=True,
      scripts=['scripts/create-compute-appendix','scripts/get-region-emissions-info', 'scripts/lookup-cloud-region-info', 'scripts/generate-carbon-impact-statement'],
      install_requires=[
          'requests',
          'bs4',
          'shapely',
          'scipy',
          'joblib',
          'numpy',
          'pandas>0.25.0',
          'matplotlib',
          'py-cpuinfo',
          'pylatex',
          'ujson',
          'geocoder',
          'deepdiff',
          'arrow',
          'bootstrapped',
          'jinja2',
          'geopy',
          'progiter', # tqdm doesn't play well with multi-threading
                      # and can lead to deadlocks. progiter is single threaded
                      # so we used it instead in this package
          'psutil',
          'seaborn'
      ], 
      extras_require={
        'tests': [
            'pytest==3.5.1',
            'pytest-cov',
            'pytest-env',
            'pytest-xdist',
        ],
        'docs': [
            'sphinx',
            'sphinx-autobuild',
            'sphinx-rtd-theme',
            'recommonmark'
        ]
      },
      description='A toolkit for tracking energy, carbon, and compute metrics for machine learning (or any other) experiments.',
      author='Peter Henderson',
      url='https://github.com/Breakend/experiment-impact-tracker',
      keywords=["machine learning", "carbon", "energy", "compute"],
      download_url="https://github.com/Breakend/experiment-impact-tracker/archive/0.1.3.tar.gz",
      license="MIT",
      version=main_ns['__version__'],
        classifiers=[
    'Development Status :: 3 - Alpha',      # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
    'Intended Audience :: Developers',      # Define that your audience are developers
    'Topic :: Software Development :: Build Tools',
    'License :: OSI Approved :: MIT License',   # Again, pick a license
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
  ]
      )

# python setup.py sdist
# python setup.py bdist_wheel
# twine upload --repository-url https://test.pypi.org/legacy/ dist/*
# twine upload dist/*
