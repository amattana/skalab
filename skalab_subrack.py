#!/usr/bin/env python
import gc
import os.path
import glob
import shutil
import sys
import numpy as np
import configparser
from PyQt5 import QtWidgets, uic, QtCore, QtGui
from hardware_client import WebHardwareClient
from skalab_utils import BarPlot, ChartPlots, colors, dt_to_timestamp, ts_to_datestring, parse_profile
from threading import Thread
from time import sleep
import datetime
from pathlib import Path
COLORI = ["b", "g", "k", "r", "orange", "magenta", "darkgrey", "turquoise"]

MgnTraces = ['board_temperatures', 'backplane_temperatures']
default_app_dir = str(Path.home()) + "/.skalab/"
default_profile = "Default"
profile_filename = "subrack.ini"

'''
In [3]: client.execute_command("list_attributes")
Out[3]: 
{'status': 'OK',
 'info': 'list_attributes completed OK',
 'command': 'list_attributes',
 'retvalue': ['backplane_temperatures',
  'board_temperatures',
  'board_current',
  'subrack_fan_speeds',
  'subrack_fan_speeds_percent',
  'subrack_fan_mode',
  'tpm_temperatures',
  'tpm_voltages',
  'tpm_currents',
  'tpm_powers',
  'tpm_present',
  'tpm_supply_fault',
  'tpm_on_off',
  'power_supply_fan_speeds',
  'power_supply_currents',
  'power_supply_powers',
  'power_supply_voltages']}
'''


