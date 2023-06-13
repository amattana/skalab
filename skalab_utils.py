import glob
import datetime
import subprocess
import calendar
import time

import h5py
import numpy as np
import configparser
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtWidgets import QWidget, QStyleOption
from PyQt5.QtGui import QPainter
import sys
sys.path.append("../../pyaavs/tests/")
from pydaq.persisters import *
from get_nic import getnic
from colorsys import rgb_to_hls, hls_to_rgb
from PyQt5.QtWidgets import QWidget, QStyleOption
from PyQt5.QtGui import QPainter
from PyQt5.QtCore import pyqtSignal, QSize, QByteArray, QRectF, pyqtProperty
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QWidget

COLORI = ["b", "g", "k", "r", "orange", "magenta", "darkgrey", "turquoise"] * 4


def parse_profile(config=""):
    confparser = configparser.ConfigParser()
    confparser.read(config)
    return confparser


def dt_to_timestamp(d):
    return calendar.timegm(d.timetuple())


def ts_to_datestring(tstamp, formato="%Y-%m-%d %H:%M:%S UTC"):
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


def getTextFromFile(fname):
    if os.path.exists(fname):
        with open(fname) as f:
            text = f.read()
        return text



class Led(QWidget):
    
    Circle   = 1
    Red    = 1
    Green  = 2
    Orange = 3
    Grey   = 4

    shapes={
        Circle:"""
            <svg height="50.000000px" id="svg9493" width="50.000000px" xmlns="http://www.w3.org/2000/svg">
              <defs id="defs9495">
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient6650" x1="23.402565" x2="23.389874" xlink:href="#linearGradient6506" y1="44.066776" y2="42.883698"/>
                <linearGradient id="linearGradient6494">
                  <stop id="stop6496" offset="0.0000000" style="stop-color:%s;stop-opacity:1.0000000;"/>              
                  <stop id="stop6498" offset="1.0000000" style="stop-color:%s;stop-opacity:1.0000000;"/>
                </linearGradient>
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient6648" x1="23.213980" x2="23.201290" xlink:href="#linearGradient6494" y1="42.754631" y2="43.892632"/>
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient6646" x1="23.349695" x2="23.440580" xlink:href="#linearGradient5756" y1="42.767944" y2="43.710873"/>
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient6644" x1="23.193102" x2="23.200001" xlink:href="#linearGradient5742" y1="42.429230" y2="44.000000"/>
                <linearGradient id="linearGradient6506">
                  <stop id="stop6508" offset="0.0000000" style="stop-color:#ffffff;stop-opacity:0.0000000;"/>
                  <stop id="stop6510" offset="1.0000000" style="stop-color:#ffffff;stop-opacity:0.87450981;"/>
                </linearGradient>
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient7498" x1="23.402565" x2="23.389874" xlink:href="#linearGradient6506" y1="44.066776" y2="42.883698"/>
                <linearGradient id="linearGradient7464">
                  <stop id="stop7466" offset="0.0000000" style="stop-color:#00039a;stop-opacity:1.0000000;"/>
                  <stop id="stop7468" offset="1.0000000" style="stop-color:#afa5ff;stop-opacity:1.0000000;"/>
                </linearGradient>
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient7496" x1="23.213980" x2="23.201290" xlink:href="#linearGradient7464" y1="42.754631" y2="43.892632"/>
                <linearGradient id="linearGradient5756">
                  <stop id="stop5758" offset="0.0000000" style="stop-color:#828282;stop-opacity:1.0000000;"/>
                  <stop id="stop5760" offset="1.0000000" style="stop-color:#929292;stop-opacity:0.35294119;"/>
                </linearGradient>
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient9321" x1="22.935030" x2="23.662106" xlink:href="#linearGradient5756" y1="42.699776" y2="43.892632"/>
                <linearGradient id="linearGradient5742">
                  <stop id="stop5744" offset="0.0000000" style="stop-color:#adadad;stop-opacity:1.0000000;"/>
                  <stop id="stop5746" offset="1.0000000" style="stop-color:#f0f0f0;stop-opacity:1.0000000;"/>
                </linearGradient>
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient7492" x1="23.193102" x2="23.200001" xlink:href="#linearGradient5742" y1="42.429230" y2="44.000000"/>
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient9527" x1="23.193102" x2="23.200001" xlink:href="#linearGradient5742" y1="42.429230" y2="44.000000"/>
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient9529" x1="22.935030" x2="23.662106" xlink:href="#linearGradient5756" y1="42.699776" y2="43.892632"/>
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient9531" x1="23.213980" x2="23.201290" xlink:href="#linearGradient7464" y1="42.754631" y2="43.892632"/>
                <linearGradient gradientUnits="userSpaceOnUse" id="linearGradient9533" x1="23.402565" x2="23.389874" xlink:href="#linearGradient6506" y1="44.066776" y2="42.883698"/>
              </defs>
              <g id="layer1">
                <g id="g9447" style="overflow:visible" transform="matrix(31.25000,0.000000,0.000000,31.25000,-625.0232,-1325.000)">
                  <path d="M 24.000001,43.200001 C 24.000001,43.641601 23.641601,44.000001 23.200001,44.000001 C 22.758401,44.000001 22.400001,43.641601 22.400001,43.200001 C 22.400001,42.758401 22.758401,42.400001 23.200001,42.400001 C 23.641601,42.400001 24.000001,42.758401 24.000001,43.200001 z " id="path6596" style="fill:url(#linearGradient6644);fill-opacity:1.0000000;stroke:Fill;stroke-width:0.00000001;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:4.0000000;stroke-opacity:0.0000000;overflow:visible" transform="translate(-2.399258,-1.000000e-6)"/>
                  <path d="M 23.906358,43.296204 C 23.906358,43.625433 23.639158,43.892633 23.309929,43.892633 C 22.980700,43.892633 22.713500,43.625433 22.713500,43.296204 C 22.713500,42.966975 22.980700,42.699774 23.309929,42.699774 C 23.639158,42.699774 23.906358,42.966975 23.906358,43.296204 z " id="path6598" style="fill:url(#linearGradient6646);fill-opacity:1.0000000;stroke:Fill;stroke-width:0.80000001;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:4.0000000;stroke-opacity:0.0000000;overflow:visible" transform="matrix(1.082474,0.000000,0.000000,1.082474,-4.431649,-3.667015)"/>
                  <path d="M 23.906358,43.296204 C 23.906358,43.625433 23.639158,43.892633 23.309929,43.892633 C 22.980700,43.892633 22.713500,43.625433 22.713500,43.296204 C 22.713500,42.966975 22.980700,42.699774 23.309929,42.699774 C 23.639158,42.699774 23.906358,42.966975 23.906358,43.296204 z " id="path6600" style="fill:url(#linearGradient6648);fill-opacity:1.0000000;stroke:Fill;stroke-width:0.80000001;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:4.0000000;stroke-opacity:0.0000000;overflow:visible" transform="matrix(0.969072,0.000000,0.000000,0.969072,-1.788256,1.242861)"/>
                  <path d="M 23.906358,43.296204 C 23.906358,43.625433 23.639158,43.892633 23.309929,43.892633 C 22.980700,43.892633 22.713500,43.625433 22.713500,43.296204 C 22.713500,42.966975 22.980700,42.699774 23.309929,42.699774 C 23.639158,42.699774 23.906358,42.966975 23.906358,43.296204 z " id="path6602" style="fill:url(#linearGradient6650);fill-opacity:1.0000000;stroke:Fill;stroke-width:0.80000001;visibility: hidden;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:4.0000000;stroke-opacity:0.0000000;overflow:visible" transform="matrix(0.773196,0.000000,0.000000,0.597938,2.776856,17.11876)"/>
                </g>
              </g>
            </svg>
        """}
    
    colours={Red: (0xCF, 0x00, 0x00), 
            Green  : (0x0f, 0x69, 0x00), 
            Orange : (0xe2, 0x76, 0x02), 
            Grey   : (0x7a, 0x7a, 0x7a)}

    def __init__(self, parent=None, **kwargs):
        self.m_value=False
        self.m_Colour=Led.Grey
        self.m_shape=Led.Circle

        QWidget.__init__(self, parent, **kwargs)
        self.renderer=QSvgRenderer()

    def Colour(self): return self.m_Colour
    def setColour(self, newColour):
        self.m_Colour=newColour
        self.update()    
    Colour=pyqtProperty(int, Colour, setColour)

    def value(self): return self.m_value
    def setValue(self, value):
        self.m_value=value
        self.update()    
    value=pyqtProperty(bool, value, setValue)

    def sizeHint(self): 
        return QSize(48,48)

    def adjust(self, r, g, b):
        def normalise(x): return x/255.0
        def denormalise(x): return int(x*255.0)
        (h,l,s)=rgb_to_hls(normalise(r),normalise(g),normalise(b))        
        (nr,ng,nb)=hls_to_rgb(h,l*1.5,s)
        return (denormalise(nr),denormalise(ng),denormalise(nb))

    def paintEvent(self, event):
        option=QStyleOption()
        option.initFrom(self)

        h=option.rect.height()
        w=option.rect.width()
        size=min(w,h)
        x=abs(size-w)/2.0
        y=abs(size-h)/2.0
        bounds=QRectF(x,y,size,size)
        painter=QPainter(self);
        painter.setRenderHint(QPainter.Antialiasing, True)

        (dark_r,dark_g,dark_b)=self.colours[self.m_Colour]
        dark_str="rgb(%d,%d,%d)" % (dark_r,dark_g,dark_b)
        light_str="rgb(%d,%d,%d)" % self.adjust(dark_r,dark_g,dark_b)

        __xml=(self.shapes[self.m_shape]%(dark_str,dark_str)).encode('utf8')
        self.renderer.load(QByteArray(__xml))
        self.renderer.render(painter, bounds)




