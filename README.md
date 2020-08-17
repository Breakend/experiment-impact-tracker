# experiment-impact-tracker

[![](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/images/0)](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/links/0)[![](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/images/1)](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/links/1)[![](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/images/2)](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/links/2)[![](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/images/3)](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/links/3)[![](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/images/4)](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/links/4)[![](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/images/5)](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/links/5)[![](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/images/6)](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/links/6)[![](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/images/7)](https://sourcerer.io/fame/asfhaslfuahsfliaufhs/Breakend/experiment-impact-tracker/links/7)

The experiment-impact-tracker is meant to be a simple drop-in method to track energy usage, carbon emissions, and compute utilization of your system. Currently, on Linux systems with Intel chips (that support the RAPL powercap interface) and NVIDIA GPUs, we record: power draw from CPU and GPU, hardware information, python package versions, estimated carbon emissions information, etc. In California we even support realtime carbon emission information by querying caiso.com!

Once all this information is logged, you can generate an online appendix which shows off this information like seen here:

https://breakend.github.io/RL-Energy-Leaderboard/reinforcement_learning_energy_leaderboard/pongnoframeskip-v4_experiments/ppo2_stable_baselines,_default_settings/0.html

## Installation

To install:

```bash
pip install experiment-impact-tracker
```

## Usage

Please go to the docs page for detailed info on the design, usage, and contributing: https://breakend.github.io/experiment-impact-tracker/ 

If you think the docs aren't helpful or need more expansion, let us know with a Github Issue!

Below we will walk through an example together.

### Add Tracking
We included a simple example in the project which can be found in ``examples/my_experiment.py``

As show in ``my_experiment.py``, you just need to add a few lines of code!

```python
from experiment_impact_tracker.compute_tracker import ImpactTracker
tracker = ImpactTracker(<your log directory here>)
tracker.launch_impact_monitor()
```

This will launch a separate python process that will gather compute/energy/carbon information in the background.

**NOTE: Because of the way python multiprocessing works, this process will not interrupt the main one even if the monitoring process errors out. To address this, you can add the following to periodically 
 read the latest info from the log file and check for any errors that might've occurred in the tracking process. 
 If you have a better idea on how to handle exceptions in the tracking thread please open an issue or submit a pull request!**

```python
info = tracker.get_latest_info_and_check_for_errors()
```

Alternatively, you can use context management!

```python
experiment1 = tempfile.mkdtemp()
experiment2 = tempfile.mkdtemp()

with ImpactTracker(experiment1):
    do_something()

with ImpactTracker(experiment2):
    do_something_else()
```

To kick off our simple experiment, run ``python my_experiment.py``. You will see our 
training starts and in the end the script will output something like ``Please find your experiment logs in: /var/folders/n_/9qzct77j68j6n9lh0lw3vjqcn96zxl/T/tmpcp7sfese`` 

Now let's go over to the temp dir, we can see our logging there!
```bash
$ log_path=/var/folders/n_/9qzct77j68j6n9lh0lw3vjqcn96zxl/T/tmpcp7sfese
$ cd $log_path
$ tree 
.
└── impacttracker
    ├── data.json
    ├── impact_tracker_log.log
    └── info.pkl
```

You can then access the information via the DataInterface:

```python
from experiment_impact_tracker.data_interface import DataInterface

data_interface1 = DataInterface([experiment1_logdir])
data_interface2 = DataInterface([experiment2_logdir])

data_interface_both = DataInterface([experiment1_logdir, experiment2_logdir])

assert data_interface1.kg_carbon + data_interface2.kg_carbon == data_interface_both.kg_carbon
assert data_interface1.total_power + data_interface2.total_power == data_interface_both.total_power
```

### Creating a carbon impact statement

We can also use a script to automatically generate a carbon impact statement for your paper! Just call this, we'll find all the logfiles generated by the tool and calculate emissions information! Specify your ISO3 country code as well to get a dollar amount based on the per-country cost of carbon.

```bash
generate-carbon-impact-statement my_directories that_contain all_my_experiments "USA"
```

#### Custom PUE

Some people may know the PUE of their data center, while we use a PUE of 1.58 in our calculations. To set a
 different PUE, do:
 
```bash
OVERRIDE_PUE=1.1 generate-carbon-impact-statement my_directories that_contain all_my_experiments "USA"
```


### Generating an HTML appendix

After logging all your experiments into a dir, we can automatically search for the impact tracker's 
logs and generate an HTML appendix.

First, create a json file with the structure of the website you'd like to see 
(this lets you create hierarchies of experiment as web pages).

For an example of all the capabilities of the tool you can see the json structure 
here: https://github.com/Breakend/RL-Energy-Leaderboard/blob/master/leaderboard_generation_format.json


Basically, you can group several runs together and specify variables to summarize. You should probably just copypaste the example above and remove what you don't need, but here are some descriptions of what is being specified:

```javascript
"Comparing Translation Methods" : {
  # FILTER: this regex we use to look through the directory 
  # you specify and find experiments with this in the directory structure,
  "filter" : "(translation)", 
 
  # Use this to talk about your experiment
  "description" : "An experiment on translation.", 
  
  # executive_summary_variables: this will aggregate the sums and averages across these metrics.
  # you can see available metrics to summarize here: 
  # https://github.com/Breakend/experiment-impact-tracker/blob/master/experiment_impact_tracker/data_info_and_router.py
  "executive_summary_variables" : ["total_power", "exp_len_hours", "cpu_hours", "gpu_hours", "estimated_carbon_impact_kg"],   
  
  # The child experiments to group together
  "child_experiments" : 
        {
            "Transformer Network" : {
                                "filter" : "(transformer)",
                                "description" : "A subset of experiments for transformer experiments"
                            },
            "Conv Network" : {
                                "filter" : "(conv)",
                                "description" : "A subset of experiments for conv experiments"
                            }
                   
        }
}
```

Then you just run this script, pointing to your data, the json file and an output directory. 

```bash
create-compute-appendix ./data/ --site_spec leaderboard_generation_format.json --output_dir ./site/
```

To see this in action, take a look at our RL Energy Leaderboard. 

The specs are here: https://github.com/Breakend/RL-Energy-Leaderboard

And the output looks like this: https://breakend.github.io/RL-Energy-Leaderboard/reinforcement_learning_energy_leaderboard/


### Looking up cloud provider emission info

Based on energy grid locations, we can estimate emission from cloud providers using our tools. A script to do that is here:

```bash
lookup-cloud-region-info aws
```

### Or you can look up emissions information for your own address!

```bash

% get-region-emissions-info address --address "Stanford, California"

({'geometry': <shapely.geometry.multipolygon.MultiPolygon object at 0x1194c3b38>,
  'id': 'US-CA',
  'properties': {'zoneName': 'US-CA'},
  'type': 'Feature'},
 {'_source': 'https://github.com/tmrowco/electricitymap-contrib/blob/master/config/co2eq_parameters.json '
             '(ElectricityMap Average, 2019)',
  'carbonIntensity': 250.73337617853463,
  'fossilFuelRatio': 0.48888711737336304,
  'renewableRatio': 0.428373256377554})
  
  ```

### Asserting certain hardware

It may be the case that you're trying to run two sets of experiments and compare emissions/energy/etc. In this case, you generally want to ensure that there's parity between the two sets of experiments. If you're running on a cluster you might not want to accidentally use a different GPU/CPU pair. To get around this we provided an assertion check that you can add to your code that will kill a job if it's running on a wrong hardware combo. For example:

```python
from experiment_impact_tracker.gpu.nvidia import assert_gpus_by_attributes
from experiment_impact_tracker.cpu.common import assert_cpus_by_attributes

assert_gpus_by_attributes({ "name" : "GeForce GTX TITAN X"})
assert_cpus_by_attributes({ "brand": "Intel(R) Xeon(R) CPU E5-2640 v3 @ 2.60GHz" })
```

## Building docs

```bash
sphinx-build -b html docsrc docs
```

## Compatible Systems

Right now, we're only compatible with Linux and Mac OS X systems running NVIDIA GPU's and Intel processors (which
 support RAPL or PowerCap). 

If you'd like support for your use-case or encounter missing/broken functionality on your system specs, please open an issue or better yet submit a pull request! It's almost impossible to cover every combination on our own!

### Mac OS X Suppport

Currently, we support only CPU and memory-related metrics on Mac OS X for Intel-based CPUs. However, these require the
 Intel PowerCap driver and the Intel PowerGadget tool. The easiest way to install this is:
 
```bash
$ brew cask install intel-power-gadget
$ which "/Applications/Intel Power Gadget/PowerLog"
```

You can also see here: https://software.intel.com/content/www/us/en/develop/articles/intel-power-gadget.html

This will install a tool called PowerLog that we rely on to get power measurements on Mac OS X systems.

### Tested Successfully On

GPUs:
+ NVIDIA Titan X
+ NVIDIA Titan V

CPUs:
+ Intel(R) Xeon(R) CPU E5-2640 v3 @ 2.60GHz
+ Intel(R) Xeon(R) CPU E5-2620 v3 @ 2.40GHz
+ 2.7 GHz Quad-Core Intel Core i7

OS:
+ Ubuntu 16.04.5 LTS
+ Mac OS X 10.15.6 

## Testing

To test, run:

```bash
pytest 
```

## Citation

If you use this work, please cite our paper:

```
@misc{henderson2020systematic,
    title={Towards the Systematic Reporting of the Energy and Carbon Footprints of Machine Learning},
    author={Peter Henderson and Jieru Hu and Joshua Romoff and Emma Brunskill and Dan Jurafsky and Joelle Pineau},
    year={2020},
    eprint={2002.05651},
    archivePrefix={arXiv},
    primaryClass={cs.CY}
}
```

Also, we rely on a number of downstream packages and work to make this work possible. For carbon accounting, we relied on open source code from https://www.electricitymap.org/ as an initial base. psutil provides many of the compute metrics we use. nvidia-smi and Intel RAPL provide energy metrics. 

