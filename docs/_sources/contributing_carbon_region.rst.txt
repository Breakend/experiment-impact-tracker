How to Contribute A New Carbon Region
=======================================================


Let's say we have a new region called Narnia that we wish to add carbon intensities for. Let's first create a geojson which encloses Narnia on a map:

.. code-block:: javascript

    {
        "type": "Feature",
        "properties": {
                        "zoneName": "ABC"},
                        "id": "ABC"
                        },
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
            [
                -17.138671875,
                67.2720426739952
            ],
            [
                -27.7294921875,
                66.31986144668052
            ],
            [
                -22.060546874999996,
                61.91827102335593
            ],
            [
                -10.37109375,
                65.5129625532949
            ],
            [
                -17.0068359375,
                67.35678538806071
            ]
            ]
        }
        }
    ]
    }

We add this as a line to https://github.com/Breakend/experiment-impact-tracker/blob/master/experiment_impact_tracker/data/zonegeometries.json

Then we add the zone ID-Name mapping: https://github.com/Breakend/experiment-impact-tracker/blob/master/experiment_impact_tracker/data/zone_names.json

.. code-block:: javascript

    "ABC": {
        "zoneName": "Narnia"
      }

Finally, we add average emissions information here: https://github.com/Breakend/experiment-impact-tracker/blob/master/experiment_impact_tracker/data/co2eq_parameters.json

.. code-block:: javascript

    "ABC": {
      "_source": "Narnia Bureau of Energy: narnia.gov/carbon",
      "carbonIntensity": 1.2814555481099,
      "fossilFuelRatio": 0.00,
      "renewableRatio": 100.0
    },

If we have realtime carbon emissions we can get from the narnia.gov site, we can add a parser and add it to our realtime carbon routing system: https://github.com/Breakend/experiment-impact-tracker/blob/bf8feba89a0dfc547d6468227e69207f4c5f6bdb/experiment_impact_tracker/emissions/common.py#L1-L6

.. code-block:: python

    import experiment_impact_tracker.emissions.us_ca_parser as us_ca_parser
    import experiment_impact_tracker.emissions.narnia_parser as narnia_parser
    import numpy

    REALTIME_REGIONS = {
        "US-CA" : us_ca_parser,
        "ABC" : narnia_parser
    }

See https://github.com/Breakend/experiment-impact-tracker/blob/master/experiment_impact_tracker/emissions/us_ca_parser.py for an example of a parser