class MiniCanvas(FigureCanvas):
    def __init__(self, nplot, parent=None, dpi=100, xlabel="MHz", ylabel="dB",
                 xlim=[0, 400], ylim=[-80, -20], size=(11.5, 6.7)):
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
        from_scratch = True
        if len(data) != 0:
            if (colore + 'line') in self.plots[int(ant)].keys():
                if len(self.plots[int(ant)][colore + 'line'].get_ydata()) == len(data):
                    self.plots[int(ant)][colore + 'line'].set_data(assex, data)
                    self.plots[int(ant)][colore + 'line'].set_visible(show_line)
                    self.plots[int(ant)][colore + 'line'].set_lw(lw)
                    self.plots[int(ant)][colore + 'line'].set_markersize(markersize)
                    self.plots[int(ant)][colore + 'line'].set_marker(".")
                    self.plots[int(ant)][colore + 'line'].set_color(colore)
                    from_scratch = False
            if from_scratch:
                line, = self.canvas.ax[int(ant)].plot(assex, data, color=colore, lw=lw, markersize=markersize, marker=".")
                self.plots[int(ant)][colore + 'line'] = line
                self.plots[int(ant)][colore + 'line'].set_visible(show_line)
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
            if xAxisRange is not None:
                self.canvas.ax[ant].set_xlim(xAxisRange)
            if yAxisRange is not None:
                self.canvas.ax[ant].set_ylim(yAxisRange)
            if not title == "":
                self.canvas.ax[ant].set_title(title, fontsize=titlesize)
            if not xLabel == "":
                self.canvas.ax[ant].set_xlabel(xLabel, fontsize=titlesize)
            if not yLabel == "":
                self.canvas.ax[ant].set_ylabel(yLabel, fontsize=titlesize)
            if grid:
                self.canvas.ax[ant].grid(grid)
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
                  titlesize=10, grid=False, show_line=True, lw=1, xdatetime=False):
        """ Plot the data as a curve"""
        self.titlesize = titlesize
        if len(data) != 0:
            line, = self.canvas.ax[int(ant)].plot(assex, data, color=colore, lw=lw, markersize=1, marker=".")
            self.plots[int(ant)][colore + 'line'] = line
            self.plots[int(ant)][colore + 'line'].set_visible(show_line)
            if not xAxisRange == None:
                if not xdatetime:
                    if xAxisRange[0] == xAxisRange[1]:
                        self.canvas.ax[ant].set_xlim(xAxisRange[0] - 1, xAxisRange[0] + 1)
                    else:
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
            if xdatetime:
                t_start = int(assex[0])
                t_stop = int(assex[-1])
                if t_start == t_stop:
                    t_start = t_start - 1
                    t_stop = t_stop + 1
                self.canvas.ax[ant].set_xlim(t_start, t_stop)
                delta = assex[-1] - assex[0]
                if delta < 3600 * 24:
                    delta_h = int((t_stop - t_start) / 60)
                    x = np.array(range(t_stop - t_start + 100)) + t_start

                    xticks = np.array(range(delta_h)) * 60 + t_start
                    xticklabels = []
                    for n, f in enumerate((np.array(range(delta_h)) + datetime.datetime.utcfromtimestamp(t_start).minute)):
                        xticklabels += [datetime.datetime.strftime(datetime.datetime.utcfromtimestamp(t_start) +
                                                                   datetime.timedelta(minutes=int(f)), "%H:%M")]
                else:
                    delta_h = int((t_stop - t_start) / 3600)
                    x = np.array(range(t_stop - t_start + 100)) + t_start

                    xticks = np.array(range(delta_h)) * 3600 + t_start
                    xticklabels = [f if f != 0 else datetime.datetime.strftime(
                        datetime.datetime.utcfromtimestamp(t_start) + datetime.timedelta(
                            (datetime.datetime.utcfromtimestamp(t_start).hour + n) / 24), "%Y-%m-%d") for n, f in
                                   enumerate((np.array(range(delta_h)) + datetime.datetime.utcfromtimestamp(
                                       t_start).hour) % 24)]

                self.canvas.ax[int(ant)].set_xticks(xticks[int(len(xticks) / 7 / 2)::int(len(xticks) / 7)])
                self.canvas.ax[int(ant)].set_xticklabels(
                    xticklabels[int(len(xticklabels) / 7 / 2)::int(len(xticklabels) / 7)], rotation=90, fontsize=8)

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
        self.canvas.flush_events()
        self.show()

    def savePicture(self, fname=""):
        if not fname == "":
            self.canvas.print_figure(fname)

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
            time.sleep(60)
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


