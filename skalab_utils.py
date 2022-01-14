import glob
import datetime
import subprocess
import calendar
import numpy as np
import configparser
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5 import QtCore, QtGui, QtWidgets, uic
import sys
sys.path.append("../../pyaavs/tests/")
from pydaq.persisters import *
from get_nic import getnic


def parse_profile(config=""):
    confparser = configparser.ConfigParser()
    confparser.read(config)
    return confparser


def dt_to_timestamp(d):
    return calendar.timegm(d.timetuple())


def ts_to_datestring(tstamp, formato="%Y-%m-%d %H:%M:%S"):
    return datetime.datetime.strftime(datetime.datetime.utcfromtimestamp(tstamp), formato)


def fname_to_tstamp(date_time_string):
    time_parts = date_time_string.split('_')
    d = datetime.datetime.strptime(time_parts[0], "%Y%m%d")  # "%d/%m/%Y %H:%M:%S"
    timestamp = calendar.timegm(d.timetuple())
    timestamp += int(time_parts[1])# - (60 * 60 * 8)  # Australian Time
    return timestamp


def colors(name):
    if name == "white_on_red":
        return "background-color: rgb(204, 0, 0); color: rgb(255, 255, 255)"
    elif name == "black_on_yellow":
        return "background-color: rgb(255, 255, 0); color: rgb(0, 0, 0)"
    elif name == "black_on_green":
        return "background-color: rgb(78, 154, 6);"
    elif name == "black_on_blue":
        return "background-color: rgb(85, 170, 255); color: rgb(0, 0, 0)"
    elif name == "black_on_red":
        return "background-color: rgb(204, 0, 0); color: rgb(0, 0, 0)"
    elif name == "yellow_on_black":
        return "background-color: rgb(0, 0, 0); color: rgb(252, 233, 79)"
    elif name == "black_on_grey":
        return ""


class MiniCanvas(FigureCanvas):
    def __init__(self, nplot, parent=None, dpi=100, xlabel="MHz", ylabel="dB", xlim=[0, 400], ylim=[-80, -20], size=(11.5, 6.8)):
        self.nplot = nplot
        self.dpi = dpi
        self.fig = Figure(size, dpi=self.dpi, facecolor='white')
        self.fig.set_tight_layout(True)
        self.ax = []
        for i in range(self.nplot):
            self.ax += [self.fig.add_subplot(int(np.ceil(math.sqrt(self.nplot))),
                                             int(np.ceil(math.sqrt(self.nplot))), i + 1)]
            self.ax[i].xaxis.set_label_text(xlabel, fontsize=7)
            self.ax[i].yaxis.set_label_text(ylabel, fontsize=9)
            self.ax[i].set_title("INPUT-%02d" % (i + 1), fontsize=10)
            self.ax[i].tick_params(axis='both', which='minor', labelsize=8)
            self.ax[i].tick_params(axis='both', which='both', labelsize=8)
            self.ax[i].set_ylim(ylim)
            self.ax[i].set_xlim(xlim)
        FigureCanvas.__init__(self, self.fig)
        FigureCanvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)


