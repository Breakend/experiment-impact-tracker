# experiment-impact-tracker

## Compatible Systems

Right now, we're only compatible with Linux systems running NVIDIA GPU's and Intel processors (which support RAPL). 

If you'd like support for your use-case or encounter missing/broken functionality on your system specs, please open an issue or better yet submit a pull request! It's almost impossible to cover every combination on our own!

### Test Successfully

GPUs:
+ NVIDIA Titan X
+ NVIDIA Titan V

CPUs:
+ Intel(R) Xeon(R) CPU E5-2640 v3 @ 2.60GHz
+ Intel(R) Xeon(R) CPU E5-2620 v3 @ 2.40GHz

OS:
+ Ubuntu 16.04.5 LTS

## Installation

To install:

```bash
git clone https://github.com/Breakend/experiment-impact-tracker.git
cd experiment-impact-tracker
pip install -e .
```

## Usage

Please go to the docs page for detailed info on the design, usage, and contributing: https://breakend.github.io/experiment-impact-tracker/ 

Below are some short snippets that might help.

### Tracking
You just need to add a few lines of code!

```python
from experiment_impact_tracker.compute_tracker import ImpactTracker
tracker = ImpactTracker(<your log directory here>)
tracker.launch_impact_monitor()
```

This will launch a separate process (more like thread) that will gather compute/energy/carbon information in the background.

**NOTE: Because of the way python multiprocessing works, this process will not interrupt the main one UNLESS you periodically call the following. This will read the latest info from the log file and check for any errors that might've occured in the tracking process. If you have a better idea on how to handle exceptions in the tracking thread please open an issue or submit a pull request!!!** 

```python
info = tracker.get_latest_info_and_check_for_errors()
```

### Asserting certain hardware

It may be the case that you're trying to run two sets of experiments and compare emissions/energy/etc. In this case, you generally want to ensure that there's parity between the two sets of experiments. If you're running on a cluster you might not want to accidentally use a different GPU/CPU pair. To get around this we provided an assertion check that you can add to your code that will kill a job if it's running on a wrong hardware combo. For example:

```python
assert_gpus_by_attributes({ "name" : "GeForce GTX TITAN X"})
assert_cpus_by_attributes({ "brand": "Intel(R) Xeon(R) CPU E5-2640 v3 @ 2.60GHz" })
```

### Generating an HTML appendix

After putting all your experments into a folder, we can automatically search for the impact tracker's logs and generate an HTML appendix using the command like below:

```bash
create-compute-appendix ./data/ --site_spec leaderboard_generation_format.json --output_dir ./site/
```

To see this in action, take a look at our RL Energy Leaderboard: https://github.com/Breakend/RL-Energy-Leaderboard

## Building docs

```bash
sphinx-build -b html docsrc docs
```

## Citation

If you use this work, please cite our paper:

```
TODO
```


