#!/usr/bin/env python
import sys
import os
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from pyaavs import station
from skalab_live import Live
from skalab_playback import Playback
from skalab_subrack import Subrack
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

    def __init__(self, uiFile):
        """ Initialise main window """
        super(SkaLab, self).__init__()
        # Load window file
        self.wgMain = uic.loadUi(uiFile)
        self.setCentralWidget(self.wgMain)
        self.resize(1211, 960)
        self.setWindowTitle("SKALAB Tool")
        self.config_file = self.wgMain.conf_qline_configfile.text()
        self.pic_ska = QtWidgets.QLabel(self.wgMain.qtabMainConf)
        self.pic_ska.setGeometry(790, 20, 370, 154)
        self.pic_ska.setPixmap(QtGui.QPixmap(os.getcwd() + "/ska_inaf_logo.jpg"))
        self.tabSubrackIndex = 1
        self.tabLiveIndex = 2
        self.tabPlayIndex = 3

        QtWidgets.QTabWidget.setTabVisible(self.wgMain.qtabMain, self.tabLiveIndex, True)
        self.wgLiveLayout = QtWidgets.QVBoxLayout()
        self.wgLive = Live(self.config_file, "skalab_live.ui")
        self.wgLiveLayout.addWidget(self.wgLive)
        self.wgMain.qwLive.setLayout(self.wgLiveLayout)

        QtWidgets.QTabWidget.setTabVisible(self.wgMain.qtabMain, self.tabPlayIndex, True)
        self.wgPlayLayout = QtWidgets.QVBoxLayout()
        self.wgPlay = Playback(self.config_file, "skalab_playback.ui")
        self.wgPlayLayout.addWidget(self.wgPlay)
        self.wgMain.qwPlay.setLayout(self.wgPlayLayout)

        QtWidgets.QTabWidget.setTabVisible(self.wgMain.qtabMain, self.tabSubrackIndex, True)
        self.wgSubrackLayout = QtWidgets.QVBoxLayout()
        self.wgSubrack = Subrack(ip="10.0.10.48", uiFile="skalab_subrack.ui")
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
        self.wgMain.conf_qbutton_browse.clicked.connect(lambda: self.browse_config())
        self.wgMain.conf_qbutton_setup.clicked.connect(lambda: self.setup_config())
        self.wgMain.conf_qbutton_profile_save.clicked.connect(lambda: self.save_profile())
        self.wgMain.conf_qbutton_profile_saveas.clicked.connect(lambda: self.save_as_profile())

    def browse_config(self):
        fd = QtWidgets.QFileDialog()
        fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        options = fd.options()
        self.config_file = fd.getOpenFileName(self, caption="Choose a data folder",
                                              directory="/opt/aavs/config/", options=options)[0]
        self.wgMain.conf_qline_configfile.setText(self.config_file)

    def setup_config(self):
        print("CONFIG: " + self.config_file)
        if not self.config_file == "":
            self.wgPlay.config_file = self.config_file
            self.wgLive.config_file = self.config_file
            station.load_configuration_file(self.config_file)
            self.station_name = station.configuration['station']['name']
            self.nof_tiles = len(station.configuration['tiles'])
            self.nof_antennas = int(station.configuration['station']['number_of_antennas'])
            self.bitfile = station.configuration['station']['bitfile']
            self.wgMain.conf_qlabel_bitfile.setText("BITFILE:   " + self.bitfile)
            self.truncation = int(station.configuration['station']['channel_truncation'])
            self.setup_populate_tables()
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
            msgBox.setText("Please SELECT a valid configuration file first...")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()

    def setup_populate_tables(self):
        # TABLE STATION
        self.wgMain.conf_qtable_station.clearSpans()
        self.wgMain.conf_qtable_station.setGeometry(QtCore.QRect(20, 230, 511, 151))
        self.wgMain.conf_qtable_station.setObjectName("conf_qtable_station")
        self.wgMain.conf_qtable_station.setColumnCount(1)
        self.wgMain.conf_qtable_station.setRowCount(len(station.configuration['station'].keys()) - 1)
        n = 0
        for i in station.configuration['station'].keys():
            if not i == "bitfile":
                self.wgMain.conf_qtable_station.setVerticalHeaderItem(n, QtWidgets.QTableWidgetItem(i.upper()))
                n = n + 1
        self.wgMain.conf_qtable_station.setHorizontalHeaderItem(0, QtWidgets.QTableWidgetItem("VALUES"))
        __sortingEnabled = self.wgMain.conf_qtable_station.isSortingEnabled()
        self.wgMain.conf_qtable_station.setSortingEnabled(False)
        n = 0
        for i in station.configuration['station'].keys():
            if not i == "bitfile":
                item = QtWidgets.QTableWidgetItem(str(station.configuration['station'][i]))
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wgMain.conf_qtable_station.setItem(n, 0, item)
                n = n + 1
        self.wgMain.conf_qtable_station.horizontalHeader().setStretchLastSection(True)
        self.wgMain.conf_qtable_station.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.conf_qtable_station.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.conf_qtable_station.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

        # TABLE TPM
        self.wgMain.conf_qtable_tpm.clearSpans()
        self.wgMain.conf_qtable_tpm.setGeometry(QtCore.QRect(20, 450, 511, 241))
        self.wgMain.conf_qtable_tpm.setObjectName("conf_qtable_tpm")
        self.wgMain.conf_qtable_tpm.setColumnCount(2)
        self.wgMain.conf_qtable_tpm.setRowCount(len(station.configuration['tiles']))
        for i in range(len(station.configuration['tiles'])):
            self.wgMain.conf_qtable_tpm.setVerticalHeaderItem(i, QtWidgets.QTableWidgetItem("TPM-%02d" % (i + 1)))
        item = QtWidgets.QTableWidgetItem("IP ADDR")
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.wgMain.conf_qtable_tpm.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem("DELAYS")
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.wgMain.conf_qtable_tpm.setHorizontalHeaderItem(1, item)
        for n, i in enumerate(station.configuration['tiles']):
            item = QtWidgets.QTableWidgetItem(str(i))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wgMain.conf_qtable_tpm.setItem(n, 0, item)
        for n, i in enumerate(station.configuration['time_delays']):
            item = QtWidgets.QTableWidgetItem(str(i))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wgMain.conf_qtable_tpm.setItem(n, 1, item)
        self.wgMain.conf_qtable_tpm.horizontalHeader().setStretchLastSection(True)
        self.wgMain.conf_qtable_tpm.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.conf_qtable_tpm.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.conf_qtable_tpm.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

        # TABLE NETWORK
        self.wgMain.conf_qtable_network.clearSpans()
        self.wgMain.conf_qtable_network.setGeometry(QtCore.QRect(600, 230, 511, 461))
        self.wgMain.conf_qtable_network.setObjectName("conf_qtable_network")
        self.wgMain.conf_qtable_network.setColumnCount(1)

        total_rows = len(station.configuration['network'].keys()) * 2 - 1
        for i in station.configuration['network'].keys():
            total_rows += len(station.configuration['network'][i])
        self.wgMain.conf_qtable_network.setRowCount(total_rows)
        item = QtWidgets.QTableWidgetItem("VALUE")
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        self.wgMain.conf_qtable_network.setHorizontalHeaderItem(0, item)
        n = 0
        for i in station.configuration['network'].keys():
            if n:
                item = QtWidgets.QTableWidgetItem(" ")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wgMain.conf_qtable_network.setVerticalHeaderItem(n, item)
                item = QtWidgets.QTableWidgetItem(" ")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wgMain.conf_qtable_network.setItem(n, 0, item)
                n = n + 1
            self.wgMain.conf_qtable_network.setVerticalHeaderItem(n, QtWidgets.QTableWidgetItem(str(i).upper()))
            item = QtWidgets.QTableWidgetItem(" ")
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wgMain.conf_qtable_network.setItem(n, 0, item)
            n = n + 1
            for k in sorted(station.configuration['network'][i].keys()):
                self.wgMain.conf_qtable_network.setVerticalHeaderItem(n, QtWidgets.QTableWidgetItem(str(k).upper()))
                if "MAC" in str(k).upper() and not str(station.configuration['network'][i][k]) == "None":
                    item = QtWidgets.QTableWidgetItem(hex(station.configuration['network'][i][k]).upper())
                else:
                    item = QtWidgets.QTableWidgetItem(str(station.configuration['network'][i][k]))
                item.setTextAlignment(QtCore.Qt.AlignLeft)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wgMain.conf_qtable_network.setItem(n, 0, item)
                n = n + 1
        self.wgMain.conf_qtable_network.horizontalHeader().setStretchLastSection(True)
        self.wgMain.conf_qtable_network.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.conf_qtable_network.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgMain.conf_qtable_network.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

    def browse_data_folder(self):
        fd = QtWidgets.QFileDialog()
        fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        options = fd.options()
        self.folder = fd.getExistingDirectory(self, caption="Choose a data folder",
                                              directory="/storage/daq/", options=options)
        self.wgMain.play_qline_datapath.setText(self.folder)
        self.check_dir()
        self.calc_data_volume()

    # def check_tab_show(self, b, index):
    #     if b.isChecked():
    #         QtWidgets.QTabWidget.setTabVisible(self.wgMain.qtabMain, index, True)
    #     else:
    #         QtWidgets.QTabWidget.setTabVisible(self.wgMain.qtabMain, index, False)
    #
    def save_profile(self):
        if os.path.exists(self.wgMain.conf_qline_profile.text()):
            print("Not yet implemented. SAVE PROFILE IN: " + self.wgMain.conf_qline_profile.text())

    def save_as_profile(self):
        fd = QtWidgets.QFileDialog()
        fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        options = fd.options()
        new_profile_file = fd.getSaveFileName(self, caption="Save to an existing file or to a new file name...",
                                              directory="/opt/aavs/config/skalab_profiles/", options=options,
                                              filter="*.ini")[0]
        print("Not yet implemented. SAVE AS PROFILE IN: " + new_profile_file)

    def closeEvent(self, event):
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Exit...",
                                                "Are you sure you want to exit ?",
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        event.ignore()

        if result == QtWidgets.QMessageBox.Yes:
            event.accept()
            self.wgSubrack.stopThreads = True

            if self.wgMain.conf_radio_autosave.isChecked():
                print("Saved profile: ")
            else:
                print("Autosave profile disabled!")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = SkaLab("skalab_main.ui")
    sys.exit(app.exec_())
