import os.path
import sys
import gc
from pyaavs.tile_wrapper import Tile
from PyQt5 import QtWidgets, uic, QtCore
from hardware_client import WebHardwareClient
from skalab_base import SkalabBase
from skalab_log import SkalabLog
from skalab_utils import dt_to_timestamp, ts_to_datestring, parse_profile, COLORI, Led, getTextFromFile, colors
from threading import Thread, Event, Lock
from time import sleep
import datetime
from pathlib import Path
import h5py
import numpy as np
import logging


default_app_dir = str(Path.home()) + "/.skalab/"
default_profile = "Default"
profile_filename = "monitor.ini"
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

subrack_attribute = {
                "backplane_temperatures": [None]*4,
                "board_temperatures": [None]*4,
                "power_supply_fan_speeds": [None]*4,
                "power_supply_powers": [None]*4,
                "subrack_fan_speeds": [None]*8,
                "subrack_fan_speeds_percent": [None]*8,
                }

tile_table_attr =  {"FPGA0": [None]*16,
                    "FPGA1": [None]*16,
                    "board":[None]*16,
                    "DDR0_VREF":[None]*16,
                    "VIN":[None]*16,
                    "MON_5V0":[None]*16,
                    "FE0_mVA":[None]*16,
                    "FE1_mVA":[None]*16,
                    }

def populate_table(qtable, attribute):
    j = 0
    for k in attribute:
        for v in range(0,16,2):
            layout = 0
            layout=QtWidgets.QVBoxLayout()
            attribute[k][v] = QtWidgets.QLineEdit(qtable)
            attribute[k][v+1]= QtWidgets.QLineEdit(qtable)
            layout.addWidget(attribute[k][v])
            layout.addWidget(attribute[k][v+1])
            cellWidget = QtWidgets.QWidget()
            cellWidget.setLayout(layout)
            qtable.setCellWidget(int(v/2),j,cellWidget)
        j+=1

def populate_subrack_ps(frame, attribute):
    j=0
    for k in attribute:
        for v in range(0,len(attribute[k]),2):
            size_x = 400 if (k == "subrack_fan_speeds_percent" ) else 120
            size_y = 10 if k == "subrack_fan_speeds_percent" else 47
            if k == "subrack_fan_speeds": 
                size_x = 400
                size_y = 25
            subrack_attribute[k][v] = QtWidgets.QLineEdit(frame)
            subrack_attribute[k][v+1]= QtWidgets.QLineEdit(frame)
            subrack_attribute[k][v].setGeometry(QtCore.QRect(  size_x+45*v, 10 +  (size_y*(j)),  70,19))
            subrack_attribute[k][v+1].setGeometry(QtCore.QRect(size_x+45*v, 30 +  (size_y*(j)),  70,19))
        j+=1

def populate_warning_alarm_table(true_table, warning, alarm):
    row = len(alarm.keys())
    for i in range(row):
        attr = list(alarm)[i]
        true_table.setRowCount(row)
        row_name = QtWidgets.QTableWidgetItem(list(warning.keys())[i])
        true_table.setVerticalHeaderItem(i, row_name)
        true_table.setItem(i , 0, QtWidgets.QTableWidgetItem(str(warning[attr][0])) )
        true_table.setItem(i , 1, QtWidgets.QTableWidgetItem(str(warning[attr][1])) )
        true_table.setItem(i , 2, QtWidgets.QTableWidgetItem(str(alarm[attr][0])))
        true_table.setItem(i , 3, QtWidgets.QTableWidgetItem(str(alarm[attr][1])))
               
def add_led(frame):
    qled_alert = []
    for i in range(8):
        qled_alert += [Led(frame)]
        qled_alert[i].setGeometry(QtCore.QRect(140, 80 + (66 * (i)), 30, 30))
        qled_alert[i].setObjectName("qled_warn_alar%d" % i)
    return qled_alert

def populateSlots(frame):
    qbutton_tpm = []
    for i in range(8):
        qbutton_tpm += [QtWidgets.QPushButton(frame)]
        qbutton_tpm[i].setGeometry(QtCore.QRect(10, 80 + (66 * (i)), 80, 30))
        qbutton_tpm[i].setObjectName("qbutton_tpm_%d" % i)
        qbutton_tpm[i].setText("TPM #%d" % (i + 1))
        qbutton_tpm[i].setEnabled(False)
    return qbutton_tpm


