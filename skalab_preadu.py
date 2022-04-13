import gc
import struct
import time

import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui

CHANNELS = 32

LABEL_WIDTH = 23
LABEL_HEIGHT = 21
TEXT_WIDTH = 50
TEXT_HEIGHT = 22
FLAG_WIDTH = 40
FLAG_HEIGHT = 21

TABLE_HSPACE = 570
TABLE_VSPACE = 30

DIALOG_WIDTH = 850
DIALOG_HEIGHT = 720

SIGNALS_MAP_FILENAME = "signals_map.txt"


def bound(value, low=0, high=31):
    '''
        Bound the PreADU DSA values between 0 and 31
    '''
    return max(low, min(high, value))


def clickable(widget):
    class Filter(QtCore.QObject):
        clicked = QtCore.pyqtSignal()

        def eventFilter(self, obj, event):
            if obj == widget:
                if event.type() == QtCore.QEvent.MouseButtonRelease:
                    if obj.rect().contains(event.pos()):
                        self.clicked.emit()
                        return True
            return False
    filter = Filter(widget)
    widget.installEventFilter(filter)
    return filter.clicked


# This createsthe input label (eg: for input 15 -> "15:")
def create_label(Dialog, x, y, text, width=LABEL_WIDTH):
    label = QtWidgets.QLabel(Dialog)
    label.setGeometry(QtCore.QRect(x, y, width, LABEL_HEIGHT))
    label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
    label.setText(text)
    return label


# This creates the text lineEdit for the attenuation values
def create_text(Dialog, x, y, text):
    qtext = QtWidgets.QLineEdit(Dialog)
    qtext.setGeometry(QtCore.QRect(x, y, TEXT_WIDTH, TEXT_HEIGHT))
    qtext.setAlignment(QtCore.Qt.AlignCenter)
    qtext.setText(text)
    return qtext


def update_text(qtext, text):
    qtext.setText(text)


# This creates the flags "hi" and "lo" using a background color
def create_flag(Dialog, x, y, color, text):
    flag = QtWidgets.QLabel(Dialog)
    flag.setGeometry(QtCore.QRect(x, y, FLAG_WIDTH, FLAG_HEIGHT))
    flag.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
    flag.setAutoFillBackground(True)
    if color == "green":
        flag.setStyleSheet("background-color: rgb(0, 170, 0);")
    elif color == "yellow":
        flag.setStyleSheet("background-color: rgb(255, 255, 0);")
    elif color == "cyan":
        flag.setStyleSheet("background-color: rgb(0, 255, 234);")
        flag.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
    else:
        flag.setStyleSheet("background-color: rgb(255, 0, 0);")
    flag.setAlignment(QtCore.Qt.AlignCenter)
    flag.setText(text)
    return flag


# This creates the buttons "-" and "+"
def create_button(Dialog, x, y, text):
    qbutton = QtWidgets.QPushButton(Dialog)
    qbutton.setGeometry(QtCore.QRect(x, y, 30, 21))
    qbutton.setText(text)
    return qbutton


def update_flag_lo_filter(record, val):
    if val:
        record['lo'].setStyleSheet("background-color: rgb(0, 170, 0);")
    else:
        record['lo'].setStyleSheet("background-color: rgb(255, 255, 0);")


def update_flag_hi_filter(record, val):
    if val:
        record['hi'].setStyleSheet("background-color: rgb(0, 170, 0);")
    else:
        record['hi'].setStyleSheet("background-color: rgb(255, 255, 0);")


def update_flag_termination(record, val):
    if not val:  # 50 Ohm
        record['rf'].setStyleSheet("background-color: rgb(220, 40, 40);")
    else:
        record['rf'].setStyleSheet("background-color: rgb(0, 170, 0);")


