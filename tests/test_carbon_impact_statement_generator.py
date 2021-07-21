from experiment_impact_tracker.emissions.rough_emissions_estimator import RoughEmissionsEstimator


def test_rough_emissoins_estimator():

    assert "GTX 1080 Ti" in RoughEmissionsEstimator.get_available_gpus()
    assert "Dual-core PowerPC MPC8641D" in RoughEmissionsEstimator.get_available_cpus()

    emissions_estimator = RoughEmissionsEstimator(gpu="GTX 1080 Ti",
                                                  cpu="PowerPC 750CXe",
                                                  gpu_utilization_factor=1.0,
                                                  cpu_utilization_factor=0.0,
                                                  location="Portland, Oregon",
                                                  experiment_length_seconds=12*60*60)
    assert emissions_estimator.kg_carbon == 0.381018
    assert emissions_estimator.cpu_kWh == 0.0
    assert emissions_estimator.gpu_kWh == 3

    assert "GTX 1080 Ti" in emissions_estimator.carbon_impact_statement
    assert "PowerPC 750CXe" in emissions_estimator.carbon_impact_statement