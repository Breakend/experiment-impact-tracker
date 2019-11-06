""" Taken mostly from https://github.com/sanderjo/disk-speed/blob/master/diskspeed.py
"""
import time, os, sys
import uuid

def writetofile(filename, size_in_mb):
    # writes string to specified file repeatdely, until mysizeMB is reached. Then deletes fle 
    mystring = "The quick brown fox jumps over the lazy dog"
    writeloops = int(1000000*size_in_mb/len(mystring))
    try:
        f = open(filename, 'w')
    except:
        # no better idea than:
        raise
    for x in range(0, writeloops):
        f.write(mystring)
    f.close()
    os.remove(filename)

############## 

def measure_disk_speed_at_dir(*args, log_dir=None, **kwargs):
    dirname = log_dir
    # returns writing speed to dirname in MB/s
    # method: keep writing a file, until 0.5 seconds is passed. Then divide bytes written by time passed
    filesize = 1    # in MB
    maxtime = 0.5     # in sec
    filename = os.path.join(dirname, str(uuid.uuid4()))
    start = time.time()
    loopcounter = 0
    while True:
        try:
            writetofile(filename, filesize)
        except:
            # I have no better idea than:
            raise    
        loopcounter += 1
        diff = time.time() - start
        if diff > maxtime: break
    return (loopcounter*filesize)/diff

