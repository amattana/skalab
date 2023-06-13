#!/usr/bin/env python
import time

from skalab_base import SkalabBase
from skalab_log import SkalabLog
import gc
import os.path
import glob
import shutil
import sys
import numpy as np
import configparser
from PyQt5 import QtWidgets, uic, QtCore, QtGui
from hardware_client import WebHardwareClient
from skalab_utils import BarPlot, ChartPlots, colors, dt_to_timestamp
from skalab_utils import ts_to_datestring, parse_profile, COLORI, getTextFromFile
from threading import Thread
from time import sleep
import datetime
from pathlib import Path
import h5py
import logging

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
        fan['sliderPressed'] = False

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


class Subrack(SkalabBase):
    """ Main UI Window class """
    # Signal for Slots
    signalTlm = QtCore.pyqtSignal()

    def __init__(self, ip=None, port=None, uiFile="", profile="", size=[1190, 936], swpath=default_app_dir):
        """ Initialise main window """
        self.tlm_keys = []
        self.tpm_ips = []
        self.system = {}
        self.telemetry = {}
        self.query_once = []
        self.query_once_armed = False
        self.query_deny = []
        # self.query_tiles = []
        # Load window file
        self.wg = uic.loadUi(uiFile)
        self.wgProBox = QtWidgets.QWidget(self.wg.qtab_conf)
        self.wgProBox.setGeometry(QtCore.QRect(1, 1, 800, 860))
        self.wgProBox.setVisible(True)
        self.wgProBox.show()

        super(Subrack, self).__init__(App="subrack", Profile=profile, Path=swpath, parent=self.wgProBox)
        self.logger = SkalabLog(parent=self.wg.qw_log, logname=__name__, profile=self.profile)
        self.connected = False
        self.populate_table_profile()
        self.reload(ip=ip, port=port)
        self.updateRequest = False

        self.setCentralWidget(self.wg)
        self.resize(size[0], size[1])

        self.tlm_file = ""
        self.tlm_hdf = None

        # self.plotTpmPower = BarPlot(parent=self.wg.qplot_tpm_power, size=(4.95, 2.3), xlim=[0, 9], ylabel="Power (W)",
        self.plotTpmPower = BarPlot(parent=self.wg.qplot_tpm_power, size=(4, 2.3), xlim=[0, 9], ylabel="Power (W)",
                                    xrotation=0, xlabel="TPM Voltages", ylim=[0, 140],
                                    yticks=np.arange(0, 160, 20), xticks=np.zeros(9))

        # self.plotTpmTemp = BarPlot(parent=self.wg.qplot_tpm_temp, size=(4.95, 2.3), xlim=[0, 9],
        #                            ylabel="Temperature (deg)", xrotation=0, xlabel="TPM Board", ylim=[20, 100],
        #                            yticks=np.arange(20, 120, 20), xticks=np.arange(9))

        # self.plotMgnTemp = BarPlot(parent=self.wg.qplot_mgn_temp, size=(2.7, 2.3), xlim=[0, 5], ylim=[0, 60],
        self.plotMgnTemp = BarPlot(parent=self.wg.qplot_mgn_temp, size=(2, 2.3), xlim=[0, 5], ylim=[0, 60],
                                   ylabel="Temperature (deg)", xrotation=0, xlabel="Subrack Temps",
                                   yticks=[0, 10, 20, 30, 40, 50, 60], xticks=["", "M1", "M2", "B1", "B2"])
                                   # yticks=[0, 10, 20, 30, 40, 50, 60], xticks=["", "Mgn-1", "Mgn-2", "Bck-1", "Bck-2"])

        # self.plotPsu = BarPlot(parent=self.wg.qplot_psu, size=(2.7, 2.3), xlim=[0, 3], ylabel="Power (W)",
        self.plotPsu = BarPlot(parent=self.wg.qplot_psu, size=(2, 2.3), xlim=[0, 3], ylabel="Power (W)",
                               xrotation=0, xlabel="PSU", ylim=[0, 1200], xticks=["", "P1", "P2"],
                               yticks=np.arange(0, 1400, 200))

        self.plotChartMgn = ChartPlots(parent=self.wg.qplot_chart_mgn, ntraces=4, xlabel="time samples", ylim=[0, 60],
                                       ylabel="Subrack Temperatures", size=(11.3, 3.45), xlim=[0, 200])

        self.plotChartTpm = ChartPlots(parent=self.wg.qplot_chart_tpm, ntraces=8, xlabel="time samples", ylim=[0, 120],
                                       ylabel="TPM Power", size=(11.3, 3.45), xlim=[0, 200])

        self.client = None
        self.qbutton_tpm = populateSlots(self.wg.frame_tpm)
        self.fans = populateFans(self.wg.frame_fan)
        self.data_charts = {}

        self.load_events()
        self.show()
        self.stopThreads = False
        self.skipThreadPause = False
        self.processTlm = Thread(target=self.readTlm)
        self.processTlm.start()
        # print("Start Thread Subrack readTlm")


        self.wg.qplot_chart_tpm.setVisible(False)

        self.populate_help()

    def load_events(self):
        self.wg.qbutton_connect.clicked.connect(lambda: self.connect())
        self.wg.qbutton_check_ips.clicked.connect(lambda: self.checkIps())
        for n, t in enumerate(self.qbutton_tpm):
            t.clicked.connect(lambda state, g=n: self.cmdSwitchTpm(g))
        self.wg.qbutton_tpm_on.clicked.connect(lambda: self.cmdSwitchTpmsOn())
        self.wg.qbutton_tpm_off.clicked.connect(lambda: self.cmdSwitchTpmsOff())
        self.wg.qcombo_chart.currentIndexChanged.connect(lambda: self.switchChart())
        self.wg.qbutton_clear_chart.clicked.connect(lambda: self.clearChart())
        for i in range(4):
            self.fans[i]['manual'].clicked.connect(lambda state, g=i: self.cmdSetFanManual(fan_id=g))
            self.fans[i]['auto'].clicked.connect(lambda state, g=i: self.cmdSetFanAuto(fan_id=g))
            #self.fans[i]['slider'].valueChanged.connect(lambda state, g=i: self.cmdSetFanSpeed(fan_id=g))
            self.fans[i]['slider'].sliderPressed.connect(lambda g=i: self.sliderPressed(fan_id=g))
            self.fans[i]['slider'].sliderReleased.connect(lambda g=i: self.cmdSetFanSpeed(fan_id=g))

    def reload(self, ip=None, port=None):
        if ip is not None:
            self.ip = ip
        else:
            self.ip = str(self.profile['Subrack']['ip'])
        if port is not None:
            self.port = port
        else:
            self.port = int(self.profile['Subrack']['port'])
        self.wg.qline_ip.setText("%s (%d)" % (self.ip, self.port))
        if 'Query' in self.profile.keys():
            if 'once' in self.profile['Query'].keys():
                self.query_once = list(self.profile['Query']['once'].split(","))
            if 'deny' in self.profile['Query'].keys():
                self.query_deny = list(self.profile['Query']['deny'].split(","))
            # if 'tiles' in self.profile['Query'].keys():
            #     self.query_tiles = list(self.profile['Query']['tiles'].split(","))

    def populate_help(self, uifile="Gui/skalab_subrack.ui"):
        with open(uifile) as f:
            data = f.readlines()
        helpkeys = [d[d.rfind('name="Help_'):].split('"')[1] for d in data if 'name="Help_' in d]
        for k in helpkeys:
            self.wg.findChild(QtWidgets.QTextEdit, k).setText(getTextFromFile(k.replace("_", "/")+".html"))

    def cmdSwitchTpm(self, slot):
        if self.connected:
            if self.telemetry["tpm_on_off"][slot]:
                self.client.execute_command(command="turn_off_tpm", parameters="%d" % (int(slot) + 1))
                self.logger.info("Turn OFF TPM-%02d" % (int(slot) + 1))
                #print("Turn OFF TPM-%02d" % (int(slot) + 1))
            else:
                self.client.execute_command(command="turn_on_tpm", parameters="%d" % (int(slot) + 1))
                self.logger.info("Turn ON TPM-%02d" % (int(slot) + 1))
                #print("Turn ON TPM-%02d" % (int(slot) + 1))
            if "tpm_on_off" in self.system.keys():
                data = self.client.get_attribute("tpm_on_off")
                while not data["status"] == "OK":
                    self.logger.info("Waiting for operation complete: " + data["info"])
                    time.sleep(0.5)
                    data = self.client.get_attribute("tpm_on_off")
            time.sleep(0.5)
            self.checkTpmIps()

    def cmdSwitchTpmsOn(self):
        if self.connected:
            self.client.execute_command(command="turn_on_tpms")
            self.logger.info("Turn On ALL TPMs")
            self.skipThreadPause = True
            if "tpm_on_off" in self.system.keys():
                data = self.client.get_attribute("tpm_on_off")
                while not data["status"] == "OK":
                    self.logger.info("Waiting for operation complete: " + data["info"])
                    time.sleep(0.5)
                    data = self.client.get_attribute("tpm_on_off")
            time.sleep(0.5)
            self.checkTpmIps()

    def cmdSwitchTpmsOff(self):
        if self.connected:
            self.client.execute_command(command="turn_off_tpms")
            self.logger.info("Turn Off ALL TPMs")
            self.skipThreadPause = True
            if "tpm_on_off" in self.system.keys():
                data = self.client.get_attribute("tpm_on_off")
                while not data["status"] == "OK":
                    self.logger.info("Waiting for operation complete: " + data["info"])
                    time.sleep(0.5)
                    data = self.client.get_attribute("tpm_on_off")
            time.sleep(0.5)
            self.checkTpmIps()

    def cmdSetFanManual(self, fan_id):
        if self.connected:
            self.client.execute_command(command="set_fan_mode", parameters="%d,0" % (fan_id + 1))
            self.logger.info("Set FAN Mode MANUAL on FAN #%d" % (fan_id + 1))
            self.skipThreadPause = True

    def cmdSetFanAuto(self, fan_id):
        if self.connected:
            self.client.execute_command(command="set_fan_mode", parameters="%d,1" % (fan_id + 1))
            self.logger.info("Set FAN Mode AUTO on FAN #%d" % (fan_id + 1))
            self.skipThreadPause = True

    def cmdSetFanSpeed(self, fan_id):
        if self.connected:
            self.client.execute_command(command="set_subrack_fan_speed",
                                        parameters="%d,%d" % (fan_id + 1, int(self.fans[fan_id]['slider'].value())))
            self.logger.info("Set FAN SPEED %d on FAN #%d" % (int(self.fans[fan_id]['slider'].value()), fan_id + 1))
            self.fans[fan_id]['sliderPressed'] = False
            self.skipThreadPause = True

    def sliderPressed(self, fan_id):
        self.fans[fan_id]['sliderPressed'] = True

    def switchChart(self):
        if self.wg.qcombo_chart.currentIndex() == 0:
            self.wg.qplot_chart_tpm.setVisible(False)
            self.wg.qplot_chart_mgn.setVisible(True)
        else:
            self.wg.qplot_chart_tpm.setVisible(True)
            self.wg.qplot_chart_mgn.setVisible(False)
        self.drawCharts()

    def drawCharts(self):
        self.plotChartMgn.set_xlabel("time sample")
        self.plotChartTpm.set_xlabel("time sample")
        # Draw selected chart
        if self.wg.qcombo_chart.currentIndex() == 0:
            # Chart: Subrack Temperatures
            self.plotChartMgn.set_ylim([0, 60])
            if MgnTraces[0] in self.data_charts.keys():
                for n, k in enumerate(MgnTraces):
                    self.plotChartMgn.plotCurve(data=self.data_charts[k][0::2], trace=(0 + n * 2), color=COLORI[(0 + n * 2)])
                    self.plotChartMgn.plotCurve(data=self.data_charts[k][1::2], trace=(1 + n * 2), color=COLORI[(1 + n * 2)])
            else:
                self.plotChartMgn.set_xlabel("Subrack attributes '" + MgnTraces[0] + "' and '" + MgnTraces[1] + "' not available.")
            self.plotChartMgn.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 1:
            # Chart: TPM Temperatures
            self.plotChartTpm.set_ylim([0, 100])
            self.plotChartTpm.set_ylabel("TPM Board Temperatures (deg)")
            if "tpms_temperatures_0" in self.data_charts.keys():
                for i in range(8):
                    self.plotChartTpm.plotCurve(data=self.data_charts["tpms_temperatures_0"][i::8], trace=i, color=COLORI[i])
            else:
                self.plotChartTpm.set_xlabel("Subrack attribute 'tpms_temperatures_0' not available.")
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 2:
            # Chart: TPM Temperatures
            self.plotChartTpm.set_ylim([0, 100])
            self.plotChartTpm.set_ylabel("TPM FPGA-0 Temperatures (deg)")
            if "tpms_temperatures_1" in self.data_charts.keys():
                for i in range(8):
                    self.plotChartTpm.plotCurve(data=self.data_charts["tpms_temperatures_1"][i::8], trace=i, color=COLORI[i])
            else:
                self.plotChartTpm.set_xlabel("Subrack attribute 'tpms_temperatures_1' not available.")
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 3:
            # Chart: TPM Temperatures
            self.plotChartTpm.set_ylim([0, 100])
            self.plotChartTpm.set_ylabel("TPM FPGA-1 Temperatures (deg)")
            if "tpms_temperatures_2" in self.data_charts.keys():
                for i in range(8):
                    self.plotChartTpm.plotCurve(data=self.data_charts["tpms_temperatures_2"][i::8], trace=i, color=COLORI[i])
            else:
                self.plotChartTpm.set_xlabel("Subrack attribute 'tpms_temperatures_2' not available.")
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 4:
            # Chart: TPM Powers
            self.plotChartTpm.set_ylim([0, 140])
            self.plotChartTpm.set_ylabel("TPM Powers (W)")
            if "tpm_powers" in self.data_charts.keys():
                for i in range(8):
                    self.plotChartTpm.plotCurve(data=self.data_charts["tpm_powers"][i::8], trace=i, color=COLORI[i])
            else:
                self.plotChartTpm.set_xlabel("Subrack attribute 'tpm_powers' not available.")
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 5:
            # Chart: TPM Currents
            self.plotChartTpm.set_ylim([0, 12])
            self.plotChartTpm.set_ylabel("TPM Currents (A)")
            if "tpm_currents" in self.data_charts.keys():
                for i in range(8):
                    self.plotChartTpm.plotCurve(data=self.data_charts["tpm_currents"][i::8], trace=i, color=COLORI[i])
            else:
                self.plotChartTpm.set_xlabel("Subrack attribute 'tpm_currents' yet available.")
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 6:
            # Chart: TPM Voltages
            self.plotChartTpm.set_ylim([0, 16])
            self.plotChartTpm.set_ylabel("TPM Voltages (V)")
            if "tpm_voltages" in self.data_charts.keys():
                for i in range(8):
                    self.plotChartTpm.plotCurve(data=self.data_charts["tpm_voltages"][i::8], trace=i, color=COLORI[i])
            else:
                self.plotChartTpm.set_xlabel("Subrack attribute 'tpm_voltages' not available.")
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 7:
            # Chart: TPM Voltages
            self.plotChartTpm.set_ylim([0, 50])
            self.plotChartTpm.set_ylabel("Power Supply Fan Speed")
            if "power_supply_fan_speeds" in self.data_charts.keys():
                for i in range(2):
                    self.plotChartTpm.plotCurve(data=self.data_charts["power_supply_fan_speeds"][i::2], trace=i,
                                                color=COLORI[i])
            else:
                self.plotChartTpm.set_xlabel("Subrack attribute 'power_supply_fan_speeds' not available.")
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 8:
            # Chart: TPM Voltages
            self.plotChartTpm.set_ylim([0, 1200])
            self.plotChartTpm.set_ylabel("Power Supply Powers")
            if "power_supply_powers" in self.data_charts.keys():
                for i in range(2):
                    self.plotChartTpm.plotCurve(data=self.data_charts["power_supply_powers"][i::2], trace=i,
                                                color=COLORI[i])
            else:
                self.plotChartTpm.set_xlabel("Subrack attribute 'power_supply_powers' not available.")
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 9:
            # Chart: TPM Voltages
            self.plotChartTpm.set_ylim([0, 100])
            self.plotChartTpm.set_ylabel("Power Supply Currents")
            if "power_supply_currents" in self.data_charts.keys():
                for i in range(2):
                    self.plotChartTpm.plotCurve(data=self.data_charts["power_supply_currents"][i::2], trace=i,
                                                color=COLORI[i])
            else:
                self.plotChartTpm.set_xlabel("Subrack attribute 'power_supply_currents' not available.")
            self.plotChartTpm.updatePlot()
        elif self.wg.qcombo_chart.currentIndex() == 10:
            # Chart: TPM Voltages
            self.plotChartTpm.set_ylim([0, 15])
            self.plotChartTpm.set_ylabel("Power Supply Voltages")
            if "power_supply_voltages" in self.data_charts.keys():
                for i in range(2):
                    self.plotChartTpm.plotCurve(data=self.data_charts["power_supply_voltages"][i::2], trace=i,
                                                color=COLORI[i])
            else:
                self.plotChartTpm.set_xlabel("Subrack attribute 'power_supply_voltages' not available.")
            self.plotChartTpm.updatePlot()

    def clearChart(self):
        del self.data_charts
        gc.collect()
        self.data_charts = {}

    def drawBars(self):
        # Draw Bars
        if ("tpm_powers" in self.telemetry.keys()) and ("tpm_voltages" in self.telemetry.keys()):
            self.plotTpmPower.set_xlabel("TPM Voltages")
            for i in range(8):
                self.plotTpmPower.plotBar(data=self.telemetry["tpm_powers"][i], bar=i, color=COLORI[i])
            self.plotTpmPower.set_xticklabels(labels=["%3.1f" % x for x in self.telemetry["tpm_voltages"]])
        else:
            self.logger.error("No data available")
            self.logger.error(self.telemetry.keys())
            self.plotTpmPower.set_xlabel("No data available")
        self.plotTpmPower.updatePlot()
        if "power_supply_powers" in self.telemetry.keys():
            self.plotPsu.set_xlabel("PSU")
            for i in range(2):
                self.plotPsu.plotBar(data=self.telemetry["power_supply_powers"][i], bar=i, color=COLORI[i])
        else:
            self.plotPsu.set_xlabel("No data available")
        self.plotPsu.updatePlot()
        if (MgnTraces[0] in self.telemetry.keys()) and (MgnTraces[1] in self.telemetry.keys()):
            self.plotMgnTemp.set_xlabel("SubRack Temps")
            for n, k in enumerate(MgnTraces):
                self.plotMgnTemp.plotBar(data=self.telemetry[k][0], bar=(n * 2), color=COLORI[(n * 2)])
                self.plotMgnTemp.plotBar(data=self.telemetry[k][1], bar=(1 + n * 2), color=COLORI[(1 + n * 2)])
        else:
            self.plotMgnTemp.set_xlabel("No data available")
        self.plotMgnTemp.updatePlot()
        # if "tpms_temperatures_0" in self.telemetry.keys():
        #     self.plotTpmTemp.set_xlabel("TPM Board Temperatures")
        #     for i in range(8):
        #         self.plotTpmTemp.plotBar(data=self.telemetry["tpms_temperatures_0"][i], bar=i, color=COLORI[i])
        # else:
        #     self.plotTpmTemp.set_xlabel("No data available")
        # self.plotTpmTemp.updatePlot()

    def setup_hdf5(self):
        if not self.profile['Subrack']['data_path'] == "":
            fname = self.profile['Subrack']['data_path']
            if not fname[-1] == "/":
                fname = fname + "/"
            fname += datetime.datetime.strftime(datetime.datetime.utcnow(), "subrack_tlm_%Y-%m-%d_%H%M%S.h5")
            return h5py.File(fname, 'a')
        else:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Please Select a valid path to save the Subrack data and save it into the current profile")
            msgBox.setWindowTitle("Error!")
            msgBox.setIcon(QtWidgets.QMessageBox.Critical)
            msgBox.exec_()
            return None

    def connect(self):
        if not self.wg.qline_ip.text() == "":
            if not self.connected:
                self.logger.logger.info("Connecting to Subrack %s:%d..." % (self.ip, int(self.port)))
                self.client = WebHardwareClient(self.ip, self.port)
                if self.client.connect():
                    self.logger.logger.info("Successfully connected")
                    self.connected = True
                    self.logger.logger.info("Querying list of Subrack API attributes")
                    self.tlm_keys = self.client.execute_command("list_attributes")["retvalue"]
                    self.checkTpmIps()
                    self.wg.qbutton_connect.setStyleSheet("background-color: rgb(78, 154, 6);")
                    self.wg.qbutton_connect.setText("ONLINE")
                    self.wg.frame_tpm.setEnabled(True)
                    self.wg.frame_fan.setEnabled(True)
                    self.tlm_hdf = self.setup_hdf5()
                    self.getTelemetry()

                else:
                    self.wg.qlabel_message.setText("The Subrack server does not respond!")
                    self.logger.logger.error("Unable to connect to the Subrack server %s:%d" % (self.ip, int(self.port)))
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
                if type(self.tlm_hdf) is not None:
                    try:
                        self.tlm_hdf.close()
                    except:
                        pass
        else:
            self.wg.qlabel_connection.setText("Missing IP!")

    def checkIps(self):
        if self.connected:
            self.checkTpmIps()
        else:
            self.logger.warning("TPM IPs check can be done only when the Subrack connection is active.")

    def checkTpmIps(self):
        if self.connected:
            self.logger.info("Checking available TPM IPs...")
            for tlmk in self.tlm_keys:
                if tlmk in self.query_once:
                    data = self.client.get_attribute(tlmk)
                    self.logger.logger.debug("GET_ATT: ", tlmk, data)
                    if data["status"] == "OK":
                        self.system[tlmk] = data["value"]
                    else:
                        retry = 0
                        time.sleep(0.1)
                        while (retry < 10) and (not data["status"] == "OK"):
                            data = self.client.get_attribute(tlmk)
                            self.logger.logger.info("RETRY: ", retry, data)
                            retry = retry + 1
                            time.sleep(0.1)
                            if data["status"] == "OK":
                                self.system[tlmk] = data["value"]
                            else:
                                self.system[tlmk] = data["info"]

            if 'api_version' in self.system.keys():
                tpm_ips = []
                self.wg.qlabel_message.setText("SubRack API version: " + self.system['api_version'])
                self.logger.logger.info("Subrack API version: " + self.system['api_version'])
                if "assigned_tpm_ip_adds" in self.system.keys():
                    if "tpm_present" in self.system.keys():
                        if "tpm_on_off" in self.system.keys():
                            for i in range(len(self.system["tpm_present"])):
                                msg = "SLOT %d: " % (i + 1)
                                if self.system["tpm_present"][i]:
                                    if self.system["tpm_on_off"][i]:
                                        msg += self.system["assigned_tpm_ip_adds"][i]
                                        tpm_ips += [self.system["assigned_tpm_ip_adds"][i]]
                                    else:
                                        msg += "OFF"
                                else:
                                    msg += "np"
                                self.logger.info(msg)
                if not tpm_ips == self.tpm_ips:
                    self.tpm_ips = tpm_ips.copy()
                    self.updateRequest = True
            else:
                self.logger.logger.warning("The Subrack is running with a very old API version!")


    def getTelemetry(self):
        tkey = ""
        telemetry = {}
        try:
            for tlmk in self.tlm_keys:
                tkey = tlmk
                if not tlmk in self.query_deny:
                    if self.connected:
                        data = self.client.get_attribute(tlmk)
                        if data["status"] == "OK":
                            telemetry[tlmk] = data["value"]
                if self.query_once_armed and (tlmk in self.query_once):
                    if self.connected:
                        data = self.client.get_attribute(tlmk)
                        if data["status"] == "OK":
                            telemetry[tlmk] = data["value"]
                        else:
                            telemetry[tlmk] = data["info"]
        except:
            self.logger.logger.error("Error reading Telemetry [attribute: %s], skipping..." % tkey)
            return
        self.telemetry = dict(telemetry)
        for tlmk in telemetry.keys():
            if tlmk not in self.query_deny:
                if type(telemetry[tlmk]) is list:
                    if type(telemetry[tlmk][0]) is list:
                        for k in range(len(telemetry[tlmk])):
                            nested_att = ("%s_%d" % (tlmk, k))
                            if nested_att not in self.data_charts.keys():
                                self.data_charts[nested_att] = np.zeros(len(telemetry[tlmk][k]) * 201) * np.nan
                            self.data_charts[nested_att] = \
                                np.append(self.data_charts[nested_att][len(telemetry[tlmk][k]):],
                                          telemetry[tlmk][k])
                            self.telemetry["%s_%d" % (tlmk, k)] = list(telemetry[tlmk][k])
                        del self.telemetry[tlmk]
                    else:
                        if tlmk not in self.data_charts.keys():
                            self.data_charts[tlmk] = np.zeros(len(telemetry[tlmk]) * 201) * np.nan
                        self.data_charts[tlmk] = np.append(self.data_charts[tlmk][len(telemetry[tlmk]):], telemetry[tlmk])
                elif telemetry[tlmk] is not None:
                    if tlmk not in self.data_charts.keys():
                        self.data_charts[tlmk] = np.zeros(201) * np.nan
                    try:
                        self.data_charts[tlmk] = self.data_charts[tlmk][1:] + [telemetry[tlmk]]
                    except:
                        self.logger.logger.error("ERROR --> key:", tlmk, "\nValue: ", telemetry[tlmk])
                        pass
                else:
                    if tlmk not in self.data_charts.keys():
                        self.data_charts[tlmk] = np.zeros(201) * np.nan
                    self.data_charts[tlmk] = self.data_charts[tlmk][1:] + [np.nan]
        self.writeTlm()

    def setup_hdf5(self):
        if not self.profile['Subrack']['data_path'] == "":
            fname = self.profile['Subrack']['data_path']
            if not fname[-1] == "/":
                fname = fname + "/"
                if  os.path.exists(str(Path.home()) + fname) != True:
                    os.makedirs(str(Path.home()) + fname)
            fname += datetime.datetime.strftime(datetime.datetime.utcnow(), "subrack_tlm_%Y-%m-%d_%H%M%S.h5")
            return h5py.File(str(Path.home()) + fname, 'a')
        else:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Please Select a valid path to save the Subrack data and save it into the current profile")
            msgBox.setWindowTitle("Error!")
            msgBox.setIcon(QtWidgets.QMessageBox.Critical)
            msgBox.exec_()
            return None

    def connect(self):
        if not self.wg.qline_ip.text() == "":
            if not self.connected:
                print("Connecting to Subrack %s:%d..." % (self.ip, int(self.port)))
                self.client = WebHardwareClient(self.ip, self.port)
                if self.client.connect():
                    self.tlm_keys = self.client.execute_command("list_attributes")["retvalue"]
                    for tlmk in self.tlm_keys:
                        if tlmk in self.query_once:
                            data = self.client.get_attribute(tlmk)
                            if data["status"] == "OK":
                                self.telemetry[tlmk] = data["value"]
                            else:
                                self.telemetry[tlmk] = data["info"]
                    if 'api_version' in self.telemetry.keys():
                        self.wg.qlabel_message.setText("Subrack API version: " + self.telemetry['api_version'])
                    self.wg.qbutton_connect.setStyleSheet("background-color: rgb(78, 154, 6);")
                    self.wg.qbutton_connect.setText("ONLINE")
                    self.wg.frame_tpm.setEnabled(True)
                    self.wg.frame_fan.setEnabled(True)
                    self.connected = True

                    self.tlm_hdf = self.setup_hdf5()
                    self.getTelemetry()
                else:
                    self.wg.qlabel_message.setText("The Subrack server does not respond!")
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
                if (type(self.tlm_hdf) is not None):
                    try:
                        self.tlm_hdf.close()
                    except:
                        pass
        else:
            self.wg.qlabel_connection.setText("Missing IP!")

    def getTelemetry(self):
        tkey = ""
        telemetry = {}
        try:
            for tlmk in self.tlm_keys:
                tkey = tlmk
                if not tlmk in self.query_deny:
                    if self.connected:
                        data = self.client.get_attribute(tlmk)
                        if data["status"] == "OK":
                            telemetry[tlmk] = data["value"]
        except:
            print("Error reading Telemetry [attribute: %s], skipping..." % tkey)
            return
        return telemetry

    def writeTlm(self):
        if self.tlm_hdf is not None:
            for tlmk in self.telemetry.keys():
                if tlmk not in self.tlm_hdf:
                    try:
                        if type(self.telemetry[tlmk]) is list:
                            self.tlm_hdf.create_dataset(tlmk, data=[self.telemetry[tlmk]], chunks=True,
                                                        maxshape=(None, len(self.telemetry[tlmk])))
                        else:
                            self.tlm_hdf.create_dataset(tlmk, data=[[self.telemetry[tlmk]]],
                                                        chunks=True, maxshape=(None, 1))
                    except:
                        self.logger.logger.error("HDF5 WRITE TLM ERROR in ", tlmk, "\nData: ", self.telemetry[tlmk])
                else:
                    if type(self.telemetry[tlmk]) is list:
                        self.tlm_hdf[tlmk].resize((self.tlm_hdf[tlmk].shape[0] +
                                                   np.array([self.tlm_hdf[tlmk]]).shape[0]), axis=0)
                        self.tlm_hdf[tlmk][-np.array([self.telemetry[tlmk]]).shape[0]:] = np.array([self.telemetry[tlmk]])
                    else:
                        self.tlm_hdf[tlmk].resize(self.tlm_hdf[tlmk].shape[0] + 1, axis=0)
                        self.tlm_hdf[tlmk][-1] = self.telemetry[tlmk]

    # def getTiles(self):
    #     try:
    #         for tlmk in self.query_tiles:
    #             data = self.client.get_attribute(tlmk)
    #             if data["status"] == "OK":
    #                 self.telemetry[tlmk] = data["value"]
    #             else:
    #                 self.telemetry[tlmk] = []
    #         return self.telemetry['tpm_ips']
    #     except:
    #         return []

    def readTlm(self):
        while True:
            if self.connected:
                try:
                    self.getTelemetry()
                    sleep(0.1)
                    self.signalTlm.emit()
                except:
                    self.logger.logger.warning("Failed to get Subrack Telemetry!")
                    pass
                cycle = 0.0
                while ((cycle < (float(self.profile['Subrack']['query_interval']))) and (not self.skipThreadPause) and (not self.stopThreads)):
                    sleep(0.1)
                    cycle = cycle + 0.1
                self.skipThreadPause = False
            if self.stopThreads:
                # print("Stopping Thread Subrack ReadTlm")
                break
            sleep(0.5)

    def updateTlm(self):
        #self.wg.qlabel_message.setText("")
        self.drawBars()
        self.drawCharts()

        # TPM status on QButtons
        if "tpm_supply_fault" in self.telemetry.keys():
            for n, fault in enumerate(self.telemetry["tpm_supply_fault"]):
                if fault:
                    self.qbutton_tpm[n].setStyleSheet(colors("yellow_on_black"))
                else:
                    if "tpm_present" in self.telemetry.keys():
                        if self.telemetry["tpm_present"][n]:
                            self.qbutton_tpm[n].setStyleSheet(colors("black_on_red"))

                        else:
                            self.qbutton_tpm[n].setStyleSheet(colors("black_on_grey"))
                    if "tpm_on_off" in self.telemetry.keys():
                        if self.telemetry["tpm_on_off"][n]:
                            self.qbutton_tpm[n].setStyleSheet(colors("black_on_green"))

        # Fan status on Sliders
        if ('subrack_fan_speeds' in self.telemetry.keys()) and ('subrack_fan_speeds_percent' in self.telemetry.keys()):
            for i in range(4):
                self.fans[i]['rpm'].setText("%d" % int(self.telemetry['subrack_fan_speeds'][i]))
                if not self.fans[i]['sliderPressed']:
                    self.fans[i]['slider'].setProperty("value", (int(self.telemetry['subrack_fan_speeds_percent'][i])))
                if 'subrack_fan_mode' in self.telemetry.keys() and int(self.telemetry['subrack_fan_mode'][i]) == 1:
                    self.fans[i]['auto'].setStyleSheet(colors("black_on_green"))
                    self.fans[i]['manual'].setStyleSheet(colors("black_on_red"))
                else:
                    self.fans[i]['auto'].setStyleSheet(colors("black_on_red"))
                    self.fans[i]['manual'].setStyleSheet(colors("black_on_green"))

        if "subrack_timestamp" in self.telemetry.keys():
            self.wg.qlabel_tstamp.setText("SUBRACK UTC TIME:     " +
                                          ts_to_datestring(int(self.telemetry['subrack_timestamp'])))
        else:
            self.wg.qlabel_tstamp.setText("")

    def cmdClose(self):
        self.stopThreads = True
        self.logger.logger.info("Stopping Threads")
        self.logger.stopLog()
        if type(self.tlm_hdf) is not None:
            try:
                self.tlm_hdf.close()
            except:
                pass

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
            if type(self.tlm_hdf) is not None:
                try:
                    self.tlm_hdf.close()
                except:
                    pass
            self.logger.stopLog()
            sleep(1)