class MiniPlots(QtWidgets.QWidget):
    """ Class encapsulating a matplotlib plot"""
    def __init__(self, parent=None, nplot=16, dpi=100, xlabel="MHz", ylabel="dB", xlim=[0, 400],
                 ylim=[-80, -20], size=(11.2, 6.8)):
        QtWidgets.QWidget.__init__(self, parent)
        """ Class initialiser """
        self.nplot = nplot
        self.canvas = MiniCanvas(self.nplot, parent=parent, dpi=dpi, xlabel=xlabel,
                                 ylabel=ylabel, xlim=xlim, ylim=ylim, size=size)
        self.updateGeometry()
        self.vbl = QtWidgets.QVBoxLayout()
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)
        self.show()
        self.canvas_elements = {}
        self.plots = [self.canvas_elements.copy() for _ in range(self.nplot)]
        self.titlesize = 10
        #self.showPlots(True)

    def showPlots(self, visu):
        for i in range(self.nplot):
            self.canvas.ax[i].set_visible(visu)
        self.canvas.draw()

    def plotCurve(self, assex, data, ant, xAxisRange=None, yAxisRange=None, colore="b", xLabel="", yLabel="", title="",
                  titlesize=10, rfpower=0, annotate_rms=False, rms_position=-20, grid=False, show_line=True, lw=1, markersize=1):
        """ Plot the data as a curve"""
        self.titlesize = titlesize
        if len(data) != 0:
            line, = self.canvas.ax[int(ant)].plot(assex, data, color=colore, lw=lw, markersize=markersize, marker=".")
            self.plots[int(ant)][colore + 'line'] = line
            self.plots[int(ant)][colore + 'line'].set_visible(show_line)
            if not xAxisRange == None:
                self.canvas.ax[ant].set_xlim(xAxisRange)
            if not yAxisRange == None:
                self.canvas.ax[ant].set_ylim(yAxisRange)
            if not title == "":
                self.canvas.ax[ant].set_title(title, fontsize=titlesize)
            if not xLabel == "":
                self.canvas.ax[ant].set_xlabel(xLabel, fontsize=titlesize)
            if not yLabel == "":
                self.canvas.ax[ant].set_ylabel(yLabel, fontsize=titlesize)
            if grid:
                self.canvas.ax[ant].grid(grid)
            if colore == "b":
                ann = self.canvas.ax[ant].annotate("%3.1f" % rfpower + " dBm",
                                                   (xAxisRange[0] + 20, rms_position),
                                                   fontsize=(titlesize - 2), color=colore)
            else:
                ann = self.canvas.ax[ant].annotate("%3.1f" % rfpower + " dBm",
                                                   (xAxisRange[1] - 130, rms_position),
                                                   fontsize=(titlesize - 2), color=colore)
            self.plots[int(ant)][colore + 'rms'] = ann
            self.plots[int(ant)][colore + 'rmsvalue'] = rfpower
            self.plots[int(ant)]['xAxisRange'] = xAxisRange
            self.plots[int(ant)]['yAxisRange'] = yAxisRange
            self.plots[int(ant)][colore + 'show_rms'] = annotate_rms
            self.plots[int(ant)][colore + 'show_rms_pos'] = rms_position
            if show_line:
                self.plots[int(ant)][colore + 'rms'].set_visible(annotate_rms)
            else:
                self.plots[int(ant)][colore + 'rms'].set_visible(False)

    def plotSpectrogram(self, spettrogramma, ant, title="", startfreq=0, stopfreq=400,
                        xmin=0, xmax=500, ytickstep=5, wclim=(-100, -10)):
        self.canvas.ax[ant].cla()
        band = str(startfreq) + "-" + str(stopfreq)
        #ystep = ytickstep
        self.canvas.ax[ant].imshow(np.rot90(spettrogramma), extent=[xmin, xmax, startfreq, stopfreq],
                                   interpolation='none', aspect='auto', cmap='jet', clim=wclim)
        #print(np.rot90(spettrogramma)[1].shape)
        #BW = stopfreq - startfreq
        #ytic = (np.array(range(int(BW / ystep) + 1)) * ystep * (len(np.rot90(spettrogramma)) / float(BW))) + xmin
        #self.canvas.ax[ant].set_yticks(len(np.rot90(spettrogramma)) - ytic)
        #ylabmax = (np.array(range(int(BW / ystep) + 1)) * ystep) + int(startfreq)
        #self.canvas.ax[ant].set_yticklabels(ylabmax.astype("str").tolist())
        self.canvas.ax[ant].xaxis.set_label_text("time samples", fontsize=7)
        self.canvas.ax[ant].yaxis.set_label_text("MHz", fontsize=9)
        self.canvas.ax[ant].set_title(title, fontsize=10)

    def plotPower(self, assex, data, ant, xAxisRange=None, yAxisRange=None, colore="b", xLabel="", yLabel="", title="",
                  titlesize=10, grid=False, show_line=True, lw=1):
        """ Plot the data as a curve"""
        self.titlesize = titlesize
        if len(data) != 0:
            line, = self.canvas.ax[int(ant)].plot(assex, data, color=colore, lw=lw, markersize=1, marker=".")
            self.plots[int(ant)][colore + 'line'] = line
            self.plots[int(ant)][colore + 'line'].set_visible(show_line)
            if not xAxisRange == None:
                self.canvas.ax[ant].set_xlim(xAxisRange)
            if not yAxisRange == None:
                self.canvas.ax[ant].set_ylim(yAxisRange)
            if not title == "":
                self.canvas.ax[ant].set_title(title, fontsize=titlesize)
            if not xLabel == "":
                self.canvas.ax[ant].set_xlabel(xLabel, fontsize=titlesize)
            if not yLabel == "":
                self.canvas.ax[ant].set_ylabel(yLabel, fontsize=titlesize)
            if grid:
                self.canvas.ax[ant].grid(grid)
            self.plots[int(ant)]['xAxisRange'] = xAxisRange
            self.plots[int(ant)]['yAxisRange'] = yAxisRange

    def showGrid(self, show_grid=True):
        for i in range(self.nplot):
            self.canvas.ax[i].grid(show_grid)
        self.canvas.draw()
        #self.show()

    def set_x_limits(self, xAxisRange):
        for i in range(self.nplot):
            self.canvas.ax[i].set_xlim(xAxisRange)
        self.canvas.draw()
        #self.show()

    def set_y_limits(self, yAxisRange):
        for n in range(self.nplot):
            self.canvas.ax[n].set_ylim(yAxisRange)
            self.plots[n]['yAxisRange'] = yAxisRange
            if 'brms' in self.plots[n].keys():
                self.plots[n]['brms'].set_visible(False)
                del self.plots[n]['brms']
                self.plots[n]['brms'] = self.canvas.ax[n].annotate("%3.1f" % self.plots[n]['brmsvalue'] + " dBm",
                                                                   (self.plots[n]['xAxisRange'][0] + 20,
                                                                    self.plots[n]['yAxisRange'][1] - 10),
                                                                   fontsize=(self.titlesize - 2), color="b")
                self.plots[n]['brms'].set_visible(self.plots[n]['bshow_rms'])
                #print("B RIDISEGNO AL POSTO GIUSTO: ", self.plots[n]['xAxisRange'][0] + 20, self.plots[n]['yAxisRange'][1] - 10, "VISIBLE", self.plots[n]['bshow_rms'])
            if 'grms' in self.plots[n].keys():
                self.plots[n]['grms'].set_visible(False)
                del self.plots[n]['grms']
                self.plots[n]['grms'] = self.canvas.ax[n].annotate("%3.1f" % self.plots[n]['grmsvalue'] + " dBm",
                                                                   (self.plots[n]['xAxisRange'][1] - 130,
                                                                    self.plots[n]['yAxisRange'][1] - 10),
                                                                   fontsize=(self.titlesize - 2), color="g")
                self.plots[n]['grms'].set_visible(self.plots[n]['gshow_rms'])
                #print("B RIDISEGNO AL POSTO GIUSTO", self.plots[n]['xAxisRange'][1] - 130, self.plots[n]['yAxisRange'][1] - 10, "VISIBLE", self.plots[n]['bshow_rms'])
        self.canvas.draw()
        #self.show()

    def hide_line(self, colore, visu=True):
        for n in range(self.nplot):
            if colore + 'line' in self.plots[n].keys():
                self.plots[n][colore + 'line'].set_visible(visu)
            if colore + 'rms' in self.plots[n].keys():
                self.plots[n][colore + 'rms'].set_visible(visu)
            self.plots[n][colore + 'show_rms'] = visu
        self.canvas.draw()

    def hide_annotation(self, pols=['b', 'g'], visu=True):
        for p in pols:
            for n in range(self.nplot):
                if p + 'rms' in self.plots[n].keys():
                    self.plots[n][p + 'rms'].set_visible(visu)
                self.plots[n][p + 'show_rms'] = visu
        self.canvas.draw()

    def updatePlot(self):
        self.canvas.draw()
        self.show()

    def plotClear(self):
        # Reset the plot landscape
        for i in range(self.nplot):
            self.canvas.ax[i].clear()
        #self.updatePlot()


