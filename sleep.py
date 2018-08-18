from IoTHealth.fitbit import Fitbit
from datetime import datetime as dt
from datetime import timedelta
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.dates import date2num
import numpy as np

class Sleep(object):
    """
    Interact with sleep logs:
        - request sleep logs
        - update sleep logs
        - create sleep.csv
        - capture explicit data from raw sleep logs
    """
    def __init__(self, sleep_file_path, tokens_file_path):
        """
        create and/or update sleep.csv
        capture sleep_logs using instance variable

        :param sleep_file_path: absolute file-path to sleep.csv
        :param tokens_file_path: absolute file-path to fitbit_tokens.txt
        """

        # assignments
        self.sleep_file_path = sleep_file_path
        self.tokens_file_path = tokens_file_path
        self.today = dt.today().strftime("%Y-%m-%d")

        # capture up-to-date sleep logs
        if os.path.isfile(self.sleep_file_path) and os.access(self.sleep_file_path, os.R_OK):
            self.sleep_logs = self.update_local_logs()
        else:
            self.sleep_logs = self.initialize_csv()

    def update_local_logs(self):
        """
        update sleep.csv and sleep_logs

        :return: up-to-date sleep_logs
        """

        # read sleep.csv and capture data
        local_logs = pd.read_csv(self.sleep_file_path)
        local_logs = local_logs.set_index("dateOfSleep")
        latest_date_local = local_logs.index.max()

        # update sleep_logs, depending on latest local entry
        if latest_date_local == self.today:
            sleep_logs = local_logs
        else:
            # request missing logs from Fitbit
            latest_date_local = dt.strptime(latest_date_local, "%Y-%m-%d")
            next_date_local = (latest_date_local + timedelta(days=1)).strftime("%Y-%m-%d")
            date_range = (next_date_local, self.today)
            fitbit = Fitbit(self.tokens_file_path)
            raw_logs = fitbit.sleeplogs_range(date_range)

            # update sleep_logs and sleep.csv, depending on logs returned from Fitbit
            if not raw_logs['sleep']:
                sleep_logs = local_logs
            else:
                # capture explicit data from raw logs and append to local_logs
                api_logs = self.capture_explicit_data(raw_logs)
                frames = [local_logs, api_logs]
                sleep_logs = pd.concat(frames)

                # update sleep.csv
                sleep_logs.to_csv(path_or_buf=self.sleep_file_path, mode='w')

        sleep_logs.index = pd.to_datetime(sleep_logs.index)
        # sleep_logs = sleep_logs.index.astype('datetime64[ns]')

        return sleep_logs

    def initialize_csv(self):
        """
        initialize sleep.csv with up-to-date sleep logs

        :return sleep_logs: up-to-date sleep logs
        """

        # request all sleep logs from Fitbit
        date_range = ("2018-08-07", self.today)
        fitbit = Fitbit(self.tokens_file_path)
        raw_logs = fitbit.sleeplogs_range(date_range)

        # capture explicit data from raw logs
        sleep_logs = self.capture_explicit_data(raw_logs)
        sleep_logs.to_csv(path_or_buf=self.sleep_file_path, mode='w+', date_format="%Y-%m-%d")

        sleep_logs.index = pd.to_datetime(sleep_logs.index)

        return sleep_logs

    def capture_explicit_data(self, sleep_logs_raw):
        """
        capture explicit data from raw sleep logs

        :param sleep_logs_raw: raw sleep data from Fitbit request
        :return sleep_logs: explicit sleep data captured from raw logs
        """

        # assignments
        dict_labels = ["dateOfSleep", "minutesAfterWakeup",
                       "minutesToFallAsleep", "startTime"]
        stages_labels = ["deep", "light", "rem", "wake"]
        sleep_logs = []
        frames = []

        # create dictionary list to capture explicit data
        for log_raw in sleep_logs_raw["sleep"]:
            sleep_log = {}
            duration_sleep = 0
            duration_total = 0
            for label in dict_labels:
                sleep_log[label] = [log_raw[label]]
            for label in stages_labels:
                sleep_log[label] = [log_raw["levels"]["summary"][label]["minutes"]]
                duration_total += sleep_log[label][0]
            for label in stages_labels[:-1]:
                duration_sleep += sleep_log[label][0]
            sleep_log["efficiency"] = [round(duration_sleep / duration_total, 2)]
            sleep_log["duration"] = [duration_total]
            sleep_logs.append(sleep_log)
        sleep_logs.reverse()

        # create DataFrame list from dictionary list
        for log in sleep_logs:
            df = pd.DataFrame.from_dict(data=log)
            df = df.set_index("dateOfSleep")
            frames.append(df)

        # concatenate DataFrames
        sleep_logs = pd.concat(frames)

        sleep_logs.index = pd.to_datetime(sleep_logs.index)

        return sleep_logs

    def plot_efficiency(self, grid_shape, position, rowspan):
        """
        plot sleep efficiency

        :param grid_shape: grid shape
        :param position: position within grid
        :param rowspan: grid rows spanned by plot
        :return:
        """

        # global plot format
        plt.rc("xtick", labelsize=18)
        plt.rc("ytick", labelsize=18)

        # initialize parameter values
        x = self.sleep_logs.index
        y = self.sleep_logs['efficiency'].tolist()
        xmin = self.sleep_logs.index.tolist()[0] - timedelta(days=1)
        xmax = self.sleep_logs.index.tolist()[-1] + timedelta(days=1)
        labelpad = 25
        labelfontsize = 20
        dateformat = "%a-%b-%d"

        # set parameters
        ax = plt.subplot2grid(grid_shape, position, rowspan=rowspan)
        ax.grid()
        ax.set_title('Sleep Efficiency', fontsize=30, pad=30)
        ax.set_ylabel('Efficiency', fontsize=labelfontsize, labelpad=labelpad)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(0, 1.0)
        ax.set_yticks(np.arange(0, 1.1, 0.1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter(dateformat))

        # annotate bars
        for date, height in zip(x, y):
            ax.text(date, height+0.02, height, fontsize=18, fontweight='bold', horizontalalignment='center')

        ax.bar(x, y, edgecolor='k', width=0.5, linewidth=1.5)

        plt.tight_layout()

        return plt

    def plot_stages(self, grid_shape, position, rowspan):

        plt.rc('xtick', labelsize=18)
        plt.rc('ytick', labelsize=18)

        x = self.sleep_logs.index
        x = date2num(x)
        durations = self.sleep_logs['duration'].values
        awake_perc = np.around(self.sleep_logs['wake'].values / durations, 3) * 100
        rem_perc = np.around(self.sleep_logs['rem'].values / durations, 3) * 100
        light_perc = np.around(self.sleep_logs['light'].values / durations, 3) * 100
        deep_perc = np.around(self.sleep_logs['deep'].values / durations, 3) * 100

        xmin = self.sleep_logs.index.tolist()[0] - timedelta(days=1)
        xmax = self.sleep_logs.index.tolist()[-1] + timedelta(days=1)
        numdays = xmax-xmin+timedelta(days=1)
        xticks = [xmin + timedelta(days=d) for d in range(0, numdays.days)]
        bar_width = 0.2
        labelpad = 25
        labelfontsize = 20
        dateformat = '%a-%b-%d'

        ax = plt.subplot2grid(grid_shape, position, rowspan=rowspan)
        ax.grid()
        ax.set_title('Sleep Stages', fontsize=30, pad=30)
        ax.set_ylabel('Percentage %', fontsize=labelfontsize, labelpad=labelpad)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation = -45, ha='left', rotation_mode='anchor')
        ax.set_xticks(xticks)
        ax.set_yticks(np.arange(0, 110, 5))
        ax.xaxis.set_major_formatter(mdates.DateFormatter(dateformat))

        ax.bar(x-0.3, awake_perc, color='m', width=bar_width, align='center')
        ax.bar(x-0.1, rem_perc, color='c', width=bar_width, align='center')
        ax.bar(x+0.1, light_perc, width=bar_width, align='center')
        ax.bar(x+0.3, deep_perc, color='b', width=bar_width, align='center')

        plt.tight_layout()

        return plt

