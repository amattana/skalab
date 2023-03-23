#!/usr/bin/env python
"""

   The SKA in LAB Project

   Easy and Quick Access Monitor and Control the SKA-LFAA Devices in Lab based on aavs-system

   Supported Devices are:

      - TPM_1_2 and TPM_1_6
      - SubRack with WebServer API

"""

__copyright__ = "Copyright 2023, Istituto di RadioAstronomia, Radiotelescopi di Medicina, INAF, Italy"
__author__ = "Andrea Mattana"
__credits__ = ["Andrea Mattana"]
__license__ = "GPL"
__version__ = "1.3.1"
__release__ = "2023-03-22"
__maintainer__ = "Andrea Mattana"

import gc
import shutil
import socket
import sys
import os
import time
from threading import Thread

import numpy as np
import configparser
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from pyaavs import station
from pyfabil import TPMGeneric
from pyfabil.base.definitions import LibraryError, BoardError, PluginError, InstrumentError

from skalab_live import Live
from skalab_playback import Playback
from skalab_subrack import Subrack
from skalab_monitor import Monitor
from skalab_utils import parse_profile, getTextFromFile
from pathlib import Path

default_app_dir = str(Path.home()) + "/.skalab/"
default_profile = "Default"
profile_filename = "skalab.ini"

COLORI = ["b", "g"]

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


