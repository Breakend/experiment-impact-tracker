import os.path
import pandas as pd
import datetime
import matplotlib.pyplot as plt
import random
import string
import seaborn as sns
from experiment_impact_tracker.data_utils import load_data_into_frame

SMALL_SIZE = 22
MEDIUM_SIZE = 24
BIGGER_SIZE = 26

plt.rc('font', size=SMALL_SIZE)          # controls default text sizes
plt.rc('axes', titlesize=MEDIUM_SIZE)     # fontsize of the axes title
plt.rc('axes', labelsize=MEDIUM_SIZE)    # fontsize of the x and y labels
plt.rc('xtick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
plt.rc('ytick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
plt.rc('legend', fontsize=MEDIUM_SIZE)    # legend fontsize
plt.rc('figure', titlesize=BIGGER_SIZE)  # fontsize of the figure title

# def random_suffix(length=4):
#     letters = string.ascii_lowercase
#     return ''.join(random.choice(letters) for i in range(stringLength))

def dateparse (time_in_secs):    
    return datetime.datetime.fromtimestamp(float(time_in_secs))

# def clean(x): #2.9066 GHz
#     x = x.replace(" GHz", "")
#     return float(x)

def handle_cpu_count_adjusted_average_load(df):
    separated_df = pd.DataFrame(df['cpu_count_adjusted_average_load'].values.tolist())
    separated_df.columns = ['5_min_cpu_count_adjusted_average_load', '10_min_cpu_count_adjusted_average_load', '15_min_cpu_count_adjusted_average_load']

    return pd.concat([separated_df, df], axis=1)


# HZ_ACTUAL_COL = 'hz_actual'
ADJUSTED_AVERAGE_LOAD = "cpu_count_adjusted_average_load"
TIMESTAMP_COL = 'timestamp'

SKIP_COLUMN = ['timestamp', 'per_gpu_performance_state']

# TODO move per_gpu_performance_state to special handler
SPECIAL_COLUMN = [ADJUSTED_AVERAGE_LOAD]

HANDLER_MAP = {ADJUSTED_AVERAGE_LOAD : handle_cpu_count_adjusted_average_load}


def create_graphs(input_path: str, output_path: str ='.', fig_x:int = 16, fig_y: int = 8, max_level=None):
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    # create graph dirs
    graph_dir = str(fig_x) + '_' + str(fig_y)
    out_dir = os.path.join(output_path, graph_dir)
    # if os.path.exists(out_dir):
    #     print("{} already exists, attaching random string to the out put dir and moving on.".format(out_dir))
    #     out_dir = out_dir + '_' + random_suffix()

    os.makedirs(out_dir, exist_ok=True)
    df, json_raw = load_data_into_frame(input_path, max_level=max_level)
    # df = pd.read_csv(os.path.join(input_path, csv), sep=',', parse_dates=[0], date_parser=dateparse)
    created_paths = []
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    print("Plotting {}".format(",".join([k for k in list(df)[1:]])))

    # Do a pass for any pre-processing
    for k in list(df)[:]:
        if k in SPECIAL_COLUMN:
            df = HANDLER_MAP[k](df)
    
    # Then graph everything
    for k in list(df)[:]:
        if k in SKIP_COLUMN:
            continue
        try:
            df.plot(kind='line', x=TIMESTAMP_COL, y=k, figsize=(25, 8))
        except:
            print("problem plotting {}, skipping".format(k))
            continue

        path_name = os.path.join(out_dir, k+'.png')
        plt.savefig(path_name)
        plt.close('all')
        created_paths.append(path_name)
    return created_paths


def create_scatterplot_from_df(df, x: str, y: str, output_path: str ='.', fig_x:int = 16, fig_y: int = 8):
    """Loads an executive summary df and creates a scatterplot from some pre-specified variables.
    
    Args:
        df ([type]): [description]
        x (str): [description]
        y (str): [description]
        output_path (str, optional): [description]. Defaults to '.'.
        fig_x (int, optional): [description]. Defaults to 16.
        fig_y (int, optional): [description]. Defaults to 8.
    """
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    # create graph dirs
    graph_dir = str(fig_x) + '_' + str(fig_y)
    out_dir = os.path.join(output_path, graph_dir)
    df[x] = df[x].astype(float)
    df[y] = df[y].astype(float)
    os.makedirs(out_dir, exist_ok=True)
    a4_dims = (14, 9)
    fig, ax = plt.subplots(figsize=a4_dims)
    graph = sns.scatterplot(ax=ax, x=x, y=y, data=df, s=325,  alpha=.5, hue='Experiment', legend='brief')#, palette="Set1")
    box = ax.get_position()
    plt.legend(markerscale=2)
    # ax.set_position([box.x0,box.y0,box.width*0.83,box.height])
    # plt.legend(loc='upper left',bbox_to_anchor=(1,1.15))
    # plt.ylim(bottom=0.0)

    # plt.legend(loc='lower right')
    #Use regplot to plot the regression line for the whole points
    # sns.regplot(x="FPOs", y=args.y_axis_var, data=df, sizes=(250, 500),  alpha=.5, scatter=False, ax=graph.axes[2])
    path_name = os.path.join(out_dir, '{}v{}.png'.format(x,y))
    plt.savefig(path_name)
    plt.close('all')
    return path_name