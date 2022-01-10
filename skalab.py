#!/usr/bin/env python
import shutil
import sys
import os
import numpy as np
import configparser
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from pyaavs import station
from skalab_live import Live
from skalab_playback import Playback
from skalab_subrack import Subrack
from skalab_utils import parse_profile
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
        # Load window file
        self.wgMain = uic.loadUi(uiFile)
        self.setCentralWidget(self.wgMain)
        self.resize(1210, 970)
        self.setWindowTitle("SKALAB Tool")

        self.updateProfileCombo(profile)
        self.profile = []
        self.profile_name = ""
        self.profile_file = ""
        self.load_profile(profile)
        self.updateProfileCombo(current=self.profile_name)

        self.config_file = self.profile['Init']['station_setup']
        self.wgMain.qline_configfile.setText(self.config_file)

        self.tabSubrackIndex = 1
        self.tabLiveIndex = 2
        self.tabPlayIndex = 3

        self.pic_ska = QtWidgets.QLabel(self.wgMain.qwpics)
        self.pic_ska.setGeometry(1, 1, 489, 120)
        self.pic_ska.setPixmap(QtGui.QPixmap(os.getcwd() + "/ska_inaf_logo.png"))

        QtWidgets.QTabWidget.setTabVisible(self.wgMain.qtabMain, self.tabLiveIndex, True)
        self.wgLiveLayout = QtWidgets.QVBoxLayout()
        self.wgLive = Live(self.config_file, "skalab_live.ui", profile=self.profile['App']['live'])
        self.wgLiveLayout.addWidget(self.wgLive)
        self.wgMain.qwLive.setLayout(self.wgLiveLayout)

        QtWidgets.QTabWidget.setTabVisible(self.wgMain.qtabMain, self.tabPlayIndex, True)
        self.wgPlayLayout = QtWidgets.QVBoxLayout()
        self.wgPlay = Playback(self.config_file, "skalab_playback.ui", profile=self.profile['App']['playback'])
        self.wgPlayLayout.addWidget(self.wgPlay)
        self.wgMain.qwPlay.setLayout(self.wgPlayLayout)

        QtWidgets.QTabWidget.setTabVisible(self.wgMain.qtabMain, self.tabSubrackIndex, True)
        self.wgSubrackLayout = QtWidgets.QVBoxLayout()
        self.wgSubrack = Subrack(uiFile="skalab_subrack.ui", size=[1190, 936],
                                 profile=self.profile['App']['subrack'])
        self.wgSubrackLayout.addWidget(self.wgSubrack)
        self.wgMain.qwSubrack.setLayout(self.wgSubrackLayout)
        self.wgSubrack.signalTlm.connect(self.wgSubrack.updateTlm)

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
        self.setup_config()

    def load_events(self):
        self.wgMain.qbutton_browse.clicked.connect(lambda: self.browse_config())
        self.wgMain.qbutton_load_configuration.clicked.connect(lambda: self.setup_config())
        self.wgMain.qbutton_profile_save.clicked.connect(lambda: self.save_profile(self.wgMain.qcombo_profiles.currentText()))
        self.wgMain.qbutton_profile_saveas.clicked.connect(lambda: self.save_as_profile())
        self.wgMain.qbutton_profile_load.clicked.connect(lambda: self.reload_profile(self.wgMain.qcombo_profiles.currentText()))
        self.wgMain.qbutton_profile_delete.clicked.connect(lambda: self.delete_profile(self.wgMain.qcombo_profiles.currentText()))

    def load_profile(self, profile):
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
        self.wgMain.qline_profile.setText(fullpath)

        if not self.profile.sections():
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Cannot find this profile!")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()
        else:
            self.config_file = self.profile['Init']['station_setup']
            self.wgMain.qline_configfile.setText(self.config_file)
            self.populate_table_profile()

    def reload_profile(self, profile):
        self.load_profile(profile=profile)
        if self.profile.sections():
            if self.profile['App']['subrack']:
                self.wgSubrack.load_profile(profile=self.profile['App']['subrack'])

    def delete_profile(self, profile):
        if os.path.exists(default_app_dir + profile):
            shutil.rmtree(default_app_dir + profile)
        self.updateProfileCombo(current="")
        self.load_profile(self.wgMain.qcombo_profiles.currentText())

    def updateProfileCombo(self, current):
        profiles = []
        for d in os.listdir(default_app_dir):
            if os.path.exists(default_app_dir + d + "/skalab.ini"):
                profiles += [d]
        if profiles:
            self.wgMain.qcombo_profiles.clear()
            for n, p in enumerate(profiles):
                self.wgMain.qcombo_profiles.addItem(p)
                if current == p:
                    self.wgMain.qcombo_profiles.setCurrentIndex(n)

    def browse_config(self):
        fd = QtWidgets.QFileDialog()
        fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        options = fd.options()
        self.config_file = fd.getOpenFileName(self, caption="Choose a data folder",
                                              directory="/opt/aavs/config/", options=options)[0]
        self.wgMain.qline_configfile.setText(self.config_file)

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
                self.wgMain.qlabel_bitfile.setText("..." + self.bitfile[-52:])
            else:
                self.wgMain.qlabel_bitfile.setText(self.bitfile)
            self.truncation = int(station.configuration['station']['channel_truncation'])
            self.populate_table_station()
            if not self.wgPlay == None:
                self.wgPlay.wg.qcombo_tpm.clear()
                self.wgLive.wg.qcombo_tpm.clear()
            self.tiles = []
            for n, i in enumerate(station.configuration['tiles']):
                if not self.wgPlay == None:
                    self.wgPlay.wg.qcombo_tpm.addItem("TPM-%02d (%s)" % (n + 1, i))
                    self.wgLive.wg.qcombo_tpm.addItem("TPM-%02d (%s)" % (n + 1, i))
                self.tiles += [i]
        else:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("SKALAB: Please SELECT a valid configuration file first...")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()

    def populate_table_profile(self):
        #self.wgMain.qtable_profile = QtWidgets.QTableWidget(self.wgMain.qtabMain)
        #self.wgMain.qtable_profile.setGeometry(QtCore.QRect(20, 575, 461, 351))
        self.wgMain.qtable_profile.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.wgMain.qtable_profile.setObjectName("qtable_profile")
        self.wgMain.qtable_profile.setColumnCount(1)
        nrows = 2
        for i in self.profile.sections():
            nrows = nrows + len(self.profile[i].keys()) + 1
        self.wgMain.qtable_profile.setRowCount(nrows)

        # Header Horizontal
        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignLeading | QtCore.Qt.AlignVCenter)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        item.setFont(font)
        self.wgMain.qtable_profile.setHorizontalHeaderItem(0, item)
        item = self.wgMain.qtable_profile.horizontalHeaderItem(0)
        item.setText("Profile: " + self.profile_name)
        __sortingEnabled = self.wgMain.qtable_profile.isSortingEnabled()
        self.wgMain.qtable_profile.setSortingEnabled(False)

        row = 0
        for k in self.profile.sections():
            # Empty Row
            item = QtWidgets.QTableWidgetItem()
            self.wgMain.qtable_profile.setVerticalHeaderItem(row, item)
            item = self.wgMain.qtable_profile.verticalHeaderItem(row)
            item.setText(" ")
            item = QtWidgets.QTableWidgetItem()
            item.setText(" ")
            self.wgMain.qtable_profile.setItem(row, 0, item)
            row = row + 1

            item = QtWidgets.QTableWidgetItem()
            font = QtGui.QFont()
            font.setBold(True)
            font.setWeight(75)
            item.setFont(font)
            item.setText("[" + k + "]")
            self.wgMain.qtable_profile.setVerticalHeaderItem(row, item)
            row = row + 1

            for s in self.profile[k].keys():
                item = QtWidgets.QTableWidgetItem()
                self.wgMain.qtable_profile.setVerticalHeaderItem(row, item)
                item = self.wgMain.qtable_profile.verticalHeaderItem(row)
                item.setText(s)
                item = QtWidgets.QTableWidgetItem()
                item.setText(self.profile[k][s])
                self.wgMain.qtable_profile.setItem(row, 0, item)
                row = row + 1

        self.wgMain.qtable_profile.horizontalHeader().setDefaultSectionSize(365)
        self.wgMain.qtable_profile.setSortingEnabled(__sortingEnabled)

    def populate_table_station(self):
        # TABLE STATION
        self.wgMain.qtable_station.clearSpans()
        #self.wgMain.qtable_station.setGeometry(QtCore.QRect(20, 140, 171, 31))
        self.wgMain.qtable_station.setObjectName("conf_qtable_station")
        self.wgMain.qtable_station.setColumnCount(1)
        self.wgMain.qtable_station.setRowCount(len(station.configuration['station'].keys()) - 1)
        n = 0
        for i in station.configuration['station'].keys():
            if not i == "bitfile":
                self.wgMain.qtable_station.setVerticalHeaderItem(n, QtWidgets.QTableWidgetItem(i.upper()))
                n = n + 1
        self.wgMain.qtable_station.setHorizontalHeaderItem(0, QtWidgets.QTableWidgetItem("VALUES"))
        __sortingEnabled = self.wgMain.qtable_station.isSortingEnabled()
        self.wgMain.qtable_station.setSortingEnabled(False)
        n = 0
        for i in station.configuration['station'].keys():
            if not i == "bitfile":
                item = QtWidgets.QTableWidgetItem(str(station.configuration['station'][i]))
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wgMain.qtable_station.setItem(n, 0, item)
                n = n + 1
        self.wgMain.qtable_station.horizontalHeader().setStretchLastSection(True)
        self.wgMain.qtable_station.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.qtable_station.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.qtable_station.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

        # TABLE TPM
        self.wgMain.qtable_tpm.clearSpans()
        #self.wgMain.qtable_tpm.setGeometry(QtCore.QRect(20, 180, 511, 141))
        self.wgMain.qtable_tpm.setObjectName("conf_qtable_tpm")
        self.wgMain.qtable_tpm.setColumnCount(2)
        self.wgMain.qtable_tpm.setRowCount(len(station.configuration['tiles']))
        for i in range(len(station.configuration['tiles'])):
            self.wgMain.qtable_tpm.setVerticalHeaderItem(i, QtWidgets.QTableWidgetItem("TPM-%02d" % (i + 1)))
        item = QtWidgets.QTableWidgetItem("IP ADDR")
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.wgMain.qtable_tpm.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem("DELAYS")
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.wgMain.qtable_tpm.setHorizontalHeaderItem(1, item)
        for n, i in enumerate(station.configuration['tiles']):
            item = QtWidgets.QTableWidgetItem(str(i))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wgMain.qtable_tpm.setItem(n, 0, item)
        for n, i in enumerate(station.configuration['time_delays']):
            item = QtWidgets.QTableWidgetItem(str(i))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wgMain.qtable_tpm.setItem(n, 1, item)
        self.wgMain.qtable_tpm.horizontalHeader().setStretchLastSection(True)
        self.wgMain.qtable_tpm.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.qtable_tpm.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.qtable_tpm.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

        # TABLE NETWORK
        self.wgMain.qtable_network.clearSpans()
        #self.wgMain.qtable_network.setGeometry(QtCore.QRect(600, 230, 511, 481))
        self.wgMain.qtable_network.setObjectName("conf_qtable_network")
        self.wgMain.qtable_network.setColumnCount(1)

        total_rows = len(station.configuration['network'].keys()) * 2 - 1
        for i in station.configuration['network'].keys():
            total_rows += len(station.configuration['network'][i])
        self.wgMain.qtable_network.setRowCount(total_rows)
        item = QtWidgets.QTableWidgetItem("VALUES")
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        self.wgMain.qtable_network.setHorizontalHeaderItem(0, item)
        n = 0
        for i in station.configuration['network'].keys():
            if n:
                item = QtWidgets.QTableWidgetItem(" ")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wgMain.qtable_network.setVerticalHeaderItem(n, item)
                item = QtWidgets.QTableWidgetItem(" ")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wgMain.qtable_network.setItem(n, 0, item)
                n = n + 1
            self.wgMain.qtable_network.setVerticalHeaderItem(n, QtWidgets.QTableWidgetItem(str(i).upper()))
            item = QtWidgets.QTableWidgetItem(" ")
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wgMain.qtable_network.setItem(n, 0, item)
            n = n + 1
            for k in sorted(station.configuration['network'][i].keys()):
                self.wgMain.qtable_network.setVerticalHeaderItem(n, QtWidgets.QTableWidgetItem(str(k).upper()))
                if "MAC" in str(k).upper() and not str(station.configuration['network'][i][k]) == "None":
                    item = QtWidgets.QTableWidgetItem(hex(station.configuration['network'][i][k]).upper())
                else:
                    item = QtWidgets.QTableWidgetItem(str(station.configuration['network'][i][k]))
                item.setTextAlignment(QtCore.Qt.AlignLeft)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wgMain.qtable_network.setItem(n, 0, item)
                n = n + 1
        self.wgMain.qtable_network.horizontalHeader().setStretchLastSection(True)
        self.wgMain.qtable_network.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.qtable_network.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.qtable_network.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

    def make_profile(self, profile="Default", subrack="Default", live="Default", playback="Default", config=""):
        conf = configparser.ConfigParser()
        conf['App'] = {'subrack': subrack,
                       'live': live,
                       'playback': playback}
        conf['Init'] = {'station_setup': config}
        if not os.path.exists(default_app_dir):
            os.makedirs(default_app_dir)
        conf_path = default_app_dir + profile
        if not os.path.exists(conf_path):
            os.makedirs(conf_path)
        conf_path = conf_path + "/skalab.ini"
        with open(conf_path, 'w') as configfile:
            conf.write(configfile)

    def setAutoload(self, load_profile="Default"):
        conf = configparser.ConfigParser()
        conf['App'] = {'autoload_profile': load_profile}
        if not os.path.exists(default_app_dir):
            os.makedirs(default_app_dir)
        conf_path = default_app_dir + "/skalab.ini"
        with open(conf_path, 'w') as configfile:
            conf.write(configfile)

    # def browse_data_folder(self):
    #     fd = QtWidgets.QFileDialog()
    #     fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
    #     options = fd.options()
    #     self.folder = fd.getExistingDirectory(self, caption="Choose a data folder",
    #                                           directory="/storage/daq/", options=options)
    #     self.wgMain.play_qline_datapath.setText(self.folder)
    #     self.check_dir()
    #     self.calc_data_volume()

    def save_profile(self, this_profile, reload=True):
        self.make_profile(profile=this_profile, subrack=self.wgSubrack.profile_name, live=self.wgLive.profile_name,
                          playback=self.wgPlay.profile_name, config=self.config_file)
        if reload:
            self.populate_table_profile()
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
            self.wgSubrack.stopThreads = True

            if self.wgMain.qradio_autosave.isChecked():
                self.save_profile(this_profile=self.profile_name, reload=False)

            if self.wgMain.qradio_autoload.isChecked():
                self.setAutoload(load_profile=self.profile_name)
            else:
                self.setAutoload()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    profile = "Default"
    if os.path.exists(default_app_dir + "skalab.ini"):
        autoload = parse_profile(default_app_dir + "skalab.ini")
        if autoload.sections():
            profile = autoload["App"]["autoload_profile"]
    window = SkaLab("skalab_main.ui", profile=profile)
    sys.exit(app.exec_())
