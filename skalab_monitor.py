from skalab_base import SkalabBase
import os.path
import sys
from pyaavs.tile_wrapper import Tile
from PyQt5 import QtWidgets, uic, QtCore
from hardware_client import WebHardwareClient
from skalab_base import SkalabBase
from skalab_utils import dt_to_timestamp, ts_to_datestring, parse_profile
from threading import Thread, Event, Lock
from skalab_utils import COLORI, Led, getTextFromFile
from time import sleep
import datetime
from pathlib import Path
import h5py
import numpy as np


default_app_dir = str(Path.home()) + "/.skalab/"
default_profile = "Default"
profile_filename = "monitor.ini"

subrack_attribute = {
                "backplane_temperatures": [None]*4,
                "board_temperatures": [None]*4,
                "power_supply_fan_speeds": [None]*4,
                "power_supply_powers": [None]*4,
                "subrack_fan_speeds": [None]*8,
                "subrack_fan_speeds_percent": [None]*8,
                }

subrack_table_attr = {"tpm_voltages":[None]*16,
                "tpm_currents":[None]*16,
                "tpm_temperatures":[None]*16,
                "tpm_supply_fault":[None]*16
                }

tile_table_attr =  {
                "fpga0_temp": [None]*16,
                "fpga1_temp": [None]*16,
                }