def create_record(Dialog, rf_map):
    rec = {}
    idx = int(rf_map[0])
    rec['reg_val'] = 0
    rec['label'] = create_label(Dialog, 10 + 20 + (((idx & 8) >> 3) * TABLE_HSPACE),
                                90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), rf_map[0] + ":")
    rec['value'] = create_label(Dialog, 10 + 45 + (((idx & 8) >> 3) * TABLE_HSPACE),
                                90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "0")
    rec['text'] = create_text(Dialog, 10 + 80 + (((idx & 8) >> 3) * TABLE_HSPACE),
                              90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "0")
    rec['minus'] = create_button(Dialog, 10 + 140 + (((idx & 8) >> 3) * TABLE_HSPACE),
                                 90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "-")
    rec['plus'] = create_button(Dialog, 10 + 170 + (((idx & 8) >> 3) * TABLE_HSPACE),
                                90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "+")
    rec['lo'] = create_flag(Dialog, 10 + 210 + (((idx & 8) >> 3) * TABLE_HSPACE),
                            90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "green", "LO")
    rec['hi'] = create_flag(Dialog, 10 + 260 + (((idx & 8) >> 3) * TABLE_HSPACE),
                            90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "yellow", "HI")
    rec['rf'] = create_flag(Dialog, 10 + 310 + (((idx & 8) >> 3) * TABLE_HSPACE),
                            90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "green", rf_map[1])
    rec['of'] = create_flag(Dialog, 10 + 360 + (((idx & 8) >> 3) * TABLE_HSPACE),
                            90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "cyan", rf_map[2])
    rec['rms'] = create_label(Dialog, 10 + 430 + (((idx & 8) >> 3) * TABLE_HSPACE),
                                90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "----", width=30)
    rec['power'] = create_label(Dialog, 10 + 480 + (((idx & 8) >> 3) * TABLE_HSPACE),
                                90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "----", width=45)
    rec['power'].setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
    return rec


def spi_bit_reverse(n):
    return int("%d" % (int('{:08b}'.format(n)[::-1], 2)))


def font_bold():
    font = QtGui.QFont()
    font.setBold(True)
    font.setWeight(75)
    return font


def font_normal():
    font = QtGui.QFont()
    return font


def read_routing_table():
    mappa = []
    f_map = open(SIGNALS_MAP_FILENAME)
    input_list = f_map.readlines()
    for i in range(CHANNELS):
        mappa += [[input_list[i].split(":")[0], input_list[i].split(":")[1].split()[0],
                   input_list[i].split(":")[1].split()[1]]]
    f_map.close()
    return mappa


class InafSkaOpticalRx:
    '''
    INAF SKA Optical Receiver
    (SKA-AAVS)

    LSB - No 50Ohm,PA,PB,1dB,2dB,4dB,8dB,16dB - MSB
    '''
    def __init__(self):
        self.bit_string = {}
        self.bit_string['b0'] = "50 Ohm termination"
        self.bit_string['b1'] = "High Pass Filter (> 350 MHz)"
        self.bit_string['b2'] = "Low Pass Filter (< 350 MHz)"
        self.bit_string['b3'] = "Attenuation 1dB"
        self.bit_string['b4'] = "Attenuation 2dB"
        self.bit_string['b5'] = "Attenuation 4dB"
        self.bit_string['b6'] = "Attenuation 8dB"
        self.bit_string['b7'] = "Attenuation 16dB"

        self.value = 4 + 128  # LowPassFilter, 16 dB of attenuation
        self.version = "OF-Rx"
        self.sn = 0

    def print_bit_description(self):
        for k in sorted(self.bit_string.keys()):
            print(k, ":", self.bit_string[k])

    def set_attenuation(self, att):
        self.value = (self.value & 0b111) + (att << 3)

    def get_attenuation(self):
        return (self.value & 0b11111000) >> 3

    def code2att(self, code):
        return (code & 0b11111000) >> 3

    def set_hipass(self):
        self.value = (self.value & 0b11111001) + 2

    def is_hipass(self):
        if (self.value & 0b10) == 2:
            return True
        else:
            return False

    def set_lopass(self):
        self.value = (self.value & 0b11111001) + 4

    def is_lopass(self):
        if (self.value & 0b100) == 4:
            return True
        else:
            return False

    def terminate(self):
        self.value = (self.value & 0b11111110) + 1

    def is_terminated(self):
        if self.value & 1:
            return True
        else:
            return False

    def rf_enable(self):
        self.value = (self.value & 0b11111110)