class Monitor(SkalabBase):

    signal_update_tpm_attribute = QtCore.pyqtSignal(dict,int)
    signal_update_log = QtCore.pyqtSignal(str,str)

    def __init__(self, config="", uiFile="", profile="", size=[1170, 919], swpath=""):
        """ Initialise main window """
        # Load window file
        self.wg = uic.loadUi(uiFile)
        self.wgProBox = QtWidgets.QWidget(self.wg.qtab_conf)
        self.wgProBox.setGeometry(QtCore.QRect(1, 1, 800, 860))
        self.wgProBox.setVisible(True)
        self.wgProBox.show()
        super(Monitor, self).__init__(App="monitor", Profile=profile, Path=swpath, parent=self.wgProBox)
        self.logger = SkalabLog(parent=self.wg.qt_log, logname=__name__, profile=self.profile)
        self.setCentralWidget(self.wg)
        self.resize(size[0], size[1])
        self.load_events_monitor()
        # Set variable
        self.from_subrack = {}
        self.interval_monitor = self.profile['Monitor']['query_interval']
        self.alarm = dict(tile_table_attr, **subrack_attribute)
        for k in self.alarm.keys():
            self.alarm[k] = [False]*8
        self.tlm_hdf_monitor = None
        # Populate table
        populate_subrack_ps(self.wg.sub_frame, subrack_attribute)
        self.populate_table_profile()
        self.qled_alert = add_led(self.wg.frame_subrack)
        self.qbutton_tpm = populateSlots(self.wg.frame_subrack)
        self.populate_tile_instance()
        self.load_warning_alarm_values()
        populate_table(self.wg.qtable_tile, tile_table_attr)
        
        # Start thread
        self.show()
        self._lock_led = Lock()
        self._lock_tab1 = Lock()
        self._lock_tab2 = Lock()
        self.check_tpm_tm = Thread(name= "TPM telemetry", target=self.monitoring_tpm, daemon=True)
        self._tpm_lock = Lock()
        self.wait_check_tpm = Event()
        self.check_tpm_tm.start()

    def writeLog(self,message,priority):
    #TODO Change with match-case statement when update to Python3.10
        if priority == "info":
            self.logger.info(message)
        elif priority == "warning":
            self.logger.warning(message)
        else:
            self.logger.error(message)
    
    
    def load_events_monitor(self):
        self.wg.qbutton_clear_led.clicked.connect(lambda: self.clear_values())
        self.wgProfile.qbutton_load.clicked.connect(lambda: self.load_new_table())
        self.wg.check_savedata.toggled.connect(self.setup_hdf5) # TODO ADD toggled


    def load_new_table(self):
        self.load_warning_alarm_values()
    
    def clear_values(self):
        with (self._lock_led and self._lock_tab1 and self._lock_tab2):
            for i in range(16):
                self.qled_alert[int(i/2)].Colour = Led.Grey
                self.qled_alert[int(i/2)].value = False  
                for attr in self.alarm:
                    self.alarm[attr][int(i/2)] = False
                    if attr in tile_table_attr:
                        tile_table_attr[attr][i].setText(str(""))
                        tile_table_attr[attr][i].setStyleSheet("color: black; background:white")  
                    elif attr in subrack_attribute:
                        try:
                            subrack_attribute[attr][int(i/2)].setText(str(""))
                            subrack_attribute[attr][int(i/2)].setStyleSheet("color: black; background:white")
                        except:
                            pass
                    
                
    def populate_tile_instance(self):
        self.tpm_on_off = [False] * 8
        self.tpm_active = [None] * 8
        self.tpm_slot_ip = eval(self.profile['Monitor']['tiles_slot_ip'])
        self.bitfile = self.profile['Monitor']['bitfile']

    def load_warning_alarm_values(self):
        self.subrack_warning = self.profile['Subrack Warning']
        self.tpm_warning = self.profile['TPM Warning']
        self.warning = dict(self.tpm_warning, **self.subrack_warning)
        self.subrack_alarm = self.profile['Subrack Alarm']
        self.tpm_alarm = self.profile['TPM Alarm']
        self.alarm_values = dict(self.tpm_alarm, **self.subrack_alarm)
        for attr in self.warning:
            self.warning[attr] = eval(self.warning[attr])
            self.alarm_values[attr] = eval(self.alarm_values[attr])
            if self.warning[attr][0] == None: self.warning[attr][0] = -float('inf')
            if self.alarm_values[attr][0]   == None: self.alarm_values[attr][0]   = -float('inf')
            if self.warning[attr][1] == None: self.warning[attr][1] =  float('inf')
            if self.alarm_values[attr][1]   == None: self.alarm_values[attr][1]   =  float('inf')   
        populate_warning_alarm_table(self.wg.true_table, self.warning, self.alarm_values)

    def tpmStatusChanged(self):
        if self.check_tpm_tm.is_alive():
            self.wait_check_tpm.clear()
            with self._tpm_lock:
                for k in range(8):
                    if self.tpm_on_off[k] and not self.tpm_active[k]:
                        self.tpm_active[k] = Tile(self.tpm_slot_ip[k+1], self.cpld_port, self.lmc_ip, self.dst_port)
                        self.tpm_active[k].program_fpgas(self.bitfile)
                        self.tpm_active[k].connect()
                    elif not self.tpm_on_off[k] and self.tpm_active[k]:
                        self.tpm_active[k] = None
            if not(any(self.tpm_active)):
                self.wait_check_tpm.clear()
            else:
                self.wait_check_tpm.set()

    def monitoring_tpm(self):
        while True:
            self.wait_check_tpm.wait()
            # Get tm from tpm
            with self._tpm_lock:
                for i in range(0,15,2):
                    index = int(i/2)
                    if self.tpm_on_off[index]:
                        try:
                            L = list(self.tpm_active[index].get_health_status().values())
                            tpm_monitoring_points = {}
                            for d in L:
                                tpm_monitoring_points.update(d)
                        except:
                            self.signal_update_log.emit(f"Failed to get TPM Telemetry. Are you turning off TPM#{index+1}?","warning")
                            #self.logger.warning(f"Failed to get TPM Telemetry. Are you turning off TPM#{index+1}?")
                            tpm_monitoring_points = "ERROR"
                            continue
                        self.signal_update_tpm_attribute.emit(tpm_monitoring_points,i)
            #if self.wg.check_savedata.isChecked(): self.saveTlm(tpm_monitoring_points)
            sleep(float(self.interval_monitor))    

    def writeTpmAttribute(self,tpm_tmp,i):
        for attr in tile_table_attr:
            value = tpm_tmp[attr]
            tile_table_attr[attr][i].setStyleSheet("color: black; background:white")
            tile_table_attr[attr][i].setText(str(value))
            tile_table_attr[attr][i].setAlignment(QtCore.Qt.AlignCenter)
            with self._lock_tab1:
                if not(type(value)==str or type(value)==str) and not(self.alarm_values[attr][0] <= value <= self.alarm_values[attr][1]):
                    # # tile_table_attr[attr][i].setStyleSheet("color: white; background:red")  
                    # segmentation error or free() pointer error
                    tile_table_attr[attr][i+1].setText(str(value))
                    tile_table_attr[attr][i+1].setStyleSheet("color: white; background:red")
                    tile_table_attr[attr][i+1].setAlignment(QtCore.Qt.AlignCenter)
                    self.alarm[attr][int(i/2)] = True
                    self.logger.error(f"ERROR: {attr} parameter is out of range!")
                    with self._lock_led:
                        self.qled_alert[int(i/2)].Colour = Led.Red
                        self.qled_alert[int(i/2)].value = True
                elif not(type(value)==str or type(value)==str) and not(self.warning[attr][0] <= value <= self.warning[attr][1]):
                    if not self.alarm[attr][int(i/2)]:
                        tile_table_attr[attr][i+1].setText(str(value))
                        tile_table_attr[attr][i+1].setStyleSheet("color: white; background:orange")
                        tile_table_attr[attr][i+1].setAlignment(QtCore.Qt.AlignCenter)
                        self.logger.warning(f"WARNING: {attr} parameter is near the out of range threshold!")
                        if self.qled_alert[int(i/2)].Colour==4:
                            with self._lock_led:
                                self.qled_alert[int(i/2)].Colour=Led.Orange
                                self.qled_alert[int(i/2)].value = True

    def readSubrackAttribute(self):
        for attr in self.from_subrack:
            if attr in subrack_attribute:
                self.write_subrack_attribute(attr,subrack_attribute,False)

    def write_subrack_attribute(self,attr,table,led_flag):
        for ind in range(0,len(table[attr]),2):
            value = self.from_subrack[attr][int(ind/2)]
            if (not(type(value) == bool) and not(type(value) == str)): value = round(value,1) 
            table[attr][ind].setStyleSheet("color: black; background:white")
            table[attr][ind].setText(str(value))
            table[attr][ind].setAlignment(QtCore.Qt.AlignCenter)
            with self._lock_tab2:
                if not(type(value)==str or type(value)==bool) and not(self.alarm_values[attr][0] <= value <= self.alarm_values[attr][1]):
                    table[attr][ind+1].setText(str(value))
                    table[attr][ind+1].setStyleSheet("color: white; background:red")
                    table[attr][ind+1].setAlignment(QtCore.Qt.AlignCenter)
                    self.logger.error(f"ERROR: {attr} parameter is out of range!")
                    self.alarm[attr][int(ind/2)] = True
                    if led_flag:
                        with self._lock_led:
                            self.qled_alert[int(ind/2)].Colour = Led.Red
                            self.qled_alert[int(ind/2)].value = True
                elif not(type(value)==str or type(value)==bool) and not(self.warning[attr][0] <= value <= self.warning[attr][1]):
                    if not self.alarm[attr][int(ind/2)]:
                        table[attr][ind+1].setText(str(value))
                        table[attr][ind+1].setStyleSheet("color: white; background:orange")
                        table[attr][ind+1].setAlignment(QtCore.Qt.AlignCenter)
                        self.logger.warning(f"WARNING: {attr} parameter is near the out of range threshold!")
                        if self.qled_alert[int(ind/2)].Colour==4 and led_flag:
                            with self._lock_led:
                                self.qled_alert[int(ind/2)].Colour=Led.Orange
                                self.qled_alert[int(ind/2)].value = True


    def setup_hdf5(self):
        if not(self.tlm_hdf_monitor):
            if not self.profile['Monitor']['data_path'] == "":
                fname = self.profile['Monitor']['data_path']
                if not fname[-1] == "/":
                    fname = fname + "/"
                    if  os.path.exists(str(Path.home()) + fname) != True:
                        os.makedirs(str(Path.home()) + fname)
                fname += datetime.datetime.strftime(datetime.datetime.utcnow(), "monitor_tlm_%Y-%m-%d_%H%M%S.h5")
                self.tlm_hdf_monitor = h5py.File(str(Path.home()) + fname, 'a')
                return self.tlm_hdf_monitor
            else:
                msgBox = QtWidgets.QMessageBox()
                msgBox.setText("Please Select a valid path to save the Monitor data and save it into the current profile")
                msgBox.setWindowTitle("Error!")
                msgBox.setIcon(QtWidgets.QMessageBox.Critical)
                msgBox.exec_()
                return None

    def saveTlm(self,data_tile):
        if self.tlm_hdf_monitor:
            for attr in tile_table_attr:
                data_tile[attr][:] = [0.0 if type(x) is str else x for x in data_tile[attr]]
                if attr not in self.tlm_hdf_monitor:
                    try:
                        self.tlm_hdf_monitor.create_dataset(attr, data=np.asarray([data_tile[attr]]), chunks = True, maxshape =(None,None))
                    except:
                        self.logger.error("WRITE TLM ERROR in ", attr, "\nData: ", data_tile[attr])
                else:
                    self.tlm_hdf_monitor[attr].resize((self.tlm_hdf_monitor[attr].shape[0] +
                                                np.asarray([self.tlm_hdf_monitor[attr]]).shape[0]), axis=0)
                    self.tlm_hdf_monitor[attr][self.tlm_hdf_monitor[attr].shape[0]-1]=np.asarray([data_tile[attr]])                            

    def closeEvent(self, event):
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Exit...",
                                                "Are you sure you want to exit ?",
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        event.ignore()
        if result == QtWidgets.QMessageBox.Yes:
            event.accept()
            if type(self.tlm_hdf_monitor) is not None:
                try:
                    self.tlm_hdf_monitor.close()
                except:
                    pass
            sleep(1)