# Antenna mapping
antenna_mapping = [0, 1, 2, 3, 8, 9, 10, 11, 15, 14, 13, 12, 7, 6, 5, 4]
#antenna_mapping = range(16)
nof_samples = 20000000
COLORE=['b', 'g']


def _connect_station(aavs_station):
    """ Return a connected station """
    # Connect to station and see if properly formed
    while True:
        try:
            aavs_station.check_station_status()
            if not aavs_station.properly_formed_station:
                raise Exception
            break
        except:
            sleep(60)
            try:
                aavs_station.connect()
            except:
                continue


def closest(serie, num):
    return serie.tolist().index(min(serie.tolist(), key=lambda z: abs(z - num)))


def calcSpectra(vett):
    window = np.hanning(len(vett))
    spettro = np.fft.rfft(vett * window)
    N = len(spettro)
    acf = 2  # amplitude correction factor
    cplx = ((acf * spettro) / N)
    spettro[:] = abs((acf * spettro) / N)
    # print len(vett), len(spettro), len(np.real(spettro))
    return np.real(spettro)


def calcolaspettro(dati, nsamples=32768, log=True, adurms=False):
    n = int(nsamples)  # split and average number, from 128k to 16 of 8k # aavs1 federico
    sp = [dati[x:x + n] for x in range(0, len(dati), n)]
    mediato = np.zeros(len(calcSpectra(sp[0])))
    for k in sp:
        singolo = calcSpectra(k)
        mediato[:] += singolo
    mediato[:] /= (2 ** 15 / nsamples)  # federico
    with np.errstate(divide='ignore', invalid='ignore'):
        mediato[:] = 20 * np.log10(mediato / 127.0)
    d = np.array(dati, dtype=np.int8)
    adu_rms = np.sqrt(np.mean(np.power(d, 2), 0))
    volt_rms = adu_rms * (1.7 / 256.)
    with np.errstate(divide='ignore', invalid='ignore'):
        power_adc = 10 * np.log10(np.power(volt_rms, 2) / 400.) + 30
    power_rf = power_adc + 12
    if not log:
        mediato = dB2Linear(mediato)
    if not adurms:
        return mediato, power_rf
    else:
        return mediato, power_rf, adu_rms


