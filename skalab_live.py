#!/usr/bin/env python
import datetime
import math
import os
import shutil
import sys
import gc
import time
from pathlib import Path
import configparser
from time import sleep
from past.utils import old_div

import numpy as np
from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt
import pydaq.daq_receiver as daq
from skalab_utils import MiniPlots, calcolaspettro, closest, MyDaq, get_if_name, BarPlot, ChartPlots, getTextFromFile
from skalab_utils import parse_profile, ts_to_datestring, dt_to_timestamp, Archive, COLORI, decodeChannelList
from skalab_preadu import Preadu, bound
from pyaavs.station import Station
from pyaavs import station
from threading import Thread
from pydaq.persisters import ChannelFormatFileManager, FileDAQModes

default_app_dir = str(Path.home()) + "/.skalab/"
default_profile = "Default"
profile_filename = "live.ini"


configuration = {'tiles': None,
                 'time_delays': None,
                 'station': {
                     'id': 0,
                     'name': "Unnamed",
                     "number_of_antennas": 256,
                     'program': False,
                     'initialise': False,
                     'program_cpld': False,
                     'enable_test': False,
                     'start_beamformer': False,
                     'bitfile': None,
                     'channel_truncation': 5,
                     'channel_integration_time': -1,
                     'beam_integration_time': -1,
                     'equalize_preadu': 0,
                     'default_preadu_attenuation': 0,
                     'beamformer_scaling': 4,
                     'pps_delays': 0},
                 'observation': {
                     'bandwidth': 8 * (400e6 / 512.0),
                     'start_frequency_channel': 50e6},
                 'network': {
                     'lmc': {
                         'tpm_cpld_port': 10000,
                         'lmc_ip': "10.0.10.200",
                         'use_teng': True,
                         'lmc_port': 4660,
                         'lmc_mac': 0x248A078F9D38,
                         'integrated_data_ip': "10.0.0.2",
                         'integrated_data_port': 5000,
                         'use_teng_integrated': True},
                     'csp_ingest': {
                         'src_ip': "10.0.10.254",
                         'dst_mac': 0x248A078F9D38,
                         'src_port': None,
                         'dst_port': 4660,
                         'dst_ip': "10.0.10.200",
                         'src_mac': None}
                    }
                 }


def moving_average(xx, w):
    return np.convolve(xx, np.ones(w), 'valid') / w