def calcolaspettro(dati, nsamples=32768, log=True):
    n = int(nsamples)  # split and average number, from 128k to 16 of 8k # aavs1 federico
    sp = [dati[x:x + n] for x in range(0, len(dati), n)]
    mediato = np.zeros(len(calcSpectra(sp[0])))
    for k in sp:
        singolo = calcSpectra(k)
        mediato[:] += singolo
    mediato[:] /= (2 ** 15 / nsamples)  # federico
    with np.errstate(divide='ignore', invalid='ignore'):
        mediato[:] = 20 * np.log10(mediato / 127.0)
    d = np.array(dati, dtype=np.int64)
    with np.errstate(divide='ignore', invalid='ignore'):
        adu_rms = np.sqrt(np.mean(np.power(d, 2), 0))
    if adu_rms == np.nan:
        adu_rms = 0
    volt_rms = adu_rms * (1.7 / 256.)
    with np.errstate(divide='ignore', invalid='ignore'):
        power_adc = 10 * np.log10(np.power(volt_rms, 2) / 400.) + 30
    power_rf = power_adc + 12
    if not log:
        mediato = dB2Linear(mediato)
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
        #print(cmd)
        l = subprocess.check_output(cmd, shell=True).decode("utf-8").split()
        # print(l)
        # total = 0
        # unit = 'MB'
        # for r in l:
        #     if not 'total' in r:
        #         val = float(r.replace(",", ".")[:-1])
        #         if 'G' in r:
        #             val = val * 1024
        #         total = total + val
        # if len(str(total)) > 3:
        #     total = total / 1000.
        #     unit = 'GB'
        return "%d%s" % (float(l[0].replace(",", ".")[:-1]), l[0][-1])
    except:
        return "0 MB"