def dircheck(directory="", tile=1):
    # Check directory
    lista = sorted(glob.glob(directory + "/raw_burst_%d_*hdf5" % int(tile)))
    return len(lista)


def findtiles(directory=""):
    tiles = []
    for i in range(16):
        if len(sorted(glob.glob(directory + "/raw_burst_%d_*hdf5" % i))):
            tiles += [i]
    return tiles


def playback(directory="", tile=1, res_bw=100):
    # Check directory
    lista = sorted(glob.glob(directory + "/raw_burst_%d_*hdf5" % int(tile)))

    # Configure Spectra Resolution Parameters
    resolutions = 2 ** np.array(range(16)) * (800000.0 / 2 ** 15)
    rbw = int(closest(resolutions, res_bw))
    print("Frequency resolution set %3.1f KHz" % resolutions[rbw])


def read_data(fmanager=None, hdf5_file="", tile=1, nof_tiles=16):
    dic = fmanager.get_metadata(timestamp=fname_to_tstamp(hdf5_file[-21:-7]), tile_id=(int(tile)))
    if fmanager.file_partitions(timestamp=fname_to_tstamp(hdf5_file[-21:-7]), tile_id=(int(tile))) == 0:
        total_samples = fmanager.n_samples * fmanager.n_blocks
    else:
        total_samples = fmanager.n_samples * fmanager.n_blocks * \
                        (fmanager.file_partitions(timestamp=fname_to_tstamp(hdf5_file[-21:-7]), tile_id=(int(tile))))
    nof_blocks = total_samples
    nof_antennas = fmanager.n_antennas * nof_tiles

    d, t = fmanager.read_data(timestamp=fname_to_tstamp(hdf5_file[-21:-7]),
                              n_samples=total_samples, tile_id=(int(tile)))
    t = int(dic['timestamp'])
    #dtimestamp = ts_to_datestring(t, formato="%Y-%m-%d %H:%M:%S")
    d = d[antenna_mapping, :, :].transpose((0, 1, 2))
    return t, d


def calc_disk_usage(directory=".", pattern="*.hdf5"):
    cmd = "find " + directory + " -type f -name '" + pattern + "' -exec du -ch {} + | grep total"
    try:
        return subprocess.check_output(cmd, shell=True).split()[0].decode("utf-8")
    except:
        return "0 MB"

COLOR = ['b', 'g']
# Define default configuration
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