class Live(QtWidgets.QMainWindow):
    """ Main UI Window class """
    # Signal for Slots
    signalRms = QtCore.pyqtSignal()
    signalTemp = QtCore.pyqtSignal()

    def __init__(self, config="", uiFile="", profile="Default", size=[1190, 936]):
        """ Initialise main window """
        super(Live, self).__init__()
        # Load window file
        self.connected = False
        self.wg = uic.loadUi(uiFile)
        self.setCentralWidget(self.wg)
        self.resize(size[0], size[1])

        self.profile_name = profile
        if self.profile_name == "":
            self.profile_name = "Default"
        self.profile = {}
        self.profile_file = ""
        self.load_profile(self.profile_name)

        # Populate the plots for the Live Spectra
        self.livePlots = MiniPlots(parent=self.wg.qplot_spectra, nplot=16)
        self.monitorPlots = MiniPlots(parent=self.wg.qplot_int_spectra, nplot=16)
        self.tempBoardPlots = BarPlot(parent=self.wg.qplot_temps_board, size=(3.65, 2.12), xlim=[0, 9],
                                      ylabel="Celsius (deg)", xrotation=0, xlabel="Board",
                                      ylim=[20, 100], yticks=np.arange(20, 120, 20), xticks=np.arange(9))
        self.tempFpga1Plots = BarPlot(parent=self.wg.qplot_temps_fpga1, size=(3.65, 2.12), xlim=[0, 9],
                                      ylabel="Celsius (deg)", xrotation=0, xlabel="FPGA1",
                                      ylim=[20, 100], yticks=np.arange(20, 120, 20), xticks=np.arange(9))
        self.tempFpga2Plots = BarPlot(parent=self.wg.qplot_temps_fpga2, size=(3.65, 2.12), xlim=[0, 9],
                                      ylabel="Celsius (deg)", xrotation=0, xlabel="FPGA2",
                                      ylim=[20, 100], yticks=np.arange(20, 120, 20), xticks=np.arange(9))
        self.tempChart = ChartPlots(parent=self.wg.qplot_chart, ntraces=8, xlabel="time samples", ylim=[20, 120],
                                    ylabel="Board Temp (deg)", size=(11.2, 4), xlim=[0, 200])
        self.rmsChart = ChartPlots(parent=self.wg.qplot_rms_chart, ntraces=32, xlabel="time samples", ylim=[-40, 20],
                                    ylabel="RMS (dBm)", size=(11.2, 6.6), xlim=[0, 200])

        self.qw_preadu = QtWidgets.QWidget(self.wg.qtab_app)
        self.qw_preadu.setGeometry(QtCore.QRect(10, 180, 1131, 681))
        self.qw_preadu.setVisible(True)
        self.qw_preadu.show()
        self.preadu = Preadu(parent=self.qw_preadu, debug=0, board_type=0)
        self.wg.ctrl_preadu.hide()
        self.data_temp_charts = {}
        self.data_rms_charts = {}
        self.qw_rms = []
        self.qp_rms = []

        self.show()
        self.load_events()

        self.newTilesIPs = None
        self.tpm_station = None
        self.station_configuration = {}
        self.tpm_nic_name = ""
        self.mydaq = None
        self.temp_path = ""
        self.temp_fname = ""
        self.temp_file = None
        self.rms_file = None
        self.temperatures = []
        self.rms = []
        self.dsa = []
        self.preaduConf = []

        self.stopThreads = False
        self.skipThreadPause = False
        self.ThreadPause = True
        self.ThreadTempPause = True
        self.MonitorBusy = False
        self.RunBusy = False
        self.commBusy = False  # UCP Communication Token
        self.live_data = []
        self.procRun = Thread(target=self.procRunDaq)
        self.procRun.start()
        self.procRms = Thread(target=self.procReadRms)
        self.procRms.start()
        self.monitor_daq = None
        self.initMonitor = True
        self.monitor_file_manager = None
        self.monitorPrecTstamp = 0
        self.monitor_asse_x = np.arange(512) * 400/512.
        #self.procMonitor = Thread(target=self.procRunMonitor)
        #self.procMonitor.start()

        self.config_file = config
        self.show_rms = False
        self.show_spectra_grid = self.wg.qcheck_spectra_grid.isChecked()

        self.resolutions = 2 ** np.array(range(16)) * (800000.0 / 2 ** 15)
        self.rbw = int(closest(self.resolutions, float(self.wg.qline_rbw.text())))
        self.avg = 2 ** self.rbw
        self.nsamples = int(2 ** 15 / self.avg)
        self.RBW = (self.avg * (400000.0 / 16384.0))
        self.asse_x = np.arange(self.nsamples / 2 + 1) * self.RBW * 0.001
        self.rms_remap = [1, 0, 3, 2, 5, 4, 7, 6,
                          8, 9, 10, 11, 12, 13, 14, 15,
                          17, 16, 19, 18, 21, 20, 23, 22,
                          24, 25, 26, 27, 28, 29, 30, 31]

        self.live_input_list = np.arange(1, 17)
        self.live_channels = self.wg.qline_channels.text()

        self.xAxisRange = [float(self.wg.qline_spectra_band_from.text()), float(self.wg.qline_spectra_band_to.text())]
        self.yAxisRange = [float(self.wg.qline_spectra_level_min.text()), float(self.wg.qline_spectra_level_max.text())]
        self.check_raw(self.wg.qradio_raw)

        w = self.wg.qplot_rms_bar.geometry().width()
        h = self.wg.qplot_rms_bar.geometry().height()
        self.qwRmsMain = QtWidgets.QWidget(self.wg.qplot_rms_bar)
        self.qwRmsMain.setGeometry(QtCore.QRect(0, 0, w, h))
        self.qwRmsMainLayout = QtWidgets.QVBoxLayout(self.qwRmsMain)
        self.qwRms = QtWidgets.QWidget()
        self.qwRms.setGeometry(QtCore.QRect(0, 0, w, h))
        self.qwRmsMainLayout.insertWidget(0, self.qwRms)

        self.populate_help()

    def load_events(self):
        # Live Plots Connections
        self.wg.qbutton_connect.clicked.connect(lambda: self.connect())
        self.wg.qbutton_single.clicked.connect(lambda: self.doSingleAcquisition())
        self.wg.qbutton_run.clicked.connect(lambda: self.startContinuousAcquisition())
        self.wg.qbutton_stop.clicked.connect(lambda: self.stopContinuousAcquisition())

        self.wg.qbutton_browse_data_directory.clicked.connect(lambda: self.browse_outdir())
        self.wg.qbutton_browse_station_config.clicked.connect(lambda: self.browse_config())
        self.wg.qbutton_load.clicked.connect(lambda: self.load())
        self.wg.qbutton_saveas.clicked.connect(lambda: self.save_as_profile())
        self.wg.qbutton_save.clicked.connect(lambda: self.save_profile(this_profile=self.profile_name))
        self.wg.qbutton_delete.clicked.connect(lambda: self.delete_profile(self.wg.qcombo_profile.currentText()))
        self.wg.qbutton_preadu_setup.clicked.connect(lambda: self.setupPreadu(self.wg.qcombo_preadu_version.currentIndex()))
        self.wg.qbutton_equalize.clicked.connect(lambda: self.equalization())
        self.wg.qline_channels.textChanged.connect(lambda: self.channelsListModified())

        self.wg.qradio_rms_adu.toggled.connect(lambda: self.customizeRms())
        self.wg.qradio_rms_power.toggled.connect(lambda: self.customizeRms())
        self.wg.qradio_rms_dsa.toggled.connect(lambda: self.customizeRms())
        self.wg.qradio_rms_chart.toggled.connect(lambda: self.customizeRms())
        self.wg.qcombo_rms_label.currentIndexChanged.connect(lambda: self.customizeRms())
        self.wg.qcheck_spectra_grid.stateChanged.connect(self.live_show_spectra_grid)
        self.wg.qradio_raw.toggled.connect(lambda: self.check_raw(self.wg.qradio_raw))
        self.wg.qradio_int_spectra.toggled.connect(lambda: self.check_int_spectra(self.wg.qradio_int_spectra))
        self.wg.qradio_rms.toggled.connect(lambda: self.check_rms(self.wg.qradio_rms))
        self.wg.qradio_temps.toggled.connect(lambda: self.check_temps(self.wg.qradio_temps))
        self.wg.qradio_preadu.toggled.connect(lambda: self.check_preadu())
        self.wg.qcombo_chart.currentIndexChanged.connect(lambda: self.switchChart())
        self.wg.qcombo_tpm.currentIndexChanged.connect(lambda: self.updatePreadu())

    def load_profile(self, profile):
        self.profile = {}
        fullpath = default_app_dir + profile + "/" + profile_filename
        if os.path.exists(fullpath):
            print("Loading Live Profile: " + profile + " (" + fullpath + ")")
        else:
            print("\nThe Live Profile does not exist.\nGenerating a new one in "
                  + fullpath + "\n")
            self.make_profile(profile=profile, prodict={})
        self.profile = parse_profile(fullpath)
        self.profile_name = profile
        self.profile_file = fullpath
        self.wg.qline_configuration_file.setText(self.profile_file)
        if 'query_interval' in self.profile['App'].keys():
            self.wg.qline_profile_interval.setText(self.profile['App']['query_interval'])
        if 'station_config' in self.profile['App'].keys():
            self.wg.qline_configfile.setText(self.profile['App']['station_config'])
        if 'data_path' in self.profile['App'].keys():
            self.wg.qline_output_dir.setText(self.profile['App']['data_path'])
        if 'temperatures_path' in self.profile['App'].keys():
            self.wg.qline_temperatures_path.setText(self.profile['App']['temperatures_path'])
        if 'integrated_spectra_path' in self.profile['App'].keys():
            self.wg.qline_integrated_spectra_path.setText(self.profile['App']['integrated_spectra_path'])
        # Overriding Configuration File with parameters
        self.updateProfileCombo(current=profile)
        self.populate_table_profile()

    def populate_help(self, uifile="skalab_live.ui"):
        with open(uifile) as f:
            data = f.readlines()
        helpkeys = [d[d.rfind('name="Help_'):].split('"')[1] for d in data if 'name="Help_' in d]
        for k in helpkeys:
            self.wg.findChild(QtWidgets.QTextEdit, k).setText(getTextFromFile(k.replace("_", "/")+".html"))

    def check_raw(self, b):
        if b.isChecked():
            # Show only spectra plot
            self.wg.qplot_rms.hide()
            self.wg.qplot_temps.hide()
            self.wg.qplot_int_spectra.hide()
            self.wg.qplot_spectra.show()
            # Show only spectra ctrl
            #self.wg.ctrl_rms.hide()
            #self.wg.ctrl_temps.hide()
            self.wg.ctrl_spectra.show()
            self.wg.ctrl_preadu.hide()
            self.wg.ctrl_rms.hide()
            # Show only spectra tstamp
            self.wg.qlabel_tstamp_spectra.show()
            self.wg.qlabel_tstamp_temp.hide()
            self.wg.qlabel_tstamp_rms.hide()
            self.wg.qlabel_tstamp_int_spectra.hide()
            self.qw_preadu.hide()

            self.wg.qline_channels.setEnabled(True)
            self.wg.qbutton_single.setEnabled(True)
            self.wg.qbutton_run.setEnabled(True)
            self.wg.qbutton_stop.setEnabled(True)
            self.wg.qbutton_save.setEnabled(True)
            self.wg.qbutton_export.setEnabled(True)
            self.wg.qcombo_rms_label.setEnabled(True)
            self.wg.qcombo_tpm.setEnabled(True)

    def check_int_spectra(self, b):
        if b.isChecked():
            # Show only spectra plot
            self.wg.qplot_rms.hide()
            self.wg.qplot_temps.hide()
            self.wg.qplot_spectra.hide()
            self.wg.qplot_int_spectra.show()
            # Show only int spectra ctrl
            self.wg.ctrl_spectra.hide()
            self.wg.ctrl_preadu.hide()
            self.wg.ctrl_rms.hide()
            # Show only int spectra tstamp
            self.wg.qlabel_tstamp_int_spectra.show()
            self.wg.qlabel_tstamp_spectra.hide()
            self.wg.qlabel_tstamp_temp.hide()
            self.wg.qlabel_tstamp_rms.hide()
            self.qw_preadu.hide()

            self.wg.qline_channels.setEnabled(False)
            self.wg.qbutton_single.setEnabled(False)
            self.wg.qbutton_run.setEnabled(False)
            self.wg.qbutton_stop.setEnabled(False)
            self.wg.qbutton_save.setEnabled(True)
            self.wg.qbutton_export.setEnabled(True)
            self.wg.qcombo_rms_label.setEnabled(False)
            self.wg.qcombo_tpm.setEnabled(True)

    def check_rms(self, b):
        if b.isChecked():
            # Show only spectra plot
            self.wg.qplot_rms.show()
            self.wg.qplot_temps.hide()
            self.wg.qplot_spectra.hide()
            self.wg.qplot_int_spectra.hide()
            # Show only spectra ctrl
            self.wg.ctrl_spectra.hide()
            self.wg.ctrl_preadu.hide()
            self.wg.ctrl_rms.show()
            # Show only spectra tstamp
            self.wg.qlabel_tstamp_spectra.hide()
            self.wg.qlabel_tstamp_temp.hide()
            self.wg.qlabel_tstamp_int_spectra.hide()
            self.wg.qlabel_tstamp_rms.show()
            self.qw_preadu.hide()

            #self.wg.qline_channels.setEnabled(False)
            self.wg.qbutton_single.setEnabled(False)
            self.wg.qbutton_run.setEnabled(False)
            self.wg.qbutton_stop.setEnabled(False)
            self.wg.qbutton_save.setEnabled(False)
            self.wg.qbutton_export.setEnabled(False)
            self.wg.qcombo_rms_label.setEnabled(True)
            #self.wg.qcombo_tpm.setEnabled(False)
            self.customizeRms()

    def check_temps(self, b):
        if b.isChecked():
            # Show only spectra plot
            self.wg.qplot_rms.hide()
            self.wg.qplot_temps.show()
            self.wg.qplot_spectra.hide()
            self.wg.qplot_int_spectra.hide()
            # Show only spectra ctrl
            #self.wg.ctrl_rms.hide()
            #self.wg.ctrl_temps.show()
            self.wg.ctrl_spectra.hide()
            self.wg.ctrl_preadu.hide()
            self.wg.ctrl_rms.hide()
            # Show only spectra tstamp
            self.wg.qlabel_tstamp_spectra.hide()
            self.wg.qlabel_tstamp_rms.hide()
            self.wg.qlabel_tstamp_int_spectra.hide()
            self.wg.qlabel_tstamp_temp.show()
            self.qw_preadu.hide()

            self.wg.qline_channels.setEnabled(False)
            self.wg.qbutton_single.setEnabled(False)
            self.wg.qbutton_run.setEnabled(False)
            self.wg.qbutton_stop.setEnabled(False)
            self.wg.qbutton_save.setEnabled(False)
            self.wg.qbutton_export.setEnabled(False)
            self.wg.qcombo_rms_label.setEnabled(False)
            self.wg.qcombo_tpm.setEnabled(False)

    def check_preadu(self):
        # Show only spectra plot
        self.wg.qplot_rms.hide()
        self.wg.qplot_temps.hide()
        self.wg.qplot_spectra.hide()
        self.wg.qplot_int_spectra.hide()
        # Show only spectra ctrl
        #self.wg.ctrl_rms.hide()
        #self.wg.ctrl_temps.show()
        self.wg.ctrl_spectra.hide()
        self.wg.ctrl_rms.hide()
        self.wg.ctrl_preadu.show()

        # Show only spectra tstamp
        self.wg.qlabel_tstamp_spectra.hide()
        self.wg.qlabel_tstamp_temp.hide()
        self.wg.qlabel_tstamp_int_spectra.hide()
        self.wg.qlabel_tstamp_rms.show()
        self.qw_preadu.show()

        self.wg.qline_channels.setEnabled(False)
        self.wg.qbutton_single.setEnabled(False)
        self.wg.qbutton_run.setEnabled(False)
        self.wg.qbutton_stop.setEnabled(False)
        self.wg.qbutton_save.setEnabled(False)
        self.wg.qbutton_export.setEnabled(False)
        self.wg.qcombo_rms_label.setEnabled(False)
        self.wg.qcombo_tpm.setEnabled(True)

    def setupPreadu(self, version):
        print("Setting preadu board version: %d" % version)
        self.preadu.set_preadu_version(version)
        #self.readDsaConfiguration()

    def updatePreadu(self):
        if self.connected:
            self.preadu.setTpm(self.tpm_station.tiles[self.wg.qcombo_tpm.currentIndex()])

    def switchChart(self):
        self.drawTempCharts()

    def browse_outdir(self):
        fd = QtWidgets.QFileDialog()
        fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        options = fd.options()
        self.folder = fd.getExistingDirectory(self, caption="Choose a directory to save the data",
                                              directory="/storage/", options=options)
        self.wg.qline_output_dir.setText(self.folder)

    def browse_config(self):
        fd = QtWidgets.QFileDialog()
        fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        options = fd.options()
        self.config_file = fd.getOpenFileName(self, caption="Select a Station Config File...",
                                              directory="/opt/aavs/config/", options=options)[0]
        self.wg.qline_configfile.setText(self.config_file)

    def populate_table_profile(self):
        self.wg.qtable_conf.clearSpans()
        self.wg.qtable_conf.setGeometry(QtCore.QRect(640, 20, 481, 821))
        self.wg.qtable_conf.setObjectName("qtable_conf")
        self.wg.qtable_conf.setColumnCount(1)
        self.wg.qtable_conf.setWordWrap(True)

        total_rows = 1
        for i in self.profile.sections():
            total_rows = total_rows + len(self.profile[i]) + 1
        self.wg.qtable_conf.setRowCount(total_rows + 2)

        item = QtWidgets.QTableWidgetItem("Profile: " + self.profile_name)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        item.setFont(font)
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        self.wg.qtable_conf.setHorizontalHeaderItem(0, item)

        item = QtWidgets.QTableWidgetItem(" ")
        item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        self.wg.qtable_conf.setVerticalHeaderItem(0, item)

        q = 1
        for i in self.profile.sections():
            item = QtWidgets.QTableWidgetItem("[" + i + "]")
            item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            font = QtGui.QFont()
            font.setBold(True)
            font.setWeight(75)
            item.setFont(font)
            self.wg.qtable_conf.setVerticalHeaderItem(q, item)
            q = q + 1
            for k in self.profile[i]:
                item = QtWidgets.QTableWidgetItem(k)
                item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wg.qtable_conf.setVerticalHeaderItem(q, item)
                item = QtWidgets.QTableWidgetItem(self.profile[i][k])
                item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wg.qtable_conf.setItem(q, 0, item)
                q = q + 1
            item = QtWidgets.QTableWidgetItem(" ")
            item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wg.qtable_conf.setVerticalHeaderItem(q, item)
            q = q + 1

        self.wg.qtable_conf.horizontalHeader().setStretchLastSection(True)
        self.wg.qtable_conf.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wg.qtable_conf.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wg.qtable_conf.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

    def make_profile(self, profile: str, prodict: dict):
        conf = configparser.ConfigParser()
        conf['App'] = {}
        if 'App' in prodict.keys() and 'station_config' in prodict['App'].keys():
            conf['App']['station_config'] = prodict['App']['station_config']
        else:
            conf['App']['station_config'] = ""
        if 'App' in prodict.keys() and 'data_path' in prodict['App'].keys():
            conf['App']['data_path'] = prodict['App']['data_path']
        else:
            conf['App']['data_path'] = ""
        if 'App' in prodict.keys() and 'temperatures_path' in prodict['App'].keys():
            conf['App']['temperatures_path'] = prodict['App']['temperatures_path']
        else:
            conf['App']['temperatures_path'] = ""
        if 'App' in prodict.keys() and 'integrated_spectra_path' in prodict['App'].keys():
            conf['App']['integrated_spectra_path'] = prodict['App']['integrated_spectra_path']
        else:
            conf['App']['integrated_spectra_path'] = ""
        if 'App' in prodict.keys() and 'query_interval' in prodict['App'].keys():
            conf['App']['query_interval'] = prodict['App']['query_interval']
        else:
            conf['App']['query_interval'] = "3"
        conf['Spectra'] = {}
        if 'Spectra' in prodict.keys() and 'qline_rbw' in prodict['Spectra'].keys():
            conf['Spectra']['qline_rbw'] = prodict['Spectra']['qline_rbw']
        else:
            conf['Spectra']['qline_rbw'] = "1000"
        if 'Spectra' in prodict.keys() and 'qline_spectra_level_min' in prodict['Spectra'].keys():
            conf['Spectra']['qline_spectra_level_min'] = prodict['Spectra']['qline_spectra_level_min']
        else:
            conf['Spectra']['qline_spectra_level_min'] = "-100"
        if 'Spectra' in prodict.keys() and 'qline_spectra_level_max' in prodict['Spectra'].keys():
            conf['Spectra']['qline_spectra_level_max'] = prodict['Spectra']['qline_spectra_level_max']
        else:
            conf['Spectra']['qline_spectra_level_max'] = "0"
        if 'Spectra' in prodict.keys() and 'qline_spectra_band_from' in prodict['Spectra'].keys():
            conf['Spectra']['qline_spectra_band_from'] = prodict['Spectra']['qline_spectra_band_from']
        else:
            conf['Spectra']['qline_spectra_band_from'] = "1"
        if 'Spectra' in prodict.keys() and 'qline_spectra_band_to' in prodict['Spectra'].keys():
            conf['Spectra']['qline_spectra_band_to'] = prodict['Spectra']['qline_spectra_band_to']
        else:
            conf['Spectra']['qline_spectra_band_to'] = "400"
        if 'Spectra' in prodict.keys() and 'qcheck_spectra_grid' in prodict['Spectra'].keys():
            conf['Spectra']['qcheck_spectra_grid'] = prodict['Spectra']['qcheck_spectra_grid']
        else:
            conf['Spectra']['qcheck_spectra_grid'] = "True"
        if 'Spectra' in prodict.keys() and 'qcheck_spectra_noline' in prodict['Spectra'].keys():
            conf['Spectra']['qcheck_spectra_noline'] = prodict['Spectra']['qcheck_spectra_noline']
        else:
            conf['Spectra']['qcheck_spectra_noline'] = "False"
        if 'Spectra' in prodict.keys() and 'qcheck_xpol_sp' in prodict['Spectra'].keys():
            conf['Spectra']['qcheck_xpol_sp'] = prodict['Spectra']['qcheck_xpol_sp']
        else:
            conf['Spectra']['qcheck_xpol_sp'] = "True"
        if 'Spectra' in prodict.keys() and 'qcheck_ypol_sp' in prodict['Spectra'].keys():
            conf['Spectra']['qcheck_ypol_sp'] = prodict['Spectra']['qcheck_ypol_sp']
        else:
            conf['Spectra']['qcheck_ypol_sp'] = "True"

        if not os.path.exists(default_app_dir):
            os.makedirs(default_app_dir)
        conf_path = default_app_dir + profile
        if not os.path.exists(conf_path):
            os.makedirs(conf_path)
        conf_path = conf_path + "/" + profile_filename
        with open(conf_path, 'w') as configfile:
            conf.write(configfile)

    def updateProfileCombo(self, current):
        profiles = []
        for d in os.listdir(default_app_dir):
            if os.path.exists(default_app_dir + "/" + d + "/" + profile_filename):
                profiles += [d]
        if profiles:
            self.wg.qcombo_profile.clear()
            for n, p in enumerate(profiles):
                self.wg.qcombo_profile.addItem(p)
                if current == p:
                    self.wg.qcombo_profile.setCurrentIndex(n)

    def load(self):
        if not self.connected:
            self.load_profile(self.wg.qcombo_profile.currentText())
        else:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Please switch to OFFLINE first!")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()

    def save_profile(self, this_profile, reload=True):
        self.make_profile(profile=this_profile,
                          prodict={'App': {'data_path': self.wg.qline_output_dir.text(),
                                           'station_config': self.wg.qline_configfile.text(),
                                           'query_interval': self.wg.qline_profile_interval.text(),
                                           'temperatures_path': self.wg.qline_temperatures_path.text(),
                                           'integrated_spectra_path': self.wg.qline_ntegrated_spectra_path.text()}})
        if reload:
            self.load_profile(profile=this_profile)

    def save_as_profile(self):
        text, ok = QtWidgets.QInputDialog.getText(self, 'Profiles', 'Enter a Profile name:')
        if ok:
            self.save_profile(this_profile=text)

    def delete_profile(self, profile):
        if os.path.exists(default_app_dir + profile):
            shutil.rmtree(default_app_dir + profile)
        self.updateProfileCombo(current="")
        self.load_profile(self.wg.qcombo_profile.currentText())

    def connect(self):
        if not self.connected:
            # Load station configuration
            station.load_configuration_file(self.config_file)
            self.station_configuration = station.configuration
            if self.newTilesIPs is not None:
                station.configuration['tiles'] = self.newTilesIPs
            # Test
            try:
                # Create station
                self.tpm_station = Station(station.configuration)
                # Connect station (program, initialise and configure if required)
                self.tpm_station.connect()
                status = True
                for t in self.tpm_station.tiles:
                    status = status * t.is_programmed()
                if status:
                    self.tpm_station.tiles[0].get_temperature()
                    #self.wg.qlabel_connection.setText("Connected")
                    self.wg.qbutton_connect.setStyleSheet("background-color: rgb(78, 154, 6);")
                    self.wg.qbutton_connect.setText("ONLINE")
                    self.tempBoardPlots.reinit(len(self.tpm_station.tiles))
                    self.tempFpga1Plots.reinit(len(self.tpm_station.tiles))
                    self.tempFpga2Plots.reinit(len(self.tpm_station.tiles))

                    if self.tpm_station.tiles[0].tpm_version() == "tpm_v1_2":
                        self.rms_remap = [1, 0, 3, 2, 5, 4, 7, 6,
                                          8, 9, 10, 11, 12, 13, 14, 15,
                                          17, 16, 19, 18, 21, 20, 23, 22,
                                          24, 25, 26, 27, 28, 29, 30, 31]
                    else:
                        self.rms_remap = np.arange(32)
                    self.connected = True

                    self.setupRms()
                    self.setupDAQ()
                    self.setupArchiveTemperatures()
                    self.ThreadTempPause = False
                    self.preadu.setTpm(self.tpm_station.tiles[self.wg.qcombo_tpm.currentIndex()])
                else:
                    msgBox = QtWidgets.QMessageBox()
                    msgBox.setText("Some TPM is not programmed,\nplease initialize the Station first!")
                    msgBox.setWindowTitle("Error!")
                    msgBox.setIcon(QtWidgets.QMessageBox.Critical)
                    msgBox.exec_()
            except Exception as e:
                msgBox = QtWidgets.QMessageBox()
                msgBox.setText("An exception occurred while trying to connect to the Station.\n\nException: " + str(e))
                msgBox.setWindowTitle("Error!")
                msgBox.setIcon(QtWidgets.QMessageBox.Critical)
                msgBox.exec_()
                #self.wg.qlabel_connection.setText("ERROR: Unable to connect to the TPMs Station. Retry...")
                self.wg.qbutton_connect.setStyleSheet("background-color: rgb(204, 0, 0);")
                self.wg.qbutton_connect.setText("OFFLINE")
                self.ThreadTempPause = True
                self.connected = False
                if self.temp_file is not None:
                    self.closeTemp()
                if self.rms_file is not None:
                    self.closeRms()
        else:
            self.disconnect()

    def disconnect(self):
        self.ThreadTempPause = True
        self.ThreadPause = True
        sleep(0.5)
        if self.temp_file is not None:
            self.closeTemp()
        if self.rms_file is not None:
            self.closeRms()
        del self.tpm_station
        gc.collect()
        self.closeDAQ()
        self.tpm_station = None
        self.wg.qbutton_connect.setStyleSheet("background-color: rgb(204, 0, 0);")
        self.wg.qbutton_connect.setText("OFFLINE")
        self.connected = False
        self.initMonitor = True

    def procRunDaq(self):
        while True:
            if self.connected:
                try:
                    if not self.ThreadPause:
                        self.RunBusy = True
                        self.getAcquisition()
                        sleep(0.1)
                        # self.signalRun.emit()
                        self.plotAcquisition()
                        sleep(0.1)
                        self.RunBusy = False
                except:
                    print("Failed to get DAQ data!")
                    pass
                cycle = 0.0
                while cycle < (int(self.profile['App']['query_interval']) - 1) and not self.skipThreadPause:
                    sleep(0.1)
                    cycle = cycle + 0.1
                self.skipThreadPause = False
            if self.stopThreads:
                break
            sleep(0.5)

    def procReadRms(self):
        monit_daq = None
        while True:
            if self.connected:
                if self.initMonitor:
                    import pydaq.daq_receiver as monit_daq
                    nof_tiles = len(self.tpm_station.configuration['tiles'])
                    int_data_port = str(self.tpm_station.configuration['network']['lmc']['lmc_port'])
                    if self.tpm_station.configuration['network']['lmc']['use_teng']:
                        int_data_port = str(self.tpm_station.configuration['network']['lmc']['integrated_data_port'])
                    daq_config = {
                        "receiver_interface": get_if_name(self.tpm_station.configuration['network']['lmc']['lmc_ip']),
                        "receiver_ports": int_data_port,
                        "nof_tiles": nof_tiles,
                        'directory': self.wg.qline_integrated_spectra_path.text()}
                    #print(daq_config)
                    self.monitor_daq = monit_daq
                    self.monitor_daq.populate_configuration(daq_config)
                    self.monitor_daq.initialise_daq()
                    self.monitor_daq.start_integrated_channel_data_consumer()
                    time.sleep(2 * 8 * float(self.tpm_station.configuration['station']['channel_integration_time']))
                    self.monitor_file_manager = ChannelFormatFileManager(root_path=self.wg.qline_integrated_spectra_path.text(),
                                                                         daq_mode=FileDAQModes.Integrated)
                    self.initMonitor = False
                try:
                    if not self.ThreadTempPause:
                        while self.commBusy:
                            time.sleep(0.2)
                        self.commBusy = True
                        self.readTemperatures()
                        sleep(0.1)
                        self.preaduConf = []
                        for t in self.tpm_station.tiles:
                            while self.preadu.Busy:
                                time.sleep(0.2)
                            self.preaduConf += [self.preadu.readConfiguration(t)]
                        sleep(0.1)
                        self.readRms()
                        sleep(0.1)
                        self.plotMonitor()
                        sleep(0.1)
                        self.commBusy = False
                        self.signalTemp.emit()
                        self.signalRms.emit()
                except:
                    print("Failed to get RMS and/or Temperature data!")
                    self.commBusy = False
                    self.preadu.Busy = False
                    pass
                cycle = 0.0
                while cycle < float(self.wg.qline_profile_interval.text()) and not self.stopThreads:
                    sleep(0.1)
                    cycle = cycle + 0.1
            if self.stopThreads:
                #self.closeRms()
                break
            sleep(1)

    def plotMonitor(self, forcePlot=False):
        remap = [0, 1, 2, 3, 8, 9, 10, 11, 15, 14, 13, 12, 7, 6, 5, 4]
        monitorData, timestamps = self.monitor_file_manager.read_data(tile_id=self.wg.qcombo_tpm.currentIndex(),
                                                                      n_samples=1,
                                                                      sample_offset=-1)
        #print("TStamp", timestamps[0][0])
        if not timestamps[0][0] == self.monitorPrecTstamp or forcePlot:
            for i in range(16):
                # Plot X Pol
                spettro = monitorData[:, remap[i], 0, -1]
                self.monitorPlots.plotCurve(self.monitor_asse_x, spettro, i, xAxisRange=[1, 400],
                                            yAxisRange=[0, 40], title="INPUT-%02d" % i,
                                            xLabel="MHz", yLabel="dB", colore="b", grid=True, lw=1,
                                            show_line=self.wg.qcheck_xpol_sp.isChecked())

                # Plot Y Pol
                spettro = monitorData[:, remap[i], 1, -1]
                self.monitorPlots.plotCurve(self.monitor_asse_x, spettro, i, xAxisRange=[1, 400],
                                            yAxisRange=[0, 40], colore="g", grid=True, lw=1,
                                            show_line=self.wg.qcheck_ypol_sp.isChecked())
            self.monitorPlots.updatePlot()
            self.monitorPrecTstamp = timestamps[0][0]

    def readRms(self):
        if self.connected:
            timestamp = dt_to_timestamp(datetime.datetime.utcnow())
            self.wg.qlabel_tstamp_rms.setText(ts_to_datestring(timestamp))
            if self.rms_file is not None:
                self.rms_file.write(name="timestamp", data=timestamp)
            rms = []
            for j, t in enumerate(self.tpm_station.tiles):
                k = ("TPM-%02d" % (j + 1))
                adc_rms = t.get_adc_rms()
                remapped_rms = [adc_rms[x] for x in self.rms_remap]
                remapped_power = []
                for x in self.rms_remap:
                    with np.errstate(divide='ignore', invalid='ignore'):
                        remapped_power += [10 * np.log10(np.power((adc_rms[x] * (1.7 / 256.)), 2) / 400.) + 30 + 12]
                rms += [remapped_rms]
                if self.rms_file is not None:
                    self.rms_file.write(name=k, data=remapped_rms)
                if k not in self.data_rms_charts.keys():
                    self.data_rms_charts[k] = [np.nan] * 32 * 201
                self.data_rms_charts[k] = self.data_rms_charts[k][32:] + remapped_power
            self.rms = rms

    def equalization(self):
        if self.connected:
            dsa_remap = [15, 14, 13, 12, 11, 10, 9, 8,
                         16, 17, 18, 19, 20, 21, 22, 23,
                         7, 6, 5, 4, 3, 2, 1, 0,
                         24, 25, 26, 27, 28, 29, 30, 31]
            #dsa_remap=range(32)
            self.ThreadTempPause = True
            self.wg.qbutton_equalize.setEnabled(False)
            self.wg.qbutton_equalize.setStyleSheet("background-color: rgb(237, 212, 0);")
            for iter in range(3):
                #print("\n\nLEVEL EQUALIZATION (iter %d/3)" % (iter + 1))
                self.readRms()
                if self.wg.qradio_eq_this.isChecked():
                    tiles = [self.tpm_station.tiles[int(self.wg.qcombo_tpm.currentIndex())]]
                    RMS = [self.rms[self.wg.qcombo_tpm.currentIndex()]]
                else:
                    tiles = self.tpm_station.tiles
                    RMS = self.rms
                target = float(self.wg.qline_eqvalue.text())
                if self.wg.qcombo_equnit.currentIndex() == 0:  # ADU RMS
                    for b, t in enumerate(tiles):
                        #print("\n Equalize TPM-%02d to RMS %3.1f" % (b, target))
                        self.preadu.setTpm(self.tpm_station.tiles[self.wg.qcombo_tpm.currentIndex()])
                        #self.preadu.setTpm(t, self.preaduConf[self.wg.qcombo_tpm.currentIndex()])
                        #dsa = self.preadu.read_dsa()
                        for i in range(len(RMS[b])):
                            rms = RMS[b][self.preadu.chan_remap[i]]
                            if old_div(rms, target) > 0:
                                with np.errstate(divide='ignore', invalid='ignore'):
                                    attenuation = 20 * math.log10(old_div(rms, target))
                            else:
                                attenuation = 0
                            #print(i, "\tRMS: %d\tDSA: " % int(round(rms)), dsa[i], "\tDIFF ATT: %3.1f\t" % attenuation,
                            #      "NEW DSA: %3.1f\t" % (bound(int(round(dsa[i] + attenuation)))))
                            #dsa[i] = bound(int(round(dsa[i] + attenuation)))
                            self.preaduConf[b][self.preadu.spi_remap[i]]['dsa'] = \
                                bound(int(round(self.preaduConf[b][self.preadu.spi_remap[i]]['dsa'] + attenuation)))
                            self.preadu.preadu.set_rx_attenuation(i, self.preaduConf[b][self.preadu.spi_remap[i]]['dsa'])
                            self.preaduConf[b][self.preadu.spi_remap[i]]['code'] = self.preadu.preadu.rx[i].value
                        self.preadu.write_configuration()
                        #self.readDsaConfiguration()
                else:
                    for b, t in enumerate(tiles):
                        self.preadu.setTpm(t)
                        for i in range(len(RMS[b])):
                            rms = RMS[b][i]  # rms_remap[i]]
                            with np.errstate(divide='ignore', invalid='ignore'):
                                power = 10 * np.log10(np.power((rms * (1.7 / 256.)), 2) / 400.) + 30 + 12
                            if power == (-np.inf):
                                power = -30
                            self.preaduConf[b][i]['dsa'] = bound(int(round(self.preaduConf[b][i]['dsa'] + (power - target))))
                            #print("INPUT-%02d, Level: %3.1f" % (i, power))
                            self.preadu.preadu.set_rx_attenuation(i, self.preaduConf[b][i]['dsa'])
                            self.preaduConf[b][i]['code'] = self.preadu.preadu.rx[i].value
                        self.preadu.write_configuration()
                        time.sleep(0.2)
                    self.preadu.setTpm(self.tpm_station.tiles[self.wg.qcombo_tpm.currentIndex()])
            self.wg.qbutton_equalize.setEnabled(True)
            self.wg.qbutton_equalize.setStyleSheet("")
            self.ThreadTempPause = False

    def readTemperatures(self):
        timestamp = dt_to_timestamp(datetime.datetime.utcnow())
        self.wg.qlabel_tstamp_temp.setText(ts_to_datestring(timestamp))
        if self.temp_file is not None:
            self.temp_file.write(name="timestamp", data=timestamp)
        self.temperatures = []
        for n, tile in enumerate(self.tpm_station.tiles):
            k = ("TPM-%02d" % (n + 1))
            tris = [tile.get_temperature(), tile.get_fpga0_temperature(), tile.get_fpga1_temperature()]
            self.temperatures += [tris]
            if self.temp_file is not None:
                self.temp_file.write(name=("TPM-%02d" % (n + 1)), data=tris)
            if k not in self.data_temp_charts.keys():
                self.data_temp_charts[k] = [[np.nan, np.nan, np.nan]] * 201
            self.data_temp_charts[k] = self.data_temp_charts[k][1:] + [tris]

            #print("TPM-%02d Temperatures: Board %3.1f,\tFPGA-0 %3.1f,\tFPGA-1 %3.1f" %
            #      (n + 1, tris[0], tris[1], tris[2]))

    def closeTemp(self):
        if self.temp_file is not None:
            self.temp_file.close()

    def closeRms(self):
        if self.rms_file is not None:
            self.rms_file.close()

    def setupDAQ(self):
        ddd = "/storage/daq/tmp/"
        self.tpm_nic_name = get_if_name(self.station_configuration['network']['lmc']['lmc_ip'])
        if self.tpm_nic_name == "":
            print("Connection Error! (ETH Card name ERROR)")
        if not self.tpm_nic_name == "":
            if os.path.exists(ddd):
                self.mydaq = MyDaq(daq, self.tpm_nic_name, self.tpm_station, len(self.station_configuration['tiles']),
                                   directory=ddd)
                print("DAQ Initialized, NIC: %s, NofTiles: %d, Data Directory: %s" %
                      (self.tpm_nic_name, len(self.station_configuration['tiles']), ddd))
            else:
                print("DAQ Error: a valid data directory is required.")

    def closeDAQ(self):
        self.mydaq.close()
        del self.mydaq
        gc.collect()

    def setupArchiveTemperatures(self):
        if self.connected:
            self.temp_path = self.profile['App']['temperatures_path']
            if not self.temp_path == "":
                if not self.temp_path[-1] == "/":
                    self.temp_path = self.temp_path + "/"
                self.temp_fname = datetime.datetime.strftime(datetime.datetime.utcnow(),
                                                             "%Y-%m-%d_%H%M%S_StationTemperatures.h5")
                self.temp_file = Archive(hfile=self.temp_path + self.temp_fname, mode='a')
            else:
                msgBox = QtWidgets.QMessageBox()
                msgBox.setText("Warning: No path defined to save Auxiliary data (Temperatures). "
                               "\nThis data will not be saved in this session.")
                msgBox.setWindowTitle("Warning!")
                msgBox.setIcon(QtWidgets.QMessageBox.Warning)
                msgBox.exec_()

    def setupRms(self):
        item = self.qwRmsMainLayout.itemAt(0)
        widget = item.widget()
        widget.deleteLater()

        w = self.wg.qplot_rms_bar.geometry().width()
        h = self.wg.qplot_rms_bar.geometry().height()
        self.qwRms = QtWidgets.QWidget()
        self.qwRms.setGeometry(QtCore.QRect(0, 0, w, h))

        s = int(np.ceil(np.sqrt(len(self.station_configuration['tiles']))))
        width = (w - 20) / s
        height = (h - 20) / s
        self.qw_rms = []
        self.qp_rms = []
        for t in range(len(self.station_configuration['tiles'])):
            self.qw_rms += [QtWidgets.QWidget(self.qwRms)]
            self.qw_rms[t].setGeometry(QtCore.QRect(width * (t % s), height * int((t / s)), width, height))
            title = self.wg.qcombo_tpm.itemText(t)
            self.qp_rms += [BarPlot(parent=self.qw_rms[t], size=((width/100), (height/100)), xlim=[0, 33],
                                    ylabel="ADU RMS", xrotation=90, xlabel="", ylim=[0, 40],
                                    yticks=np.arange(0, 50, 10), xticks=(np.arange(33)-1), fsize=10-s, markersize=10-s,
                                    labelpad=10)]
        self.qwRmsMainLayout.insertWidget(0, self.qwRms)
        self.qwRms.show()

    def customizeRms(self):
        self.wg.qline_rms_level_min.setEnabled(True)
        self.wg.qline_rms_level_max.setEnabled(True)
        if self.wg.qradio_rms_chart.isChecked():
            self.wg.qplot_rms_chart.show()
            self.wg.qplot_rms_bar.hide()
            self.wg.qcombo_tpm.setEnabled(True)
            self.wg.qline_channels.setEnabled(True)

        else:
            if not self.wg.qradio_rms_power.isChecked():
                self.wg.qline_rms_level_min.setEnabled(False)
                self.wg.qline_rms_level_max.setEnabled(False)
            self.wg.qplot_rms_chart.hide()
            self.wg.qplot_rms_bar.show()
            self.wg.qcombo_tpm.setEnabled(False)
            self.wg.qline_channels.setEnabled(False)
            for t in range(len(self.qw_rms)):
                self.qp_rms[t].setTitle(self.wg.qcombo_tpm.itemText(t))
                if self.wg.qradio_rms_adu.isChecked():
                    self.qp_rms[t].showBars()
                    self.qp_rms[t].hideMarkers()
                    self.qp_rms[t].set_yticks(np.arange(0, 45, 5))
                    self.qp_rms[t].set_ylabel(" ADU RMS ")
                elif self.wg.qradio_rms_power.isChecked():
                    self.qp_rms[t].hideBars()
                    self.qp_rms[t].showMarkers()
                    self.qp_rms[t].set_ylabel(" Power (dBm) ")
                    self.qp_rms[t].set_yticks(np.arange(-35, 15, 5))
                else:
                    self.qp_rms[t].showBars()
                    self.qp_rms[t].hideMarkers()
                    self.qp_rms[t].set_yticks(np.arange(0, 36, 4))
                    self.qp_rms[t].set_ylabel(" PreADU DSA (dB) ")
                #self.qp_rms[t].set_xlabel(self.wg.qcombo_rms_label.currentText(), labelpad=10)
                if self.wg.qcombo_rms_label.currentIndex() == 0:
                    self.qp_rms[t].set_xticklabels(np.arange(32))
                else:
                    labels = []
                    for i in range(16):
                        labels += ["%d X" % (i + 1)]
                        labels += ["%d Y" % (i + 1)]
                    self.qp_rms[t].set_xticklabels(labels)
            if self.connected:
                self.updateRms()

    def setupNewTilesIPs(self, newTiles):
        if self.connected:
            self.disconnect()
        self.newTilesIPs = [x for x in newTiles if not x == '0']
        self.station_configuration['tiles'] = self.newTilesIPs
        self.updateComboIps(newTiles)

    def runAcquisition(self):
        self.live_data = self.mydaq.execute()
        self.wg.qlabel_tstamp_spectra.setText(ts_to_datestring(dt_to_timestamp(datetime.datetime.utcnow())))

    def updateRms(self):
        if self.connected:
            if self.rms:
                self.preadu.updateRms(self.rms[self.wg.qcombo_tpm.currentIndex()])
            if self.wg.qradio_rms_chart.isChecked():
                self.drawRmsCharts()
            else:
                if len(self.rms) == len(self.tpm_station.tiles):
                    dsa_remap = np.arange(32)
                    # self.wg.qlabel_tstamp_rms.setText(ts_to_datestring(dt_to_timestamp(datetime.datetime.utcnow())))
                    # ADU Map
                    rms_remap = np.arange(32)
                    colors = ['b'] * 32
                    if self.wg.qcombo_rms_label.currentIndex() == 1:
                        # ADU RF Receivers Polarization X-Y remapping
                        rms_remap = [1, 0, 3, 2, 5, 4, 7, 6,
                                     8, 9, 10, 11, 12, 13, 14, 15,
                                     17, 16, 19, 18, 21, 20, 23, 22,
                                     24, 25, 26, 27, 28, 29, 30, 31]
                        colors = ['b', 'g'] * 16
                    elif self.wg.qcombo_rms_label.currentIndex() == 2:
                        # TPM 1.2 Fibre Mapping
                        rms_remap = [1, 0, 3, 2, 5, 4, 7, 6,
                                     17, 16, 19, 18, 21, 20, 23, 22,
                                     30, 31, 28, 29, 26, 27, 24, 25,
                                     14, 15, 12, 13, 10, 11, 8, 9]
                        colors = ['b', 'g'] * 16
                    elif self.wg.qcombo_rms_label.currentIndex() == 3:
                        # TPM 1.6 RF Rx
                        rms_remap = [0, 1, 2, 3, 4, 5, 6, 7,
                                     9, 8, 11, 10, 13, 12, 15, 14,
                                     16, 17, 18, 19, 20, 21, 22, 23,
                                     25, 24, 27, 26, 29, 28, 31, 30]
                        colors = ['b', 'g'] * 16
                    elif self.wg.qcombo_rms_label.currentIndex() == 4:
                        # TPM 1.6 Fibre Mapping
                        rms_remap = [15, 14, 13, 12, 11, 10,  9,  8,
                                       6,  7,  4,  5,  2,  3, 0,  1,
                                     31, 30, 29, 28, 27, 26, 25, 24,
                                     22, 23, 20, 21, 18, 19, 16, 17]
                        colors = ['b', 'g'] * 16
                    for t in range(len(self.station_configuration['tiles'])):
                        powers = np.zeros(32)
                        for i in range(32):
                            if self.wg.qradio_rms_adu.isChecked():
                                self.qp_rms[t].plotBar(self.rms[t][rms_remap[i]], i, colors[i])
                            elif self.wg.qradio_rms_dsa.isChecked():
                                self.qp_rms[t].plotBar(self.preaduConf[t][i]['dsa'], i, 'r')
                            with np.errstate(divide='ignore', invalid='ignore'):
                                power = 10 * np.log10(np.power((self.rms[t][rms_remap[i]] * (1.7 / 256.)), 2) / 400.) + 30 + 12
                            if power == -np.inf:
                                power = -60
                            powers[i] = power
                        if self.wg.qradio_rms_power.isChecked():
                            for pol in range(2):
                                self.qp_rms[t].markers[pol].set_ydata(powers[pol::2])
                                self.qp_rms[t].markers[pol].set_markerfacecolor(colors[pol])
                                self.qp_rms[t].markers[pol].set_markeredgecolor(colors[pol])
                        self.qp_rms[t].updatePlot()
                else:
                    print("ERROR Reading RMS: got less data (tiles = %d)" % len(self.rms))

    def updatePlots(self):
        self.plotAcquisition()

    def updateTempPlot(self):
        # Draw Bars
        #print("TEMPERATURE: ", self.temperatures)
        if self.connected:
            if not self.temperatures == []:
                if len(self.temperatures) == len(self.tpm_station.tiles):
                    for i in range(len(self.tpm_station.tiles)):
                        self.tempBoardPlots.plotBar(data=float(self.temperatures[i][0]), bar=i, color=COLORI[i])
                        self.tempFpga1Plots.plotBar(data=float(self.temperatures[i][1]), bar=i, color=COLORI[i])
                        self.tempFpga2Plots.plotBar(data=float(self.temperatures[i][2]), bar=i, color=COLORI[i])
                    self.tempBoardPlots.set_xlabel("Board")
                    self.tempFpga1Plots.set_xlabel("FPGA1")
                    self.tempFpga2Plots.set_xlabel("FPGA2")
                else:
                    self.tempBoardPlots.set_xlabel("Error Reading Temps from TPMs!")
                    self.tempFpga1Plots.set_xlabel("Error Reading Temps from TPMs!")
                    self.tempFpga2Plots.set_xlabel("Error Reading Temps from TPMs!")
            else:
                self.tempBoardPlots.set_xlabel("No data available!")
                self.tempFpga1Plots.set_xlabel("No data available!")
                self.tempFpga2Plots.set_xlabel("No data available!")
            self.tempBoardPlots.updatePlot()
            self.tempFpga1Plots.updatePlot()
            self.tempFpga2Plots.updatePlot()
            # Draw Charts
            self.drawTempCharts()

    def drawTempCharts(self):
        self.tempChart.set_xlabel("time sample")
        # Draw selected chart
        if self.wg.qcombo_chart.currentIndex() == 0:
            self.tempChart.set_ylabel("TPM Board Temperatures (deg)")
        elif self.wg.qcombo_chart.currentIndex() == 1:
            self.tempChart.set_ylabel("TPM FPGA1 Temperatures (deg)")
        elif self.wg.qcombo_chart.currentIndex() == 2:
            self.tempChart.set_ylabel("TPM FPGA2 Temperatures (deg)")
        # Chart: TPM Temperatures
        self.tempChart.set_ylim([20, 120])
        for i in range(len(self.data_temp_charts.keys())):
            self.tempChart.plotCurve(data=np.array(self.data_temp_charts["TPM-%02d" % (i + 1)]).transpose()[
                self.wg.qcombo_chart.currentIndex()], trace=i, color=COLORI[i])
        self.tempChart.updatePlot()

    def drawRmsCharts(self):
        self.rmsChart.set_xlabel("time sample")
        self.rmsChart.set_ylim([float(self.wg.qline_rms_level_min.text()), float(self.wg.qline_rms_level_max.text())])
        for i in range(32):
            self.rmsChart.plotCurve(data=self.data_rms_charts["TPM-%02d" % (self.wg.qcombo_tpm.currentIndex() + 1)][i::32], trace=i, color=COLORI[i])
        self.rmsChart.updatePlot()

    def plotAcquisition(self):
        if not self.RunBusy:
            if not self.wg.qline_channels.text() == self.live_channels:
                self.reformat_plots()

        self.resolutions = 2 ** np.array(range(16)) * (800000.0 / 2 ** 15)
        self.rbw = int(closest(self.resolutions, float(self.wg.qline_rbw.text())))
        self.avg = 2 ** self.rbw
        self.nsamples = int(2 ** 15 / self.avg)
        self.RBW = (self.avg * (400000.0 / 16384.0))
        self.asse_x = np.arange(self.nsamples / 2 + 1) * self.RBW * 0.001

        xAxisRange = (float(self.wg.qline_spectra_band_from.text()),
                      float(self.wg.qline_spectra_band_to.text()))
        yAxisRange = (float(self.wg.qline_spectra_level_min.text()),
                      float(self.wg.qline_spectra_level_max.text()))

        # print("RECEIVED DATA: %d" % len(self.live_data[int(self.wg.qcombo_tpm.currentIndex())]))
        lw = 1
        if self.wg.qcheck_spectra_noline.isChecked():
            lw = 0
        if not self.live_data == []:
            #self.livePlots.plotClear()
            for n, i in enumerate(self.live_input_list):
                # Plot X Pol
                spettro, rms = calcolaspettro(self.live_data[int(self.wg.qcombo_tpm.currentIndex())][i - 1, 0, :],
                                                self.nsamples)
                self.livePlots.plotCurve(self.asse_x, spettro, n, xAxisRange=xAxisRange,
                                         yAxisRange=yAxisRange, title="INPUT-%02d" % i,
                                         xLabel="MHz", yLabel="dB", colore="b", rfpower=rms,
                                         annotate_rms=self.show_rms, grid=self.show_spectra_grid, lw=lw,
                                         show_line=self.wg.qcheck_xpol_sp.isChecked())

                # Plot Y Pol
                spettro, rms = calcolaspettro(self.live_data[int(self.wg.qcombo_tpm.currentIndex())][i - 1, 1, :],
                                              self.nsamples)
                self.livePlots.plotCurve(self.asse_x, spettro, n, xAxisRange=xAxisRange,
                                         yAxisRange=yAxisRange, colore="g", rfpower=rms,
                                         annotate_rms=self.show_rms, grid=self.show_spectra_grid, lw=lw,
                                         show_line=self.wg.qcheck_ypol_sp.isChecked())
            self.livePlots.updatePlot()

    def doSingleAcquisition(self):
        self.getAcquisition()
        self.plotAcquisition()
        #self.wg.qbutton_run.setEnabled(True)

    def startContinuousAcquisition(self):
        if self.connected:
            self.ThreadPause = False
            self.wg.qbutton_run.setEnabled(False)
            self.wg.qbutton_single.setEnabled(False)
            self.wg.qline_channels.setEnabled(False)
            self.wg.qline_rbw.setEnabled(False)
            self.wg.qline_spectra_level_min.setEnabled(False)
            self.wg.qline_spectra_level_max.setEnabled(False)
            self.wg.qline_spectra_band_from.setEnabled(False)
            self.wg.qline_spectra_band_to.setEnabled(False)

    def stopContinuousAcquisition(self):
        self.ThreadPause = True
        self.wg.qbutton_single.setEnabled(True)
        self.wg.qbutton_run.setEnabled(True)
        self.wg.qline_channels.setEnabled(True)
        self.wg.qline_rbw.setEnabled(True)
        self.wg.qline_spectra_level_min.setEnabled(True)
        self.wg.qline_spectra_level_max.setEnabled(True)
        self.wg.qline_spectra_band_from.setEnabled(True)
        self.wg.qline_spectra_band_to.setEnabled(True)

    def getAcquisition(self):
        if self.connected:
            if self.mydaq is not None:
                self.runAcquisition()
            else:
                msgBox = QtWidgets.QMessageBox()
                msgBox.setText("The DAQ is not running, please check the setup")
                msgBox.setWindowTitle("Error!")
                msgBox.setIcon(QtWidgets.QMessageBox.Critical)
                msgBox.exec_()
        else:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Please connect to the STATION first!")
            msgBox.setWindowTitle("Error!")
            msgBox.setIcon(QtWidgets.QMessageBox.Critical)
            msgBox.exec_()

    def updateComboIps(self, tpm_list=list):
        # Update TPM list
        self.wg.qcombo_tpm.clear()
        for nn, i in enumerate(tpm_list):
            if not i == "0":
                self.wg.qcombo_tpm.addItem("TPM-%02d (%s)" % (nn + 1, i))

    def export_data(self):
        if self.wg.play_qradio_spectrogram.isChecked():
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Spectrogram Data Export is not yet implemented")
            msgBox.setWindowTitle("Message")
            msgBox.exec_()
            pass
        elif self.wg.play_qradio_oplot.isChecked():
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Oplot Data Export is not yet implemented")
            msgBox.setWindowTitle("Message")
            msgBox.exec_()
            pass
        elif self.wg.play_qradio_avg.isChecked():
            pass
        elif self.wg.play_qradio_power.isChecked():
            pass
        elif self.wg.play_qradio_raw.isChecked():
            result = QtWidgets.QMessageBox.question(self, "Export Data...",
                        "Are you sure you want to export %d files?" % (len(self.input_list)),
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if result == QtWidgets.QMessageBox.Yes:
                print("Saving data")
            else:
                print("ciao")

    def channelsListModified(self):
        if not self.wg.qline_channels.text() == self.live_channels:
            self.wg.qbutton_run.setEnabled(False)

    def reformat_plots(self):
        try:
            new_input_list = decodeChannelList(self.wg.qline_channels.text())
            self.livePlots.plotClear()
            del self.livePlots
            gc.collect()
            self.live_input_list = new_input_list
            self.livePlots = MiniPlots(parent=self.wg.qplot_spectra, nplot=len(self.live_input_list))
            self.live_channels = self.wg.qline_channels.text()
        except ValueError:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Value Error: please check the Channels string syntax")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()

    def live_show_spectra_grid(self, state):
        if state == Qt.Checked:
            self.show_spectra_grid = True
            self.livePlots.showGrid(show_grid=True)
        else:
            self.show_spectra_grid = False
            self.livePlots.showGrid(show_grid=False)

    def closeEvent(self, event):
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Exit...",
                                                "Are you sure you want to exit ?",
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        event.ignore()

        if result == QtWidgets.QMessageBox.Yes:
            event.accept()
            self.stopThreads = True
            sleep(1)
            if self.monitor_daq is not None:
                self.monitor_daq.stop_daq()


if __name__ == "__main__":
    from optparse import OptionParser
    from sys import argv, stdout

    parser = OptionParser(usage="usage: %station_live [options]")
    parser.add_option("--config", action="store", dest="config",
                      type="str", default=None, help="Configuration file [default: None]")
    parser.add_option("--nogui", action="store_true", dest="nogui",
                      default=False, help="Do not show GUI")
    parser.add_option("--temperatures", action="store_true", dest="temperatures",
                      default=False, help="Acquire and save temperatures")
    parser.add_option("--profile", action="store", dest="profile",
                      type="str", default="Default", help="Live Profile file to load")
    (opt, args) = parser.parse_args(argv[1:])

    if not opt.nogui:
        app = QtWidgets.QApplication(sys.argv)
        window = Live(config=opt.config, uiFile="skalab_live.ui")
        window.signalTemp.connect(window.updateTempPlot)
        window.signalRms.connect(window.updateRms)
        sys.exit(app.exec_())
    else:
        profile = []
        fullpath = default_app_dir + opt.profile + "/" + profile_filename
        if not os.path.exists(fullpath):
            print("\nThe Live Profile does not exist.\n")
        else:
            print("Loading Live Profile: " + opt.profile + " (" + fullpath + ")")
            profile = parse_profile(fullpath)
            profile_name = profile
            profile_file = fullpath
            if not opt.config == "":
                station_config = opt.config
            else:
                station_config = profile['App']['station_config']
            if not station_config == "":
                station.load_configuration_file(station_config)
                # Create station
                tpm_station = Station(station.configuration)
                # Connect station (program, initialise and configure if required)
                tpm_station.connect()

                if opt.temperatures:
                    temp_path = ""
                    if "temperatures_path" in profile['App'].keys():
                        temp_path = profile['App']['temperatures_path']
                    if not temp_path == "":
                        if not temp_path[-1] == "/":
                            temp_path = temp_path + "/"
                        fname = datetime.datetime.strftime(datetime.datetime.utcnow(),
                                                           "%Y-%m-%d_%H%M%S_StationTemperatures.h5")
                        temp_file = Archive(hfile=temp_path + fname, mode='a')
                        while True:
                            tstamp = dt_to_timestamp(datetime.datetime.utcnow())
                            temp_file.write(name="timestamp", data=tstamp)
                            try:
                                for n, tile in enumerate(tpm_station.tiles):
                                    tris = [tile.get_temperature(),  tile.get_fpga0_temperature(),
                                            tile.get_fpga1_temperature()]
                                    temp_file.write(name=("TPM-%02d" % (n + 1)), data=tris)
                                    print("TPM-%02d Temperatures: Board %3.1f,\tFPGA-0 %3.1f,\tFPGA-1 %3.1f" %
                                          (n + 1, tris[0], tris[1], tris[2]))
                                sleep(1)
                            except KeyboardInterrupt:
                                print("\n\nTerminated by the user.\n\n")
                                temp_file.close()
                                print("File closed: ", temp_path + fname, "\n")
                                break
                            except:
                                print("ERROR SAVING TEMPERATURES!")
                                temp_file.close()
                                print("File closed: ", temp_path + fname, "\n")
                                break
                    else:
                        print("There is no any temperatures path specified in the profile file.\n")
            else:
                print("The profile File doesn't have a Station Configuration File.\n")