COLOR = ['b', 'g'] * 16


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


def decodeChannelList(stringa="1-16"):
    new_list = []
    for i in stringa.split(","):
        if "-" in i:
            for a in range(int(i.split("-")[0]), int(i.split("-")[1]) + 1):
                new_list += [a]
        else:
            new_list += [int(i)]
    return new_list


# def calcolaspettro(dati, nsamples=32768):
#     n = int(nsamples)  # split and average number, from 128k to 16 of 8k # aavs1 federico
#     sp = [dati[x:x + n] for x in range(0, len(dati), n)]
#     mediato = np.zeros(len(calcSpectra(sp[0])))
#     for k in sp:
#         singolo = calcSpectra(k)
#         mediato[:] += singolo
#     mediato[:] /= (2 ** 15 / nsamples)  # federico
#     with np.errstate(divide='ignore', invalid='ignore'):
#         mediato[:] = 20 * np.log10(mediato / 127.0)
#     d = np.array(dati, dtype=np.float64)
#     adu_rms = np.sqrt(np.mean(np.power(d, 2), 0))
#     volt_rms = adu_rms * (1.7 / 256.)
#     with np.errstate(divide='ignore', invalid='ignore'):
#         power_adc = 10 * np.log10(np.power(volt_rms, 2) / 400.) + 30
#     power_rf = power_adc + 12
#     return mediato, power_rf