class MonitorSubrack(Monitor):
    """ Main UI Window class """
    # Signal for Slots
    signalTlm = QtCore.pyqtSignal()
    signal_to_monitor = QtCore.pyqtSignal()
    signal_to_monitor_for_tpm = QtCore.pyqtSignal()

    def __init__(self, ip=None, port=None, uiFile="", profile="", size=[1190, 936], swpath=""):
        """ Initialise main window """

        super(MonitorSubrack, self).__init__(uiFile="skalab_monitor.ui", size=[1190, 936], profile=opt.profile, swpath=default_app_dir)   
        self.interval_monitor = self.profile['Monitor']['query_interval']

        self.tlm_keys = []
        self.telemetry = {} 
        self.last_telemetry = {"tpm_supply_fault":[None] *8,"tpm_present":[None] *8,"tpm_on_off":[None] *8}
        self.query_once = []
        self.query_deny = []
        self.query_tiles = []
        self.connected = False
        self.reload(ip=ip, port=port)
        self.resize(size[0], size[1])

        self.tlm_file = ""
        self.tlm_hdf = None

        self.client = None
        self.data_charts = {}

        self.load_events_subrack()
        self.show()
        self.skipThreadPause = False
        #self.processTlm = QThread(target=self.readTlm, daemon=True)
        self.processTlm = Thread(name="Subrack Telemetry", target=self.readTlm, daemon=True)
        self.wait_check_subrack = Event()
        self._subrack_lock = Lock()
        self.processTlm.start()

    def load_events_subrack(self):
        self.wg.subrack_button.clicked.connect(lambda: self.connect())
        for n, t in enumerate(self.qbutton_tpm):
            t.clicked.connect(lambda state, g=n: self.cmdSwitchTpm(g))

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
            if 'deny' in self.profile['Query'].keys():
                self.query_tiles = list(self.profile['Query']['tiles'].split(","))

    def cmdSwitchTpm(self, slot):
        self.wait_check_subrack.clear()
        self.skipThreadPause = True
        with self._subrack_lock:
            if self.connected:
                if self.telemetry["tpm_on_off"][slot]:
                    self.client.execute_command(command="turn_off_tpm", parameters="%d" % (int(slot) + 1))
                    self.logger.info("Turn OFF TPM-%02d" % (int(slot) + 1))
                else:
                    self.client.execute_command(command="turn_on_tpm", parameters="%d" % (int(slot) + 1))
                    self.logger.info("Turn ON TPM-%02d" % (int(slot) + 1)) 
            sleep(2.0) # Sleep required to wait for the turn_off/on_tpm command to complete
        self.wait_check_subrack.set()

    def connect(self):
        if not self.wg.qline_ip.text() == "":
            if not self.connected:
                self.logger.info("Connecting to Subrack %s:%d..." % (self.ip, int(self.port)))
                self.client = WebHardwareClient(self.ip, self.port)
                if self.client.connect():
                    self.logger.info("Successfully connected")
                    self.tlm_keys = self.client.execute_command("list_attributes")["retvalue"]
                    self.logger.info("Querying list of Subrack API attributes")
                    for tlmk in self.tlm_keys:
                        if tlmk in self.query_once:
                            data = self.client.get_attribute(tlmk)
                            if data["status"] == "OK":
                                self.telemetry[tlmk] = data["value"]
                            else:
                                self.telemetry[tlmk] = data["info"]
                    if 'api_version' in self.telemetry.keys():
                        self.wg.qlabel_message.setText("Subrack API version: " + self.telemetry['api_version'])
                        self.logger.info("Subrack API version: " + self.telemetry['api_version'])
                    else:
                        self.logger.warning("The Subrack is running with a very old API version!")
                    self.wg.subrack_button.setStyleSheet("background-color: rgb(78, 154, 6);")
                    self.wg.subrack_button.setText("ONLINE")
                    self.wg.subrack_button.setStyleSheet("background-color: rgb(78, 154, 6);")
                    [item.setEnabled(True) for item in self.qbutton_tpm]
                    self.connected = True

                    self.tlm_hdf = self.setup_hdf5()
                    with self._subrack_lock:
                        telemetry = self.getTelemetry()
                        self.telemetry = dict(telemetry)
                        self.signal_to_monitor.emit()
                        self.signalTlm.emit()
                    self.wait_check_subrack.set()
                else:
                    self.wg.qlabel_message.setText("The Subrack server does not respond!")
                    self.logger.error("Unable to connect to the Subrack server %s:%d" % (self.ip, int(self.port)))
                    self.wg.subrack_button.setStyleSheet("background-color: rgb(204, 0, 0);")
                    self.wg.subrack_button.setStyleSheet("background-color: rgb(204, 0, 0);")
                    self.wg.subrack_button.setText("OFFLINE")
                    [item.setEnabled(False) for item in self.qbutton_tpm]
                    self.client = None
                    self.connected = False

            else:
                self.logger.info("Disconneting from Subrack %s:%d..." % (self.ip, int(self.port)))
                self.wait_check_tpm.clear()
                self.wait_check_subrack.clear()
                self.connected = False
                self.wg.subrack_button.setStyleSheet("background-color: rgb(204, 0, 0);")
                self.wg.subrack_button.setText("OFFLINE")
                self.wg.subrack_button.setStyleSheet("background-color: rgb(204, 0, 0);")
                [item.setEnabled(False) for item in self.qbutton_tpm]
                self.client.disconnect()
                del self.client
                gc.collect()
                if (type(self.tlm_hdf) is not None) or (type(self.tlm_hdf_monitor) is not None):
                    try:
                        self.tlm_hdf.close()
                        self.tlm_hdf_monitor.close()
                    except:
                        pass
        else:
            self.wg.qlabel_connection.setText("Missing IP!")
            self.wait_check_tpm.clear()
            self.wait_check_subrack.clear()

    def getTelemetry(self):
        tkey = ""
        telem = {}
        monitor_tlm = {}
        try:
            for tlmk in self.tlm_keys:
                tkey = tlmk
                if not tlmk in self.query_deny:
                    if self.connected:
                        data = self.client.get_attribute(tlmk)
                        if data["status"] == "OK":
                            telem[tlmk] = data["value"]
                            monitor_tlm[tlmk] = telem[tlmk]
                        else:
                            monitor_tlm[tlmk] = "NOT AVAILABLE"
        except:
            self.signal_update_log.emit("Error reading Telemetry [attribute: %s], skipping..." % tkey,"error")
            #self.logger.error("Error reading Telemetry [attribute: %s], skipping..." % tkey)
            monitor_tlm[tlmk] = f"ERROR{tkey}"
            self.from_subrack =  monitor_tlm 
            return
        self.from_subrack =  monitor_tlm  
        return telem

    def getTiles(self):
        try:
            for tlmk in self.query_tiles:
                data = self.client.get_attribute(tlmk)
                if data["status"] == "OK":
                    self.telemetry[tlmk] = data["value"]
                else:
                    self.telemetry[tlmk] = []
            return self.telemetry['tpm_ips']
        except:
            return []

    def readTlm(self):
        while True:
            self.wait_check_subrack.wait()
            with self._subrack_lock:
                if self.connected:
                    try:
                        telemetry = self.getTelemetry()
                        self.telemetry = dict(telemetry)
                    except:
                        self.signal_update_log.emit("Failed to get Subrack Telemetry!","warning")
                        pass
                    self.signalTlm.emit()
                    self.signal_to_monitor.emit()
                    cycle = 0.0
                    while cycle < (float(self.profile['Subrack']['query_interval'])) and not self.skipThreadPause:
                        sleep(0.1)
                        cycle = cycle + 0.1
                    self.skipThreadPause = False
            sleep(0.5)        

    def updateTpmStatus(self):
        # TPM status on QButtons
        if "tpm_supply_fault" in self.telemetry.keys():
            for n, fault in enumerate(self.telemetry["tpm_supply_fault"]):
                if fault:
                    self.qbutton_tpm[n].setStyleSheet(colors("yellow_on_black"))
                    self.tpm_on_off[n] = False
                else:
                    if "tpm_present" in self.telemetry.keys():
                        if self.telemetry["tpm_present"][n]:
                            self.qbutton_tpm[n].setStyleSheet(colors("black_on_red"))
                            self.tpm_on_off[n] = False
                        else:
                            self.qbutton_tpm[n].setStyleSheet(colors("black_on_grey"))
                            self.tpm_on_off[n] = False
                    if "tpm_on_off" in self.telemetry.keys():
                        if self.telemetry["tpm_on_off"][n]:
                            self.qbutton_tpm[n].setStyleSheet(colors("black_on_green"))
                            self.tpm_on_off[n] = True
            try:
                if (self.telemetry["tpm_supply_fault"]!= self.last_telemetry["tpm_supply_fault"]) | (self.telemetry["tpm_present"]!= self.last_telemetry["tpm_present"]) | (self.telemetry["tpm_on_off"]!= self.last_telemetry["tpm_on_off"]):
                    self.signal_to_monitor_for_tpm.emit()
                    self.last_telemetry["tpm_supply_fault"] = self.telemetry["tpm_supply_fault"]
                    self.last_telemetry["tpm_present"] = self.telemetry["tpm_present"]
                    self.last_telemetry["tpm_on_off"] = self.telemetry["tpm_on_off"]
                    
            except:
                self.signal_to_monitor_for_tpm.emit()            

    def closeEvent(self, event):
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Exit...",
                                                "Are you sure you want to exit ?",
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        event.ignore()
        if result == QtWidgets.QMessageBox.Yes:
            event.accept()
            self.stopThreads = True
            self.logger.info("Stopping Threads")
            if type(self.tlm_hdf) is not None:
                try:
                    self.tlm_hdf.close()
                    self.tlm_hdf_monitor.close()
                except:
                    pass
            sleep(1)