def dB2Linear(valueIndB):
    """
    Convert input from dB to linear scale.
    Parameters
    ----------
    valueIndB : float | np.ndarray
        Value in dB
    Returns
    -------
    valueInLinear : float | np.ndarray
        Value in Linear scale.
    Examples
    --------
    #>>> dB2Linear(30)
    1000.0
    """
    return pow(10, valueIndB / 10.0)


def linear2dB(valueInLinear):
    """
    Convert input from linear to dB scale.
    Parameters
    ----------
    valueInLinear : float | np.ndarray
        Value in Linear scale.
    Returns
    -------
    valueIndB : float | np.ndarray
        Value in dB scale.
    Examples
    --------
    #>>> linear2dB(1000)
    30.0
    """
    return 10.0 * np.log10(valueInLinear)


def dBm2Linear(valueIndBm):
    """
    Convert input from dBm to linear scale.
    Parameters
    ----------
    valueIndBm : float | np.ndarray
        Value in dBm.
    Returns
    -------
    valueInLinear : float | np.ndarray
        Value in linear scale.
    Examples
    --------
    #>>> dBm2Linear(60)
    1000.0
    """
    return dB2Linear(valueIndBm) / 1000.


def linear2dBm(valueInLinear):
    """
    Convert input from linear to dBm scale.
    Parameters
    ----------
    valueInLinear : float | np.ndarray
        Value in Linear scale
    Returns
    -------
    valueIndBm : float | np.ndarray
        Value in dBm.
    Examples
    --------
    #>>> linear2dBm(1000)
    60.0
    """
    return linear2dB(valueInLinear * 1000.)


def closest(serie, num):
    return serie.tolist().index(min(serie.tolist(), key=lambda z: abs(z - num)))


def calcSpectra(vett):
    window = np.hanning(len(vett))
    spettro = np.fft.rfft(vett * window)
    N = len(spettro)
    acf = 2  # amplitude correction factor
    cplx = ((acf * spettro) / N)
    spettro[:] = abs((acf * spettro) / N)
    # print len(vett), len(spettro), len(np.real(spettro))
    return np.real(spettro)


def calcolaspettro(dati, nsamples=32768):
    n = int(nsamples)  # split and average number, from 128k to 16 of 8k # aavs1 federico
    sp = [dati[x:x + n] for x in range(0, len(dati), n)]
    mediato = np.zeros(len(calcSpectra(sp[0])))
    for k in sp:
        singolo = calcSpectra(k)
        mediato[:] += singolo
    mediato[:] /= (2 ** 15 / nsamples)  # federico
    with np.errstate(divide='ignore', invalid='ignore'):
        mediato[:] = 20 * np.log10(mediato / 127.0)
    d = np.array(dati, dtype=np.float64)
    adu_rms = np.sqrt(np.mean(np.power(d, 2), 0))
    volt_rms = adu_rms * (1.7 / 256.)
    with np.errstate(divide='ignore', invalid='ignore'):
        power_adc = 10 * np.log10(np.power(volt_rms, 2) / 400.) + 30
    power_rf = power_adc + 12
    return mediato, power_rf


def get_if_name(lmc_ip):
    #print("Scan for TPM Network interface...")
    tpm_nic = ""
    interfaces = getnic.interfaces()
    for i in interfaces:
        if 'inet4' in getnic.ipaddr([i])[i].keys():
            if lmc_ip in getnic.ipaddr([i])[i]['inet4']:
                #print("IF: %s, Addr: %s" %(i, getnic.ipaddr([i])[i]['inet4']))
                tpm_nic = i
    return tpm_nic


