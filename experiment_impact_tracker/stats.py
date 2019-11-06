import numpy as np
from scipy.stats import ttest_ind, mannwhitneyu, rankdata, median_test
import bootstrapped.bootstrap as bs
import bootstrapped.compare_functions as bs_compare
import bootstrapped.stats_functions as bs_stats

tests_list = ['t-test', "Welch t-test", 'Mann-Whitney', 'Ranked t-test', 'bootstrap', 'permutation']


def run_permutation_test(all_data, n1, n2):
    np.random.shuffle(all_data)
    data_a = all_data[:n1]
    data_b = all_data[-n2:]
    return data_a.mean() - data_b.mean()


def get_average_treatment_effect(data1, data2):
    delta = np.mean(data1) - np.mean(data2)
    delta_err = 1.96 * np.sqrt(np.var(data1) / len(data1) + \
        np.var(data2) / len(data2))
    return delta, delta_err


def run_test(test_id, data1, data2, alpha=0.05):
    """
    Compute tests comparing data1 and data2 with confidence level alpha

    Taken from: https://arxiv.org/abs/1904.06979
    Please cite that work if using this function.


    :param test_id: (str) refers to what test should be used
    :param data1: (np.ndarray) sample 1
    :param data2: (np.ndarray) sample 2
    :param alpha: (float) confidence level of the test
    :return: (bool) if True, the null hypothesis is rejected
    """
    data1 = np.array(data1)
    data2 = np.array(data2)
    data1 = data1.squeeze()
    data2 = data2.squeeze()
    n1 = data1.size
    n2 = data2.size

    if test_id == 'bootstrap':
        assert alpha < 1 and alpha > 0, "alpha should be between 0 and 1"
        res = bs.bootstrap_ab(data1, data2, bs_stats.mean, bs_compare.difference, alpha=alpha, num_iterations=1000)
        rejection = np.sign(res.upper_bound) == np.sign(res.lower_bound)
        return rejection, res

    elif test_id == 't-test':
        _, p = ttest_ind(data1, data2, equal_var=True)
        return p < alpha, p

    elif test_id == "Welch t-test":
        _, p = ttest_ind(data1, data2, equal_var=False)
        return p < alpha, p

    elif test_id == 'Mann-Whitney':
        _, p = mannwhitneyu(data1, data2, alternative='two-sided')
        return p < alpha, p

    elif test_id == 'Ranked t-test':
        all_data = np.concatenate([data1.copy(), data2.copy()], axis=0)
        ranks = rankdata(all_data)
        ranks1 = ranks[: n1]
        ranks2 = ranks[n1:n1 + n2]
        assert ranks2.size == n2
        _, p = ttest_ind(ranks1, ranks2, equal_var=True)
        return p < alpha, p

    elif test_id == 'permutation':
        all_data = np.concatenate([data1.copy(), data2.copy()], axis=0)
        delta = np.abs(data1.mean() - data2.mean())
        num_samples = 1000
        estimates = []
        for _ in range(num_samples):
            estimates.append(run_permutation_test(all_data.copy(), n1, n2))
        estimates = np.abs(np.array(estimates))
        diff_count = len(np.where(estimates <= delta)[0])
        return (1.0 - (float(diff_count) / float(num_samples))) < alpha, (1.0 - (float(diff_count) / float(num_samples)))

    else:
        raise NotImplementedError