def get_if_name(lmc_ip):
    #print("Scan for TPM Network interface...")
    tpm_nic = ""
    interfaces = os.listdir('/sys/class/net/') # getnic.interfaces() replaced!
    for i in interfaces:
        if 'inet4' in getnic.ipaddr([i])[i].keys():
            if lmc_ip in getnic.ipaddr([i])[i]['inet4']:
                #print("IF: %s, Addr: %s" %(i, getnic.ipaddr([i])[i]['inet4']))
                tpm_nic = i
    return tpm_nic


class MyDaq:
    def __init__(self, mydaq, eth_nic, station, n_of_tiles, directory="/storage/daq/tmp/"):
        self.daq = mydaq
        self.nof_tiles = n_of_tiles
        self.daq_config = {
            'receiver_interface': eth_nic,  # CHANGE THIS if required
            'directory': directory,  # CHANGE THIS if required
            'nof_tiles': n_of_tiles,
            'nof_beam_channels': 384,
            'nof_beam_samples': 42,
            'receiver_frame_size': 9000
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
        #print("Send Raw Data Request...")
        if self.station.tiles[0].tpm_version() == "tpm_v1_2":
            self.station.send_raw_data()
        else:
            for i in range(self.nof_tiles):
                self.station.tiles[i].send_raw_data(seconds=0.2)
            #self.station.send_raw_data()
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
            #print("TILE-%02d, INPUT CHANNEL LEN DATA: %d" % (i, len(data)))
            #print("TILE-%02d, GLOBAL LEN: %d" % (i, len(self.data)))

    def close(self):
        self.daq.stop_daq()


class BarCanvas(FigureCanvas):
    def __init__(self, dpi=100, size=(11, 5.3), xticks=[0, 1, 2, 3, 4, 5, 6, 7, 8], xrotation=0, fsize=8,
                 yticks=[0, 2, 4, 6, 8, 10], xlim=[0, 10], ylim=[0, 40], xlabel="x", ylabel="y", labelpad=10):
        self.dpi = dpi
        self.fig = Figure(size, dpi=self.dpi)#, facecolor='white')
        #self.fig = Figure(dpi=self.dpi)#, facecolor='white')
        self.fig.set_tight_layout(True)
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.ax.tick_params(axis='both', which='both', labelsize=fsize)
        self.ax.set_ylim(ylim)
        self.ax.set_xlim(xlim)
        self.ax.set_xticks(np.arange(1, len(xticks)))
        self.ax.set_xticklabels(xticks[1:], rotation=xrotation, fontsize=fsize)
        self.ax.set_yticks(yticks)
        self.ax.set_xlabel(xlabel, labelpad=labelpad)
        self.ax.set_ylabel(ylabel)
        self.ax.grid()

        FigureCanvas.__init__(self, self.fig)
        FigureCanvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)