class InafSkaRfRx:
    '''
    INAF SKA Prototype Receiver without optical rx
    (SKA-AAVS)

    By the programming point of view
    it differs just for configuration bit remapping
    on the EVEN channels (RF2)

    LSB - No 50Ohm,2dB,PA,4dB,PB,8dB,1dB,16dB - MSB
    '''
    def __init__(self):
        self.bit_string = {}
        self.bit_string['b0'] = "50 Ohm termination"
        self.bit_string['b1'] = "Attenuation 2dB"
        self.bit_string['b2'] = "High Pass Filter (> 350 MHz)"
        self.bit_string['b3'] = "Attenuation 4dB"
        self.bit_string['b4'] = "Low Pass Filter (< 350 MHz)"
        self.bit_string['b5'] = "Attenuation 8dB"
        self.bit_string['b6'] = "Attenuation 1dB"
        self.bit_string['b7'] = "Attenuation 16dB"

        self.value = 16 + 128  # LowPassFilter, 16 dB of attenuation
        self.version = "RF-Rx"
        self.sn = 0

    def print_bit_description(self):
        for k in sorted(self.bit_string.keys()):
            print(k, ":", self.bit_string[k])

    def set_attenuation(self, att):
        #print format(self.value, '08b'), att,
        self.value = self.value & 0b00010101
        self.value = self.value + ((att & 0b1) << 6)  # 1dB
        self.value = self.value + (att & 0b10)  # 2dB
        self.value = self.value + ((att & 0b100) << 1) # 4dB
        self.value = self.value + ((att & 0b1000) << 2)  # 8dB
        self.value = self.value + ((att & 0b10000) << 3)  # 16dB
        #print format(self.value, '08b')

    def get_attenuation(self):
        a = ((self.value & 0b10) >> 1) * 2
        a += ((self.value & 0b1000) >> 3) * 4
        a += ((self.value & 0b100000) >> 5) * 8
        a += ((self.value & 0b1000000) >> 6) * 1
        a += ((self.value & 0b10000000) >> 7) * 16
        return a

    def code2att(self, code):
        a = ((code & 0b10) >> 1) * 2
        a += ((code & 0b1000) >> 3) * 4
        a += ((code & 0b100000) >> 5) * 8
        a += ((code & 0b1000000) >> 6) * 1
        a += ((code & 0b10000000) >> 7) * 16
        return a

    def set_hipass(self):
        self.value = (self.value & 0b11101011) + 4

    def is_hipass(self):
        if (self.value & 0b100) == 4:
            return True
        else:
            return False

    def set_lopass(self):
        self.value = (self.value & 0b11101011) + 16

    def is_lopass(self):
        if (self.value & 0b10000) == 16:
            return True
        else:
            return False

    def terminate(self):
        self.value = (self.value & 0b11111110) + 1

    def is_terminated(self):
        if self.value & 1:
            return True
        else:
            return False

    def rf_enable(self):
        self.value = (self.value & 0b11111110)


class preAduRf:
    '''
    A preADU board having INAF SKA prototype receivers
    with a different bit mapping
    for odd and even channels (RF1,RF2)

    RF1 Channel       RF2 Channel
    opticalRX like    prototype like
    0:No 50Ohm        0:No 50Ohm
    1:PA              1:2dB
    2:PB              2:PA
    3:1dB             3:4dB
    4:2dB             4:PB
    5:4dB             5:8dB
    6:8dB             6:1dB
    7:16dB            7:16dB

    Also, the receivers mapping is affected by the mechanical feature of the TPM
    having 2 preADU boards mounted either to the bottom and to the top of the ADU board
    RF1,RF2 on ADU Input (0,1),(2,3),(4,5),(6,7), (16,17),(18,19),(20,21),(22,23)
    RF2,RF1 on ADU Input ()
    '''
    def __init__(self):
        self.nof_rx = 32
        self.rx = []

        # TPM input fibres 1-4, ADU Input 0-7
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]

        # TPM input fibres 5-8, ADU Input 16-23
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]

        # TPM input fibres 16-13, ADU Input 8-15
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]

        # TPM input fibres 12-09, ADU Input 24-31
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]

        for i in range(32):
            self.rx[i].sn = i

    def set_rx_attenuation(self, nrx, att):
        self.rx[nrx].set_attenuation(bound(att))

    def get_rx_attenuation(self, nrx):
        return self.rx[nrx].get_attenuation()

    def set_rx_hi_filter(self, nrx):
        self.rx[nrx].set_hipass()

    def set_rx_lo_filter(self, nrx):
        self.rx[nrx].set_lopass()

    def set_all_hi_filter(self):
        for i in range(self.nof_rx):
            self.rx[i].set_hipass()

    def set_all_lo_filter(self):
        for i in range(self.nof_rx):
            self.rx[i].set_lopass()

    def set_all_rx_attenuation(self, att):
        for i in range(self.nof_rx):
            self.rx[i].set_attenuation(bound(att))