# assignments
tokens_fp = '/home/sosa/Documents/IoTHealth/fitbit_tokens.txt'
sleep_logs_fp = '/home/sosa/Documents/IoTHealth/sleep.csv'

# fig parameters
grid_shape = (4, 1)
eff_plt_pos = (2, 0)
stages_plt_pos = (0, 0)
rowspan = 2

# capture sleep data
sleep = Sleep(sleep_logs_fp, tokens_fp)

"""
with pd.option_context("display.max_rows", 11, "display.max_columns", 10):
    print(sleep.sleep_logs)
"""

# set fig shape and show
plt.figure(figsize=(17,12))
efficiency_plot = sleep.plot_efficiency(grid_shape, eff_plt_pos, rowspan)
stages_plot = sleep.plot_stages(grid_shape, stages_plt_pos, rowspan)
stages_plot.show()
efficiency_plot.show()



# TODO Dev

"""
    1. Create Sleep() class with attributes:
       DONE a. capture_explicit_data() returns pandas df
       DONE b. create are_logs_uptodate boolean
       DONE c. write sleep.csv file if nonexistent
       DONE d. update sleep.csv
       DONE e. create sleep_logs_dataframe
       DONE f. clean and comment sleep.py code
       DONE g. find out why minutesAfterWakeup and minutesToFallAsleep are mostly 0
                -- for minutesToFallAsleep = 0 makes sense as I've been staying awake till
                    im ready to KO
                -- for minutesAfterWakeup = 0 makes sense as I've pressed "awake" on app
                    when I get up from bed rather than pressing it as soon as I wake and press
                    "done" when I get up from bed
       DONE h. create efficiency_plot()
            i. create stages_plot()
            h. create fig, capturing plots, using sleep_logs_dataframe
            etc ...
"""

# TODO Dev Future

"""
    1. create sleep_%YYYY-%mm-%dd.csv backup file every month on 1st
        - may be useful to create datetime class variable which updates to current
            date each month and date is posted to filename 

"""
