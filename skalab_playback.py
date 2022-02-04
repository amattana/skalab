#!/usr/bin/env python
import shutil
import sys
import os
import gc
import glob
from pathlib import Path

import configparser
import numpy as np
from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt
from skalab_utils import dB2Linear, linear2dB, MiniPlots, read_data, dircheck, findtiles, calc_disk_usage, \
    calcolaspettro, closest, parse_profile
from pyaavs import station
from pydaq.persisters import FileDAQModes, RawFormatFileManager
COLORI = ["b", "g"]

default_app_dir = str(Path.home()) + "/.skalab/"
default_profile = "Default"
profile_filename = "playback.ini"

# import warnings
# warnings.filterwarnings('ignore')
# warnings.warn('*GtkDialog mapped*')

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

class Playback(QtWidgets.QMainWindow):
    """ Main UI Window class """

    def __init__(self, config="", uiFile="", profile="Default", size=[1190, 936]):
        """ Initialise main window """
        super(Playback, self).__init__()
        # Load window file
        self.wg = uic.loadUi(uiFile)
        self.setCentralWidget(self.wg)
        self.resize(size[0], size[1])

        self.profile_name = profile
        if self.profile_name == "":
            self.profile_name = "Default"
        self.profile = {}
        self.profile_file = ""
        self.load_profile(self.profile_name)

        # Populate the playback plots for the spectra, and power data
        self.miniPlots = MiniPlots(parent=self.wg.qplot_spectra, nplot=16)

        # Populate the playback plots for the spectrogram
        self.spectrogramPlots = MiniPlots(parent=self.wg.qplot_spectrogram,
                                          nplot=16, xlabel="samples", ylabel="MHz",
                                          xlim=[0, 100], ylim=[0, 400])

        # Populate the playback plots for the Power
        self.powerPlots = MiniPlots(parent=self.wg.qplot_power,
                                          nplot=16, xlabel="time samples", ylabel="dB",
                                          xlim=[0, 100], ylim=[-100, 0])

        # Populate the playback plots for the Raw Data
        self.rawPlots = MiniPlots(parent=self.wg.qplot_raw,
                                          nplot=16, xlabel="time samples", ylabel="ADU",
                                          xlim=[0, 32768], ylim=[-10000, 10000])

        # Populate the playback plots for the RMS
        self.rmsPlots = MiniPlots(parent=self.wg.qplot_rms,
                                          nplot=16, xlabel="time samples", ylabel="ADU RMS",
                                          xlim=[0, 100], ylim=[0, 50])

        self.show()
        self.load_events()

        self.config_file = config
        #self.setup_config()

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
        self.show_rms = self.wg.qcheck_rms.isChecked()
        self.show_spectra_grid = self.wg.qcheck_spectra_grid.isChecked()
        self.show_raw_grid = self.wg.qcheck_raw_grid.isChecked()
        self.show_rms_grid = self.wg.qcheck_rms_grid.isChecked()
        self.show_power_grid = self.wg.qcheck_power_grid.isChecked()

        self.input_list = np.arange(1, 17)
        self.channels_line = self.wg.qline_channels.text()

        self.xAxisRange = [float(self.wg.qline_band_from.text()), float(self.wg.qline_band_to.text())]
        self.yAxisRange = [float(self.wg.qline_level_min.text()), float(self.wg.qline_level_max.text())]

        self.tiles = []
        self.data = []
        self.power = {}
        self.raw = {}
        self.rms = {}

        # Show only the first plot view
        self.wg.qplot_spectra.show()
        self.wg.qplot_spectrogram.hide()
        self.wg.qplot_power.hide()
        self.wg.qplot_raw.hide()
        self.wg.qplot_rms.hide()

        # Show only the first plot ctrl
        self.wg.ctrl_spectrogram.hide()
        self.wg.ctrl_power.hide()
        self.wg.ctrl_raw.hide()
        self.wg.ctrl_rms.hide()
        self.wg.ctrl_spectra.show()

    def load_events(self):
        self.wg.qbutton_browse.clicked.connect(lambda: self.browse_data_folder())
        self.wg.qbutton_load.clicked.connect(lambda: self.load_data())
        self.wg.qbutton_plot.clicked.connect(lambda: self.plot_data())
        self.wg.qcombo_tpm.currentIndexChanged.connect(self.calc_data_volume)
        self.wg.qbutton_export.clicked.connect(lambda: self.export_data())
        self.wg.qcheck_spectra_grid.stateChanged.connect(self.cb_show_spectra_grid)
        self.wg.qcheck_raw_grid.stateChanged.connect(self.cb_show_raw_grid)
        self.wg.qcheck_power_grid.stateChanged.connect(self.cb_show_power_grid)
        self.wg.qcheck_rms_grid.stateChanged.connect(self.cb_show_rms_grid)
        self.wg.qradio_oplot.toggled.connect(lambda: self.check_oplot(self.wg.qradio_oplot))
        self.wg.qradio_power.toggled.connect(lambda: self.check_power(self.wg.qradio_power))
        self.wg.qradio_raw.toggled.connect(lambda: self.check_raw(self.wg.qradio_raw))
        self.wg.qradio_rms.toggled.connect(lambda: self.check_rms(self.wg.qradio_rms))
        self.wg.qradio_spectrogram.toggled.connect(lambda: self.check_spectrogram(self.wg.qradio_spectrogram))
        self.wg.qradio_avg.toggled.connect(lambda: self.check_avg_spectra(self.wg.qradio_avg))
        self.wg.qline_level_min.textEdited.connect(lambda: self.applyEnable())
        self.wg.qline_level_max.textEdited.connect(lambda: self.applyEnable())
        self.wg.qline_band_from.textEdited.connect(lambda: self.applyEnable())
        self.wg.qline_band_to.textEdited.connect(lambda: self.applyEnable())
        self.wg.qbutton_apply.clicked.connect(lambda: self.applyPressed())
        self.wg.qcheck_xpol_sp.stateChanged.connect(self.cb_show_xline)
        self.wg.qcheck_ypol_sp.stateChanged.connect(self.cb_show_yline)
        self.wg.qcheck_rms.stateChanged.connect(self.cb_show_rms)

        self.wg.qbutton_load_profile.clicked.connect(lambda: self.load())
        self.wg.qbutton_browse_station_config.clicked.connect(lambda: self.browse_config())
        self.wg.qbutton_saveas_profile.clicked.connect(lambda: self.save_as_profile())
        self.wg.qbutton_save_profile.clicked.connect(lambda: self.save_profile(this_profile=self.profile_name))
        self.wg.qbutton_delete_profile.clicked.connect(lambda: self.delete_profile(self.wg.qcombo_profile.currentText()))

    def setup_config(self):
        if not self.config_file == "":
            station.load_configuration_file(self.config_file)
            self.station_name = station.configuration['station']['name']
            self.nof_tiles = len(station.configuration['tiles'])
            self.nof_antennas = int(station.configuration['station']['number_of_antennas'])
            self.bitfile = station.configuration['station']['bitfile']
            self.truncation = int(station.configuration['station']['channel_truncation'])
            self.wg.qcombo_tpm.clear()
            self.tiles = []
            for n, i in enumerate(station.configuration['tiles']):
                self.wg.qcombo_tpm.addItem("TPM-%02d (%s)" % (n + 1, i))
                self.tiles += [i]
        else:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("PLAYBACK: Please SELECT a valid configuration file first...")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()

    def play_tpm_update(self, tpm_list=[]):
        # Update TPM list
        self.wg.qcombo_tpm.clear()
        for n, i in enumerate(station.configuration['tiles']):
            if n in tpm_list:
                self.wg.qcombo_tpm.addItem("TPM-%02d (%s)" % (n + 1, i))

    def load_profile(self, profile):
        self.profile = {}
        fullpath = default_app_dir + profile + "/" + profile_filename
        if os.path.exists(fullpath):
            print("Loading Playback Profile: " + profile + " (" + fullpath + ")")
        else:
            print("\nThe Playback Profile does not exist.\nGenerating a new one in "
                  + fullpath + "\n")
            self.make_profile(profile=profile, prodict={})
        self.profile = parse_profile(fullpath)
        self.profile_name = profile
        self.profile_file = fullpath
        self.wg.qline_configuration_file.setText(self.profile_file)
        self.wg.qline_configfile.setText(self.profile['App']['station_config'])
        # Overriding Configuration File with parameters
        self.updateProfileCombo(current=profile)
        self.populate_table_profile()

    def browse_data_folder(self):
        #if self.
        fd = QtWidgets.QFileDialog()
        fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        options = fd.options()
        self.folder = fd.getExistingDirectory(self, caption="Choose a data folder",
                                              directory="/storage/daq/", options=options)
        self.wg.qline_datapath.setText(self.folder)
        self.check_dir()
        self.calc_data_volume()

    def check_dir(self):
        if not self.wg.qline_datapath.text() == "":
            self.data_tiles = findtiles(directory=self.wg.qline_datapath.text())
            self.wg.qlabel_dircheck.setText("Found HDF5 Raw files for %d Tiles" % len(self.data_tiles))
            self.play_tpm_update(self.data_tiles)

    def calc_data_volume(self):
        if not self.wg.qline_datapath.text() == "":
            if len(self.data_tiles):
                self.wg.qlabel_dataload.setText("# Files: %d" %
                        dircheck(self.wg.qline_datapath.text(),
                                 int(self.data_tiles[self.wg.qcombo_tpm.currentIndex()])) +
                        ", Data Volume: " + calc_disk_usage(self.wg.qline_datapath.text(),
                        "raw_burst_%d_*.hdf5" % int(self.data_tiles[self.wg.qcombo_tpm.currentIndex()])))

    def load_data(self):
        if not self.wg.qline_datapath.text() == "":
            if os.path.isdir(self.wg.qline_datapath.text()):
                lista = sorted(glob.glob(self.wg.qline_datapath.text() +
                                         "/raw_burst_%d_*hdf5" % int(self.data_tiles[self.wg.qcombo_tpm.currentIndex()])))
                self.nof_files = len(lista)
                if self.nof_files:
                    progress_format = "TPM-%02d   " % (self.data_tiles[self.wg.qcombo_tpm.currentIndex()] + 1) + "%p%"
                    self.wg.qprogress_load.setFormat(progress_format)

                    file_manager = RawFormatFileManager(root_path=self.wg.qline_datapath.text(),
                                                        daq_mode=FileDAQModes.Burst)
                    del self.data
                    gc.collect()
                    self.data = []
                    for nn, l in enumerate(lista):
                        # Call the data Load
                        t, d = read_data(fmanager=file_manager,
                                         hdf5_file=l,
                                         tile=self.data_tiles[self.wg.qcombo_tpm.currentIndex()],
                                         nof_tiles=self.nof_tiles)
                        if t:
                            self.data += [{'timestamp': t, 'data': d}]
                        self.wg.qprogress_load.setValue(int((nn + 1) * 100 / len(lista)))
                    self.wg.qline_sample_start.setText("1")
                    self.wg.qline_sample_stop.setText("%d" % len(lista))
                    self.wg.qline_avg_sample_stop.setText("%d" % len(lista))
                    self.wg.qline_power_sample_stop.setText("%d" % len(lista))
                    self.wg.qlabel_raw_filenum.setText("Select File Number (%d-%d)" % (1, self.nof_files))
                    self.wg.qline_raw_filenum.setText("1")
                else:
                    self.wg.qlabel_raw_filenum.setText("Select File Number (#)")
                    self.wg.qline_raw_filenum.setText("0")
            else:
                msgBox = QtWidgets.QMessageBox()
                msgBox.setText("Please SELECT a valid data directory first...")
                msgBox.setWindowTitle("Error!")
                msgBox.exec_()
        else:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Please SELECT a valid data directory first...")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()

    def plot_data(self):
        if not self.wg.qline_channels.text() == self.channels_line:
            self.reformat_plots()

        self.resolutions = 2 ** np.array(range(16)) * (800000.0 / 2 ** 15)
        if self.wg.qradio_spectrogram.isChecked():
            self.rbw = int(closest(self.resolutions, float(self.wg.qline_spg_rbw.text())))
        elif self.wg.qradio_power.isChecked():
            self.rbw = int(closest(self.resolutions, float(self.wg.qline_power_rbw.text())))
        else:
            self.rbw = int(closest(self.resolutions, float(self.wg.qline_rbw.text())))
        self.avg = 2 ** self.rbw
        self.nsamples = int(2 ** 15 / self.avg)
        self.RBW = (self.avg * (400000.0 / 16384.0))
        self.asse_x = np.arange(self.nsamples / 2 + 1) * self.RBW * 0.001

        if self.wg.qradio_spectrogram.isChecked():
            self.wg.qcheck_rms.setEnabled(False)
            xAxisRange = (float(self.wg.qline_spg_band_from.text()),
                          float(self.wg.qline_spg_band_to.text()))
            xmin = closest(self.asse_x, xAxisRange[0])
            xmax = closest(self.asse_x, xAxisRange[1])
            yticksteps = int((xAxisRange[1] - xAxisRange[0]) / 5)

            pol = 0
            if self.wg.qcheck_ypol_spg.isChecked():
                pol = 1
            if not self.data == []:
                self.miniPlots.plotClear()
                allspgram = []
                gc.collect()
                for n in range(len(self.input_list)):
                    allspgram += [[]]
                    allspgram[n] = np.empty((3, xmax - xmin + 1,))
                    allspgram[n][:] = np.nan
                t_start = int(self.wg.qline_sample_start.text())
                t_stop = int(self.wg.qline_sample_stop.text())
                for k in range(t_start, t_stop):
                    for num, tpm_input in enumerate(self.input_list):
                        spettro, rms = calcolaspettro(self.data[k]['data'][tpm_input - 1, pol, :], self.nsamples)
                        allspgram[num] = np.concatenate((allspgram[num], [spettro[xmin:xmax + 1]]), axis=0)
                    self.wg.qprogress_plot.setValue(int((k - t_start + 1) * 100 / (t_stop - t_start)))
                for num, tpm_input in enumerate(self.input_list):
                    first_empty, allspgram[num] = allspgram[num][:3], allspgram[num][3:]
                    self.spectrogramPlots.plotSpectrogram(spettrogramma=allspgram[num], ant=num, ytickstep=yticksteps,
                                                          xmin=t_start, xmax=t_stop, startfreq=xAxisRange[0],
                                                          stopfreq=xAxisRange[1], title="INPUT-%02d" % int(tpm_input))
                self.spectrogramPlots.updatePlot()

        elif self.wg.qradio_oplot.isChecked():
            lw = 1
            if self.wg.qcheck_spectra_noline.isChecked():
                lw = 0
            if not self.data == []:
                self.miniPlots.plotClear()
                for k in range(self.nof_files):
                    for n, i in enumerate(self.input_list):
                        # Plot X Pol
                        spettro, rms = calcolaspettro(self.data[k]['data'][i - 1, 0, :], self.nsamples)
                        self.miniPlots.plotCurve(self.asse_x, spettro, n, xAxisRange=self.xAxisRange,
                                                 yAxisRange=self.yAxisRange, title="INPUT-%02d" % i,
                                                 xLabel="MHz", yLabel="dB", colore="b", rfpower=rms,
                                                 annotate_rms=False, grid=self.show_spectra_grid,
                                                 show_line=self.wg.qcheck_xpol_sp.isChecked(), lw=lw)
                        # Plot Y Pol
                        spettro, rms = calcolaspettro(self.data[k]['data'][i - 1, 1, :], self.nsamples)
                        self.miniPlots.plotCurve(self.asse_x, spettro, n, xAxisRange=self.xAxisRange,
                                                 yAxisRange=self.yAxisRange, colore="g", rfpower=rms,
                                                 annotate_rms=False, grid=self.show_spectra_grid,
                                                 show_line=self.wg.qcheck_ypol_sp.isChecked(), lw=lw)
                    self.wg.qprogress_plot.setValue(int((k + 1) * 100 / self.nof_files))
                self.miniPlots.updatePlot()
            else:
                msgBox = QtWidgets.QMessageBox()
                msgBox.setText("Please LOAD a data set first...")
                msgBox.setWindowTitle("Error!")
                msgBox.exec_()

        elif self.wg.qradio_avg.isChecked():
            lw = 1
            if self.wg.qcheck_spectra_noline.isChecked():
                lw = 0
            if not self.data == []:
                self.miniPlots.plotClear()
                spettri_x = [np.zeros(len(self.asse_x))] * len(self.input_list)
                rms_x = [0] * len(self.input_list)
                spettri_y = [np.zeros(len(self.asse_x))] * len(self.input_list)
                # rms_y = [[] for _ in range(len(self.input_list))]
                rms_y = [0] * len(self.input_list)
                avgnum = int(self.wg.qline_avg_sample_stop.text()) - int(self.wg.qline_avg_sample_start.text())
                for k in range(int(self.wg.qline_avg_sample_start.text())-1,
                               int(self.wg.qline_avg_sample_stop.text())-1):
                    for n, i in enumerate(self.input_list):
                        # Plot X Pol
                        spettro, rfpow = calcolaspettro(self.data[k]['data'][i - 1, 0, :], self.nsamples)
                        spettri_x[n] = np.add(spettri_x[n], dB2Linear(spettro))
                        rms_x[n] = np.add(rms_x[n], dB2Linear(rfpow))

                        # Plot Y Pol
                        spettro, rfpow = calcolaspettro(self.data[k]['data'][i - 1, 1, :], self.nsamples)
                        spettri_y[n] = np.add(spettri_y[n], dB2Linear(spettro))
                        rms_y[n] = np.add(rms_y[n], dB2Linear(rfpow))
                    self.wg.qprogress_plot.setValue(int((k + 1) * 100 / avgnum))
                for n, i in enumerate(self.input_list):
                    # Plot X Pol
                    spettro = linear2dB(spettri_x[n] / avgnum)
                    rms = linear2dB(rms_x[n] / avgnum)
                    self.miniPlots.plotCurve(self.asse_x, spettro, n, xAxisRange=self.xAxisRange,
                                             yAxisRange=self.yAxisRange, title="INPUT-%02d" % i,
                                             xLabel="MHz", yLabel="dB", colore="b", rfpower=rms,
                                             annotate_rms=self.show_rms, grid=self.show_spectra_grid, lw=lw,
                                             show_line=self.wg.qcheck_xpol_sp.isChecked(),
                                             rms_position=float(self.wg.qline_rms_pos.text()))
                    # Plot Y Pol
                    spettro = linear2dB(spettri_y[n] / avgnum)
                    rms = linear2dB(rms_y[n] / self.nof_files)
                    self.miniPlots.plotCurve(self.asse_x, spettro, n, xAxisRange=self.xAxisRange,
                                             yAxisRange=self.yAxisRange, colore="g", rfpower=rms,
                                             annotate_rms=self.show_rms, grid=self.show_spectra_grid, lw=lw,
                                             show_line=self.wg.qcheck_ypol_sp.isChecked(),
                                             rms_position=float(self.wg.qline_rms_pos.text()))
                self.wg.qcheck_rms.setEnabled(True)
                self.wg.qcheck_spectra_grid.setEnabled(True)
                self.miniPlots.updatePlot()
            else:
                msgBox = QtWidgets.QMessageBox()
                msgBox.setText("Please LOAD a data set first...")
                msgBox.setWindowTitle("Error!")
                msgBox.exec_()

        elif self.wg.qradio_power.isChecked():
            lw = 1
            if self.wg.qcheck_power_noline.isChecked():
                lw = 0
            if not self.data == []:
                xAxisRange = (float(self.wg.qline_power_sample_start.text()),
                              float(self.wg.qline_power_sample_stop.text()))
                yAxisRange = (float(self.wg.qline_power_level_min.text()),
                              float(self.wg.qline_power_level_max.text()))
                self.powerPlots.plotClear()
                for n, i in enumerate(self.input_list):
                    for npol, pol in enumerate(["Pol-X", "Pol-Y"]):
                        self.power["Input-%02d_%s" % (i, pol)] = []
                        self.power["Input-%02d_%s_adc-clip" % (i, pol)] = []
                for k in range(self.nof_files):
                    for n, i in enumerate(self.input_list):
                        for npol, pol in enumerate(["Pol-X", "Pol-Y"]):
                            if 127 in self.data[k]['data'][i - 1, npol, :] or \
                                    -128 in self.data[k]['data'][i - 1, npol, :]:
                                self.power["Input-%02d_%s_adc-clip" % (i, pol)] += [self.data[k]['timestamp']]
                            spettro, rms = calcolaspettro(self.data[k]['data'][i - 1, npol, :], self.nsamples, log=False)
                            bandpower = np.sum(spettro[closest(self.asse_x, float(self.wg.qline_power_band_from.text())): closest(self.asse_x, float(self.wg.qline_power_band_to.text()))])
                            if not len(self.power["Input-%02d_%s" % (i, pol)]):
                                self.power["Input-%02d_%s" % (i, pol)] = [linear2dB(bandpower)]
                            else:
                                self.power["Input-%02d_%s" % (i, pol)] += [linear2dB(bandpower)]
                    self.wg.qprogress_plot.setValue(int((k + 1) * 100 / self.nof_files))

                for n, i in enumerate(self.input_list):
                    # Plot X Pol
                    mov_avg = self.power["Input-%02d_Pol-X" % i]
                    if self.wg.qcheck_movavg.isChecked():
                        mov_avg = moving_average(self.power["Input-%02d_Pol-X" % i], int(self.wg.qline_movavgwdw.text()))
                    self.powerPlots.plotPower(range(len(mov_avg)), mov_avg, n, xAxisRange=xAxisRange,
                                              yAxisRange=yAxisRange, title="INPUT-%02d" % i, xLabel="time samples",
                                              yLabel="dB", colore="b", grid=self.show_power_grid, lw=lw,
                                              show_line=self.wg.qcheck_xpol_power.isChecked())
                    mov_avg = self.power["Input-%02d_Pol-Y" % i]
                    if self.wg.qcheck_movavg.isChecked():
                        mov_avg = moving_average(self.power["Input-%02d_Pol-Y" % i], int(self.wg.qline_movavgwdw.text()))
                    self.powerPlots.plotPower(range(len(mov_avg)), mov_avg, n, colore="g",
                                              show_line=self.wg.qcheck_ypol_power.isChecked(), lw=lw)
                self.powerPlots.updatePlot()
                #print("First tstamp: %d" % int(self.data[0]['timestamp']))
                #print("Last  tstamp: %d" % int(self.data[self.nof_files - 1]['timestamp']))

        elif self.wg.qradio_raw.isChecked():
            if 1 <= int(self.wg.qline_raw_filenum.text()) <= self.nof_files:
                lw = 1
                msize = 0
                if self.wg.qcheck_raw_noline.isChecked():
                    lw = 0
                    msize = 1
                if not self.data == []:
                    xAxisRange = (float(self.wg.qline_raw_start.text()),
                                  float(self.wg.qline_raw_stop.text()))
                    yAxisRange = (float(self.wg.qline_raw_min.text()),
                                  float(self.wg.qline_raw_max.text()))
                    self.rawPlots.plotClear()
                    for n, i in enumerate(self.input_list):
                        for npol, pol in enumerate(["Pol-X", "Pol-Y"]):
                            self.raw["Input-%02d_%s" % (i, pol)] = []
                            self.raw["Input-%02d_%s_adc-clip" % (i, pol)] = []
                    for k in [int(self.wg.qline_raw_filenum.text()) - 1]:
                        for n, i in enumerate(self.input_list):
                            for npol, pol in enumerate(["Pol-X", "Pol-Y"]):
                                if 127 in self.data[k]['data'][i - 1, npol, :] or \
                                        -128 in self.data[k]['data'][i - 1, npol, :]:
                                    self.raw["Input-%02d_%s_adc-clip" % (i, pol)] += [self.data[k]['timestamp']]
                                #spettro, rms = calcolaspettro(self.data[k]['data'][i - 1, npol, :], self.nsamples, log=False)
                                self.raw["Input-%02d_%s" % (i, pol)] = self.data[k]['data'][i - 1, npol, :]
                    for n, i in enumerate(self.input_list):
                        self.rawPlots.plotCurve(np.arange(len(self.raw["Input-%02d_Pol-X" % i])),
                                                 self.raw["Input-%02d_Pol-X" % i], n, xAxisRange=xAxisRange,
                                                 yAxisRange=yAxisRange, title="INPUT-%02d" % i, xLabel="samples",
                                                 yLabel="ADU", colore="b", annotate_rms=False, markersize=msize,
                                                 grid=self.show_raw_grid, lw=lw, rms_position=140,
                                                 show_line=self.wg.qradio_raw_x.isChecked())
                        self.rawPlots.plotCurve(np.arange(len(self.raw["Input-%02d_Pol-Y" % i])),
                                                 self.raw["Input-%02d_Pol-Y" % i], n, xAxisRange=xAxisRange,
                                                 yAxisRange=yAxisRange, title="INPUT-%02d" % i, xLabel="samples",
                                                 yLabel="ADU", colore="g", annotate_rms=False, markersize=msize,
                                                 grid=self.show_raw_grid, lw=lw, rms_position=140,
                                                 show_line=self.wg.qradio_raw_y.isChecked())
                        self.wg.qprogress_plot.setValue(int((k + 1) * 100 / 1))
                    self.rawPlots.updatePlot()
                self.wg.qbutton_export.setEnabled(True)
            else:
                msgBox = QtWidgets.QMessageBox()
                msgBox.setText("Please select a file number within the range 1-%d." % self.nof_files)
                msgBox.setWindowTitle("Error!")
                msgBox.exec_()

        elif self.wg.qradio_rms.isChecked():
            lw = 1
            if self.wg.qcheck_rms_noline.isChecked():
                lw = 0
            if not self.data == []:
                xAxisRange = (float(self.wg.qline_rms_sample_start.text()),
                              float(self.wg.qline_rms_sample_stop.text()))
                if self.wg.qcheck_raw_dbm.isChecked():
                    yAxisRange = (float(self.wg.qline_rms_level_min.text()),
                                  float(self.wg.qline_rms_level_max.text()))
                else:
                    yAxisRange = (float(self.wg.qline_rms_min.text()),
                                  float(self.wg.qline_rms_max.text()))

                self.rmsPlots.plotClear()
                for n, i in enumerate(self.input_list):
                    for npol, pol in enumerate(["Pol-X", "Pol-Y"]):
                        self.rms["Input-%02d_%s" % (i, pol)] = []
                for k in range(self.nof_files):
                    for n, i in enumerate(self.input_list):
                        for npol, pol in enumerate(["Pol-X", "Pol-Y"]):
                            spettro, rfpow, rms = calcolaspettro(self.data[k]['data'][i - 1, npol, :], self.nsamples,
                                                                 log=False, adurms=True)
                            if self.wg.qcheck_raw_dbm.isChecked():
                                self.rms["Input-%02d_%s" % (i, pol)] = np.append(self.rms["Input-%02d_%s" % (i, pol)], rfpow)
                            else:
                                self.rms["Input-%02d_%s" % (i, pol)] = np.append(self.rms["Input-%02d_%s" % (i, pol)], rms)
                    self.wg.qprogress_plot.setValue(int((k + 1) * 100 / self.nof_files))

                for n, i in enumerate(self.input_list):
                    # Plot X Pol
                    self.rmsPlots.plotPower(range(len(self.rms["Input-%02d_Pol-X" % i])),
                                            self.rms["Input-%02d_Pol-X" % i] , n, xAxisRange=xAxisRange,
                                            yAxisRange=yAxisRange, title="INPUT-%02d" % i, xLabel="time samples",
                                            yLabel="ADU RMS", colore="b", grid=self.show_rms_grid, lw=lw,
                                            show_line=self.wg.qcheck_xpol_rms.isChecked())
                    self.rmsPlots.plotPower(range(len(self.rms["Input-%02d_Pol-Y" % i])),
                                            self.rms["Input-%02d_Pol-Y" % i], n, colore="g",
                                            show_line=self.wg.qcheck_ypol_rms.isChecked(), lw=lw)
                self.rmsPlots.updatePlot()

    def export_data(self):
        if self.wg.qradio_spectrogram.isChecked():
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Spectrogram Data Export is not yet implemented")
            msgBox.setWindowTitle("Message")
            msgBox.exec_()
            pass
        elif self.wg.qradio_oplot.isChecked():
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Oplot Data Export is not yet implemented")
            msgBox.setWindowTitle("Message")
            msgBox.exec_()
            pass
        elif self.wg.qradio_avg.isChecked():
            pass
        elif self.wg.qradio_power.isChecked():
            pass
        elif self.wg.qradio_raw.isChecked():
            result = QtWidgets.QMessageBox.question(self, "Export Data...",
                        "Are you sure you want to export %d files?" % (len(self.input_list)),
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if result == QtWidgets.QMessageBox.Yes:
                print("Saving data")
            else:
                print("ciao")

    def reformat_plots(self):
        try:
            new_input_list = []
            for i in self.wg.qline_channels.text().split(","):
                if "-" in i:
                    for a in range(int(i.split("-")[0]), int(i.split("-")[1]) + 1):
                        new_input_list += [a]
                else:
                    new_input_list += [int(i)]
            self.miniPlots.plotClear()
            self.spectrogramPlots.plotClear()
            self.powerPlots.plotClear()
            del self.miniPlots
            del self.spectrogramPlots
            del self.powerPlots
            del self.rawPlots
            del self.rmsPlots
            gc.collect()
            self.input_list = new_input_list
            self.miniPlots = MiniPlots(self.wg.qplot_spectra, len(self.input_list))
            self.spectrogramPlots = MiniPlots(parent=self.wg.qplot_spectrogram,
                                              nplot=len(self.input_list), xlabel="samples", ylabel="MHz",
                                              xlim=[0, 100], ylim=[0, 400])
            self.powerPlots = MiniPlots(parent=self.wg.qplot_power, nplot=len(self.input_list),
                                        xlabel="time samples", ylabel="dB", xlim=[0, 100], ylim=[-100, 0])
            self.rmsPlots = MiniPlots(parent=self.wg.qplot_rms, nplot=len(self.input_list),
                                        xlabel="time samples", ylabel="ADU RMS", xlim=[0, 100], ylim=[0, 50])
            self.rawPlots = MiniPlots(parent=self.wg.qplot_raw,
                                      nplot=len(self.input_list), xlabel="time samples", ylabel="ADU",
                                      xlim=[0, 32768], ylim=[-150, 150])

            self.channels_line = self.wg.qline_channels.text()
        except ValueError:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Value Error: please check the Channels string syntax")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()

    def cb_show_spectra_grid(self, state):
        if state == Qt.Checked:
            self.show_spectra_grid = True
            self.miniPlots.showGrid(show_grid=True)
        else:
            self.show_spectra_grid = False
            self.miniPlots.showGrid(show_grid=False)

    def cb_show_raw_grid(self, state):
        if state == Qt.Checked:
            self.show_raw_grid = True
            self.rawPlots.showGrid(show_grid=True)
        else:
            self.show_raw_grid = False
            self.rawPlots.showGrid(show_grid=False)

    def cb_show_power_grid(self, state):
        if state == Qt.Checked:
            self.show_power_grid = True
            self.powerPlots.showGrid(show_grid=True)
        else:
            self.show_power_grid = False
            self.powerPlots.showGrid(show_grid=False)

    def cb_show_rms_grid(self, state):
        if state == Qt.Checked:
            self.show_rms_grid = True
            self.rmsPlots.showGrid(show_grid=True)
        else:
            self.show_rms_grid = False
            self.rmsPlots.showGrid(show_grid=False)

    def cb_show_xline(self, state):
        times = [0] #if self.wg.qradio_avg.isChecked() else range(self.nof_files)
        if state == Qt.Checked:
            for k in times:
                self.miniPlots.hide_line("b", True)
            self.miniPlots.hide_annotation(["b"], self.wg.qcheck_rms.isChecked())
        else:
            for k in times:
                self.miniPlots.hide_line("b", False)
            self.miniPlots.hide_annotation(["b"], False)

    def cb_show_yline(self, state):
        times = [0] #if self.wg.qradio_avg.isChecked() else range(self.nof_files)
        if state == Qt.Checked:
            for k in times:
                self.miniPlots.hide_line("g", True)
            self.miniPlots.hide_annotation(["g"], self.wg.qcheck_rms.isChecked())
        else:
            for k in times:
                self.miniPlots.hide_line("g", False)
            self.miniPlots.hide_annotation(["g"], False)

    def cb_show_rms(self, state):
        times = [0] #if self.wg.qradio_avg.isChecked() else range(len(self.lines))
        if state == Qt.Checked:
            self.show_rms = True
            for k in times:
                self.miniPlots.hide_annotation(["b"], visu=self.wg.qcheck_xpol_sp.isChecked())
                self.miniPlots.hide_annotation(["g"], visu=self.wg.qcheck_ypol_sp.isChecked())
        else:
            self.show_rms = False
            for k in times:
                self.miniPlots.hide_annotation(["b", "g"], visu=False)

    def check_oplot(self, b):
        if b.isChecked():
            # Show only spectra plot
            self.wg.qplot_spectrogram.hide()
            self.wg.qplot_power.hide()
            self.wg.qplot_raw.hide()
            self.wg.qplot_rms.hide()
            self.wg.qplot_spectra.show()
            # Show only spectra ctrl
            self.wg.ctrl_spectrogram.hide()
            self.wg.ctrl_power.hide()
            self.wg.ctrl_raw.hide()
            self.wg.ctrl_rms.hide()
            self.wg.ctrl_spectra.show()

    def check_power(self, b):
        if b.isChecked():
            # Show only power plot
            self.wg.qplot_spectrogram.hide()
            self.wg.qplot_spectra.hide()
            self.wg.qplot_raw.hide()
            self.wg.qplot_rms.hide()
            self.wg.qplot_power.show()
            # Show only power ctrl
            self.wg.ctrl_spectrogram.hide()
            self.wg.ctrl_spectra.hide()
            self.wg.ctrl_raw.hide()
            self.wg.ctrl_rms.hide()
            self.wg.ctrl_power.show()

    def check_spectrogram(self, b):
        if b.isChecked():
            #self.wg.qcheck_rms.setEnabled(False)
            #self.wg.qcheck_grid.setEnabled(False)
            # Show only spectrogram plot
            self.wg.qplot_spectra.hide()
            self.wg.qplot_power.hide()
            self.wg.qplot_raw.hide()
            self.wg.qplot_rms.hide()
            self.wg.qplot_spectrogram.show()
            # Show only spectrogram ctrl
            self.wg.ctrl_spectrogram.show()
            self.wg.ctrl_spectra.hide()
            self.wg.ctrl_raw.hide()
            self.wg.ctrl_rms.hide()
            self.wg.ctrl_power.hide()

    def check_avg_spectra(self, b):
        if b.isChecked():
            # Show only spectra plot
            self.wg.qplot_power.hide()
            self.wg.qplot_spectrogram.hide()
            self.wg.qplot_raw.hide()
            self.wg.qplot_rms.hide()
            self.wg.qplot_spectra.show()
            # Show only spectra ctrl
            self.wg.ctrl_spectrogram.hide()
            self.wg.ctrl_power.hide()
            self.wg.ctrl_raw.hide()
            self.wg.ctrl_rms.hide()
            self.wg.ctrl_spectra.show()

    def check_raw(self, b):
        if b.isChecked():
            # Show only raw plot
            self.wg.qplot_power.hide()
            self.wg.qplot_spectrogram.hide()
            self.wg.qplot_spectra.hide()
            self.wg.qplot_rms.hide()
            self.wg.qplot_raw.show()
            # Show only raw ctrl
            self.wg.ctrl_spectrogram.hide()
            self.wg.ctrl_power.hide()
            self.wg.ctrl_spectra.hide()
            self.wg.ctrl_rms.hide()
            self.wg.ctrl_raw.show()

    def check_rms(self, b):
        if b.isChecked():
            # Show only rms plot
            self.wg.qplot_power.hide()
            self.wg.qplot_spectrogram.hide()
            self.wg.qplot_spectra.hide()
            self.wg.qplot_raw.hide()
            self.wg.qplot_rms.show()
            # Show only rms ctrl
            self.wg.ctrl_spectrogram.hide()
            self.wg.ctrl_power.hide()
            self.wg.ctrl_spectra.hide()
            self.wg.ctrl_raw.hide()
            self.wg.ctrl_rms.show()

    def check_tab_show(self, b, index):
        if b.isChecked():
            QtWidgets.QTabWidget.setTabVisible(self.wg.qtabMain, index, True)
        else:
            QtWidgets.QTabWidget.setTabVisible(self.wg.qtabMain, index, False)

    def applyEnable(self):
        try:
            if self.xAxisRange[0] == float(self.wg.qline_band_from.text()) \
                    and self.xAxisRange[1] == float(self.wg.qline_band_to.text())\
                    and self.yAxisRange[0] == float(self.wg.qline_level_min.text())\
                    and self.yAxisRange[1] == float(self.wg.qline_level_max.text()):
                self.wg.qbutton_apply.setEnabled(False)
            else:
                self.wg.qbutton_apply.setEnabled(True)
        except ValueError:
            pass

    def applyPressed(self):
        #if not self.xAxisRange[0] == float(self.wg.qline_band_from.text()) \
        #        or not self.xAxisRange[1] == float(self.wg.qline_band_to.text()):
        self.xAxisRange = [float(self.wg.qline_band_from.text()), float(self.wg.qline_band_to.text())]
        self.miniPlots.set_x_limits(self.xAxisRange)
        self.wg.qbutton_apply.setEnabled(False)

        #if not self.yAxisRange[0] == float(self.wg.qline_level_min.text())\
        #        or not self.yAxisRange[1] == float(self.wg.qline_level_max.text()):
        self.yAxisRange = [float(self.wg.qline_level_min.text()), float(self.wg.qline_level_max.text())]
        self.miniPlots.set_y_limits(self.yAxisRange)
        self.wg.qbutton_apply.setEnabled(False)

    def load(self):
        self.load_profile(self.wg.qcombo_profile.currentText())

    def browse_config(self):
        fd = QtWidgets.QFileDialog()
        fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        options = fd.options()
        self.config_file = fd.getOpenFileName(self, caption="Select a Station Config File...",
                                              directory="/opt/aavs/config/", options=options)[0]
        self.wg.qline_configfile.setText(self.config_file)

    def populate_table_profile(self):
        self.wg.qtable_conf.clearSpans()
        self.wg.qtable_conf.setGeometry(QtCore.QRect(640, 20, 481, 171))
        self.wg.qtable_conf.setObjectName("qtable_conf")
        self.wg.qtable_conf.setColumnCount(1)
        self.wg.qtable_conf.setWordWrap(True)

        total_rows = 1
        for i in self.profile.sections():
            total_rows = total_rows + len(self.profile[i]) + 1
        self.wg.qtable_conf.setRowCount(total_rows + 1)

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

        #self.wg.qtable_conf.horizontalHeader().setStretchLastSection(True)
        self.wg.qtable_conf.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        #self.wg.qtable_conf.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wg.qtable_conf.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

    def make_profile(self, profile: str, prodict: dict):
        conf = configparser.ConfigParser()
        conf['App'] = {}
        if 'App' in prodict.keys() and 'station_config' in prodict['App'].keys():
            conf['App']['station_config'] = prodict['App']['station_config']
        else:
            conf['App']['station_config'] = ""

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

    def save_profile(self, this_profile, reload=True):
        self.make_profile(profile=this_profile,
                          prodict={'App': {'station_config': self.wg.qline_configfile.text()}})
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

    def closeEvent(self, event):
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Exit...",
                                                "Are you sure you want to exit ?",
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        event.ignore()

        if result == QtWidgets.QMessageBox.Yes:
            event.accept()


if __name__ == "__main__":
    from optparse import OptionParser
    from sys import argv, stdout

    parser = OptionParser(usage="usage: %station_playback [options]")
    parser.add_option("--config", action="store", dest="config",
                      type="str", default=None, help="Configuration file [default: None]")
    (conf, args) = parser.parse_args(argv[1:])

    app = QtWidgets.QApplication(sys.argv)
    window = Playback(config=conf.config, uiFile="skalab_playback.ui")

    sys.exit(app.exec_())