class MyDaq:
    def __init__(self, mydaq, eth_nic, station, n_of_tiles):
        self.daq = mydaq
        self.nof_tiles = n_of_tiles
        self.daq_config = {
            'receiver_interface': eth_nic,  # CHANGE THIS if required
            'directory': "/storage/daq/tmp/",  # CHANGE THIS if required
            'nof_beam_channels': 384,
            'nof_beam_samples': 42,
            'receiver_frame_size': 9000,
            'nof_tiles': n_of_tiles
        }

        self.station = station

        # Configure the DAQ receiver and start receiving data
        self.daq.populate_configuration(self.daq_config)
        self.daq.initialise_daq()
        self.daq.start_raw_data_consumer(callback=self.data_callback)
        self.data_received = 0
        self.antenna_mapping = [0, 1, 2, 3, 8, 9, 10, 11, 15, 14, 13, 12, 7, 6, 5, 4]

    def data_callback(self, mode, filepath, tile):
        if mode == "burst_raw":
            #raw_file = RawFormatFileManager(root_path=os.path.dirname(filepath))
            #data, timestamps = raw_file.read_data(antennas=range(16),  # List of channels to read (not use in raw case)
            #                                      polarizations=[0, 1],
            #                                      n_samples=32 * 1024)
            #self.data = data
            self.data_received = self.data_received + 1
            #print("RCV Raw data in %s %d  %d %d" % (filepath, tile, self.data_received, self.nof_tiles))

    def execute(self):
        # Start whichever consumer is required and provide callback
        self.data_received = 0
        self.station.send_raw_data()
        while not self.data_received == self.nof_tiles:
            time.sleep(0.1)
        self.get_data()
        return self.data

    def get_data(self):
        self.data = []
        for i in range(self.nof_tiles):
            raw_file = RawFormatFileManager(root_path=self.daq_config['directory'], daq_mode=FileDAQModes.Burst)
            data, timestamps = raw_file.read_data(tile_id=i, antennas=range(16), polarizations=[0, 1], n_samples=32 * 1024)
            self.data += [data[self.antenna_mapping, :, :].transpose((0, 1, 2))]
            #print("LEN DATA: %d" % len(data))
            #print("LEN GLOBAL: %d" % len(self.data))


    def close(self):
        self.daq.stop_daq()



class BarCanvas(FigureCanvas):
    def __init__(self, dpi=100, size=(11, 5.3), xticks=[0, 1, 2, 3, 4, 5, 6, 7, 8],
                 yticks=[0, 2, 4, 6, 8, 10], xlim=[0, 10], ylim=[0, 40], xlabel="x", ylabel="y"):
        self.dpi = dpi
        self.fig = Figure(size, dpi=self.dpi)#, facecolor='white')
        self.fig.set_tight_layout(True)
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.ax.tick_params(axis='both', which='both', labelsize=8)
        self.ax.set_ylim(ylim)
        self.ax.set_xlim(xlim)
        self.ax.set_xticks(np.arange(1, len(xticks)))
        self.ax.set_xticklabels(xticks[1:])
        self.ax.set_yticks(yticks)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.grid()

        FigureCanvas.__init__(self, self.fig)
        FigureCanvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)


class BarPlot(QtWidgets.QWidget):
    """ Class encapsulating a matplotlib plot"""
    def __init__(self, parent=None, size=(11, 5.3), xlabel="TPM", ylabel="Volt", xlim=[0, 10], ylim=[0, 9],
                 xticks=[0, 1, 2, 3, 4, 5, 6, 7], yticks=[0, 2, 4, 6, 8, 10], xrotation=0):
        QtWidgets.QWidget.__init__(self, parent)
        """ Class initialiser """
        self.canvas = BarCanvas(dpi=100, size=size, xticks=xticks, yticks=yticks,
                                xlim=xlim, ylim=ylim, ylabel=ylabel, xlabel=xlabel)  # create canvas that will hold our plot
        self.updateGeometry()
        self.vbl = QtWidgets.QVBoxLayout()
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)
        self.xrotation = xrotation
        self.show()
        self.bars = self.canvas.ax.bar(np.arange(xlim[-1]-1) + 1, np.zeros(xlim[-1]-1), 0.8, color='b')

    def set_xlabel(self, label):
        self.canvas.ax.set_xlabel(label)

    def set_xticklabels(self, labels):
        self.canvas.ax.set_xlim([0, len(labels) + 1])
        self.canvas.ax.set_xticks(np.arange(1, len(labels) + 1))
        self.canvas.ax.set_xticklabels(labels)
        self.updatePlot()

    def plotBar(self, data, bar, color):
        """ Plot the data as Bars"""
        self.bars[bar].set_height(data)
        self.bars[bar].set_color(color)

    def plotAxBars(self, ydata, xdata):
        """ Plot the data as Bars"""
        if len(ydata) != 0:
            for n, y in enumerate(ydata):
                self.bars[n].set_height(y)
            self.canvas.ax.set_xticklabels(xdata, rotation=self.xrotation)
            self.updatePlot()

    def updatePlot(self):
        self.canvas.draw()
        self.show()

    def plotClear(self):
        # Reset the plot landscape
        self.canvas.ax.clear()
        self.updatePlot()


