import sys
sys.path.append("../")
import os.path
import time
from tqdm import tqdm
from matplotlib import pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
from pyaavs.station import Station
from pyaavs import station
import datetime
from skalab_utils import MyDaq, get_if_name, closest, calcolaspettro, linear2dB
import pydaq.daq_receiver as daq
from skalab_preadu import *

def bound(value, low=0, high=31):
    '''
        Bound the PreADU DSA values between 0 and 31
    '''
    return max(low, min(high, value))

def read_routing_table(map_file):
    mappa = []
    f_map = open(map_file)
    input_list = f_map.readlines()
    for i in input_list:
        if not'#' in i[:2] and not " " in i[0]:
            if len(i.split(",")) > 2:
                mappa += [i.split(",")]
    f_map.close()
    return mappa


def raw2pow(raw_data, tile=0, chan=0, res=1000, startfreq=160, stopfreq=160):
    resolutions = 2 ** np.array(range(16)) * (800000.0 / 2 ** 15)
    rbw = int(closest(resolutions, res))
    avg = 2 ** rbw
    nsamples = int(2 ** 15 / avg)
    RBW = (avg * (400000.0 / 16384.0))
    asse_x = np.arange(nsamples / 2 + 1) * RBW * 0.001

    # Compute X Pol
    spettro, rms = calcolaspettro(raw_data[tile][chan, 0, :], nsamples, log=False)
    bandpower = np.sum(spettro[closest(asse_x, float(startfreq)): closest(asse_x, float(stopfreq))])
    pwr = [linear2dB(bandpower)]

    # Compute Y Pol
    spettro, rms = calcolaspettro(raw_data[tile][chan, 1, :], nsamples, log=False)
    bandpower = np.sum(spettro[closest(asse_x, float(startfreq)): closest(asse_x, float(stopfreq))])
    pwr += [linear2dB(bandpower)]

    return pwr


def runDAQ(directory="/storage/daq/tmp/", chan=0, tpm=0, duration=10, interval=0.01, resolution=1000, band=None):
    mydaq = None
    if band is None:
        band = [160, 160]
    power = {'tstamp': [], 'Pol-X': [], 'Pol-Y': []}
    pol = ['Pol-X', 'Pol-Y']
    tpm_nic_name = get_if_name(station_configuration['network']['lmc']['lmc_ip'])
    if tpm_nic_name == "":
        print("Connection Error! (ETH Card name ERROR)")
    if not tpm_nic_name == "":
        if os.path.exists(directory):
            mydaq = MyDaq(daq, tpm_nic_name, tpm_station, len(station_configuration['tiles']), directory=directory)
            print("DAQ Initialized, NIC: %s, NofTiles: %d, Data Directory: %s" %
                  (tpm_nic_name, len(station_configuration['tiles']), directory))
            data = mydaq.execute()
            t_start = datetime.datetime.utcnow().timestamp()
            t_stamp = 0.0
            while t_stamp < duration:
                power['tstamp'] += [t_stamp]
                pw = raw2pow(data, tile=tpm, chan=chan, res=resolution, startfreq=band[0], stopfreq=band[1])
                for n, p in enumerate(pol):
                    power[p] += [pw[n]]
                #time.sleep(interval)
                t_stamp = datetime.datetime.utcnow().timestamp() - t_start
                data = mydaq.execute()
            mydaq.close()
    else:
        print("DAQ Error: a valid data directory is required.")
    return power