if __name__ == "__main__":
    from optparse import OptionParser
    from sys import argv, stdout 

    parser = OptionParser(usage="usage: %station_subrack [options]")
    parser.add_option("--profile", action="store", dest="profile",
                      type="str", default="Default", help="Monitor Profile to load")
    parser.add_option("--ip", action="store", dest="ip",
                      type="str", default=None, help="Subrack IP address [default: None]")
    parser.add_option("--port", action="store", dest="port",
                      type="int", default=8081, help="Subrack WebServer Port [default: 8081]")
    parser.add_option("--interval", action="store", dest="interval",
                      type="int", default=5, help="Time interval (sec) between telemetry requests [default: 1]")
    parser.add_option("--nogui", action="store_true", dest="nogui",
                      default=False, help="Do not show GUI")
    parser.add_option("--single", action="store_true", dest="single",
                      default=False, help="Single Telemetry Request. If not provided, the script runs indefinitely")
    parser.add_option("--directory", action="store", dest="directory",
                      type="str", default="", help="Output Directory [Default: "", it means do not save data]")
    (opt, args) = parser.parse_args(argv[1:])

    monitor_logger = logging.getLogger(__name__)
    if not opt.nogui:
        app = QtWidgets.QApplication(sys.argv)
        window = MonitorSubrack(uiFile="skalab_monitor.ui", size=[1190, 936],
                                 profile=opt.profile,
                                 swpath=default_app_dir)
        window.dst_port = configuration['network']['lmc']['lmc_port']
        window.lmc_ip = configuration['network']['lmc']['lmc_ip']
        window.cpld_port = configuration['network']['lmc']['tpm_cpld_port']
        window.signalTlm.connect(window.updateTpmStatus)
        window.signal_to_monitor.connect(window.readSubrackAttribute)
        window.signal_to_monitor_for_tpm.connect(window.tpmStatusChanged)
        window.signal_update_tpm_attribute.connect(window.writeTpmAttribute)
        window.signal_update_log.connect(window.writeLog)
        sys.exit(app.exec_())
    else:
        profile = []
        fullpath = default_app_dir + opt.profile + "/" + profile_filename
        if not os.path.exists(fullpath):
            monitor_logger.error("\nThe Monitor Profile does not exist.\n")
        else:
            monitor_logger.info("Loading Monitor Profile: " + opt.profile + " (" + fullpath + ")")
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
                    monitor_logger.error("Unable to connect to the Webserver on %s:%d" % (opt.ip, opt.port))
            if connected:
                if opt.single:
                    monitor_logger.info("SINGLE REQUEST")
                    tstamp = dt_to_timestamp(datetime.datetime.utcnow())
                    attributes = {}
                    monitor_logger.info("\nTstamp: %d\tDateTime: %s\n" % (tstamp, ts_to_datestring(tstamp)))
                    for att in tlm_keys:
                        attributes[att] = client.get_attribute(att)["value"]
                        monitor_logger.info(att, attributes[att])
                else:
                    try:
                        monitor_logger.info("CONTINUOUS REQUESTS")
                        while True:
                            tstamp = dt_to_timestamp(datetime.datetime.utcnow())
                            attributes = {}
                            monitor_logger.info("\nTstamp: %d\tDateTime: %s\n" % (tstamp, ts_to_datestring(tstamp)))
                            for att in subAttr:
                                attributes[att] = client.get_attribute(att)["value"]
                                monitor_logger.info(att, attributes[att])
                            sleep(opt.interval)
                    except KeyboardInterrupt:
                        monitor_logger.warning("\nTerminated by the user.\n")
                client.disconnect()
                del client