if __name__ == "__main__":
    from optparse import OptionParser
    from sys import argv, stdout

    parser = OptionParser(usage="usage: %station_subrack [options]")
    parser.add_option("--profile", action="store", dest="profile",
                      type="str", default="Default", help="Subrack Profile to load")
    parser.add_option("--ip", action="store", dest="ip",
                      type="str", default=None, help="Subrack IP address [default: None]")
    parser.add_option("--port", action="store", dest="port",
                      type="int", default=8081, help="Subrack WebServer Port [default: 8081]")
    parser.add_option("--interval", action="store", dest="interval",
                      type="int", default=5, help="Time interval (sec) between telemetry requests [default: 5]")
    parser.add_option("--nogui", action="store_true", dest="nogui",
                      default=False, help="Do not show GUI")
    parser.add_option("--single", action="store_true", dest="single",
                      default=False, help="Single Telemetry Request. If not provided, the script runs indefinitely")
    parser.add_option("--directory", action="store", dest="directory",
                      type="str", default="", help="Output Directory [Default: "", it means do not save data]")
    (opt, args) = parser.parse_args(argv[1:])

    subrack_logger = logging.getLogger(__name__)
    if not opt.nogui:
        app = QtWidgets.QApplication(sys.argv)
        window = Subrack(ip=opt.ip, port=opt.port, uiFile="Gui/skalab_subrack.ui", profile=opt.profile, swpath=default_app_dir)
        window.signalTlm.connect(window.updateTlm)
        sys.exit(app.exec_())
    else:
        profile = []
        fullpath = default_app_dir + opt.profile + "/" + profile_filename
        if not os.path.exists(fullpath):
            subrack_logger.error("\nThe Subrack Profile does not exist.\n")
        else:
            subrack_logger.info("Loading Subrack Profile: " + opt.profile + " (" + fullpath + ")")
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
                    tlm_keys = client.execute_command("list_attributes")["retvalue"]
                else:
                    subrack_logger.error("Unable to connect to the Webserver on %s:%d" % (opt.ip, opt.port))
            if connected:
                if opt.single:
                    subrack_logger.info("SINGLE REQUEST")
                    tstamp = dt_to_timestamp(datetime.datetime.utcnow())
                    attributes = {}
                    subrack_logger.info("\nTstamp: %d\tDateTime: %s\n" % (tstamp, ts_to_datestring(tstamp)))
                    for att in tlm_keys:
                        attributes[att] = client.get_attribute(att)["value"]
                        subrack_logger.info("%s\t%s" % (att, str(attributes[att])))
                else:
                    try:
                        subrack_logger.info("CONTINUOUS REQUESTS")
                        while True:
                            tstamp = dt_to_timestamp(datetime.datetime.utcnow())
                            attributes = {}
                            subrack_logger.info("\nTstamp: %d\tDateTime: %s\n" % (tstamp, ts_to_datestring(tstamp)))
                            for att in subAttr:
                                attributes[att] = client.get_attribute(att)["value"]
                                subrack_logger.info("%s\t%s" % (att, str(attributes[att])))
                            sleep(opt.interval)
                    except KeyboardInterrupt:
                        subrack_logger.info("\nTerminated by the user.\n")
                client.disconnect()
                del client