class preAduSadino:
    '''
    A preADU board having INAF SKA prototype receivers
    with a different bit mapping
    for odd and even channels (RF1,RF2)

    RF1 Channel       RF2 Channel
    opticalRX like    prototype like
    0:No 50Ohm        0:No 50Ohm
    1:PA              1:2dB
    2:PB              2:PA
    3:1dB             3:4dB
    4:2dB             4:PB
    5:4dB             5:8dB
    6:8dB             6:1dB
    7:16dB            7:16dB

    and some Optical Rx modified!!!

    Also, the receivers mapping is affected by the mechanical feature of the TPM
    having 2 preADU boards mounted either to the bottom and to the top of the ADU board
    RF1,RF2 on ADU Input (0,1),(2,3),(4,5),(6,7), (16,17),(18,19),(20,21),(22,23)
    RF2,RF1 on ADU Input ()
    '''
    def __init__(self):
        self.nof_rx = 32
        self.rx = []

        # TPM input fibres 1-4, ADU Input 0-7
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]

        # TPM input fibres 16-13, ADU Input 8-15
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]

        # TPM input fibres 5-8, ADU Input 16-23
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]

        # TPM input fibres 12-09, ADU Input 24-31
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [InafSkaOpticalRx()]

        for i in range(32):
            self.rx[i].sn = i

    def set_rx_attenuation(self, nrx, att):
        #print("PRIMA\t", nrx, self.rx[nrx].sn, self.rx[nrx].version, "DSA", self.rx[nrx].get_attenuation(), "OLD VALUE", self.rx[nrx].value, "SET DSA", att)
        self.rx[nrx].set_attenuation(bound(att))
        #print(" DOPO\t", nrx, self.rx[nrx].sn, self.rx[nrx].version, "DSA", self.rx[nrx].get_attenuation(), "NEW VALUE", self.rx[nrx].value)

    def get_rx_attenuation(self, nrx):
        return self.rx[nrx].get_attenuation()

    def set_rx_hi_filter(self, nrx):
        self.rx[nrx].set_hipass()

    def set_rx_lo_filter(self, nrx):
        self.rx[nrx].set_lopass()

    def set_all_hi_filter(self):
        for i in range(self.nof_rx):
            self.rx[i].set_hipass()

    def set_all_lo_filter(self):
        for i in range(self.nof_rx):
            self.rx[i].set_lopass()

    def set_all_rx_attenuation(self, att):
        for i in range(self.nof_rx):
            self.rx[i].set_attenuation(bound(att))


class preAduOptRx:
    '''
    A preADU board having INAF SKA optical receivers
    The receiver bit mapping is the same for RF1 and RF2

    '''
    def __init__(self):
        self.nof_rx = 32
        self.rx = []
        for i in range(self.nof_rx):
            self.rx += [InafSkaOpticalRx()]
            self.rx[i].sn = i

    def set_rx_attenuation(self, nrx, att):
        self.rx[nrx].set_attenuation(bound(att))

    def get_rx_attenuation(self, nrx):
        return self.rx[nrx].get_attenuation()

    def set_rx_hi_filter(self, nrx):
        self.rx[nrx].set_hipass()

    def set_rx_lo_filter(self, nrx):
        self.rx[nrx].set_lopass()

    def set_all_hi_filter(self):
        for i in range(self.nof_rx):
            self.rx[i].set_hipass()

    def set_all_lo_filter(self):
        for i in range(self.nof_rx):
            self.rx[i].set_lopass()

    def set_all_rx_attenuation(self, att):
        for i in range(self.nof_rx):
            self.rx[i].set_attenuation(bound(att))