class BarPlot(QtWidgets.QWidget):
    """ Class encapsulating a matplotlib plot"""
    def __init__(self, parent=None, size=(11, 5.3), xlabel="TPM", ylabel="Volt", xlim=[0, 10], ylim=[0, 9], fsize=8,
                 xticks=[0, 1, 2, 3, 4, 5, 6, 7], yticks=[0, 2, 4, 6, 8, 10], xrotation=0, markersize=6, labelpad=10):
        QtWidgets.QWidget.__init__(self, parent)
        self.xrotation = xrotation
        """ Class initialiser """
        self.canvas = BarCanvas(dpi=100, size=size, xticks=xticks, yticks=yticks, xrotation=self.xrotation, fsize=fsize,
                                xlim=xlim, ylim=ylim, ylabel=ylabel, xlabel=xlabel, labelpad=labelpad)  # create canvas that will hold our plot
        self.updateGeometry()
        self.vbl = QtWidgets.QVBoxLayout()
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)
        self.show()
        self.bars = self.canvas.ax.bar(np.arange(xlim[-1]-1) + 1, np.zeros(xlim[-1]-1), 0.8, color='b')
        self.markersize = markersize
        self.markers = []
        for pol in range(2):
            markers, = self.canvas.ax.plot(np.arange(0, xlim[-1]-1, 2) + 1 + pol, np.zeros(int((xlim[-1]-1)/2)),
                                           linestyle='None', marker="s", markersize=self.markersize)
            markers.set_visible(False)
            self.markers += [markers]

    def reinit(self, nbar=8):
        del self.bars
        self.bars = self.canvas.ax.bar(np.arange(8 * (((nbar - 1) // 8) + 1)) + 1, np.zeros(8 * (((nbar - 1) // 8) + 1)),
                                       (0.8 / (((nbar - 1) // 8) + 1)), color='b')
        del self.markers
        self.markers = []
        if nbar > 1:
            if nbar % 2:
                nbar = nbar + 1
            for pol in range(2):
                markers, = self.canvas.ax.plot(np.arange(0, nbar, 2) + 1 + pol, np.zeros(int(nbar/2)),
                                               linestyle='None', marker="s", markersize=self.markersize)
                markers.set_visible(False)
                self.markers += [markers]
        else:
            markers, = self.canvas.ax.plot(np.arange(nbar) + 1, np.zeros(nbar), linestyle='None', marker="s",
                                           markersize=self.markersize)
            markers.set_visible(False)
            self.markers += [markers]
        self.canvas.ax.set_xlim([0, nbar])
        self.updatePlot()

    def showMarkers(self):
        for pol in range(2):
            self.markers[pol].set_visible(True)

    def showBars(self):
        for b in self.bars:
            b.set_visible(True)

    def hideMarkers(self):
        for pol in range(2):
            self.markers[pol].set_visible(False)

    def hideBars(self):
        for b in self.bars:
            b.set_visible(False)

    def setTitle(self, title):
        self.canvas.ax.set_title(title)

    def set_xlabel(self, label, labelpad=10):
        self.canvas.ax.set_xlabel(label, labelpad=labelpad)

    def set_ylabel(self, label):
        self.canvas.ax.set_ylabel(label)

    def set_ylim(self, ylim):
        self.canvas.ax.set_ylim(ylim)

    def set_xticklabels(self, labels):
        self.canvas.ax.set_xlim([0, len(labels) + 1])
        self.canvas.ax.set_xticks(np.arange(1, len(labels) + 1))
        self.canvas.ax.set_xticklabels(labels)
        self.updatePlot()

    def set_yticks(self, yticks):
        self.canvas.ax.set_ylim([yticks[0], yticks[-1]])
        self.canvas.ax.set_yticks(yticks)
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

    def savePicture(self, fname=""):
        if not fname == "":
            self.canvas.print_figure(fname)

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
        #self.show()

    def savePicture(self, fname=""):
        if not fname == "":
            self.canvas.print_figure(fname)

    def plotClear(self):
        # Reset the plot landscape
        self.canvas.ax.clear()


class Archive:
    def __init__(self, hfile, mode='a'):
        self.hfile = h5py.File(hfile, mode)
        self.open = True

    def keys(self):
        return self.hfile.keys()

    def len(self, name, field=-1):
        if name in self.keys():
            if field == -1:
                return len(self.hfile[name])
            else:
                if field < self.hfile[name].shape[1]:
                    return len(self.read(name, field))
                else:
                    return -1
        else:
            return None

    def write(self, name, data):
        if type(data) is not list:
            if name not in self.hfile.keys():
                self.hfile.create_dataset(name, data=[[data]], chunks=True, maxshape=(None, 1))
            else:
                self.hfile[name].resize(self.hfile[name].shape[0] + 1, axis=0)
                self.hfile[name][-1] = [data]
        else:
            if name not in self.hfile.keys():
                self.hfile.create_dataset(name, data=[data], chunks=True,  maxshape=(None, len(data)))
            else:
                self.hfile[name].resize((self.hfile[name].shape[0] + np.array([data]).shape[0]), axis=0)
                self.hfile[name][-np.array([data]).shape[0]:] = np.array([data])

    def read(self, name, field=0):
        if self.hfile[name].shape[1] == 1:
            return self.hfile[name][:].reshape(len(self.hfile[name][:])).tolist()
        else:
            return self.hfile[name][:].transpose()[field].tolist()

    def close(self):
        self.hfile.close()
        self.open = False


class MapCanvas(FigureCanvas):
    def __init__(self, parent=None, dpi=80, size=(9.8, 9.8)):
        self.dpi = dpi
        self.fig = Figure(size, dpi=self.dpi, facecolor='white')
        self.fig.set_tight_layout(True)
        self.ax = self.fig.add_subplot(1, 1, 1)
        #self.ax.set_facecolor('white')
        self.ax.axis([-20, 20, -20, 20])
        self.ax.set_xlabel("West-East (m)", fontsize=14)
        self.ax.set_ylabel("South-North (m)", fontsize=14)
        self.circle1 = plt.Circle((0, 0), 38.5/2, color='tan', linewidth=1.5)  # , fill=False)
        self.ax.add_artist(self.circle1)
        # self.circle1 = plt.Circle((0, 0), 38.1/2, color='w', linewidth=1.5)  # , fill=False)
        # self.ax.add_artist(self.circle1)
        # self.ax.grid()

        FigureCanvas.__init__(self, self.fig)
        FigureCanvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)


class MapPlot(QtWidgets.QWidget):

    def __init__(self, parent=None, ant=None, mask=None):
        QtWidgets.QWidget.__init__(self, parent)
        if mask is None:
            mask = []
        if ant is None:
            ant = []
        self.canvas = MapCanvas()  # create canvas that will hold our plot
        self.updateGeometry()
        self.vbl = QtWidgets.QVBoxLayout()
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)
        self.show()
        self.tiles = [int(a['tile']) for a in ant]
        self.x = [float(str(a['East']).replace(",", ".")) for a in ant]
        self.y = [float(str(a['North']).replace(",", ".")) for a in ant]
        self.ids = [int(str(a['id'])) for a in ant]
        self.mask = mask
        self.circle = []
        self.cross = []
        self.names = []
        self.locate = []
        self.located = []

    def plotMap(self):
        if len(self.x):
            for i, ant in enumerate(self.ids):
                circle = [self.canvas.ax.plot(self.x[i], self.y[i], marker='o', markersize=22,
                                                     linestyle='None', color='k')[0],
                                 self.canvas.ax.plot(self.x[i], self.y[i], marker='o', markersize=20,
                                                     linestyle='None', color='wheat')[0],
                                 self.canvas.ax.plot(self.x[i], self.y[i], marker='o', markersize=20,
                                                     linestyle='None', color='w')[0]]
                locate = self.canvas.ax.plot(self.x[i], self.y[i], marker='o', markersize=20,
                                                     linestyle='None', color='y')[0]
                for c in circle:
                    c.set(visible=False)
                self.circle += [circle]
                self.cross += [
                    self.canvas.ax.plot(self.x[i], self.y[i], marker='+', markersize=24, mew=2, linestyle='None',
                                        color='#636363')[0]]
                self.cross[-1].set(visible=False)
                self.locate += [locate]
                self.locate[-1].set(visible=False)
                self.names += [self.canvas.ax.text(self.x[i] + 0.1, self.y[i] + 0.3, ("%d" % ant), fontsize=10)]
                self.names[-1].set(visible=False)
            self.updatePlot()

    def showCross(self, flag=True):
        for i, cross in enumerate(self.cross):
            if self.tiles[i] in self.mask:
                cross.set(visible=flag)
            else:
                cross.set(visible=False)

    def showCircle(self, flag=True):
        for i, circle in enumerate(self.circle):
            if self.tiles[i] in self.mask:
                for c in circle:
                    c.set(visible=flag)
            else:
                for c in circle:
                    c.set(visible=False)

    def highlightClear(self):
        if len(self.located):
            for l in self.located:
                self.locate[l].set(visible=False)
            self.located = []
            self.updatePlot()

    def highlightAntenna(self, antId=None, color='b'):
        if len(antId):
            for a in antId:
                mapId = self.ids.index(a)
                self.locate[mapId].set(visible=True)
                self.locate[mapId].set(color=color)
                self.located += [mapId]
            self.updatePlot()

    def printId(self, flag=True):
        for i, ant_id in enumerate(self.names):
            if self.tiles[i] in self.mask:
                ant_id.set(visible=flag)
            else:
                ant_id.set(visible=False)

    def updatePlot(self):
        self.canvas.draw()
        self.show()

    def oPlot(self, x, y, marker='8', markersize=8, color='b'):
        self.canvas.ax.plot(x, y, marker=marker, markersize=markersize, linestyle='None', color=color)
        self.updatePlot()

    def plotClear(self):
        # Reset the plot landscape
        self.canvas.ax.clear()
        self.canvas.ax.axis([-20, 20, -20, 20])
        self.canvas.ax.set_xlabel("West-East (m)", fontsize=14)
        self.canvas.ax.set_ylabel("South-North (m)", fontsize=14)
        self.canvas.ax.axis([-20, 20, -20, 20])
        circle1 = plt.Circle((0, 0), 38.5/2, color='tan', linewidth=1.5)  # , fill=False)
        self.canvas.ax.add_artist(circle1)
        self.updatePlot()