def runRms(chan=0, tpm=0, duration=10, interval=0.01, ylim="", autoy=False, title=""):
    power = {'tstamp': [], 'Pol-X': np.array([]), 'Pol-Y': np.array([])}
    pol = ['Pol-X', 'Pol-Y']

    plt.ion()
    gs = gridspec.GridSpec(2, 1, height_ratios=[6, 1])
    fig = plt.figure(figsize=(14, 9), facecolor='w')
    plt.pause(0.1)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    pol_x_line, = ax1.plot([], [], color='b', lw=2)
    pol_y_line, = ax1.plot([], [], color='g', lw=2)
    ax1.set_xlim(0, duration)
    ax1.set_xlabel("time (s)", fontsize=20)
    if not autoy:
        ax1.set_ylim(float(ylim.split(",")[0]), float(ylim.split(",")[1]))
    ax1.set_ylabel("normalized dB", fontsize=20)
    ax1.grid(True)
    ax1.autoscale(enable=True, axis='y')
    if title == "":
        ax1.set_title("PDL Measure of TPM-%02d Input Fibre %02d" % (tpm + 1, chan + 1), fontsize=26)
    else:
        ax1.set_title(title, fontsize=26)
    ax2.plot(range(100), color='w')
    ax2.set_xlim(0, 100)
    pdl_x_ann = ax2.annotate("Pol-X:", (2, 80), fontsize=38, color='b')
    pdl_y_ann = ax2.annotate("Pol-Y:", (64, 80), fontsize=38, color='g')
    for n in range(2):
        id = fibre_remap[chan * 2 + n]
        fw_map = preadu.get_spi_conf(nrx=id)
        #print(fw_map)
        if fw_map['pol'].upper() == "RF-2":
            dsa_x_ann = ax2.annotate("DSA: %02d dB" % (preadu.get_rx_attenuation(nrx=id)), (3, 20), fontsize=16, color='b')
            level_x_ann = ax2.annotate("LEVEL: - dBm", (18, 20), fontsize=16, color='b')
        else:
            dsa_y_ann = ax2.annotate("DSA: %02d dB" % (preadu.get_rx_attenuation(nrx=id)), (65, 20), fontsize=16, color='g')
            level_y_ann = ax2.annotate("LEVEL: - dBm", (80, 20), fontsize=16, color='g')
    ax2.set_axis_off()
    fig.tight_layout()
    fig.canvas.draw()
    fig.canvas.flush_events()

    rms = get_rms(tile=tpm_station.tiles[tpm], version=board_version)
    # for i in range(32):
    #     print(i, 10 * np.log10(np.power((rms[i] * (1.7 / 256.)), 2) / 400.) + 30 + 12)
    #exit()
    t_start = datetime.datetime.utcnow().timestamp()
    t_stamp = 0.0
    # pbar = tqdm(total=duration, desc="TPM-%02d - Input Fibre #%02d" % (tpm, chan),
    #             bar_format="{desc}: {percentage:3.0f}%|{bar}| {n:.1f}/{total_fmt} [{elapsed}<{remaining}")
    while t_stamp <= duration:
        # pbar.update(t_stamp - pbar.last_print_n)
        power['tstamp'] += [t_stamp]

        for n in range(2):
            id = fibre_remap[chan * 2 + n]
            fw_map = preadu.get_spi_conf(nrx=id)
            with np.errstate(divide='ignore', invalid='ignore'):
                pw = 10 * np.log10(np.power((rms[id] * (1.7 / 256.)), 2) / 400.) + 30 + 12
            if pw == -np.inf:
                pw = -60
            if fw_map['pol'].upper() == "RF-2":
                pol = 'Pol-X'
            else:
                pol = 'Pol-Y'
            #print(int(fw_map['adu_in']), pol, pw)
            power[pol] = np.append(power[pol], pw)
        pol_x_line.set_data(power['tstamp'], (power['Pol-X'] - power['Pol-X'][0]))
        pol_y_line.set_data(power['tstamp'], (power['Pol-Y'] - power['Pol-Y'][0]))
        level_x_ann.set_text("LEVEL: %3.3f dBm" % power['Pol-X'][-1])
        level_y_ann.set_text("LEVEL: %3.3f dBm" % power['Pol-Y'][-1])
        pdl_x = max(power['Pol-X']) - min(power['Pol-X'])
        pdl_y = max(power['Pol-Y']) - min(power['Pol-Y'])
        pdl_x_ann.set_text("Pol-X:   %.3f dB" % pdl_x)
        pdl_y_ann.set_text("Pol-Y:   %.3f dB" % pdl_y)
        if autoy:
            ax1.relim()
            ax1.autoscale_view(True, True, True)
        fig.canvas.draw()
        fig.canvas.flush_events()
        time.sleep(interval)

        t_stamp = datetime.datetime.utcnow().timestamp() - t_start
        rms = get_rms(tile=tpm_station.tiles[tpm], version=board_version)

    # pbar.update(duration - pbar.last_print_n)
    # pbar.close()
    plt.ioff()
    return power