class SkaLab(QtWidgets.QMainWindow):
    """ Main UI Window class """

    def __init__(self, uiFile, profile="Default"):
        """ Initialise main window """
        super(SkaLab, self).__init__()
        #super(SkalabBase, self).__init__(App="", Profile="", Path="")
        # Load window file
        self.wg = uic.loadUi(uiFile)
        self.setCentralWidget(self.wg)
        self.resize(1210, 970)
        self.setWindowTitle("The SKA in LAB Project")
        self.profile = {'App': {'subrack': "",
                                'monitor': "",
                                'live': "",
                                'playback': ""},
                        'Init': {'station_setup': ""}}
        self.profile_name = ""
        self.profile_file = ""
        self.text_editor = ""
        self.load_profile(profile)
        self.updateProfileCombo(current=self.profile_name)

        self.config_file = ""
        if self.profile_name:
            self.config_file = self.profile['Init']['station_file']
            self.wg.qline_configfile.setText(self.config_file)
        self.tpm_station = None
        self.doInit = False
        self.stopThreads = False
        self.processInit = Thread(target=self.do_station_init)
        self.processInit.start()

        self.tabSubrackIndex = 1
        self.tabMonitorIndex = 2
        self.tabLiveIndex = 3
        self.tabPlayIndex = 4


        self.pic_ska = QtWidgets.QLabel(self.wg.qwpics)
        self.pic_ska.setGeometry(1, 1, 489, 120)
        self.pic_ska.setPixmap(QtGui.QPixmap(os.getcwd() + "/Pictures/ska_inaf_logo.png"))

        self.pic_ska_help = QtWidgets.QLabel(self.wg.qwpics_help)
        self.pic_ska_help.setGeometry(1, 1, 489, 120)
        self.pic_ska_help.setPixmap(QtGui.QPixmap(os.getcwd() + "/Pictures/ska_inaf_logo.png"))
        self.wg.qlabel_sw_version.setText("Version: " + __version__)
        self.wg.qlabel_sw_release.setText("Released on: " + __release__)
        self.wg.qlabel_sw_author.setText("Author: " + __author__)

        QtWidgets.QTabWidget.setTabVisible(self.wg.qtabMain, self.tabMonitorIndex, True)
        self.wgMonitorLayout = QtWidgets.QVBoxLayout()
        self.wgMonitor = Monitor(self.config_file, uiFile="skalab_monitor.ui", size=[1190, 936],
                                 profile=self.profile['Base']['monitor'],
                                 swpath=default_app_dir)
        self.wgMonitorLayout.addWidget(self.wgMonitor)
        self.wg.qwMonitor.setLayout(self.wgMonitorLayout)
        self.wgMonitor.dst_port = configuration['network']['lmc']['lmc_port']
        self.wgMonitor.lmc_ip = configuration['network']['lmc']['lmc_ip']
        self.wgMonitor.cpld_port = configuration['network']['lmc']['tpm_cpld_port']

        QtWidgets.QTabWidget.setTabVisible(self.wg.qtabMain, self.tabLiveIndex, True)
        self.wgLiveLayout = QtWidgets.QVBoxLayout()
        self.wgLive = Live(self.config_file, "skalab_live.ui", size=[1190, 936],
                           profile=self.profile['Base']['live'],
                           swpath=default_app_dir)
        self.wgLive.signalTemp.connect(self.wgLive.updateTempPlot)
        self.wgLive.signalRms.connect(self.wgLive.updateRms)

        self.wgLiveLayout.addWidget(self.wgLive)
        self.wg.qwLive.setLayout(self.wgLiveLayout)

        QtWidgets.QTabWidget.setTabVisible(self.wg.qtabMain, self.tabPlayIndex, True)
        self.wgPlayLayout = QtWidgets.QVBoxLayout()
        self.wgPlay = Playback(self.config_file, "skalab_playback.ui", size=[1190, 936],
                               profile=self.profile['Base']['playback'],
                               swpath=default_app_dir)
        self.wgPlayLayout.addWidget(self.wgPlay)
        self.wg.qwPlay.setLayout(self.wgPlayLayout)

        QtWidgets.QTabWidget.setTabVisible(self.wg.qtabMain, self.tabSubrackIndex, True)
        self.wgSubrackLayout = QtWidgets.QVBoxLayout()
        self.wgSubrack = Subrack(self.wgMonitor, uiFile="skalab_subrack.ui", size=[1190, 936],
                                 profile=self.profile['Base']['subrack'],
                                 swpath=default_app_dir)
        self.wgSubrackLayout.addWidget(self.wgSubrack)
        self.wg.qwSubrack.setLayout(self.wgSubrackLayout)
        self.wgSubrack.signalTlm.connect(self.wgSubrack.updateTlm)
        self.wgSubrack.signal_to_monitor.connect(self.wgMonitor.read_subrack_attribute)
        self.wgSubrack.signal_to_monitor_for_tpm.connect(self.wgMonitor.tpm_status_changed)

        self.show()
        self.load_events()

        self.station_name = ""
        self.folder = ""
        self.nof_files = 0
        self.nof_tiles = 0
        self.data_tiles = []
        self.nof_antennas = 0
        self.bitfile = ""
        self.truncation = 0
        self.resolutions = 2 ** np.array(range(16)) * (800000.0 / 2 ** 15)
        self.rbw = 100
        self.avg = 2 ** self.rbw
        self.nsamples = int(2 ** 15 / self.avg)
        self.RBW = (self.avg * (400000.0 / 16384.0))
        self.asse_x = np.arange(self.nsamples/2 + 1) * self.RBW * 0.001

        self.input_list = np.arange(1, 17)

        self.tiles = []
        self.data = []
        self.power = {}
        self.raw = {}
        self.rms = {}
        if self.config_file:
            self.setup_config()
        self.populate_help()

    def load_events(self):
        self.wg.qbutton_browse.clicked.connect(lambda: self.browse_config())
        self.wg.qbutton_edit.clicked.connect(lambda: self.edit_config())
        self.wg.qbutton_load_configuration.clicked.connect(lambda: self.setup_config())
        self.wg.qbutton_profile_save.clicked.connect(lambda: self.save_profile(self.wg.qcombo_profiles.currentText()))
        self.wg.qbutton_profile_saveas.clicked.connect(lambda: self.save_as_profile())
        self.wg.qbutton_profile_load.clicked.connect(lambda: self.reload_profile(self.wg.qcombo_profiles.currentText()))
        self.wg.qbutton_profile_delete.clicked.connect(lambda: self.delete_profile(self.wg.qcombo_profiles.currentText()))
        self.wg.qbutton_station_init.clicked.connect(lambda: self.station_init())

    def edit_config(self):
        if not self.text_editor == "":
            fname = self.wg.qline_configfile.text()
            if not fname == "":
                if os.path.exists(fname):
                    os.system(self.text_editor + " " + fname + " &")
                else:
                    msgBox = QtWidgets.QMessageBox()
                    msgBox.setText("The selected config file does not exist!")
                    msgBox.setWindowTitle("Error!")
                    msgBox.exec_()
        else:
            msgBox = QtWidgets.QMessageBox()
            txt = "\nA text editor is not defined in the current profile file.\n\n['Extras']\ntext_editor = <example: gedit>'\n\n"
            msgBox.setText(txt)
            msgBox.setWindowTitle("Warning!")
            msgBox.setIcon(QtWidgets.QMessageBox.Warning)
            msgBox.exec_()

    def load_profile(self, profile):
        if not profile == "":
            self.profile = []
            fullpath = default_app_dir + profile + "/" + profile_filename
            if os.path.exists(fullpath):
                print("Loading Skalab Profile: " + profile + " (" + fullpath + ")")
            else:
                print("\nThe Skalab Profile does not exist.\nGenerating a new one in "
                      + fullpath + "\n")
                self.make_profile(profile=profile)
            self.profile = parse_profile(fullpath)
            self.profile_name = profile
            self.profile_file = fullpath
            self.wg.qline_profile.setText(fullpath)

            if not self.profile.sections():
                msgBox = QtWidgets.QMessageBox()
                msgBox.setText("Cannot find this profile!")
                msgBox.setWindowTitle("Error!")
                msgBox.exec_()
            else:
                self.config_file = self.profile['Init']['station_file']
                self.wg.qline_configfile.setText(self.config_file)
                self.populate_table_profile()
                if 'Extras' in self.profile.keys():
                    if 'text_editor' in self.profile['Extras'].keys():
                        self.text_editor = self.profile['Extras']['text_editor']

    def reload_profile(self, profile):
        self.load_profile(profile=profile)
        if self.profile.sections():
            if self.profile['Base']['subrack']:
                self.wgSubrack.load_profile(App="subrack", Profile=self.profile['Base']['subrack'], Path=default_app_dir)
            if self.profile['Base']['monitor']:
                self.wgMonitor.load_profile(App="monitor", Profile=self.profile['Base']['monitor'], Path=default_app_dir)
            if self.profile['Base']['live']:
                self.wgLive.load_profile(App="live", Profile=self.profile['Base']['live'], Path=default_app_dir)
            if self.profile['Base']['playback']:
                self.wgPlay.load_profile(App="playback", Profile=self.profile['Base']['playback'], Path=default_app_dir)

    def delete_profile(self, profile):
        if os.path.exists(default_app_dir + profile):
            shutil.rmtree(default_app_dir + profile)
        self.updateProfileCombo(current="")
        self.load_profile(self.wg.qcombo_profiles.currentText())

    def updateProfileCombo(self, current):
        profiles = []
        for d in os.listdir(default_app_dir):
            if os.path.exists(default_app_dir + d + "/skalab.ini"):
                profiles += [d]
        if profiles:
            self.wg.qcombo_profiles.clear()
            for n, p in enumerate(profiles):
                self.wg.qcombo_profiles.addItem(p)
                if current == p:
                    self.wg.qcombo_profiles.setCurrentIndex(n)

    def populate_help(self, uifile="skalab_main.ui"):
        with open(uifile) as f:
            data = f.readlines()
        helpkeys = [d[d.rfind('name="Help_'):].split('"')[1] for d in data if 'name="Help_' in d]
        for k in helpkeys:
            self.wg.findChild(QtWidgets.QTextEdit, k).setText(getTextFromFile(k.replace("_", "/")+".html"))

    def browse_config(self):
        fd = QtWidgets.QFileDialog()
        fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        options = fd.options()
        self.config_file = fd.getOpenFileName(self, caption="Select a Station Config File...",
                                              directory="/opt/aavs/config/", options=options)[0]
        self.wg.qline_configfile.setText(self.config_file)

    def setup_config(self):
        if not self.config_file == "":
            self.wgPlay.config_file = self.config_file
            self.wgLive.config_file = self.config_file
            station.load_configuration_file(self.config_file)
            self.station_name = station.configuration['station']['name']
            self.nof_tiles = len(station.configuration['tiles'])
            self.nof_antennas = int(station.configuration['station']['number_of_antennas'])
            self.bitfile = station.configuration['station']['bitfile']
            if len(self.bitfile) > 52:
                self.wg.qlabel_bitfile.setText("..." + self.bitfile[-52:])
            else:
                self.wg.qlabel_bitfile.setText(self.bitfile)
            self.truncation = int(station.configuration['station']['channel_truncation'])
            self.populate_table_station()
            if not self.wgPlay == None:
                self.wgPlay.wg.qcombo_tpm.clear()
            if not self.wgLive == None:
                self.wgLive.wg.qcombo_tpm.clear()
            self.tiles = []
            for n, i in enumerate(station.configuration['tiles']):
                if not self.wgPlay == None:
                    self.wgPlay.wg.qcombo_tpm.addItem("TPM-%02d (%s)" % (n + 1, i))
                if not self.wgLive == None:
                    self.wgLive.wg.qcombo_tpm.addItem("TPM-%02d (%s)" % (n + 1, i))
                self.tiles += [i]
        else:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("SKALAB: Please SELECT a valid configuration file first...")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()

    def station_init(self):
        result = QtWidgets.QMessageBox.question(self, "Confirm Action -IP",
                                                "Are you sure to Program and Init the Station?",
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if result == QtWidgets.QMessageBox.Yes:
            if self.config_file:
                # Create station
                station.load_configuration_file(self.config_file)
                # Check wether the TPM are ON or OFF
                station_on = True
                tpm_ip_list = list(station.configuration['tiles'])
                tpm_ip_from_subrack = self.wgSubrack.getTiles()
                if tpm_ip_from_subrack:
                    tpm_ip_from_subrack_short = [x for x in tpm_ip_from_subrack if not x == '0']
                    if not len(tpm_ip_list) == len(tpm_ip_from_subrack_short):
                        msgBox = QtWidgets.QMessageBox()
                        message = "STATION\nOne or more TPMs forming the station are OFF\nPlease check the power!"
                        msgBox.setText(message)
                        msgBox.setWindowTitle("ERROR: TPM POWERED OFF")
                        msgBox.setIcon(QtWidgets.QMessageBox.Critical)
                        details = "STATION IP LIST FROM CONFIG FILE (%d): " % len(tpm_ip_list)
                        for i in tpm_ip_list:
                            details += "\n%s" % i
                        details += "\n\nSUBRACK IP LIST OF TPM POWERED ON: (%d): " % len(tpm_ip_from_subrack_short)
                        for i in tpm_ip_from_subrack_short:
                            details += "\n%s" % i
                        msgBox.setDetailedText(details)
                        msgBox.exec_()
                        print(self.wgSubrack.telemetry)
                        return
                    else:
                        if not np.array_equal(tpm_ip_list, tpm_ip_from_subrack_short):
                            msgBox = QtWidgets.QMessageBox()
                            message = "STATION\nIPs provided by the SubRack are different from what defined in the " \
                                      "config file.\nINIT will use the new assigned IPs."
                            msgBox.setText(message)
                            msgBox.setWindowTitle("WARNING: IP mismatch")
                            msgBox.setIcon(QtWidgets.QMessageBox.Warning)
                            details = "STATION IP LIST FROM CONFIG FILE (%d): " % len(tpm_ip_list)
                            for i in tpm_ip_list:
                                details += "\n%s" % i
                            details += "\n\nSUBRACK IP LIST OF TPM POWERED ON: (%d): " % len(tpm_ip_from_subrack_short)
                            for i in tpm_ip_from_subrack_short:
                                details += "\n%s" % i
                            msgBox.setDetailedText(details)
                            msgBox.exec_()
                            station.configuration['tiles'] = list(tpm_ip_from_subrack_short)
                            self.wgLive.setupNewTilesIPs(list(tpm_ip_from_subrack))
                for tpm_ip in station.configuration['tiles']:
                    try:
                        tpm = TPMGeneric()
                        tpm_version = tpm.get_tpm_version(socket.gethostbyname(tpm_ip), 10000)
                    except (BoardError, LibraryError):
                        station_on = False
                        break
                if station_on:
                    self.doInit = True
                else:
                    msgBox = QtWidgets.QMessageBox()
                    msgBox.setText("STATION\nOne or more TPMs forming the station is unreachable\n"
                                   "Please check the power or the connection!")
                    msgBox.setWindowTitle("ERROR: TPM UNREACHABLE")
                    msgBox.setIcon(QtWidgets.QMessageBox.Critical)
                    details = "STATION IP LIST FROM CONFIG FILE (%d): " % len(tpm_ip_list)
                    for i in tpm_ip_list:
                        details += "\n%s" % i
                    details += "\n\nSUBRACK IP LIST OF TPM POWERED ON: (%d): " % len(tpm_ip_from_subrack)
                    for i in tpm_ip_from_subrack:
                        details += "\n%s" % i
                    msgBox.setDetailedText(details)
                    msgBox.exec_()
            else:
                msgBox = QtWidgets.QMessageBox()
                msgBox.setText("SKALAB: Please LOAD a configuration file first...")
                msgBox.setWindowTitle("Error!")
                msgBox.setIcon(QtWidgets.QMessageBox.Critical)
                msgBox.exec_()

    def do_station_init(self):
        while True:
            if self.doInit:
                station.configuration['station']['initialise'] = True
                station.configuration['station']['program'] = True
                try:
                    self.tpm_station = station.Station(station.configuration)
                    self.wg.qbutton_station_init.setEnabled(False)
                    self.tpm_station.connect()
                    station.configuration['station']['initialise'] = False
                    station.configuration['station']['program'] = False
                    if self.tpm_station.properly_formed_station:
                        self.wg.qbutton_station_init.setStyleSheet("background-color: rgb(78, 154, 6);")

                        # if not self.tpm_station.tiles[0].tpm_version() == "tpm_v1_2":
                        #     # ByPass the MCU temperature controls on TPM 1.6
                        #     for tile in self.tpm_station.tiles:
                        #         tile[0x90000034] = 0xBADC0DE
                        #         tile[0x30000518] = 1
                        #         time.sleep(0.1)
                        #     time.sleep(1)
                        #     print("MCU Controls Hacked with \nVal 0xBADC0DE in Reg 0x90000034,"
                        #           "\nVal 0x0000001 in Reg 0x30000518")

                        # Switch On the PreADUs
                        for tile in self.tpm_station.tiles:
                            tile["board.regfile.enable.fe"] = 1
                            time.sleep(0.1)
                        time.sleep(1)
                        self.tpm_station.set_preadu_attenuation(0)
                        print("TPM PreADUs Powered ON")

                    else:
                        self.wg.qbutton_station_init.setStyleSheet("background-color: rgb(204, 0, 0);")
                    self.wg.qbutton_station_init.setEnabled(True)
                    del self.tpm_station
                    gc.collect()
                except:
                    self.wg.qbutton_station_init.setEnabled(True)
                self.tpm_station = None
                self.doInit = False
            if self.stopThreads:
                break
            time.sleep(0.3)

    def populate_table_profile(self):
        #self.wg.qtable_profile = QtWidgets.QTableWidget(self.wg.qtabMain)
        #self.wg.qtable_profile.setGeometry(QtCore.QRect(20, 575, 461, 351))
        self.wg.qtable_profile.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.wg.qtable_profile.setObjectName("qtable_profile")
        self.wg.qtable_profile.setColumnCount(1)
        nrows = len(self.profile.sections())
        for i in self.profile.sections():
            nrows = nrows + len(self.profile[i].keys()) + 1
        self.wg.qtable_profile.setRowCount(nrows)

        # Header Horizontal
        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignLeading | QtCore.Qt.AlignVCenter)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        item.setFont(font)
        self.wg.qtable_profile.setHorizontalHeaderItem(0, item)
        item = self.wg.qtable_profile.horizontalHeaderItem(0)
        item.setText("Profile: " + self.profile_name)
        __sortingEnabled = self.wg.qtable_profile.isSortingEnabled()
        self.wg.qtable_profile.setSortingEnabled(False)

        row = 0
        for k in self.profile.sections():
            # Empty Row
            item = QtWidgets.QTableWidgetItem()
            self.wg.qtable_profile.setVerticalHeaderItem(row, item)
            item = self.wg.qtable_profile.verticalHeaderItem(row)
            item.setText(" ")
            item = QtWidgets.QTableWidgetItem()
            item.setText(" ")
            self.wg.qtable_profile.setItem(row, 0, item)
            row = row + 1

            item = QtWidgets.QTableWidgetItem()
            font = QtGui.QFont()
            font.setBold(True)
            font.setWeight(75)
            item.setFont(font)
            item.setText("[" + k + "]")
            self.wg.qtable_profile.setVerticalHeaderItem(row, item)
            row = row + 1

            for s in self.profile[k].keys():
                item = QtWidgets.QTableWidgetItem()
                self.wg.qtable_profile.setVerticalHeaderItem(row, item)
                item = self.wg.qtable_profile.verticalHeaderItem(row)
                item.setText(s)
                item = QtWidgets.QTableWidgetItem()
                item.setText(self.profile[k][s])
                self.wg.qtable_profile.setItem(row, 0, item)
                row = row + 1

        self.wg.qtable_profile.horizontalHeader().setDefaultSectionSize(365)
        self.wg.qtable_profile.setSortingEnabled(__sortingEnabled)

    def populate_table_station(self):
        # TABLE STATION
        self.wg.qtable_station.clearSpans()
        #self.wg.qtable_station.setGeometry(QtCore.QRect(20, 140, 171, 31))
        self.wg.qtable_station.setObjectName("conf_qtable_station")
        self.wg.qtable_station.setColumnCount(1)
        self.wg.qtable_station.setRowCount(len(station.configuration['station'].keys()) - 1)
        n = 0
        for i in station.configuration['station'].keys():
            if not i == "bitfile":
                self.wg.qtable_station.setVerticalHeaderItem(n, QtWidgets.QTableWidgetItem(i.upper()))
                n = n + 1

        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        item.setFont(font)
        item.setText("SECTION: STATION")
        self.wg.qtable_station.setHorizontalHeaderItem(0, item)
        __sortingEnabled = self.wg.qtable_station.isSortingEnabled()
        self.wg.qtable_station.setSortingEnabled(False)
        n = 0
        for i in station.configuration['station'].keys():
            if not i == "bitfile":
                item = QtWidgets.QTableWidgetItem(str(station.configuration['station'][i]))
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wg.qtable_station.setItem(n, 0, item)
                n = n + 1
        self.wg.qtable_station.horizontalHeader().setStretchLastSection(True)
        self.wg.qtable_station.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wg.qtable_station.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wg.qtable_station.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

        # TABLE TPM
        self.wg.qtable_tpm.clearSpans()
        #self.wg.qtable_tpm.setGeometry(QtCore.QRect(20, 180, 511, 141))
        self.wg.qtable_tpm.setObjectName("conf_qtable_tpm")
        self.wg.qtable_tpm.setColumnCount(2)
        self.wg.qtable_tpm.setRowCount(len(station.configuration['tiles']))
        for i in range(len(station.configuration['tiles'])):
            self.wg.qtable_tpm.setVerticalHeaderItem(i, QtWidgets.QTableWidgetItem("TPM-%02d" % (i + 1)))
        item = QtWidgets.QTableWidgetItem("IP ADDR")
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        item.setFont(font)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.wg.qtable_tpm.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem("DELAYS")
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        item.setFont(font)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.wg.qtable_tpm.setHorizontalHeaderItem(1, item)
        for n, i in enumerate(station.configuration['tiles']):
            item = QtWidgets.QTableWidgetItem(str(i))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wg.qtable_tpm.setItem(n, 0, item)
        for n, i in enumerate(station.configuration['time_delays']):
            item = QtWidgets.QTableWidgetItem(str(i))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wg.qtable_tpm.setItem(n, 1, item)
        self.wg.qtable_tpm.horizontalHeader().setStretchLastSection(True)
        self.wg.qtable_tpm.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wg.qtable_tpm.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wg.qtable_tpm.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

        # TABLE NETWORK
        self.wg.qtable_network.clearSpans()
        #self.wg.qtable_network.setGeometry(QtCore.QRect(600, 230, 511, 481))
        self.wg.qtable_network.setObjectName("conf_qtable_network")
        self.wg.qtable_network.setColumnCount(1)

        total_rows = len(station.configuration['network'].keys()) * 2 - 1
        for i in station.configuration['network'].keys():
            total_rows += len(station.configuration['network'][i])
        self.wg.qtable_network.setRowCount(total_rows)
        item = QtWidgets.QTableWidgetItem("SECTION: NETWORK")
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        item.setFont(font)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        self.wg.qtable_network.setHorizontalHeaderItem(0, item)
        n = 0
        for i in station.configuration['network'].keys():
            if n:
                item = QtWidgets.QTableWidgetItem(" ")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wg.qtable_network.setVerticalHeaderItem(n, item)
                item = QtWidgets.QTableWidgetItem(" ")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wg.qtable_network.setItem(n, 0, item)
                n = n + 1
            self.wg.qtable_network.setVerticalHeaderItem(n, QtWidgets.QTableWidgetItem(str(i).upper()))
            item = QtWidgets.QTableWidgetItem(" ")
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wg.qtable_network.setItem(n, 0, item)
            n = n + 1
            for k in sorted(station.configuration['network'][i].keys()):
                self.wg.qtable_network.setVerticalHeaderItem(n, QtWidgets.QTableWidgetItem(str(k).upper()))
                if "MAC" in str(k).upper() and not str(station.configuration['network'][i][k]) == "None":
                    item = QtWidgets.QTableWidgetItem(hex(station.configuration['network'][i][k]).upper())
                else:
                    item = QtWidgets.QTableWidgetItem(str(station.configuration['network'][i][k]))
                item.setTextAlignment(QtCore.Qt.AlignLeft)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wg.qtable_network.setItem(n, 0, item)
                n = n + 1
        self.wg.qtable_network.horizontalHeader().setStretchLastSection(True)
        self.wg.qtable_network.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wg.qtable_network.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wg.qtable_network.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

    def make_profile(self, profile="Default", subrack="Default", monitor="Default", live="Default", playback="Default", config=""):
        conf = configparser.ConfigParser()
        conf['Base'] = {'subrack': subrack,
                        'monitor': monitor,
                        'live': live,
                        'playback': playback}
        conf['Init'] = {'station_file': config}
        conf['Extras'] = {'text_editor': self.text_editor}
        if not os.path.exists(default_app_dir):
            os.makedirs(default_app_dir)
        conf_path = default_app_dir + profile
        if not os.path.exists(conf_path):
            os.makedirs(conf_path)
        conf_path = conf_path + "/skalab.ini"
        with open(conf_path, 'w') as configfile:
            conf.write(configfile)

    def setAutoload(self, load_profile=""):
        conf = configparser.ConfigParser()
        conf['Base'] = {'autoload_profile': load_profile}
        if not os.path.exists(default_app_dir):
            os.makedirs(default_app_dir)
        conf_path = default_app_dir + "/startup.ini"
        with open(conf_path, 'w') as configfile:
            conf.write(configfile)

    def save_profile(self, this_profile, reload=True):
        self.make_profile(profile=this_profile,
                          subrack=self.wgSubrack.profile['Base']['profile'],
                          monitor=self.wgMonitor.profile['Base']['profile'],
                          live=self.wgLive.profile['Base']['profile'],
                          playback=self.wgPlay.profile['Base']['profile'],
                          config=self.config_file)
        if reload:
            self.load_profile(profile=this_profile)

    def save_as_profile(self):
        text, ok = QtWidgets.QInputDialog.getText(self, 'Profiles', 'Enter a Profile name:')
        if ok:
            self.save_profile(this_profile=text)
            self.updateProfileCombo(current=text)
            #self.load_profile(profile=text)

    def closeEvent(self, event):
        result = QtWidgets.QMessageBox.question(self, "Confirm Exit...", "Are you sure you want to exit ?",
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        event.ignore()

        if result == QtWidgets.QMessageBox.Yes:
            event.accept()
            self.wgLive.stopThreads = True
            self.wgSubrack.stopThreads = True
            self.wgMonitor.stopThreads = True
            self.stopThreads = True
            time.sleep(1)
            if self.wg.qradio_autosave.isChecked():
                self.save_profile(this_profile=self.profile_name, reload=False)

            if self.wg.qradio_autoload.isChecked():
                self.setAutoload(load_profile=self.profile_name)
            else:
                self.setAutoload()


if __name__ == "__main__":
    from optparse import OptionParser
    from sys import argv, stdout

    parser = OptionParser(usage="usage: %station_subrack [options]")
    parser.add_option("--profile", action="store", dest="profile",
                      type="str", default="Default", help="Skalab Profile to load")
    (opt, args) = parser.parse_args(argv[1:])

    app = QtWidgets.QApplication(sys.argv)
    if os.path.exists(default_app_dir + "startup.ini"):
        autoload = parse_profile(default_app_dir + "startup.ini")
        if autoload.sections():
            profile = autoload['Base']["autoload_profile"]
    else:
        profile = opt.profile

    window = SkaLab("skalab_main.ui", profile=profile)
    sys.exit(app.exec_())