values_from_tile = {
                "fpga0_temp": [None]*8,
                "fpga1_temp": [None]*8,
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
    qtpm = []
    for i in range(8):
        qtpm += [QtWidgets.QPushButton(frame)]
        qtpm[i].setGeometry(QtCore.QRect(10, 80 + (66 * (i)), 80, 30))
        qtpm[i].setObjectName("qtpm_%d" % i)
        qtpm[i].setText("TPM #%d" % (i + 1))
    return qtpm


class Monitor(SkalabBase):

    def __init__(self, config="", uiFile="", profile="", size=[1170, 919], swpath=""):
        """ Initialise main window """
        # Load window file
        self.wg = uic.loadUi(uiFile)
        self.wgProBox = QtWidgets.QWidget(self.wg.qtab_conf)
        self.wgProBox.setGeometry(QtCore.QRect(1, 1, 800, 860))
        self.wgProBox.setVisible(True)
        self.wgProBox.show()
        super(Monitor, self).__init__(App="monitor", Profile=profile, Path=swpath, parent=self.wgProBox)
        self.setCentralWidget(self.wg)
        self.resize(size[0], size[1])
        self.load_events()
        # Set variable
        self.from_subrack = {}
        self.interval_monitor = self.profile['Monitor']['query_interval']
        self.Alarm = dict(subrack_table_attr, **tile_table_attr, **subrack_attribute)
        for k in self.Alarm.keys():
            self.Alarm[k] = [False]*8
        self.tlm_hdf_monitor = None
        # Populate table
        populate_subrack_ps(self.wg.sub_frame, subrack_attribute)
        self.populate_table_profile()
        self.qled_alert = add_led(self.wg.frame_subrack)
        self.qtpm = populateSlots(self.wg.frame_subrack)
        self.populate_tile_instance()
        self.load_warning_alarm_values()
        populate_table(self.wg.qtable_subrack,subrack_table_attr)
        populate_table(self.wg.qtable_tile, tile_table_attr)
        
        # Start thread
        self.show()
        self._lock_led = Lock()
        self._lock_tab1 = Lock()
        self._lock_tab2 = Lock()
        self.check_tpm_tm = Thread(target=self.monitoring_tpm, daemon=True)
        self.wait_check_tpm = Event()
        self.check_tpm_tm.start()


    def load_events(self):
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
                for attr in self.Alarm:
                    self.Alarm[attr][int(i/2)] = False
                    if attr in tile_table_attr:
                        tile_table_attr[attr][i].setText(str(""))
                        tile_table_attr[attr][i].setStyleSheet("color: black; background:white")  
                    elif attr in subrack_table_attr:      
                        subrack_table_attr[attr][i].setText(str(""))
                        subrack_table_attr[attr][i].setStyleSheet("color: black; background:white")
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
        self.warning = self.profile['Warning']
        self.alarm = self.profile['Alarm']
        for attr in self.warning:
            self.warning[attr] = eval(self.warning[attr])
            self.alarm[attr] = eval(self.alarm[attr])
            if self.warning[attr][0] == None: self.warning[attr][0] = -float('inf')
            if self.alarm[attr][0]   == None: self.alarm[attr][0]   = -float('inf')
            if self.warning[attr][1] == None: self.warning[attr][1] =  float('inf')
            if self.alarm[attr][1]   == None: self.alarm[attr][1]   =  float('inf')   
        populate_warning_alarm_table(self.wg.true_table, self.warning, self.alarm)

    def tpm_status_changed(self):
        if self.check_tpm_tm.is_alive():
            self.wait_check_tpm.clear()
            sleep(0.1)
            for k in range(8):
                if self.tpm_on_off[k] and not self.tpm_active[k]:
                    self.tpm_active[k] = Tile(self.tpm_slot_ip[k+1], self.cpld_port, self.lmc_ip, self.dst_port)
                    self.tpm_active[k].program_fpgas(self.bitfile)
                    self.tpm_active[k].connect()
                elif not self.tpm_on_off[k] and self.tpm_active[k]:
                    self.tpm_active[k] = None

            self.wait_check_tpm.set()
            if not(any(self.tpm_active)):
                self.wait_check_tpm.clear()
        sleep(0.1)

    def monitoring_tpm(self):
        while True:
            self.wait_check_tpm.wait()
            # Get tm from tpm
            for j in range(8):
                if self.tpm_on_off[j]:
                    try:
                        temperature = [round(self.tpm_active[j].get_temperature(),1),
                                    round(self.tpm_active[j].get_fpga0_temperature(),1),
                                    round(self.tpm_active[j].get_fpga1_temperature(),1)]
                    except:
                        print("Failed to get TPM Telemetry!")
                        temperature = ["ERROR"] * 3
                else:
                    temperature = ["NOT AVAILABLE"] * 3
                i = 1
                for attr in tile_table_attr:
                    values_from_tile[attr][j] = temperature[i]
                    i+=1

            if self.wg.check_savedata.isChecked(): self.saveTlm(values_from_tile)

            for attr in tile_table_attr:
                for i in range(0,15,2):
                    value = values_from_tile[attr][int(i/2)]
                    tile_table_attr[attr][i].setStyleSheet("color: black; background:white")
                    tile_table_attr[attr][i].setText(str(value))
                    tile_table_attr[attr][i].setAlignment(QtCore.Qt.AlignCenter)
                    with self._lock_tab1:
                        if not(type(value)==str or type(value)==str) and not(self.alarm[attr][0] <= value <= self.alarm[attr][1]):
                            # # tile_table_attr[attr][i].setStyleSheet("color: white; background:red")  
                            # segmentation error or free() pointer error
                            tile_table_attr[attr][i+1].setText(str(value))
                            tile_table_attr[attr][i+1].setStyleSheet("color: white; background:red")
                            tile_table_attr[attr][i+1].setAlignment(QtCore.Qt.AlignCenter)
                            self.Alarm[attr][int(i/2)] = True
                            with self._lock_led:
                                self.qled_alert[int(i/2)].Colour = Led.Red
                                self.qled_alert[int(i/2)].value = True
                        elif not(type(value)==str or type(value)==str) and not(self.warning[attr][0] <= value <= self.warning[attr][1]):
                            if not self.Alarm[attr][int(i/2)]:
                                tile_table_attr[attr][i+1].setText(str(value))
                                tile_table_attr[attr][i+1].setStyleSheet("color: white; background:orange")
                                tile_table_attr[attr][i+1].setAlignment(QtCore.Qt.AlignCenter)
                                if self.qled_alert[int(i/2)].Colour==4:
                                    with self._lock_led:
                                        self.qled_alert[int(i/2)].Colour=Led.Orange
                                        self.qled_alert[int(i/2)].value = True
            sleep(float(self.interval_monitor))    


    def read_subrack_attribute(self):
        for attr in self.from_subrack:
            if attr in subrack_table_attr:
                self.write_subrack_attribute(attr,subrack_table_attr,True)
            elif attr in subrack_attribute:
                self.write_subrack_attribute(attr,subrack_attribute,False)

    def write_subrack_attribute(self,attr,table,led_flag):
       #print("write1",attr,table[attr],led_flag)
        for ind in range(0,len(table[attr]),2):
            value = self.from_subrack[attr][int(ind/2)]
            if (not(type(value) == bool) and not(type(value) == str)): value = round(value,1) 
            table[attr][ind].setStyleSheet("color: black; background:white")
            table[attr][ind].setText(str(value))
            table[attr][ind].setAlignment(QtCore.Qt.AlignCenter)
            with self._lock_tab2:
                #print("write2")
                if not(type(value)==str or type(value)==bool) and not(self.alarm[attr][0] <= value <= self.alarm[attr][1]):
                    table[attr][ind+1].setText(str(value))
                    table[attr][ind+1].setStyleSheet("color: white; background:red")
                    table[attr][ind+1].setAlignment(QtCore.Qt.AlignCenter)
                    self.Alarm[attr][int(ind/2)] = True
                    if led_flag:
                        with self._lock_led:
                            self.qled_alert[int(ind/2)].Colour = Led.Red
                            self.qled_alert[int(ind/2)].value = True
                elif not(type(value)==str or type(value)==bool) and not(self.warning[attr][0] <= value <= self.warning[attr][1]):
                    #print("write3")
                    if not self.Alarm[attr][int(ind/2)]:
                        table[attr][ind+1].setText(str(value))
                        table[attr][ind+1].setStyleSheet("color: white; background:orange")
                        table[attr][ind+1].setAlignment(QtCore.Qt.AlignCenter)
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
                fname += datetime.datetime.strftime(datetime.datetime.utcnow(), "monitor_tlm_%Y-%m-%d_%H%M%S.h5")
                self.tlm_hdf_monitor = h5py.File(fname, 'a')
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
            for attr in data_tile:
                data_tile[attr][:] = [0.0 if type(x) is str else x for x in data_tile[attr]]
                if attr not in self.tlm_hdf_monitor:
                    try:
                        self.tlm_hdf_monitor.create_dataset(attr, data=np.asarray([data_tile[attr]]), chunks = True, maxshape =(None,None))
                    except:
                        print("WRITE TLM ERROR in ", attr, "\nData: ", data_tile[attr])
                else:
                    self.tlm_hdf_monitor[attr].resize((self.tlm_hdf_monitor[attr].shape[0] +
                                                np.asarray([self.tlm_hdf_monitor[attr]]).shape[0]), axis=0)
                    self.tlm_hdf_monitor[attr][self.tlm_hdf_monitor[attr].shape[0]-1]=np.asarray([data_tile[attr]])                            


    def populate_help(self, uifile="skalab_subrack.ui"):
        with open(uifile) as f:
            data = f.readlines()
        helpkeys = [d[d.rfind('name="Help_'):].split('"')[1] for d in data if 'name="Help_' in d]
        for k in helpkeys:
            self.wg.findChild(QtWidgets.QTextEdit, k).setText(getTextFromFile(k.replace("_", "/")+".html"))

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



if __name__ == "__main__":
    from optparse import OptionParser
    from sys import argv, stdout

    parser = OptionParser(usage="usage: %station_subrack [options]")
    parser.add_option("--profile", action="store", dest="profile",
                      type="str", default="Default", help="Monitor Profile to load")
    parser.add_option("--ip", action="store", dest="ip",
                      type="str", default=None, help="SubRack IP address [default: None]")
    parser.add_option("--port", action="store", dest="port",
                      type="int", default=8081, help="SubRack WebServer Port [default: 8081]")
    parser.add_option("--interval", action="store", dest="interval",
                      type="int", default=5, help="Time interval (sec) between telemetry requests [default: 1]")
    parser.add_option("--nogui", action="store_true", dest="nogui",
                      default=False, help="Do not show GUI")
    parser.add_option("--single", action="store_true", dest="single",
                      default=False, help="Single Telemetry Request. If not provided, the script runs indefinitely")
    parser.add_option("--directory", action="store", dest="directory",
                      type="str", default="", help="Output Directory [Default: "", it means do not save data]")
    (opt, args) = parser.parse_args(argv[1:])

    if not opt.nogui:
        app = QtWidgets.QApplication(sys.argv)
        window = Monitor( uiFile="skalab_monitor.ui", profile=opt.profile,swpath=default_app_dir)
        # window.signalTlm.connect(window.updateTlm)
        sys.exit(app.exec_())
    else:
        profile = []
        fullpath = default_app_dir + opt.profile + "/" + profile_filename
        if not os.path.exists(fullpath):
            print("\nThe Monitor Profile does not exist.\n")
        else:
            print("Loading Monitor Profile: " + opt.profile + " (" + fullpath + ")")
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
                    print("Unable to connect to the Webserver on %s:%d" % (opt.ip, opt.port))
            if connected:
                if opt.single:
                    print("SINGLE REQUEST")
                    tstamp = dt_to_timestamp(datetime.datetime.utcnow())
                    attributes = {}
                    print("\nTstamp: %d\tDateTime: %s\n" % (tstamp, ts_to_datestring(tstamp)))
                    for att in tlm_keys:
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