def get_rms(tile, version):
    adc_rms = tile.get_adc_rms()
    rms_remap = np.arange(32)
    if version < 3:
        rms_remap = [1, 0, 3, 2, 5, 4, 7, 6,
                     8, 9, 10, 11, 12, 13, 14, 15,
                     17, 16, 19, 18, 21, 20, 23, 22,
                     24, 25, 26, 27, 28, 29, 30, 31]
    return [adc_rms[x] for x in rms_remap]


if __name__ == "__main__":
    from optparse import OptionParser
    from sys import argv

    parser = OptionParser(usage="usage: %pdl_check.py [options]")
    parser.add_option("--dir", action="store", dest="dir",
                      default="/storage/monitoring/PDL/",
                      help="Output directory")
    parser.add_option("--conf", action="store", dest="conf",
                      default="",
                      help="Station configuration File")
    parser.add_option("--ip", action="store", dest="ip",
                      default="",
                      help="TPM IP (if different wrt config file)")
    parser.add_option("--tpm", action="store", dest="tpm",
                      default=1, type=int,
                      help="Station Tile Number")
    parser.add_option("--channel", action="store", dest="channel", type=int,
                      default=1, help="TPM Input Fibre Number (1-16)")
    parser.add_option("--duration", action="store", dest="duration", type=float,
                      default=10, help="Duration of the acquisition (secs)")
    parser.add_option("--interval", action="store", dest="interval", type=float,
                      default=0.1, help="Interval between acquisition (secs, float, def: 0.1)")
    parser.add_option("--eqvalue", action="store", dest="eqvalue", type=str,
                      default="", help="Equalization value in dB. If not given do not equalize")
    parser.add_option("--daq", action="store_true", dest="daq",
                      default=False, help="Use DAQ Raw Data instead of ADC RMS")
    parser.add_option("--resolution", action="store", dest="resolution", type=int,
                      default=1000, help="Spectra resolution (only used in DAQ acquisition)")
    parser.add_option("--band", action="store", dest="band", type=str,
                      default="160,160", help="Start and Stop Band Frequencies to compute the power "
                                              "(only used in DAQ acquisition)")
    parser.add_option("--title", action="store", dest="title", type=str,
                      default="", help="Measurement File Name (if not given the channel number is appended)")
    parser.add_option("--version", action="store", dest="version", type=str,
                      default="2.1", help="TPM Version (default: 2.1)")
    parser.add_option("--ylim", action="store", dest="ylim", type=str,
                      default="-0.5,0.5", help="Y Plot Limits (def. '-0.5,0.5'). ")
    parser.add_option("--autoscale", action="store_true", dest="autoscale",
                      default=False, help="Set Plot Y Autoscale")
    (opts, args) = parser.parse_args(argv[1:])

    if opts.conf == "":
        exit()
    station.load_configuration_file(opts.conf)
    station.configuration['tiles'] = opts.ip.split(",")
    station_configuration = station.configuration
    band = [float(opts.band.split(",")[0]), float(opts.band.split(",")[1])]

    # TPM 1.2 Fibre Mapping
    fibre_remap = np.arange(32)
    if opts.version == "2.1":
        print("Using RMS Mapping for TPM 1.2 with PreADU<3.0")
        fibre_remap = [1, 0, 3, 2, 5, 4, 7, 6,
                     17, 16, 19, 18, 21, 20, 23, 22,
                     30, 31, 28, 29, 26, 27, 24, 25,
                     14, 15, 12, 13, 10, 11, 8, 9]
        signal_map_file = "../SignalMap/TPM_AAVS1.txt"
    elif opts.version == "3.1":
        print("Using RMS Mapping for TPM 1.6 with PreADU>=3.0")
        fibre_remap = [15, 14, 13, 12, 11, 10, 9, 8,
                       6, 7, 4, 5, 2, 3, 0, 1,
                       31, 30, 29, 28, 27, 26, 25, 24,
                       22, 23, 20, 21, 18, 19, 16, 17]
        signal_map_file = "../SignalMap/TPM_AAVS3.txt"
    else:
        print("Board version do not satisfy requirements (is a preadu with optical receivers?!?) Version %s", opts.version)
        exit(0)
    rf_map = read_routing_table(signal_map_file)

    try:
        # Create station
        tpm_station = Station(station.configuration)
        # Connect station (program, initialise and configure if required)
        tpm_station.connect()
        status = True
        for t in tpm_station.tiles:
            status = status * t.is_programmed()
        if status:
            tpm_station.tiles[0].get_temperature()
        else:
            print("Some TPM is not programmed,\nplease initialize the Station first!")

    except BaseException as e:
        print("Exiting with errors: ", e)

    # Instantiate PreADU
    board_version = float(opts.version)
    preadu = None
    rf_map = read_routing_table("../SignalMap/TPM_AAVS1.txt")
    if board_version == 3.1:
        preadu = preAduAAVS3()
        rf_map = read_routing_table("../SignalMap/TPM_AAVS3.txt")
        print("PreADU 3.1 with Optical Receivers selected (pre-AAVS3)")
    elif board_version == 2.0:
        preadu = preAduRf()
        print("PreADU 2.0 (RF) without optical receivers")
    elif board_version == 2.1:
        preadu = preAduAAVS1()
        print("PreADU 2.1 with Optical Receivers selected (AAVS1/AAVS2)")
    elif board_version == 2.2:
        preadu = preAduSadino()
        print("PreADU 2.2 (RF SADino) with Mixed RF and Optical Rxs selected")
    for spimap in rf_map:
        preadu.set_spi_conf(nrx=int(spimap[0]), preadu_id=int(spimap[3]), channel_filter=int(spimap[4]),
                            pol=spimap[1], adu_in=spimap[0], tpm_in=spimap[2])
        #print(spimap)

    # Read DSA
    preaduConf = []
    tpm_station.tiles[opts.tpm - 1].tpm.tpm_preadu[0].read_configuration()  # TOP
    tpm_station.tiles[opts.tpm - 1].tpm.tpm_preadu[1].read_configuration()  # BOTTOM
    for i in range(32):
        fw_map = preadu.get_spi_conf(nrx=i)
        #preadu_id, channel_filter, pol = preadu.get_spi_conf(nrx=i)
        value = tpm_station.tiles[0].tpm.tpm_preadu[int(fw_map['preadu_id'])].channel_filters[int(fw_map['channel_filter'])]
        preadu.set_register_value(nrx=i, value=value)
        preaduConf += [{'id': i,
                        'sn': "n/a",
                        'code': value,
                        'preadu_id': int(fw_map['preadu_id']),
                        'channel_filter': int(fw_map['channel_filter']),
                        'pol': fw_map['pol'],
                        'adu_in': int(fw_map['adu_in']),
                        'tpm_in': int(fw_map['tpm_in'][1:]),
                        'dsa': preadu.get_rx_attenuation(i),
                        'version': preadu.rx[i].version}]
        #print(i, preaduConf[i])

    # # Check RF Power and DSA
    # rms = 10 * np.log10(np.power((np.array(tpm_station.tiles[0].get_adc_rms()) * (1.7 / 256.)), 2) / 400.) + 30 + 12
    # for i in range(32):
    #     preadu_id = int(rf_map[remap[i]][3])
    #     channel_filter = int(rf_map[remap[i]][4])
    #     print(preadu_id, channel_filter,
    #           tpm_station.tiles[opts.tpm - 1].tpm.tpm_preadu[preadu_id].channel_filters[channel_filter] >> 3,
    #           rms[remap[i]])

    #pol = [['Pol-X', 'RF-2'], ['Pol-Y', 'RF-1']]
    pol = ['Pol-X', 'Pol-Y']
    dsa = []
    # for p in [0,1]:
    #     for c in range(16):
    #         print(p, c, tpm_station.tiles[opts.tpm - 1].tpm.tpm_preadu[p].channel_filters[c] >> 3)
    #print()

    for n, pol in enumerate(pol):
        rx_id = fibre_remap[(opts.channel - 1) * 2 + n]
        fw_map = preadu.get_spi_conf(nrx=rx_id)
        #preadu_id, channel_filter, rfpol = preadu.get_spi_conf(nrx=rx_id)
        preadu_id = int(fw_map['preadu_id'])
        channel_filter = int(fw_map['channel_filter'])
        dsa = preadu.get_rx_attenuation(nrx=rx_id)
        # print("RX # %d" % rx_id, "PreADU Id: %d" % preadu_id,
        #       " Channel Filter: %d" % channel_filter, "  -->  ",
        #       fw_map['pol'], " DSA: %02d dB" % dsa)
        # Equalization
        if not opts.eqvalue == "":
            print("Equalization of TPM-%02d Input Channel Fibre %02d to RF Power %3.1f dBm" %
                  (opts.tpm, opts.channel, float(opts.eqvalue)))
            for k in range(3):
                rms = get_rms(tile=tpm_station.tiles[opts.tpm - 1], version=board_version)
                with np.errstate(divide='ignore', invalid='ignore'):
                    power = 10 * np.log10(np.power((rms[rx_id] * (1.7 / 256.)), 2) / 400.) + 30 + 12
                if power == (-np.inf):
                    power = -30
                dsa = bound(int(round(dsa + (power - float(opts.eqvalue)))))
                preadu.set_rx_attenuation(nrx=rx_id, att=dsa)
                tpm_station.tiles[opts.tpm - 1].tpm.tpm_preadu[preadu_id].channel_filters[channel_filter] = \
                    preadu.get_register_value(nrx=rx_id)
                tpm_station.tiles[opts.tpm - 1].tpm.tpm_preadu[preadu_id].write_configuration()
                time.sleep(1)
                # print("PreADU Id: %d" % preadu_id, " Channel Filter: %d" % channel_filter, "  -->  ", pol,
                #       " DSA: %02d dB\n" % preadu.get_rx_attenuation(nrx=rx_id))
        rms = get_rms(tile=tpm_station.tiles[opts.tpm - 1], version=board_version)
        if fw_map['pol'].upper() == "RF-2":
            dsa_x = dsa
        else:
            dsa_y = dsa
    #print()

    if opts.daq:
        data = runDAQ(opts.dir, chan=(opts.channel - 1), tpm=(opts.tpm - 1), duration=opts.duration,
                      interval=opts.interval, resolution=opts.resolution, band=band)
    else:
        data = runRms(chan=(opts.channel - 1), tpm=(opts.tpm - 1), duration=opts.duration, interval=opts.interval,
                      ylim=opts.ylim, autoy=opts.autoscale, title=opts.title)
    if len(data['Pol-X']):
        path = opts.dir
        if not path[-1] == "/":
            path += "/"
        if not os.path.exists(path + "DATA"):
            os.mkdir(path + "DATA")
        data_ora = datetime.datetime.strftime(datetime.datetime.utcnow(), "%Y-%m-%d_%H%M%S")
        if not opts.title == "":
            fname = path + "DATA/%s_PDL_%s.txt" % (data_ora, opts.title)
        else:
            fname = path + "DATA/%s_PDL_%s_INPUT-%02d.txt" % (data_ora, opts.title, opts.channel)
        with open(fname, "w") as f:
            f.write("Timestamp\tPol-Y\tPol-X\tDSA (Y-X)\t%d\t%d\n" % (dsa_y, dsa_x))
            for i in range(len(data['tstamp'])):
                f.write("%f\t%6.3f\t%6.3f\n" % (data['tstamp'][i], data['Pol-Y'][i], data['Pol-X'][i]))
        if not os.path.exists(path + "PICTURES"):
            os.mkdir(path + "PICTURES")
        #plt.title("PDL of Fibre #%d are --> Pol-X %3.2f dB,  Pol-Y %3.2f dB" % (opts.channel, pdl_x, pdl_y))
        if not opts.title == "":
            fname = path + "PICTURES/%s_PDL_%s.png" % (data_ora, opts.title)
        else:
            fname = path + "PICTURES/%s_PDL_%s_INPUT-%02d.png" % (data_ora, opts.title, opts.channel)
        plt.savefig(fname)
        plt.show()
    else:
        print("\nReturned data length zero. Something went wrong!\n")

