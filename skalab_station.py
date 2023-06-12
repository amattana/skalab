#!/usr/bin/env python
from skalab_base import SkalabBase
from skalab_log import SkalabLog
from PyQt5 import QtWidgets, uic, QtCore, QtGui
import logging
import socket
from threading import Thread
import time
import gc
import os
import numpy as np
from pathlib import Path
from pyaavs import station
from pyaavs.station import Station, get_slack_instance
from pyaavs.tile_wrapper import Tile
from pyfabil import TPMGeneric
from pyfabil.base.definitions import LibraryError, BoardError, PluginError, InstrumentError
import subprocess

from skalab_utils import MapPlot

default_app_dir = str(Path.home()) + "/.skalab/"
default_profile = "Default"
profile_filename = "station.ini"


# class MyStation(Station):
#     """ Customized Class representing an AAVS station using parent Logger """
#
#     def __init__(self, config, logger):
#         self.log = logger
#         super().__init__(config)
#
#     def add_tile(self, tile_ip):
#         """ override add_tile only to provide the Tile Logger """
#
#         # If all traffic is going through 1G then set the destination port to
#         # the lmc_port. If only integrated data is going through the 1G set the
#         # destination port to integrated_data_port
#         dst_port = self.configuration['network']['lmc']['lmc_port']
#         lmc_ip = self.configuration['network']['lmc']['lmc_ip']
#
#         if not self.configuration['network']['lmc']['use_teng_integrated'] and \
#                 self.configuration['network']['lmc']['use_teng']:
#             dst_port = self.configuration['network']['lmc']['integrated_data_port']
#             lmc_ip = self.configuration['network']['lmc']['integrated_data_ip']
#
#         self.tiles.append(
#             Tile(tile_ip, self.configuration['network']['lmc']['tpm_cpld_port'], lmc_ip, dst_port, logger=self.log))
#
#
class SkalabStation(SkalabBase):
    """ Main UI Window class """
    # Signal for Slots
    signalTlm = QtCore.pyqtSignal()

    def __init__(self, uiFile="", profile="", size=[1190, 936], swpath=default_app_dir):
        """ Initialise main window """
        # Load window file
        self.wg = uic.loadUi(uiFile)
        self.wgProBox = QtWidgets.QWidget(self.wg.qtab_conf)
        self.wgProBox.setGeometry(QtCore.QRect(1, 1, 800, 860))
        self.wgProBox.setVisible(True)
        self.wgProBox.show()

        super(SkalabStation, self).__init__(App="station", Profile=profile, Path=swpath, parent=self.wgProBox)
        self.logger = SkalabLog(parent=self.wg.qw_log, logname=__name__, profile=self.profile)
        self.connected = False
        self.tpm_station = None
        self.doInit = False
        self.stopThreads = False
        self.processInit = Thread(target=self.do_station_init)
        self.processInit.start()
        # print("Start Thread Station do_station_init")

        self.updateRequest = False

        self.setCentralWidget(self.wg)
        self.resize(size[0], size[1])
        self.text_editor = ""
        if 'Extras' in self.profile.keys():
            if 'text_editor' in self.profile['Extras'].keys():
                self.text_editor = self.profile['Extras']['text_editor']

        self.load_events()
        self.config_file = self.profile['Station']['station_file']
        self.setup_config()
        self.tpm_ips_from_subrack = []

        self.maks_tiles = np.arange(1, 17).tolist()
        self.populate_cb_tiles()
        self.pauseAction = False
        self.station_map = []
        if "station_map" in self.profile['Station'].keys():
            self.wg.qline_map_file.setText(self.profile['Station']["station_map"])
            self.station_map = self.loadStationMap(self.profile['Station']["station_map"])
            ant_id_list = sorted(["%03d" % x['id'] for x in self.station_map])
            tpm_list = list(dict.fromkeys(["%d" % x['tile'] for x in self.station_map]))
            input_list = ["%d" % x for x in np.arange(1, 17)]
            self.wg.combo_antenna.addItems(ant_id_list)
            self.wg.combo_tpm.addItems(tpm_list)
            self.wg.combo_input.addItems(input_list)
            self.mapPlot = MapPlot(self.wg.plotWidgetMap, self.station_map, self.maks_tiles)
            self.mapPlot.plotMap()
            self.mapPlot.canvas.mpl_connect('motion_notify_event', self.onmotion)
            self.plotMap()
            self.annot = self.mapPlot.canvas.ax.annotate("", xy=(0, 0), xytext=(20, 20), textcoords="offset points",
                                bbox=dict(boxstyle="round", fc="w"),
                                arrowprops=dict(arrowstyle="->"))
            self.annot.set_visible(False)

    def update_annot(self, x, y, text):
        pos = (x, y)
        self.annot.xy = pos
        self.annot.set_text(text)
        self.annot.get_bbox_patch().set_facecolor('w')

    def mouseonbase(self, x, y):
        for a in self.station_map:
            if (a['East'] > x - 0.6) and (a['East'] < x + 0.6):
                if (a['North'] > y - 0.6) and (a['North'] < y + 0.6):
                    return "Antenna ID: " + str(a['id']) + "\nTILE: " + str(int(a['tile'])) + ", Input: " + str(
                        int(a['input']))
        return ""

    def onmotion(self, event):
        if self.wg.cb_tooltip.isChecked():
            vis = self.annot.get_visible()
            if event.inaxes == self.mapPlot.canvas.ax:
                cont, ind = self.mapPlot.canvas.ax.contains(event)
                hc = self.mouseonbase(event.xdata, event.ydata)
                if cont and (hc != ""):
                    self.update_annot(event.xdata, event.ydata, hc)
                    self.annot.set_visible(True)
                    self.mapPlot.updatePlot()
                else:
                    if vis:
                        self.annot.set_visible(False)
                        self.mapPlot.updatePlot()

    def rb_changed(self):
        if self.wg.rb_circle.isChecked():
            self.plotMap()
        elif self.wg.rb_cross.isChecked():
            self.plotMap()

    def plotMap(self):
        if len(self.station_map):
            self.mapPlot.showCircle(flag=self.wg.rb_circle.isChecked())
            self.mapPlot.showCross(flag=self.wg.rb_cross.isChecked())
            self.mapPlot.printId(flag=self.wg.cb_id.isChecked())
            self.mapPlot.updatePlot()

    def populate_cb_tiles(self):
        self.wg.cb_tiles = []
        for i in range(16):
            self.wg.cb_tiles += [QtWidgets.QCheckBox(self.wg.qframe_tiles)]
            self.wg.cb_tiles[-1].setGeometry(QtCore.QRect(20 + (70 * (i % 4)), 20 + (40 * int(i / 4)), 51, 23))
            self.wg.cb_tiles[-1].setChecked(True)
            self.wg.cb_tiles[-1].setText(str(i + 1))
            self.wg.cb_tiles[-1].stateChanged.connect(self.change_mask)

    def change_mask(self):
        if not self.pauseAction:
            self.mapPlot.mask = []
            for i in range(16):
                if self.wg.cb_tiles[i].isChecked():
                    self.mapPlot.mask += [i + 1]
            self.plotMap()

    def tile_select_none(self):
        self.pauseAction = True
        for i in range(16):
            self.wg.cb_tiles[i].setChecked(False)
        self.pauseAction = False
        self.mapPlot.mask = []
        self.plotMap()

    def tile_select_all(self):
        self.pauseAction = True
        for i in range(16):
            self.wg.cb_tiles[i].setChecked(True)
        self.pauseAction = False
        self.mapPlot.mask = np.arange(1, 17).tolist()
        self.plotMap()

    def locateAntenna(self):
        self.mapPlot.highlightClear()
        if self.wg.cb_locate_enable_antenna.isChecked():
            antId = [ant['id'] for ant in self.station_map if ant['id'] == int(self.wg.combo_antenna.currentText())]
            if len(antId):
                self.mapPlot.highlightAntenna(antId=antId, color='yellow')
        if self.wg.cb_locate_enable_antenna_list.isChecked():
            try:
                ant_records = self.wg.qline_find_antlist.text().split(",")
                ant_list = []
                for a in ant_records:
                    if "-" in a:
                        ant_list += np.arange(int(a.split("-")[0]), int(a.split("-")[1])+1).tolist()
                    else:
                        ant_list += [int(a)]
                antId = []
                for a in ant_list:
                    antId += [ant['id'] for ant in self.station_map if ant['id'] == a]
                self.wg.qlabel_malformed_list.setText("query form ok")
                self.mapPlot.highlightAntenna(antId=antId, color='#00c800')
            except:
                self.wg.qlabel_malformed_list.setText("<-- malformed")
        if self.wg.cb_locate_enable_tpm.isChecked():
            tpmId = int(self.wg.combo_tpm.currentText())
            inputId = int(self.wg.combo_input.currentText())
            antId = [ant['id'] for ant in self.station_map if ((ant['tile'] == tpmId) and (ant['input'] == inputId))]
            if len(antId):
                self.mapPlot.highlightAntenna(antId=antId, color='b')

    def enableLocateAntenna(self):
        if self.wg.cb_locate_enable_antenna.isChecked():
            self.wg.cb_locate_enable_tpm.setChecked(False)
            self.wg.cb_locate_enable_antenna_list.setChecked(False)
        self.locateAntenna()

    def enableLocateAntennaList(self):
        if self.wg.cb_locate_enable_antenna_list.isChecked():
            self.wg.cb_locate_enable_tpm.setChecked(False)
            self.wg.cb_locate_enable_antenna.setChecked(False)
        self.locateAntenna()

    def enableLocateTpmInput(self):
        if self.wg.cb_locate_enable_tpm.isChecked():
            self.wg.cb_locate_enable_antenna.setChecked(False)
            self.wg.cb_locate_enable_antenna_list.setChecked(False)
        self.locateAntenna()

    def enableTooltip(self):
        if not self.wg.cb_tooltip.isChecked():
            self.annot.set_visible(False)
            self.mapPlot.updatePlot()

    def load_events(self):
        self.wg.qbutton_browse.clicked.connect(lambda: self.browse_config())
        self.wg.qbutton_edit.clicked.connect(lambda: self.edit_config())
        self.wg.qbutton_load_configuration.clicked.connect(lambda: self.setup_config())
        self.wg.qbutton_station_init.clicked.connect(lambda: self.station_init())
        self.wg.rb_circle.toggled.connect(lambda: self.rb_changed())
        self.wg.rb_cross.toggled.connect(lambda: self.rb_changed())
        self.wg.cb_id.stateChanged.connect(lambda: self.plotMap())
        self.wg.combo_antenna.currentIndexChanged.connect(lambda: self.locateAntenna())
        self.wg.combo_tpm.currentIndexChanged.connect(lambda: self.locateAntenna())
        self.wg.combo_input.currentIndexChanged.connect(lambda: self.locateAntenna())
        self.wg.cb_locate_enable_antenna.stateChanged.connect(lambda: self.enableLocateAntenna())
        self.wg.cb_locate_enable_antenna_list.stateChanged.connect(lambda: self.enableLocateAntennaList())
        self.wg.qline_find_antlist.textChanged.connect(lambda: self.enableLocateAntennaList())
        self.wg.cb_locate_enable_tpm.stateChanged.connect(lambda: self.enableLocateTpmInput())
        self.wg.cb_tooltip.stateChanged.connect(lambda: self.enableTooltip())
        self.wg.qbutton_map_deselect.clicked.connect(lambda: self.tile_select_none())
        self.wg.qbutton_map_select.clicked.connect(lambda: self.tile_select_all())

    def browse_config(self):
        fd = QtWidgets.QFileDialog()
        fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        options = fd.options()
        self.config_file = fd.getOpenFileName(self, caption="Select a Station Config File...",
                                              directory="/opt/aavs/config/", options=options)[0]
        self.wg.qline_configfile.setText(self.config_file)

    def loadStationMap(self, map_file):
        with open(map_file) as f:
            data = f.readlines()
        station_map = []
        for d in data:
            if (len(d.split()) == 5) and (d[0] != "#"):
                antenna_map = {'tile': int(d.split()[0]),
                               'input': int(d.split()[1]),
                               'id': int(d.split()[2]),
                               'North': float(d.split()[3]),
                               'East': float(d.split()[4])}
                station_map += [antenna_map]
        return station_map

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

    def setup_config(self):
        if not self.config_file == "":
            # self.wgPlay.config_file = self.config_file
            # self.wgLive.config_file = self.config_file
            station.load_configuration_file(self.config_file)
            self.wg.qline_configfile.setText(self.config_file)
            self.station_name = station.configuration['station']['name']
            self.nof_tiles = len(station.configuration['tiles'])
            self.nof_antennas = int(station.configuration['station']['number_of_antennas'])
            self.bitfile = station.configuration['station']['bitfile']
            self.wg.qlabel_bitfile.setText(self.bitfile)
            self.truncation = int(station.configuration['station']['channel_truncation'])
            self.populate_table_station()
            # if not self.wgPlay == None:
            #     self.wgPlay.wg.qcombo_tpm.clear()
            # if not self.wgLive == None:
            #     self.wgLive.wg.qcombo_tpm.clear()
            self.tiles = []
            for n, i in enumerate(station.configuration['tiles']):
                # if not self.wgPlay == None:
                #     self.wgPlay.wg.qcombo_tpm.addItem("TPM-%02d (%s)" % (n + 1, i))
                # if not self.wgLive == None:
                #     self.wgLive.wg.qcombo_tpm.addItem("TPM-%02d (%s)" % (n + 1, i))
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
                if self.tpm_ips_from_subrack:
                    if not len(tpm_ip_list) == len(self.tpm_ips_from_subrack):
                        msgBox = QtWidgets.QMessageBox()
                        message = "STATION\nOne or more TPMs forming the station are OFF\nPlease check the power!"
                        msgBox.setText(message)
                        msgBox.setWindowTitle("ERROR: TPM POWERED OFF")
                        msgBox.setIcon(QtWidgets.QMessageBox.Critical)
                        details = "STATION IP LIST FROM CONFIG FILE (%d): " % len(tpm_ip_list)
                        for i in tpm_ip_list:
                            details += "\n%s" % i
                        details += "\n\nSUBRACK IP LIST OF TPM POWERED ON: (%d): " % len(self.tpm_ips_from_subrack)
                        for i in tpm_ip_from_subrack_short:
                            details += "\n%s" % i
                        msgBox.setDetailedText(details)
                        msgBox.exec_()
                    else:
                        if not np.array_equal(tpm_ip_list, self.tpm_ips_from_subrack):
                            msgBox = QtWidgets.QMessageBox()
                            message = "STATION\nIPs provided by the SubRack are different from what defined in the " \
                                      "config file.\nINIT will use the new assigned IPs."
                            msgBox.setText(message)
                            msgBox.setWindowTitle("WARNING: IP mismatch")
                            msgBox.setIcon(QtWidgets.QMessageBox.Warning)
                            details = "STATION IP LIST FROM CONFIG FILE (%d): " % len(tpm_ip_list)
                            for i in tpm_ip_list:
                                details += "\n%s" % i
                            details += "\n\nSUBRACK IP LIST OF TPM POWERED ON: (%d): " % len(self.tpm_ips_from_subrack)
                            for i in self.tpm_ips_from_subrack:
                                details += "\n%s" % i
                            msgBox.setDetailedText(details)
                            msgBox.exec_()
                            station.configuration['tiles'] = list(self.tpm_ips_from_subrack)
                            # self.wgLive.setupNewTilesIPs(list(self.tpm_ips_from_subrack))
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
                    details += "\n\nSUBRACK IP LIST OF TPM POWERED ON: (%d): " % len(self.tpm_ips_from_subrack)
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
                if True:
                    swpath = os.getenv("AAVS_HOME")[:-1]
                    swstation = "/aavs-system/python/pyaavs/station.py "
                    swopt = " -I"
                    if self.wg.checkProgram.isChecked():
                        swopt += " -P"
                    sp = subprocess.Popen(
                        "python " + swpath + swstation + " --config='" + self.config_file + "'" + swopt, shell=True,
                        stdout=subprocess.PIPE)
                    while True:
                        msg = sp.stdout.readline()
                        if (len(msg) == 0) and (sp.poll() is not None):
                            break
                        if "ERROR" in msg.decode()[:-1]:
                            self.logger.error(msg.decode()[:-1])
                        elif "WARNING" in msg.decode()[:-1]:
                            self.logger.warning(msg.decode()[:-1])
                        else:
                            self.logger.info(msg.decode()[:-1])
                        # print(msg.decode()[:-1])
                        time.sleep(0.01)

                    self.tpm_station = station.Station(station.configuration)
                    self.wg.qbutton_station_init.setEnabled(False)
                    station.configuration['station']['initialise'] = False
                    station.configuration['station']['program'] = False
                    self.logger.info("Station Initialization completed, verifying if properly formed...")
                    self.tpm_station.connect()
                    if self.tpm_station.properly_formed_station:
                        self.logger.info("The Station is properly formed!")
                        self.logger.info("Switching On TPM PreADUs...")
                        self.wg.qbutton_station_init.setStyleSheet("background-color: rgb(78, 154, 6);")
                        # Switch On the PreADUs
                        for tile in self.tpm_station.tiles:
                            tile["board.regfile.enable.fe"] = 1
                            time.sleep(0.1)
                        self.logger.info("TPM PreADUs Powered ON")
                        time.sleep(1)
                        if "default_preadu_attenuation" in station.configuration['station'].keys():
                            for tile in self.tpm_station.tiles:
                                tile.set_preadu_attenuation(int(station.configuration['station']["default_preadu_attenuation"]))
                        if "equalize_preadu" in station.configuration['station'].keys():
                            for tile in self.tpm_station.tiles:
                                tile.equalize_preadu_gain(int(station.configuration['station']["equalize_preadu"]))
                            self.logger.info("Equalization of Levels done")
                    else:
                        self.wg.qbutton_station_init.setStyleSheet("background-color: rgb(204, 0, 0);")
                    self.wg.qbutton_station_init.setEnabled(True)
                    del self.tpm_station
                    gc.collect()
                else:
                    self.wg.qbutton_station_init.setEnabled(True)
                self.tpm_station = None
                self.doInit = False
            if self.stopThreads:
                #print("Stopping Thread Station do_station_init")
                break
            time.sleep(0.3)

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

    def cmdClose(self):
        self.stopThreads = True
        self.logger.logger.info("Stopping Threads")
        self.logger.stopLog()

    def closeEvent(self, event):
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Exit...",
                                                "Are you sure you want to exit ?",
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        event.ignore()

        if result == QtWidgets.QMessageBox.Yes:
            event.accept()
            self.stopThreads = True
            self.logger.logger.info("Stopping Threads")
            self.logger.stopLog()
            time.sleep(1)