class ChartCanvas(FigureCanvas):
    def __init__(self, parent=None, ntraces=1, dpi=100, xlabel="samples", ylabel="Temperature",
                 xlim=[0, 10], ylim=[-80, -20], size=(11.5, 6.8)):
        self.dpi = dpi
        self.fig = Figure(size, dpi=self.dpi, facecolor='white')
        self.fig.set_tight_layout(True)
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.ax.xaxis.set_label_text(xlabel, fontsize=10)
        self.ax.yaxis.set_label_text(ylabel, fontsize=10)
        self.ax.tick_params(axis='both', which='minor', labelsize=8)
        self.ax.tick_params(axis='both', which='both', labelsize=8)
        self.ax.set_ylim(ylim)
        self.ax.set_xlim(xlim)
        self.ax.grid()
        punti = range(xlim[1] + 1)
        self.lines = []
        for t in range(ntraces):
            line, = self.ax.plot(punti, np.zeros(len(punti)) * np.nan)
            self.lines += [line]
        FigureCanvas.__init__(self, self.fig)
        FigureCanvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)


class ChartPlots(QtWidgets.QWidget):
    """ Class encapsulating a matplotlib plot"""
    def __init__(self, parent=None, ntraces=1, dpi=100, xlabel="MHz", ylabel="dB", xlim=[0, 200],
                 ylim=[0, 140], size=(11.5, 6.8)):
        QtWidgets.QWidget.__init__(self, parent)
        """ Class initialiser """
        self.canvas = ChartCanvas(parent=parent, ntraces=ntraces, dpi=dpi, xlabel=xlabel,
                                 ylabel=ylabel, xlim=xlim, ylim=ylim, size=size)
        self.updateGeometry()
        self.vbl = QtWidgets.QVBoxLayout()
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)
        self.show()
        self.canvas_elements = {}
        self.ylim = ylim
        self.ntraces = ntraces
        #self.plots = [self.canvas_elements.copy() for _ in range(self.nplot)]
        self.titlesize = 10

    # def showPlots(self, visu):
    #     for i in range(self.nplot):
    #         self.canvas.ax[i].set_visible(visu)
    #     self.canvas.draw()
    #
    def plotCurve(self, data, trace, color):
        self.canvas.lines[trace].set_ydata(data)
        self.canvas.lines[trace].set_color(color)

    def showGrid(self, show_grid=True):
        self.canvas.ax.grid(show_grid)
        self.canvas.draw()

    def set_ylabel(self, ylabel):
        self.canvas.ax.yaxis.set_label_text(ylabel, fontsize=10)

    def set_xlabel(self, xlabel):
        self.canvas.ax.xaxis.set_label_text(xlabel, fontsize=10)

    def set_ylim(self, ylim):
        self.canvas.ax.set_ylim(ylim)

    # def set_x_limits(self, xAxisRange):
    #     for i in range(self.nplot):
    #         self.canvas.ax[i].set_xlim(xAxisRange)
    #     self.canvas.draw()
    #     #self.show()
    #
    # def set_y_limits(self, yAxisRange):
    #     for n in range(self.nplot):
    #         self.canvas.ax[n].set_ylim(yAxisRange)
    #         self.plots[n]['yAxisRange'] = yAxisRange
    #     self.canvas.draw()

    # def hide_line(self, colore, visu=True):
    #     for n in range(self.nplot):
    #         if colore + 'line' in self.plots[n].keys():
    #             self.plots[n][colore + 'line'].set_visible(visu)
    #         if colore + 'rms' in self.plots[n].keys():
    #             self.plots[n][colore + 'rms'].set_visible(visu)
    #         self.plots[n][colore + 'show_rms'] = visu
    #     self.canvas.draw()
    #
    # def hide_annotation(self, pols=['b', 'g'], visu=True):
    #     for p in pols:
    #         for n in range(self.nplot):
    #             if p + 'rms' in self.plots[n].keys():
    #                 self.plots[n][p + 'rms'].set_visible(visu)
    #             self.plots[n][p + 'show_rms'] = visu
    #     self.canvas.draw()

    def updatePlot(self):
        self.canvas.draw()
        self.show()

    def plotClear(self):
        # Reset the plot landscape
        self.canvas.ax.clear()
