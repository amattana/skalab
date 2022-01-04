#!/usr/bin/env python
import sys
import gc
import threading
import numpy as np
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt
import pydaq.daq_receiver as daq
from skalab_utils import MiniPlots, calcolaspettro, closest, MyDaq, get_if_name
from pyaavs.station import Station, load_station_configuration
from pyaavs import station

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


def moving_average(xx, w):
    return np.convolve(xx, np.ones(w), 'valid') / w

class Live(QtWidgets.QMainWindow):
    """ Main UI Window class """
    # Signal for Slots
    #housekeeping_signal = QtCore.pyqtSignal()
    #antenna_test_signal = QtCore.pyqtSignal()

    def __init__(self, config="", uiFile=""):
        """ Initialise main window """
        super(Live, self).__init__()
        # Load window file
        self.wg = uic.loadUi(uiFile)
        self.setCentralWidget(self.wg)
        self.resize(1168, 901)

        # Populate the playback plots for the Live Spectra
        self.livePlots = MiniPlots(parent=self.wg.qplot_spectra, nplot=16)

        self.show()
        self.load_events()

        self.tpm_station = None
        self.station_connected = False
        self.station_configuration = {}
        self.tpm_nic_name = ""
        self.mydaq = None

        self.config_file = config
        self.show_live_spectra_grid = self.wg.qcheck_spectra_grid.isChecked()

        self.live_resolutions = 2 ** np.array(range(16)) * (800000.0 / 2 ** 15)
        self.live_rbw = int(closest(self.live_resolutions, float(self.wg.qline_rbw.text())))
        self.live_avg = 2 ** self.live_rbw
        self.live_nsamples = int(2 ** 15 / self.live_avg)
        self.live_RBW = (self.live_avg * (400000.0 / 16384.0))
        self.live_asse_x = np.arange(self.live_nsamples / 2 + 1) * self.live_RBW * 0.001

        self.live_input_list = np.arange(1, 17)
        self.live_channels = self.wg.qline_channels.text()

        self.live_xAxisRange = [float(self.wg.qline_spectra_band_from.text()), float(self.wg.qline_spectra_band_to.text())]
        self.live_yAxisRange = [float(self.wg.qline_spectra_level_min.text()), float(self.wg.qline_spectra_level_max.text())]

    def load_events(self):
        # Live Plots Connections
        self.wg.qbutton_connect.clicked.connect(lambda: self.station_connect())
        self.wg.qbutton_single.clicked.connect(lambda: self.get_single_meas())
        self.wg.qcheck_spectra_grid.stateChanged.connect(self.live_show_spectra_grid)

    def station_connect(self):
        # Set current thread name
        threading.currentThread().name = "Station"
        # Load station configuration
        station.load_configuration_file(self.config_file)

        self.station_configuration = station.configuration
        # Test
        try:
            # Create station
            self.tpm_station = Station(station.configuration)
            # Connect station (program, initialise and configure if required)
            self.tpm_station.connect()
            self.tpm_station.tiles[0].get_temperature()
            self.wg.qlabel_connection.setText("Connected")
            self.wg.qbutton_connect.setStyleSheet("background-color: rgb(78, 154, 6);")
            self.wg.qbutton_connect.setText("ONLINE")
            self.station_connected = True

        except:
            self.wg.qlabel_connection.setText("ERROR: Unable to connect to the TPMs Station. Retry...")
            self.wg.qbutton_connect.setStyleSheet("background-color: rgb(204, 0, 0);")
            self.wg.qbutton_connect.setText("OFFLINE")
            self.station_connected = False

    def get_single_meas(self):
        if not self.wg.qline_channels.text() == self.live_channels:
            self.live_reformat_plots()

        self.live_resolutions = 2 ** np.array(range(16)) * (800000.0 / 2 ** 15)
        self.live_rbw = int(closest(self.live_resolutions, float(self.wg.qline_rbw.text())))
        self.live_avg = 2 ** self.live_rbw
        self.live_nsamples = int(2 ** 15 / self.live_avg)
        self.live_RBW = (self.live_avg * (400000.0 / 16384.0))
        self.live_asse_x = np.arange(self.live_nsamples / 2 + 1) * self.live_RBW * 0.001

        xAxisRange = (float(self.wg.qline_spectra_band_from.text()),
                      float(self.wg.qline_spectra_band_to.text()))
        yAxisRange = (float(self.wg.qline_spectra_level_min.text()),
                      float(self.wg.qline_spectra_level_max.text()))

        self.tpm_nic_name = get_if_name(self.station_configuration['network']['lmc']['lmc_ip'])
        if self.tpm_nic_name == "":
            self.wg.qlabel_connection.setText("Connected. (ETH Card name ERROR)")
        if not self.tpm_nic_name == "":
            self.mydaq = MyDaq(daq, self.tpm_nic_name, self.tpm_station, len(self.station_configuration['tiles']))
        self.live_data = self.mydaq.execute()
        #print("RECEIVED DATA: %d" % len(self.live_data[int(self.wg.qcombo_tpm.currentIndex())]))
        lw = 1
        if self.wg.qcheck_spectra_noline.isChecked():
            lw = 0
        if not self.live_data == []:
            self.livePlots.plotClear()
            for n, i in enumerate(self.live_input_list):
                # Plot X Pol
                spettro, rfpow = calcolaspettro(self.live_data[int(self.wg.qcombo_tpm.currentIndex())][i - 1, 0, :], self.live_nsamples, log=True)
                self.livePlots.plotCurve(self.live_asse_x, spettro, n, xAxisRange=self.live_xAxisRange,
                                        yAxisRange=self.live_yAxisRange, title="INPUT-%02d" % i,
                                        xLabel="MHz", yLabel="dB", colore="b") #, rfpower=rms,
                                        # annotate_rms=self.show_rms, grid=self.show_spectra_grid, lw=lw,
                                        # show_line=self.wg.play_qcheck_xpol_sp.isChecked(),
                                        # rms_position=float(self.wg.play_qline_rms_pos.text()))

                # Plot Y Pol
                spettro, rfpow = calcolaspettro(
                    self.live_data[int(self.wg.qcombo_tpm.currentIndex())][i - 1, 1, :], self.live_nsamples, log=True)
                self.livePlots.plotCurve(self.live_asse_x, spettro, n, xAxisRange=self.live_xAxisRange,
                                        yAxisRange=self.live_yAxisRange, colore="g") #, rfpower=rms,
                                      #  annotate_rms=self.show_rms, grid=self.show_spectra_grid, lw=lw,
                                      #  show_line=self.wg.play_qcheck_ypol_sp.isChecked(),
                                      #  rms_position=float(self.wg.play_qline_rms_pos.text()))
            self.livePlots.updatePlot()
        self.mydaq.close()
        del self.mydaq
        gc.collect()

    def live_tpm_update(self, tpm_list=[]):
        # Update TPM list
        self.wg.qcombo_tpm.clear()
        for n, i in enumerate(station.configuration['tiles']):
            if n in tpm_list:
                self.wg.qcombo_tpm.addItem("TPM-%02d (%s)" % (n + 1, i))

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

    def live_reformat_plots(self):
        try:
            new_input_list = []
            for i in self.wg.qline_channels.text().split(","):
                if "-" in i:
                    for a in range(int(i.split("-")[0]), int(i.split("-")[1]) + 1):
                        new_input_list += [a]
                else:
                    new_input_list += [int(i)]
            self.livePlots.plotClear()
            del self.livePlots
            gc.collect()
            self.live_input_list = new_input_list
            self.livePlots = MiniPlots(self.wg.qplot_spectra, len(self.live_input_list))
            self.live_channels = self.wg.qline_channels.text()
        except ValueError:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Value Error: please check the Channels string syntax")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()

    def live_show_spectra_grid(self, state):
        if state == Qt.Checked:
            self.show_live_spectra_grid = True
            self.livePlots.showGrid(show_grid=True)
        else:
            self.show_live_spectra_grid = False
            self.livePlots.showGrid(show_grid=False)

    def closeEvent(self, event):
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Exit...",
                                                "Are you sure you want to exit ?",
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        event.ignore()

        if result == QtWidgets.QMessageBox.Yes:
            event.accept()
            #self.stopThreads = True

    #def updateHK(self):
    #    pass


if __name__ == "__main__":
    from optparse import OptionParser
    from sys import argv, stdout

    parser = OptionParser(usage="usage: %station_live [options]")
    parser.add_option("--config", action="store", dest="config",
                      type="str", default=None, help="Configuration file [default: None]")
    (conf, args) = parser.parse_args(argv[1:])

    app = QtWidgets.QApplication(sys.argv)
    window = Live(config=conf.config, uiFile="skalab_live.ui")

    sys.exit(app.exec_())