class Preadu(object):
    def __init__(self, parent, tpm=None, board_type=0, debug=0):
        """ Initialise main window """
        super(Preadu, self).__init__()

        self.board_type = board_type
        self.debug = debug
        self.tpm = tpm
        self.Busy = False  # UCP Communication Token

        self.inputs = CHANNELS
        if self.board_type == 0:
            self.preadu = preAduOptRx()
            print("PreADU with Optical Receivers selected")
        elif self.board_type == 1:
            self.preadu = preAduRf()
            print("RF PreADU without optical receivers")
        else:
            self.preadu = preAduSadino()
            print("SADino preADU with Mixed RF and Optical Rxs selected")

        self.spi_remap = [23, 22, 21, 20, 19, 18, 17, 16,
                           7,  6,  5,  4,  3,  2,  1,  0,
                           8,  9, 10, 11, 12, 13, 14, 15,
                          24, 25, 26, 27, 28, 29, 30, 31]

        self.chan_remap = [
            15, 14, 13, 12, 11, 10, 9, 8,  # ok
            17, 16, 19, 18, 21, 20, 23, 22,  # ok
            31, 30, 29, 28, 27, 26, 25, 24,  # ok
            1, 0, 3, 2, 5, 4, 7, 6,  # ok
        ]

        self.signal_map = {0: {'preadu_id': 1, 'channel': 14},
                           1: {'preadu_id': 1, 'channel': 15},
                           2: {'preadu_id': 1, 'channel': 12},
                           3: {'preadu_id': 1, 'channel': 13},
                           4: {'preadu_id': 1, 'channel': 10},
                           5: {'preadu_id': 1, 'channel': 11},
                           6: {'preadu_id': 1, 'channel': 8},
                           7: {'preadu_id': 1, 'channel': 9},
                           8: {'preadu_id': 0, 'channel': 0},
                           9: {'preadu_id': 0, 'channel': 1},
                           10: {'preadu_id': 0, 'channel': 2},
                           11: {'preadu_id': 0, 'channel': 3},
                           12: {'preadu_id': 0, 'channel': 4},
                           13: {'preadu_id': 0, 'channel': 5},
                           14: {'preadu_id': 0, 'channel': 6},
                           15: {'preadu_id': 0, 'channel': 7},
                           16: {'preadu_id': 1, 'channel': 6},
                           17: {'preadu_id': 1, 'channel': 7},
                           18: {'preadu_id': 1, 'channel': 4},
                           19: {'preadu_id': 1, 'channel': 5},
                           20: {'preadu_id': 1, 'channel': 2},
                           21: {'preadu_id': 1, 'channel': 3},
                           22: {'preadu_id': 1, 'channel': 0},
                           23: {'preadu_id': 1, 'channel': 1},
                           24: {'preadu_id': 0, 'channel': 8},
                           25: {'preadu_id': 0, 'channel': 9},
                           26: {'preadu_id': 0, 'channel': 10},
                           27: {'preadu_id': 0, 'channel': 11},
                           28: {'preadu_id': 0, 'channel': 12},
                           29: {'preadu_id': 0, 'channel': 13},
                           30: {'preadu_id': 0, 'channel': 14},
                           31: {'preadu_id': 0, 'channel': 15}}

        self.label_top = QtWidgets.QLabel(parent)
        self.label_top.setGeometry(QtCore.QRect(80, 15, 380, 21))
        self.label_top.setAlignment(QtCore.Qt.AlignCenter)
        self.label_top.setText("PRE-ADU BOTTOM (LEFT)") #+self.tpm_config['preadu_l'])

        self.label_bottom = QtWidgets.QLabel(parent)
        self.label_bottom.setGeometry(QtCore.QRect(640, 15, 380, 21))
        self.label_bottom.setAlignment(QtCore.Qt.AlignCenter)
        self.label_bottom.setText("PRE-ADU TOP (RIGHT)") #+self.tpm_config['preadu_r'])

        table_names = "ADU#  Code      Attenuation               Bands             Rx      Fibre          RMS         dBm"
        self.label_legend_1 = QtWidgets.QLabel(parent)
        self.label_legend_1.setGeometry(QtCore.QRect(14, 55, 560, 31))
        self.label_legend_1.setText(table_names)
        self.label_legend_2 = QtWidgets.QLabel(parent)
        self.label_legend_2.setGeometry(QtCore.QRect(584, 55, 560, 31))
        self.label_legend_2.setText(table_names)
        self.label_legend_3 = QtWidgets.QLabel(parent)
        self.label_legend_3.setGeometry(QtCore.QRect(14, 335, 560, 31))
        self.label_legend_3.setText(table_names)
        self.label_legend_4 = QtWidgets.QLabel(parent)
        self.label_legend_4.setGeometry(QtCore.QRect(584, 335, 560, 31))
        self.label_legend_4.setText(table_names)

        self.frame_all = QtWidgets.QFrame(parent)
        self.frame_all.setGeometry(QtCore.QRect(180, 635, 640, 40))
        self.label_all = QtWidgets.QLabel(self.frame_all)
        self.label_all.setGeometry(QtCore.QRect(5, 10, 200, 21))
        self.label_all.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_all.setText("Action to ALL:   Attenuation")
        self.comboBox = QtWidgets.QComboBox(self.frame_all)
        self.comboBox.setGeometry(QtCore.QRect(220, 5, 50, 31))
        self.comboBox.addItems([ "0",  "1",  "2",  "3",  "4",  "5",  "6",  "7",  "8",  "9",
                                "10", "11", "12", "13", "14", "15", "16", "17", "18", "19",
                                "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
                                "30", "31"])
        self.comboBox.setCurrentIndex(0)
        self.comboBox.currentIndexChanged.connect(self.selection_change)

        self.button_decrease = QtWidgets.QPushButton(self.frame_all)
        self.button_decrease.setGeometry(QtCore.QRect(310, 5, 50, 31))
        self.button_increase = QtWidgets.QPushButton(self.frame_all)
        self.button_increase.setGeometry(QtCore.QRect(370, 5, 50, 31))
        self.button_rfon = QtWidgets.QPushButton(self.frame_all)
        self.button_rfon.setGeometry(QtCore.QRect(460, 5, 70, 31))
        self.button_rfoff = QtWidgets.QPushButton(self.frame_all)
        self.button_rfoff.setGeometry(QtCore.QRect(540, 5, 70, 31))
        self.button_discard = QtWidgets.QPushButton(parent)
        self.button_discard.setGeometry(QtCore.QRect(900, 640, 90, 31))
        self.button_apply = QtWidgets.QPushButton(parent)
        self.button_apply.setGeometry(QtCore.QRect(1020, 640, 90, 31))

        self.button_discard.setText("Discard")
        self.button_decrease.setText("-")
        self.button_increase.setText("+")
        self.button_rfon.setText("RF ON")
        self.button_rfoff.setText("RF OFF")
        self.button_apply.setText("Apply")

        rf_map = read_routing_table()
        self.records = []
        for i in range(self.inputs):
            self.records += [create_record(parent, rf_map[i])]

        self.label_comments = QtWidgets.QLabel(parent)
        self.label_comments.setGeometry(QtCore.QRect(20, 630, DIALOG_WIDTH - 20, 21))
        self.label_comments.setAlignment(QtCore.Qt.AlignCenter)
        self.adjustControls(self.board_type)
        self.connections()

    def connections(self):
        self.button_discard.clicked.connect(self.reload)
        self.button_apply.clicked.connect(lambda: self.apply_configuration())
        self.button_decrease.clicked.connect(lambda: self.decreaseAll())
        self.button_increase.clicked.connect(lambda: self.increaseAll())
        self.button_rfon.clicked.connect(lambda: self.rfonAll())
        self.button_rfoff.clicked.connect(lambda: self.rfoffAll())
        #self.button_test.clicked.connect(lambda: self.test_configuration())
        for group in range(self.inputs):
            self.records[group]['minus'].clicked.connect(lambda state, g=group: self.action_minus(g))
            self.records[group]['plus'].clicked.connect(lambda  state, g=group:  self.action_plus(g))
            # Making clickable non clickable object!
            clickable(self.records[group]['lo']).connect(self.set_lo) # signal/slot connection for flag "lo"
            clickable(self.records[group]['hi']).connect(self.set_hi) # signal/slot connection for flag "hi"
            clickable(self.records[group]['rf']).connect(lambda  g=group:  self.set_rf(g)) # signal/slot connection for flag "rf"

    def updateForm(self):
        for num in range(self.inputs):
            # SPI Register Value
            #register_value = int(self.preadu_val[self.spi_remap[num]])
            register_value = int(self.preadu.rx[num].value)
            self.preadu.rx[num].value = register_value
            self.records[num]['reg_val'] = register_value
            self.records[num]['value'].setText(str(hex(register_value))[2:])
            # Attenuation
            update_text(self.records[num]['text'], str(self.preadu.get_rx_attenuation(num)))
            #update_text(self.records[num]['text'], str((register_value & 0b11111000) >> 3))
            update_flag_lo_filter(self.records[num], self.preadu.rx[num].is_lopass())
            update_flag_hi_filter(self.records[num], self.preadu.rx[num].is_hipass())
            update_flag_termination(self.records[num], self.preadu.rx[num].is_terminated())
            self.records[num]['value'].setFont(font_normal())
        if self.debug:
            for num in range(self.inputs):
                print(format(num, '02d'), format(self.preadu.rx[num].value, '08b'), "ATT:",
                      self.preadu.rx[num].get_attenuation(), ", LO:", self.preadu.rx[num].is_lopass(),
                      ", HI:", self.preadu.rx[num].is_hipass(), ", RF-ENABLED: ", self.preadu.rx[num].is_terminated())

    def set_hi(self):
        for num in range(self.inputs):
            self.records[num]['lo'].setStyleSheet("background-color: rgb(255, 255, 0);")
            self.records[num]['hi'].setStyleSheet("background-color: rgb(0, 170, 0);")
            self.preadu.rx[num].set_hipass()
            #conf_value = ('0x' + self.records[num]['value'].text()).toInt(16)[0] & 0b11111011
            #conf_value = conf_value | 0b10
            self.records[num]['value'].setFont(font_bold())
            self.records[num]['value'].setText(hex(self.preadu.rx[num].value)[2:])
            update_flag_lo_filter(self.records[num], self.preadu.rx[num].is_lopass())
            update_flag_hi_filter(self.records[num], self.preadu.rx[num].is_hipass())
            #update_flag(self.records[num], (conf_value & 0b111))

    def set_lo(self):
        for num in range(self.inputs):
            self.records[num]['hi'].setStyleSheet("background-color: rgb(255, 255, 0);")
            self.records[num]['lo'].setStyleSheet("background-color: rgb(0, 170, 0);")
            self.preadu.rx[num].set_lopass()
            #conf_value=('0x'+self.records[num]['value'].text()).toInt(16)[0] & 0b11111101
            #conf_value=conf_value | 0b100
            self.records[num]['value'].setFont(font_bold())
            self.records[num]['value'].setText(hex(self.preadu.rx[num].value)[2:])
            update_flag_lo_filter(self.records[num], self.preadu.rx[num].is_lopass())
            update_flag_hi_filter(self.records[num], self.preadu.rx[num].is_hipass())
            #update_flag(self.records[num], (conf_value & 0b111) )

    def set_rf(self, num):
        if (self.preadu.rx[num].value & 1) == 1:
            self.preadu.rx[num].value = self.preadu.rx[num].value & 0b11111110
            self.records[num]['value'].setFont(font_bold())
            self.records[num]['value'].setText(hex(self.preadu.rx[num].value)[2:])
            update_flag_termination(self.records[num], False)
        else:
            self.preadu.rx[num].value = self.preadu.rx[num].value | 1
            self.records[num]['value'].setFont(font_bold())
            self.records[num]['value'].setText(hex(self.preadu.rx[num].value)[2:])
            update_flag_termination(self.records[num], True)

    def action_plus(self, num):
        valore = int(self.records[num]['text'].text()) + 1
        # print "Valore: ", valore
        if valore > 31:
            valore = 31
        self.preadu.rx[num].set_attenuation(bound(valore))
        self.records[num]['value'].setFont(font_bold())
        self.records[num]['value'].setText(hex(self.preadu.rx[num].value)[2:])
        self.records[num]['text'].setText(str(self.preadu.rx[num].get_attenuation()))

    def action_minus(self, num):
        valore = int(self.records[num]['text'].text()) - 1
        if valore < 0:
            valore = 0
        self.preadu.rx[num].set_attenuation(bound(valore))
        self.records[num]['value'].setFont(font_bold())
        self.records[num]['value'].setText(hex(self.preadu.rx[num].value)[2:])
        self.records[num]['text'].setText(str(self.preadu.rx[num].get_attenuation()))

    def action_rfoff(self, num):
        self.preadu.rx[num].value = self.preadu.rx[num].value & 0b11111110
        self.records[num]['value'].setFont(font_bold())
        self.records[num]['value'].setText(hex(self.preadu.rx[num].value)[2:])
        update_flag_termination(self.records[num], False)

    def action_rfon(self, num):
        self.preadu.rx[num].value = self.preadu.rx[num].value | 1
        self.records[num]['value'].setFont(font_bold())
        self.records[num]['value'].setText(hex(self.preadu.rx[num].value)[2:])
        update_flag_termination(self.records[num], True)

    def decreaseAll(self):
        for i in range(self.inputs):
            self.action_minus(i)

    def increaseAll(self):
        for i in range(self.inputs):
            self.action_plus(i)

    def rfoffAll(self):
        for i in range(self.inputs):
            self.action_rfoff(i)

    def rfonAll(self):
        for i in range(self.inputs):
            self.action_rfon(i)

    def selection_change(self, valore):
        for num in range(self.inputs):
            self.preadu.rx[num].set_attenuation(bound(valore))
            self.records[num]['value'].setFont(font_bold())
            self.records[num]['value'].setText(hex(self.preadu.rx[num].value)[2:])
            self.records[num]['text'].setText(str(self.preadu.rx[num].get_attenuation()))

    def readConfiguration(self, tpm=None):
        if tpm is None:
            tpm = self.tpm
        while self.Busy:
            time.sleep(0.2)
        self.Busy = True
        tpm.tpm.tpm_preadu[0].read_configuration()  # TOP
        tpm.tpm.tpm_preadu[1].read_configuration()  # BOTTOM
        remap = list(np.flip(np.arange(8)) + 8) + list(np.arange(8)) + list(np.flip(np.arange(8))) + list(
            np.arange(8) + 8)
        preaduConf = []
        for i in range(32):
            value = tpm.tpm.tpm_preadu[(((i + 8) // 8) % 2)].channel_filters[remap[i]]
            preaduConf += [{'id': i,
                            'sn': "n/a",
                            'code': value,
                            'dsa': self.preadu.rx[i].code2att(value),
                            'version': self.preadu.rx[i].version}]
        self.Busy = False
        return preaduConf

    def apply_configuration(self):
        if self.tpm is not None:
            new_values = []
            for i in range(CHANNELS):
                new_values += [int("0x" + self.records[i]['value'].text(), 16)]
            self.write_configuration(new_values)

    def write_configuration(self, new_values=None):
        if self.tpm is not None:
            if new_values is None:
                new_values = []
                for i in range(CHANNELS):
                    new_values += [self.preadu.rx[i].value]
            g = 0
            while self.Busy:
                time.sleep(0.2)
            self.Busy = True
            for preadu in [1, 0]:
                for i in range(16):
                    self.tpm.tpm.tpm_preadu[preadu].channel_filters[i] = new_values[self.spi_remap[g]]
                    g = g + 1
            for preadu in [1, 0]:
                self.tpm.tpm.tpm_preadu[preadu].write_configuration()
            self.Busy = False
            self.reload()

    def reload(self):
        conf = self.readConfiguration()
        for i in range(32):
            self.preadu.rx[i].value = conf[i]['code']
        self.updateForm()

    def setTpm(self, tpm):
        self.tpm = tpm
        self.reload()

    def set_preadu_version(self, board_type=0):
        del self.preadu
        gc.collect()
        self.board_type = board_type
        if self.board_type == 0:
            self.preadu = preAduOptRx()
            print("PreADU 3.0 with Optical Receivers selected")
        elif self.board_type == 1:
            self.preadu = preAduOptRx()
            print("PreADU 2.1 with Optical Receivers selected")
        elif self.board_type == 2:
            self.preadu = preAduRf()
            print("PreADU 2.0 (RF) without optical receivers")
        elif self.board_type == 3:
            self.preadu = preAduSadino()
            print("PreADU 2.0b (RF SADino) with Mixed RF and Optical Rxs selected")
        self.adjustControls(board_type)
        self.reload()

    def adjustControls(self, board_type=0):
        if self.board_type == 0:
            table_names = "ADU#  Code      Attenuation          Fibre           RMS           dBm"
            self.label_legend_1.setText(table_names)
            self.label_legend_2.setText(table_names)
            self.label_legend_3.setText(table_names)
            self.label_legend_4.setText(table_names)
            self.button_rfon.setVisible(False)
            self.button_rfoff.setVisible(False)
            for i in range(CHANNELS):
                self.records[i]['hi'].setVisible(False)
                self.records[i]['lo'].setVisible(False)
                self.records[i]['rf'].setVisible(False)
                pos = self.records[i]['of'].geometry()
                wdt = pos.width()
                self.records[i]['of'].setGeometry((10 + 220 + (((i & 8) >> 3) * TABLE_HSPACE)),
                                                  pos.y(), pos.width(), pos.height())
                pos = self.records[i]['rms'].geometry()
                wdt = pos.width()
                self.records[i]['rms'].setGeometry(10 + 290 + (((i & 8) >> 3) * TABLE_HSPACE),
                                                   pos.y(), pos.width(), pos.height())
                pos = self.records[i]['power'].geometry()
                wdt = pos.width()
                self.records[i]['power'].setGeometry((10 + 350 + (((i & 8) >> 3) * TABLE_HSPACE)),
                                                     pos.y(), pos.width(), pos.height())
        else:
            table_names = "ADU#  Code      Attenuation               Bands"
            table_names += "             Rx      Fibre          RMS         dBm"
            self.label_legend_1.setText(table_names)
            self.label_legend_2.setText(table_names)
            self.label_legend_3.setText(table_names)
            self.label_legend_4.setText(table_names)
            self.button_rfon.setVisible(True)
            self.button_rfoff.setVisible(True)
            for i in range(CHANNELS):
                self.records[i]['hi'].setVisible(True)
                self.records[i]['lo'].setVisible(True)
                self.records[i]['rf'].setVisible(True)
                pos = self.records[i]['of'].geometry()
                wdt = pos.width()
                self.records[i]['of'].setGeometry((10 + 360 + (((i & 8) >> 3) * TABLE_HSPACE)),
                                                  pos.y(), pos.width(), pos.height())
                pos = self.records[i]['rms'].geometry()
                wdt = pos.width()
                self.records[i]['rms'].setGeometry(10 + 430 + (((i & 8) >> 3) * TABLE_HSPACE),
                                                   pos.y(), pos.width(), pos.height())
                pos = self.records[i]['power'].geometry()
                wdt = pos.width()
                self.records[i]['power'].setGeometry((10 + 480 + (((i & 8) >> 3) * TABLE_HSPACE)),
                                                     pos.y(), pos.width(), pos.height())

    def updateRms(self, rms):
        for num in range(self.inputs):
            self.records[num]['rms'].setText("%d" % int(round(rms[num])))
            with np.errstate(divide='ignore', invalid='ignore'):
                power = 10 * np.log10(np.power((rms[num] * (1.7 / 256.)), 2) / 400.) + 30 + 12
            if power == (-np.inf):
                power = -60
            self.records[num]['power'].setText("%3.1f" % power)
