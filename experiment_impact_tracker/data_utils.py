import pickle
import ujson as json
from pandas.io.json import json_normalize
from datetime import datetime
import os
import zipfile
import csv

BASE_LOG_PATH = 'impacttracker/'
DATAPATH = BASE_LOG_PATH + 'data.json'
INFOPATH = BASE_LOG_PATH + 'info.pkl'

def load_initial_info(log_dir):
    info_path = safe_file_path(os.path.join(log_dir, INFOPATH))
    with open(info_path, 'rb') as info_file:
        return pickle.load(info_file)

def _read_json_file(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
        return [json.loads(line) for line in lines]

def load_data_into_frame(log_dir, max_level=None):
    data_path = safe_file_path(os.path.join(log_dir, DATAPATH))
    json_array = _read_json_file(data_path)
    return json_normalize(json_array, max_level=max_level), json_array

def log_final_info(log_dir):
    final_time = datetime.now()
    info = load_initial_info(log_dir)
    info["experiment_end"] = final_time
    info_path = safe_file_path(os.path.join(log_dir, INFOPATH))

    with open(info_path, 'wb') as info_file:
        pickle.dump(info, info_file)

def safe_file_path(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)
    return file_path

def write_csv_data_to_file(file_path, data, overwrite=False):
    file_path = safe_file_path(file_path)
    with open(file_path, 'w' if overwrite else 'a') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(data)

def write_json_data_to_file(file_path, data, overwrite=False):
    file_path = safe_file_path(file_path)
    with open(file_path, 'w' if overwrite else 'a') as outfile:
        outfile.write(json.dumps(data) + "\n")

def zip_data_and_info(log_dir, zip_path):
    info_path = safe_file_path(os.path.join(log_dir, INFOPATH))
    data_path = safe_file_path(os.path.join(log_dir, DATAPATH))
    zip_files([info_path, data_path], zip_path)
    return zip_path

def zip_files(src, dst, arcname=None):
    """ Compress a list of files to a given zip 
    
    From https://stackoverflow.com/questions/16809328/zipfile-write-relative-path-of-files-reproduced-in-the-zip-archive
    
    Args:
        @src: Iterable object containing one or more element
        @dst: filename (path/filename if needed)
        @arcname: Iterable object containing the names we want to give to the elements in the archive (has to correspond to src) 
    """
    zip_ = zipfile.ZipFile(dst, 'w')

    for i in range(len(src)):
        if arcname is None:
            zip_.write(src[i], os.path.basename(src[i]), compress_type = zipfile.ZIP_DEFLATED)
        else:
            zip_.write(src[i], arcname[i], compress_type = zipfile.ZIP_DEFLATED)

    zip_.close()