def populateSlots(frame):
    qbutton_tpm = []
    for i in range(8):
        qbutton_tpm += [QtWidgets.QPushButton(frame)]
        qbutton_tpm[i].setGeometry(QtCore.QRect(126 + 46 * (i % 4), 20 + (40 * (i // 4)), 41, 31))
        qbutton_tpm[i].setObjectName("qbutton_tpm_%d" % i)
        qbutton_tpm[i].setText("%d" % (i + 1))
    return qbutton_tpm


def populateFans(frame):
    fans = []
    for i in range(4):
        fan = {}

        fan['rpm'] = QtWidgets.QLabel(frame)
        fan['rpm'].setEnabled(False)
        fan['rpm'].setGeometry(QtCore.QRect(50 + 60 * i, 20, 41, 20))
        font = QtGui.QFont()
        font.setPointSize(8)
        fan['rpm'].setFont(font)
        fan['rpm'].setAlignment(QtCore.Qt.AlignCenter)
        fan['rpm'].setObjectName("label_rpm_%d" % i)
        fan['rpm'].setStyleSheet("color: rgb(0, 0, 0);")
        fan['rpm'].setText("RPM")

        fan['slider'] = QtWidgets.QSlider(frame)
        fan['slider'].setGeometry(QtCore.QRect(60 + 60 * i, 50, 20, 131))
        fan['slider'].setMaximum(100)
        fan['slider'].setPageStep(20)
        fan['slider'].setProperty("value", 0)
        fan['slider'].setOrientation(QtCore.Qt.Vertical)
        fan['slider'].setTickPosition(QtWidgets.QSlider.TicksBothSides)
        fan['slider'].setTickInterval(20)
        fan['slider'].setObjectName("verticalSlider_%d" % i)

        fan['manual'] = QtWidgets.QPushButton(frame)
        fan['manual'].setGeometry(QtCore.QRect(55 + 60 * i, 213, 31, 21))
        fan['manual'].setObjectName("qbutton_fan_manual_%d" % i)
        fan['manual'].setText("M")

        fan['auto'] = QtWidgets.QPushButton(frame)
        fan['auto'].setGeometry(QtCore.QRect(55 + 60 * i, 240, 31, 21))
        fan['auto'].setObjectName("qbutton_fan_auto_%d" % i)
        fan['auto'].setText("A")

        fans += [fan]
    return fans


def populateCharts(form):
    qbuttons = []
    for i in range(8):
        qbuttons += [QtWidgets.QPushButton(form)]
        qbuttons[i].setGeometry(QtCore.QRect(590 + (70 * i), 850, 61, 31))
        qbuttons[i].setStyleSheet("background-color: rgb(78, 154, 6);color: rgb(0, 0, 0);")
        #qbuttons[i].setStyleSheet("background-color: rgb(204, 0, 0);color: rgb(0, 0, 0);")
        qbuttons[i].setObjectName("qbutton_tpm_%d" % (i + 1))
        qbuttons[i].setText("TPM-%d" % (i + 1))
    return qbuttons


class Subrack(QtWidgets.QMainWindow):
    """ Main UI Window class """
    # Signal for Slots
    signalTlm = QtCore.pyqtSignal()

    def __init__(self, ip=None, port=None, uiFile="", profile="", size=[1190, 936]):
        """ Initialise main window """
        super(Subrack, self).__init__()
        # Load window file
        self.wg = uic.loadUi(uiFile)
        self.setCentralWidget(self.wg)
        self.resize(size[0], size[1])

        self.profile_name = profile
        if self.profile_name == "":
            self.profile_name = "Default"
        self.profile = []
        self.load_profile(self.profile_name, ip, port)

        self.plotTpmPower = BarPlot(parent=self.wg.qplot_tpm_power, size=(4.95, 2.3), xlim=[0, 9], ylabel="Power (W)",
                                    xrotation=0, xlabel="TPM Voltages", ylim=[0, 140],
                                    yticks=np.arange(0, 160, 20), xticks=np.zeros(9))

        self.plotTpmTemp = BarPlot(parent=self.wg.qplot_tpm_temp, size=(4.95, 2.3), xlim=[0, 9],
                                   ylabel="Temperature (deg)", xrotation=0, xlabel="TPM Board", ylim=[20, 100],
                                   yticks=np.arange(20, 120, 20), xticks=np.arange(9))

        self.plotMgnTemp = BarPlot(parent=self.wg.qplot_mgn_temp, size=(2.7, 2.3), xlim=[0, 5], ylim=[0, 60],
                                   ylabel="Temperature (deg)", xrotation=45, xlabel="SubRack Temperatures",
                                   yticks=[0, 10, 20, 30, 40, 50, 60], xticks=["", "Mgn-1", "Mgn-2", "Bck-1", "Bck-2"])

        self.plotPsu = BarPlot(parent=self.wg.qplot_psu, size=(2.7, 2.3), xlim=[0, 3], ylabel="Power (W)",
                               xrotation=0, xlabel="PSU", ylim=[0, 1200], xticks=["", "PSU-1", "PSU-2"],
                               yticks=np.arange(0, 1400, 200))

        self.plotChartMgn = ChartPlots(parent=self.wg.qplot_chart_mgn, ntraces=4, xlabel="time samples", ylim=[0, 60],
                                       ylabel="SubRack Temperatures", size=(11.3, 3.45), xlim=[0, 200])

        self.plotChartTpm = ChartPlots(parent=self.wg.qplot_chart_tpm, ntraces=8, xlabel="time samples", ylim=[0, 120],
                                       ylabel="TPM Power", size=(11.3, 3.45), xlim=[0, 200])

        self.connected = False
        self.client = None
        self.subAttr = []
        self.attributes = {}
        self.qbutton_tpm = populateSlots(self.wg.frame_tpm)
        self.fans = populateFans(self.wg.frame_fan)
        self.data_charts = {}

        self.load_events()
        self.show()
        self.stopThreads = False
        self.skip = False
        self.processTlm = Thread(target=self.readTlm)
        self.processTlm.start()

        self.wg.qplot_chart_tpm.setVisible(False)

    def load_events(self):
        self.wg.qbutton_connect.clicked.connect(lambda: self.subrack_connect())
        for n, t in enumerate(self.qbutton_tpm):
            t.clicked.connect(lambda state, g=n: self.switchTpm(g))
        self.wg.qbutton_tpm_on.clicked.connect(lambda: self.switchTpmsOn())
        self.wg.qbutton_tpm_off.clicked.connect(lambda: self.switchTpmsOff())
        self.wg.qcombo_chart.currentIndexChanged.connect(lambda: self.switchChart())
        self.wg.qbutton_load.clicked.connect(lambda: self.load())
        self.wg.qbutton_browse.clicked.connect(lambda: self.browse_outdir())
        self.wg.qbutton_saveas.clicked.connect(lambda: self.save_as_profile())
        self.wg.qbutton_save.clicked.connect(lambda: self.save_profile(this_profile=self.profile_name))
        self.wg.qbutton_delete.clicked.connect(lambda: self.delete_profile(self.wg.qcombo_profile.currentText()))

    def populate_table_profile(self):
        self.wg.qtable_conf.clearSpans()
        self.wg.qtable_conf.setGeometry(QtCore.QRect(660, 20, 461, 291))
        self.wg.qtable_conf.setObjectName("qtable_conf")
        self.wg.qtable_conf.setColumnCount(1)

        total_rows = 0
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

    def load(self):
        if not self.connected:
            self.load_profile(self.wg.qcombo_profile.currentText())
        else:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Please DISCONNECT from the Subrack first!")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()

    def load_profile(self, profile, eth_ip=None, eth_port=None):
        self.profile = []
        fullpath = default_app_dir + profile + "/" + profile_filename
        if os.path.exists(fullpath):
            print("Loading SubRack Profile: " + profile + " (" + fullpath + ")")
        else:
            print("\nThe SubRack Profile does not exist.\nGenerating a new one in "
                  + fullpath + "\n")
            self.make_profile(profile=profile, prodict={})
        self.profile = parse_profile(fullpath)
        self.profile_name = profile
        self.profile_file = fullpath
        self.wg.qline_configuration_file.setText(self.profile_file)
        self.wg.qline_profile_ip.setText(self.profile['Device']['ip'])
        self.wg.qline_profile_port.setText(self.profile['Device']['port'])
        self.wg.qline_profile_interval.setText(self.profile['Device']['query_interval'])
        self.wg.qline_output_dir.setText(self.profile['App']['data_path'])
        # Overriding Configuration File with parameters
        if eth_ip is not None:
            self.ip = eth_ip
        else:
            self.ip = str(self.profile['Device']['ip'])
        if eth_port is not None:
            self.port = eth_port
        else:
            self.port = int(self.profile['Device']['port'])
        self.wg.qline_ip.setText("%s:%d" % (self.ip, self.port))
        self.updateProfileCombo(current=profile)
        self.populate_table_profile()

    def updateProfileCombo(self, current):
        profiles = []
        for d in os.listdir(default_app_dir):
            if os.path.exists(default_app_dir + "/" + d + "/subrack.ini"):
                profiles += [d]
        if profiles:
            self.wg.qcombo_profile.clear()
            for n, p in enumerate(profiles):
                self.wg.qcombo_profile.addItem(p)
                if current == p:
                    self.wg.qcombo_profile.setCurrentIndex(n)

    def save_profile(self, this_profile, reload=True):
        self.make_profile(profile=this_profile,
                          prodict={'App': {'data_path': self.wg.qline_output_dir.text()},
                                   'Device': {'ip': self.wg.qline_profile_ip.text(),
                                              'port': self.wg.qline_profile_port.text(),
                                              'query_interval': self.wg.qline_profile_interval.text()}})
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

    def make_profile(self, profile: str, prodict: dict):
        conf = configparser.ConfigParser()
        if 'App' in prodict.keys() and 'data_path' in prodict['App'].keys():
            conf['App'] = {'data_path': prodict['App']['data_path']}
        else:
            conf['App'] = {'data_path': ""}
        conf['Device'] = {}
        if 'Device' in prodict.keys() and 'ip' in prodict['Device'].keys():
            conf['Device']['ip'] = prodict['Device']['ip']
        else:
            conf['Device']['ip'] = ""
        if 'Device' in prodict.keys() and 'port' in prodict['Device'].keys():
            conf['Device']['port'] = prodict['Device']['port']
        else:
            conf['Device']['port'] = "8081"
        if 'Device' in prodict.keys() and 'query_interval' in prodict['Device'].keys():
            conf['Device']['query_interval'] = prodict['Device']['query_interval']
        else:
            conf['Device']['query_interval'] = "3"
        if not os.path.exists(default_app_dir):
            os.makedirs(default_app_dir)
        conf_path = default_app_dir + profile
        if not os.path.exists(conf_path):
            os.makedirs(conf_path)
        conf_path = conf_path + "/" + profile_filename
        with open(conf_path, 'w') as configfile:
            conf.write(configfile)

    def browse_outdir(self):
        fd = QtWidgets.QFileDialog()
        fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        options = fd.options()
        self.folder = fd.getExistingDirectory(self, caption="Choose a directory to save the Subrack data",
                                              directory="/storage/", options=options)
        self.wg.qline_output_dir.setText(self.folder)
        #self.check_dir()
        #self.calc_data_volume()

    def switchChart(self):
        if self.wg.qcombo_chart.currentIndex() == 0:
            self.wg.qplot_chart_tpm.setVisible(False)
            self.wg.qplot_chart_mgn.setVisible(True)
        else:
            self.wg.qplot_chart_tpm.setVisible(True)
            self.wg.qplot_chart_mgn.setVisible(False)
        self.drawCharts()

    def drawCharts(self):
        # Draw selected chart
        if self.wg.qcombo_chart.currentIndex() == 0:
            # Chart: Subrack Temperatures
            self.plotChartMgn.set_ylim([0, 60])
            for n, k in enumerate(MgnTraces):
                self.plotChartMgn.plotCurve(data=self.data_charts[k][0::2], trace=(0 + n * 2), color=COLORI[(0 + n * 2)])
                self.plotChartMgn.plotCurve(data=self.data_charts[k][1::2], trace=(1 + n * 2), color=COLORI[(1 + n * 2)])
            self.plotChartMgn.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 1:
            # Chart: TPM Temperatures
            self.plotChartTpm.set_ylim([0, 100])
            self.plotChartTpm.set_ylabel("TPM Board Temperatures (deg)")
            for i in range(8):
                try:
                    self.plotChartTpm.plotCurve(data=self.data_charts["tpm_temperatures_0"][i::8], trace=i, color=COLORI[i])
                except:
                    print(self.data_charts.keys())
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 2:
            # Chart: TPM Temperatures
            self.plotChartTpm.set_ylim([0, 100])
            self.plotChartTpm.set_ylabel("TPM FPGA-0 Temperatures (deg)")
            for i in range(8):
                self.plotChartTpm.plotCurve(data=self.data_charts["tpm_temperatures_1"][i::8], trace=i, color=COLORI[i])
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 3:
            # Chart: TPM Temperatures
            self.plotChartTpm.set_ylim([0, 100])
            self.plotChartTpm.set_ylabel("TPM FPGA-1 Temperatures (deg)")
            for i in range(8):
                self.plotChartTpm.plotCurve(data=self.data_charts["tpm_temperatures_2"][i::8], trace=i, color=COLORI[i])
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 4:
            # Chart: TPM Powers
            self.plotChartTpm.set_ylim([0, 140])
            self.plotChartTpm.set_ylabel("TPM Powers (W)")
            for i in range(8):
                self.plotChartTpm.plotCurve(data=self.data_charts["tpm_powers"][i::8], trace=i, color=COLORI[i])
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 5:
            # Chart: TPM Currents
            self.plotChartTpm.set_ylim([0, 12])
            self.plotChartTpm.set_ylabel("TPM Currents (A)")
            for i in range(8):
                self.plotChartTpm.plotCurve(data=self.data_charts["tpm_currents"][i::8], trace=i, color=COLORI[i])
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 6:
            # Chart: TPM Voltages
            self.plotChartTpm.set_ylim([0, 16])
            self.plotChartTpm.set_ylabel("TPM Voltages (V)")
            for i in range(8):
                self.plotChartTpm.plotCurve(data=self.data_charts["tpm_voltages"][i::8], trace=i, color=COLORI[i])
            self.plotChartTpm.updatePlot()

    def drawBars(self):
        # Draw Bars
        for i in range(8):
            self.plotTpmPower.plotBar(data=self.attributes["tpm_powers"][i], bar=i, color=COLORI[i])
        self.plotTpmPower.set_xticklabels(labels=["%3.1f" % x for x in self.attributes["tpm_voltages"]])
        self.plotTpmPower.updatePlot()
        for i in range(2):
            self.plotPsu.plotBar(data=self.attributes["power_supply_powers"][i], bar=i, color=COLORI[i])
        self.plotPsu.updatePlot()
        for n, k in enumerate(MgnTraces):
            self.plotMgnTemp.plotBar(data=self.attributes[k][0], bar=(n * 2), color=COLORI[(n * 2)])
            self.plotMgnTemp.plotBar(data=self.attributes[k][1], bar=(1 + n * 2), color=COLORI[(1 + n * 2)])
        self.plotMgnTemp.updatePlot()

    def switchTpm(self, slot):
        if self.connected:
            if self.attributes["tpm_on_off"][slot]:
                self.client.execute_command(command="turn_off_tpm", parameters="%d" % (int(slot) + 1))
                print("Turn OFF TPM-%02d" % (int(slot) + 1))
            else:
                self.client.execute_command(command="turn_on_tpm", parameters="%d" % (int(slot) + 1))
                print("Turn ON TPM-%02d" % (int(slot) + 1))
            # self.getTelemetry()
            # self.signalTlm.emit()

    def switchTpmsOn(self):
        if self.connected:
            self.client.execute_command(command="turn_on_tpms")
            print("Turn ON ALL")
            self.skip = True

    def switchTpmsOff(self):
        if self.connected:
            self.client.execute_command(command="turn_off_tpms")
            print("Turn OFF ALL")
            self.skip = True

    def subrack_connect(self):
        if not self.wg.qline_ip.text() == "":
            if not self.connected:
                self.ip = self.wg.qline_ip.text().split(":")[0]
                self.port = int(self.wg.qline_ip.text().split(":")[1])
                print("Connecting to Subrack %s:%d..." % (self.ip, self.port))
                self.client = WebHardwareClient(self.ip, self.port)
                if self.client.connect():
                    self.subAttr = self.client.execute_command("list_attributes")["retvalue"]
                    self.wg.qbutton_connect.setStyleSheet("background-color: rgb(78, 154, 6);")
                    self.wg.qbutton_connect.setText("ONLINE")
                    self.wg.frame_tpm.setEnabled(True)
                    self.wg.frame_fan.setEnabled(True)
                    self.getTelemetry()
                    self.connected = True
                else:
                    self.wg.qlabel_message.setText("The SubRack server does not respond!")
                    self.wg.qbutton_connect.setStyleSheet("background-color: rgb(204, 0, 0);")
                    self.wg.qbutton_connect.setText("OFFLINE")
                    self.wg.frame_tpm.setEnabled(False)
                    self.wg.frame_fan.setEnabled(False)
                    self.client = None
                    self.connected = False
            else:
                self.connected = False
                self.wg.qbutton_connect.setStyleSheet("background-color: rgb(204, 0, 0);")
                self.wg.qbutton_connect.setText("OFFLINE")
                self.wg.frame_tpm.setEnabled(False)
                self.wg.frame_fan.setEnabled(False)
                self.client.disconnect()
                del self.client
                gc.collect()
        else:
            self.wg.qlabel_connection.setText("Missing IP!")

    def getTelemetry(self):
        try:
            attributes = {}
            for att in self.subAttr:
                attributes[att] = self.client.get_attribute(att)["value"]
        except:
            print("Error reading Telemetry, skipping...")
            pass
        for att in self.subAttr:
            if not att == "api_version":
                try:
                    if type(attributes[att]) is list:
                        if type(attributes[att][0]) is list:
                            for k in range(len(attributes[att])):
                                nested_att = ("%s_%d" % (att, k))
                                if nested_att not in self.data_charts.keys():
                                    self.data_charts[nested_att] = np.zeros(len(attributes[att][k]) * 201) * np.nan
                                self.data_charts[nested_att] = np.append(self.data_charts[nested_att][len(attributes[att][k]):], attributes[att][k])
                        else:
                            if att not in self.data_charts.keys():
                                self.data_charts[att] = np.zeros(len(attributes[att]) * 201) * np.nan
                            self.data_charts[att] = np.append(self.data_charts[att][len(attributes[att]):], attributes[att])
                    elif attributes[att] is not None:
                        if att not in self.data_charts.keys():
                            self.data_charts[att] = np.zeros(201) * np.nan
                        self.data_charts[att] = self.data_charts[att][1:] + [attributes[att]]
                except:
                    print("ERROR!!! ", self.subAttr)
        self.attributes = attributes

    def readTlm(self):
        while True:
            if self.connected:
                try:
                    self.getTelemetry()
                except:
                    pass
                sleep(0.2)
                self.signalTlm.emit()
                cycle = 0.0
                while cycle < (int(self.profile['Device']['query_interval']) - 1) and not self.skip:
                    sleep(0.5)
                    cycle = cycle + 0.5
                self.skip = False
            if self.stopThreads:
                break
            sleep(1)

    def updateTlm(self):
        self.wg.qlabel_message.setText("")
        self.drawBars()
        self.drawCharts()

        # TPM status on QButtons
        for n, fault in enumerate(self.attributes["tpm_supply_fault"]):
            if fault:
                self.qbutton_tpm[n].setStyleSheet(colors("yellow_on_black"))
            else:
                if self.attributes["tpm_present"][n]:
                    self.qbutton_tpm[n].setStyleSheet(colors("black_on_red"))
                else:
                    self.qbutton_tpm[n].setStyleSheet(colors("black_on_grey"))
                if self.attributes["tpm_on_off"][n]:
                    self.qbutton_tpm[n].setStyleSheet(colors("black_on_green"))

        # Fan status on Sliders
        for i in range(4):
            self.fans[i]['rpm'].setText("%d" % int(self.attributes['subrack_fan_speeds'][i]))
            self.fans[i]['slider'].setProperty("value", (int(self.attributes['subrack_fan_speeds_percent'][i])))
            if int(self.attributes['subrack_fan_mode'][i]) == 1:
                self.fans[i]['auto'].setStyleSheet(colors("black_on_green"))
                self.fans[i]['manual'].setStyleSheet(colors("black_on_red"))
            else:
                self.fans[i]['auto'].setStyleSheet(colors("black_on_red"))
                self.fans[i]['manual'].setStyleSheet(colors("black_on_green"))

    def closeEvent(self, event):
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Exit...",
                                                "Are you sure you want to exit ?",
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        event.ignore()

        if result == QtWidgets.QMessageBox.Yes:
            event.accept()
            self.stopThreads = True
            print("Stopping Threads")
            sleep(1)


if __name__ == "__main__":
    from optparse import OptionParser
    from sys import argv, stdout

    parser = OptionParser(usage="usage: %station_subrack [options]")
    parser.add_option("--profile", action="store", dest="profile",
                      type="str", default="Default", help="Subrack Profile to load")
    parser.add_option("--ip", action="store", dest="ip",
                      type="str", default=None, help="SubRack IP address [default: None]")
    parser.add_option("--port", action="store", dest="port",
                      type="int", default=8081, help="SubRack WebServer Port [default: 8081]")
    parser.add_option("--interval", action="store", dest="interval",
                      type="int", default=5, help="Time interval (sec) between telemetry requests [default: 5]")
    parser.add_option("--nogui", action="store_true", dest="nogui",
                      default=False, help="Do not show GUI")
    parser.add_option("--single", action="store_true", dest="single",
                      default=False, help="Single Telemetry Request. If not provided, the script runs indefinitely")
    parser.add_option("--directory", action="store", dest="directory",
                      type="str", default="", help="Output Directory [Default: "", it means do not save data]")
    (opt, args) = parser.parse_args(argv[1:])

    if not opt.nogui:
        app = QtWidgets.QApplication(sys.argv)
        window = Subrack(ip=opt.ip, port=opt.port, uiFile="skalab_subrack.ui", profile=opt.profile)
        window.signalTlm.connect(window.updateTlm)
        sys.exit(app.exec_())
    else:
        profile = []
        fullpath = default_app_dir + opt.profile + "/" + profile_filename
        if not os.path.exists(fullpath):
            print("\nThe SubRack Profile does not exist.\n")
        else:
            print("Loading SubRack Profile: " + opt.profile + " (" + fullpath + ")")
            profile = parse_profile(fullpath)
            profile_name = profile
            profile_file = fullpath

            # Overriding Configuration File with parameters
            if opt.ip is not None:
                ip = opt.ip
            else:
                ip = str(profile['Device']['ip'])
            if opt.port is not None:
                port = opt.port
            else:
                port = int(profile['Device']['port'])
            interval = int(profile['Device']['query_interval'])
            if not opt.interval == int(profile['Device']['query_interval']):
                interval = opt.interval

            connected = False
            if not opt.ip == "":
                client = WebHardwareClient(opt.ip, opt.port)
                if client.connect():
                    connected = True
                    subAttr = client.execute_command("list_attributes")["retvalue"]
                else:
                    print("Unable to connect to the Webserver on %s:%d" % (opt.ip, opt.port))
            if connected:
                if opt.single:
                    print("SINGLE REQUEST")
                    tstamp = dt_to_timestamp(datetime.datetime.utcnow())
                    attributes = {}
                    print("\nTstamp: %d\tDateTime: %s\n" % (tstamp, ts_to_datestring(tstamp)))
                    for att in subAttr:
                        attributes[att] = client.get_attribute(att)["value"]
                        print(att, attributes[att])
                else:
                    try:
                        print("CONTINUOUS REQUESTS")
                        while True:
                            tstamp = dt_to_timestamp(datetime.datetime.utcnow())
                            attributes = {}
                            print("\nTstamp: %d\tDateTime: %s\n" % (tstamp, ts_to_datestring(tstamp)))
                            for att in subAttr:
                                attributes[att] = client.get_attribute(att)["value"]
                                print(att, attributes[att])
                            sleep(opt.interval)
                    except KeyboardInterrupt:
                        print("\nTerminated by the user.\n")
                client.disconnect()
                del client

