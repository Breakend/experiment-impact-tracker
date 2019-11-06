# ClimateChangeFromMachineLearningResearch

## Compatible Systems

Right now, we're only compatible with Linux systems running NVIDIA GPU's and Intel processors (which support RAPL). If you'd like support for your use-case or encounter missing/broken functionality on your system specs, please open an issue or better yet submit a pull request! It's almost impossible to cover every combination on our own!

## Installation

To install:

```bash
cd ClimateChangeFromMachineLearningResearch;
pip install -e .
```

## Usage

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


Here's an example for us generating an appendix for all the pong experiments

```bash
python ./scripts/create_compute_appendix_html.py ./experiment_results/rl/ --experiment_set_names "ppo2 (stable_baselines)" "a2c (stable_baselines)" "dqn (stable_baselines)" "a2c+vtrace (cule)" --experiment_set_filters "ppo2" "a2c_Pong" "dqn" "vtrace_cule" --output_dir ./testhtml/ --title "PongNoFrameskip-v4 Experiments" --description "Evaluate on separate environments every 250k timesteps in parallel (see code for details), run for 5M timesteps (roughly 23.15 hrs of experience)."
```
