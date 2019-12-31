How to Contribute A New Metric
=======================================================


To contribute a new metric, you create a function call which gets the metric and returns a dictionary of style:

.. code-block:: python
def my_func():
    return {
        "metric_name" : metric_value
    }

Then you add the metric to our data router: https://github.com/Breakend/experiment-impact-tracker/blob/master/experiment_impact_tracker/data_info_and_router.py

.. code-block:: python

    {
        "name": "metric_name",
        "description": "This is a description of what my metric is. It uses <units>.",
        "compatability": [_function_to_call], # this is the compatability functions to call to make sure the system can use this metric
        "routing": {
            "function": path.to.metric.function
        }
    },

If a new compatability is introduced, add it here: https://github.com/Breakend/experiment-impact-tracker/blob/master/experiment_impact_tracker/compute_tracker.py#L131

If the system is compatible, your metric should now be logged at every iteration of the main logging loop!
