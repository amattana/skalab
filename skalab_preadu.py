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

SIGNALS_MAP_FILENAME = "SignalMap/signals_map.txt"


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
                                90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), rf_map[0].strip() + ":")
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
                            90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "green", rf_map[1].strip())
    rec['of'] = create_flag(Dialog, 10 + 360 + (((idx & 8) >> 3) * TABLE_HSPACE),
                            90 + ((idx & 7) * TABLE_VSPACE) + (((idx & 16) >> 4) * 280), "cyan", rf_map[2].strip())
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


class AAVSOpticalRx:
    '''
    INAF SKA Optical Receiver
    (SKA-AAVS1)

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

        self._value_ = 4 + 128  # LowPassFilter, 16 dB of attenuation
        self.version = "AAVS1 OF-Rx"
        self.type = "RF-X"
        self.fw_map = {'preadu_id': 0, 'channel': 0, 'pol': 'n/a', 'adu_in': 0, 'tpm_in': 0}
        self.sn = 0

    def print_bit_description(self):
        for k in sorted(self.bit_string.keys()):
            print(k, ":", self.bit_string[k])

    def set_attenuation(self, att):
        self._value_ = (self._value_ & 0b111) + (att << 3)

    def get_attenuation(self):
        return (self._value_ & 0b11111000) >> 3

    def code2att(self, code):
        return (code & 0b11111000) >> 3

    def set_hipass(self):
        self._value_ = (self._value_ & 0b11111001) + 2

    def is_hipass(self):
        if (self._value_ & 0b10) == 2:
            return True
        else:
            return False

    def set_lopass(self):
        self._value_ = (self._value_ & 0b11111001) + 4

    def is_lopass(self):
        if (self._value_ & 0b100) == 4:
            return True
        else:
            return False

    def terminate(self):
        self._value_ = (self._value_ & 0b11111110) + 1

    def is_terminated(self):
        if self._value_ & 1:
            return True
        else:
            return False

    def rf_enable(self):
        self._value_ = (self._value_ & 0b11111110)

    def get_reg_value(self):
        return self._value_

    def set_reg_value(self, value):
        self._value_ = value


class NewSKAOpticalRx:
    '''
    INAF NEW SKA Optical Receiver
    (SKA-AAVS3 for TPM 1.6)

    No 50 Ohm Termination Capability, Only one pass-band filter (50-350MHz)

    LSB - *,*,*,1dB,2dB,4dB,8dB,16dB - MSB
    '''
    def __init__(self):
        self.bit_string = {}
        self.bit_string['b0'] = "Spare / Unused"
        self.bit_string['b1'] = "Spare / Unused"
        self.bit_string['b2'] = "Spare / Unused"
        self.bit_string['b3'] = "Attenuation 1dB"
        self.bit_string['b4'] = "Attenuation 2dB"
        self.bit_string['b5'] = "Attenuation 4dB"
        self.bit_string['b6'] = "Attenuation 8dB"
        self.bit_string['b7'] = "Attenuation 16dB"

        self._value_ = 0  # register value
        self.version = "AAVS3 OF-Rx"
        self.type = "RF-X"
        self.fw_map = {'preadu_id': 0, 'channel': 0, 'pol': 'n/a', 'adu_in': 0, 'tpm_in': 0}
        self.sn = 0

    def print_bit_description(self):
        for k in sorted(self.bit_string.keys()):
            print(k, ":", self.bit_string[k])

    def set_attenuation(self, att):
        self._value_ = (self._value_ & 0b111) + (att << 3)

    def get_attenuation(self):
        return (self._value_ & 0b11111000) >> 3

    def code2att(self, code):
        return (code & 0b11111000) >> 3

    def get_reg_value(self):
        return self._value_

    def set_reg_value(self, value):
        self._value_ = value


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

        self._value_ = 16 + 128  # LowPassFilter, 16 dB of attenuation
        self.version = "RF-Rx"
        self.type = "RF-X"
        self.fw_map = {'preadu_id': 0, 'channel': 0, 'pol': 'n/a', 'adu_in': 0, 'tpm_in': 0}
        self.sn = 0

    def print_bit_description(self):
        for k in sorted(self.bit_string.keys()):
            print(k, ":", self.bit_string[k])

    def set_attenuation(self, att):
        #print format(self.value, '08b'), att,
        self._value_ = self._value_ & 0b00010101
        self._value_ = self._value_ + ((att & 0b1) << 6)  # 1dB
        self._value_ = self._value_ + (att & 0b10)  # 2dB
        self._value_ = self._value_ + ((att & 0b100) << 1) # 4dB
        self._value_ = self._value_ + ((att & 0b1000) << 2)  # 8dB
        self._value_ = self._value_ + ((att & 0b10000) << 3)  # 16dB
        #print format(self.value, '08b')

    def get_attenuation(self):
        a = ((self._value_ & 0b10) >> 1) * 2
        a += ((self._value_ & 0b1000) >> 3) * 4
        a += ((self._value_ & 0b100000) >> 5) * 8
        a += ((self._value_ & 0b1000000) >> 6) * 1
        a += ((self._value_ & 0b10000000) >> 7) * 16
        return a

    def code2att(self, code):
        a = ((code & 0b10) >> 1) * 2
        a += ((code & 0b1000) >> 3) * 4
        a += ((code & 0b100000) >> 5) * 8
        a += ((code & 0b1000000) >> 6) * 1
        a += ((code & 0b10000000) >> 7) * 16
        return a

    def set_hipass(self):
        self._value_ = (self._value_ & 0b11101011) + 4

    def is_hipass(self):
        if (self._value_ & 0b100) == 4:
            return True
        else:
            return False

    def set_lopass(self):
        self._value_ = (self._value_ & 0b11101011) + 16

    def is_lopass(self):
        if (self._value_ & 0b10000) == 16:
            return True
        else:
            return False

    def terminate(self):
        self._value_ = (self._value_ & 0b11111110) + 1

    def is_terminated(self):
        if self._value_ & 1:
            return True
        else:
            return False

    def rf_enable(self):
        self._value_ = (self._value_ & 0b11111110)

    def get_reg_value(self):
        return self._value_

    def set_reg_value(self, value):
        self._value_ = value


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
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]

        # TPM input fibres 5-8, ADU Input 16-23
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]

        # TPM input fibres 16-13, ADU Input 8-15
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]

        # TPM input fibres 12-09, ADU Input 24-31
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]

        for i in range(32):
            self.rx[i].sn = i

        self.spi_remap = np.arange(32)

    def set_rx_attenuation(self, nrx, att):
        self.rx[self.spi_remap[nrx]].set_attenuation(bound(att))

    def get_rx_attenuation(self, nrx):
        return self.rx[self.spi_remap[nrx]].get_attenuation()

    def set_rx_hi_filter(self, nrx):
        self.rx[self.spi_remap[nrx]].set_hipass()

    def set_rx_lo_filter(self, nrx):
        self.rx[self.spi_remap[nrx]].set_lopass()

    def is_lopass(self, nrx):
        return self.rx[self.spi_remap[nrx]].is_lopass()

    def is_hipass(self, nrx):
        return self.rx[self.spi_remap[nrx]].is_hipass()

    def is_terminated(self, nrx):
        return self.rx[self.spi_remap[nrx]].is_terminated()

    def set_all_hi_filter(self):
        for i in range(self.nof_rx):
            self.rx[self.spi_remap[i]].set_hipass()

    def set_all_lo_filter(self):
        for i in range(self.nof_rx):
            self.rx[self.spi_remap[i]].set_lopass()

    def set_all_rx_attenuation(self, att):
        for i in range(self.nof_rx):
            self.rx[self.spi_remap[i]].set_attenuation(bound(att))

    def get_register_value(self, nrx):
        return self.rx[self.spi_remap[nrx]].get_reg_value()

    def set_register_value(self, nrx, value):
        return self.rx[self.spi_remap[nrx]].set_reg_value(value=value)

    def set_spi_conf(self, nrx, preadu_id, channel_filter, pol, adu_in, tpm_in):
        self.rx[self.spi_remap[nrx]].fw_map['preadu_id'] = preadu_id
        self.rx[self.spi_remap[nrx]].fw_map['channel_filter'] = channel_filter
        self.rx[self.spi_remap[nrx]].fw_map['pol'] = pol
        self.rx[self.spi_remap[nrx]].fw_map['adu_in'] = adu_in
        self.rx[self.spi_remap[nrx]].fw_map['tpm_in'] = tpm_in

    def get_spi_conf(self, nrx):
        return self.rx[self.spi_remap[nrx]].fw_map


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
        self.rx += [AAVSOpticalRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]

        # TPM input fibres 16-13, ADU Input 8-15
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]

        # TPM input fibres 5-8, ADU Input 16-23
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]

        # TPM input fibres 12-09, ADU Input 24-31
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]
        self.rx += [InafSkaRfRx()]
        self.rx += [AAVSOpticalRx()]

        for i in range(32):
            self.rx[i].sn = i
        self.spi_remap = np.arange(32)

    def set_rx_attenuation(self, nrx, att):
        #print("PRIMA\t", nrx, self.rx[nrx].sn, self.rx[nrx].version, "DSA", self.rx[nrx].get_attenuation(), "OLD VALUE", self.rx[nrx].value, "SET DSA", att)
        self.rx[self.spi_remap[nrx]].set_attenuation(bound(att))
        #print(" DOPO\t", nrx, self.rx[nrx].sn, self.rx[nrx].version, "DSA", self.rx[nrx].get_attenuation(), "NEW VALUE", self.rx[nrx].value)

    def get_rx_attenuation(self, nrx):
        return self.rx[self.spi_remap[nrx]].get_attenuation()

    def set_rx_hi_filter(self, nrx):
        self.rx[self.spi_remap[nrx]].set_hipass()

    def set_rx_lo_filter(self, nrx):
        self.rx[self.spi_remap[nrx]].set_lopass()

    def is_lopass(self, nrx):
        return self.rx[self.spi_remap[nrx]].is_lopass()

    def is_hipass(self, nrx):
        return self.rx[self.spi_remap[nrx]].is_hipass()

    def is_terminated(self, nrx):
        return self.rx[self.spi_remap[nrx]].is_terminated()

    def set_all_hi_filter(self):
        for i in range(self.nof_rx):
            self.rx[self.spi_remap[i]].set_hipass()

    def set_all_lo_filter(self):
        for i in range(self.nof_rx):
            self.rx[self.spi_remap[i]].set_lopass()

    def set_all_rx_attenuation(self, att):
        for i in range(self.nof_rx):
            self.rx[self.spi_remap[i]].set_attenuation(bound(att))

    def get_register_value(self, nrx):
        return self.rx[self.spi_remap[nrx]].get_reg_value()

    def set_register_value(self, nrx, value):
        return self.rx[self.spi_remap[nrx]].set_reg_value(value=value)

    def set_spi_conf(self, nrx, preadu_id, channel_filter, pol, adu_in, tpm_in):
        self.rx[self.spi_remap[nrx]].fw_map['preadu_id'] = preadu_id
        self.rx[self.spi_remap[nrx]].fw_map['channel_filter'] = channel_filter
        self.rx[self.spi_remap[nrx]].fw_map['pol'] = pol
        self.rx[self.spi_remap[nrx]].fw_map['adu_in'] = adu_in
        self.rx[self.spi_remap[nrx]].fw_map['tpm_in'] = tpm_in

    def get_spi_conf(self, nrx):
        return self.rx[self.spi_remap[nrx]].fw_map


class preAduAAVS1:
    '''
    A preADU board having INAF SKA optical WDM receivers
    The receiver bit mapping is the same for RF1 and RF2
    SPI lane chain from Rx-01 to Rx-8
    '''
    def __init__(self):
        self.nof_rx = 32
        self.rx = []
        for i in range(self.nof_rx):
            self.rx += [AAVSOpticalRx()]
            self.rx[i].sn = i

        # self.spi_remap = [23, 22, 21, 20, 19, 18, 17, 16,
        #                   7, 6, 5, 4, 3, 2, 1, 0,
        #                   8, 9, 10, 11, 12, 13, 14, 15,
        #                   24, 25, 26, 27, 28, 29, 30, 31]
        self.spi_remap = np.arange(32)

    def set_rx_attenuation(self, nrx, att):
        self.rx[self.spi_remap[nrx]].set_attenuation(bound(att))

    def get_rx_attenuation(self, nrx):
        return self.rx[self.spi_remap[nrx]].get_attenuation()

    def set_rx_hi_filter(self, nrx):
        self.rx[self.spi_remap[nrx]].set_hipass()

    def set_rx_lo_filter(self, nrx):
        self.rx[self.spi_remap[nrx]].set_lopass()

    def is_lopass(self, nrx):
        return self.rx[self.spi_remap[nrx]].is_lopass()

    def is_hipass(self, nrx):
        return self.rx[self.spi_remap[nrx]].is_hipass()

    def is_terminated(self, nrx):
        return self.rx[self.spi_remap[nrx]].is_terminated()

    def set_all_hi_filter(self):
        for i in range(self.nof_rx):
            self.rx[self.spi_remap[i]].set_hipass()

    def set_all_lo_filter(self):
        for i in range(self.nof_rx):
            self.rx[self.spi_remap[i]].set_lopass()

    def set_all_rx_attenuation(self, att):
        for i in range(self.nof_rx):
            self.rx[self.spi_remap[i]].set_attenuation(bound(att))

    def get_register_value(self, nrx):
        return self.rx[self.spi_remap[nrx]].get_reg_value()

    def set_register_value(self, nrx, value):
        return self.rx[self.spi_remap[nrx]].set_reg_value(value=value)

    def set_spi_conf(self, nrx, preadu_id, channel_filter, pol, adu_in, tpm_in):
        self.rx[self.spi_remap[nrx]].fw_map['preadu_id'] = preadu_id
        self.rx[self.spi_remap[nrx]].fw_map['channel_filter'] = channel_filter
        self.rx[self.spi_remap[nrx]].fw_map['pol'] = pol
        self.rx[self.spi_remap[nrx]].fw_map['adu_in'] = adu_in
        self.rx[self.spi_remap[nrx]].fw_map['tpm_in'] = tpm_in

    def get_spi_conf(self, nrx):
        return self.rx[self.spi_remap[nrx]].fw_map


class preAduAAVS3:
    '''
    A preADU board with embedded optical WDM receivers
    The receiver bit mapping is the same for RF1 and RF2 and Ctrl only DSA
    Reversed RF1-RF2 (RF connectors placed to the opposite layer)
    Funny SPI lane trace (15-16-13-14-11-12-9-10-7-8-5-6-3-4-1-2)
    It will be corrected in the next version
    '''
    def __init__(self):
        self.nof_rx = 32
        self.rx = []
        for i in range(self.nof_rx):
            self.rx += [NewSKAOpticalRx()]
            self.rx[i].sn = i

        self.spi_remap = [1, 0, 3, 2, 5, 4, 7, 6,
                          17, 16, 19, 18, 21, 20, 23, 22,
                          30, 31, 28, 29, 26, 27, 24, 25,
                          14, 15, 12, 13, 10, 11, 8, 9]

    # E' corretto che mappatura SPI appartenga alla classe PREADU di questo livello
    # e che gli altri la utilizzino tramite lei
    #
    # Lettura e Scrittura qui devono essre coerenti

    def set_rx_attenuation(self, nrx, att):
        self.rx[self.spi_remap[nrx]].set_attenuation(bound(att))

    def get_rx_attenuation(self, nrx):
        return self.rx[self.spi_remap[nrx]].get_attenuation()

    def set_all_rx_attenuation(self, att):
        for i in range(self.nof_rx):
            self.rx[self.spi_remap[i]].set_attenuation(bound(att))

    def get_register_value(self, nrx):
        return self.rx[self.spi_remap[nrx]].get_reg_value()

    def set_register_value(self, nrx, value):
        return self.rx[self.spi_remap[nrx]].set_reg_value(value=value)

    def set_spi_conf(self, nrx, preadu_id, channel_filter, pol, adu_in, tpm_in):
        self.rx[self.spi_remap[nrx]].fw_map['preadu_id'] = preadu_id
        self.rx[self.spi_remap[nrx]].fw_map['channel_filter'] = channel_filter
        self.rx[self.spi_remap[nrx]].fw_map['pol'] = pol
        self.rx[self.spi_remap[nrx]].fw_map['adu_in'] = adu_in
        self.rx[self.spi_remap[nrx]].fw_map['tpm_in'] = tpm_in

    def get_spi_conf(self, nrx):
        return self.rx[self.spi_remap[nrx]].fw_map


class Preadu(object):
    def __init__(self, parent, tpm=None, board_version="3.0", debug=0):
        """ Initialise main window """
        super(Preadu, self).__init__()

        self.board_version = board_version
        self.debug = debug
        self.tpm = tpm
        self.Busy = False  # UCP Communication Token
        self.write_armed = False  # Tells the top layer (skalab_live) that a write operation is ready to go

        self.inputs = CHANNELS
        self.rf_map = read_routing_table("./SignalMap/TPM_AAVS1.txt")
        if self.board_version == "1.0":
            self.preadu = preAduRf()
            print("RF PreADU without optical receivers")
        elif self.board_version == "1.1":
            self.preadu = preAduSadino()
            print("SADino preADU with Mixed RF and AAVS1 Like RF Rxs selected")
        elif self.board_version == "2.0":
            self.preadu = preAduAAVS1()
            print("AAVS1 PreADU with Optical WDM Receivers selected")
        elif self.board_version == "3.0":
            self.preadu = preAduAAVS3()
            self.rf_map = read_routing_table("./SignalMap/TPM_AAVS3.txt")
            print("New PreADU with Embedded Optical WDM Receivers selected")

        for spimap in self.rf_map:
            self.preadu.set_spi_conf(nrx=int(spimap[0]),
                                     preadu_id=int(spimap[3]),
                                     channel_filter=int(spimap[4]),
                                     pol=spimap[1], adu_in=spimap[0], tpm_in=spimap[2])

        self.spi_remap = self.preadu.spi_remap

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

        self.records = []
        for i in range(self.inputs):
            self.records += [create_record(parent, self.rf_map[i])]

        self.label_comments = QtWidgets.QLabel(parent)
        self.label_comments.setGeometry(QtCore.QRect(20, 630, DIALOG_WIDTH - 20, 21))
        self.label_comments.setAlignment(QtCore.Qt.AlignCenter)
        self.adjustControls(self.board_version)
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
            register_value = int(self.preadu.get_register_value(nrx=num))
            #self.preadu.rx[num].value = register_value # ????
            self.records[num]['reg_val'] = register_value
            self.records[num]['value'].setText(str(hex(register_value))[2:])
            # Attenuation
            #print(num, register_value, str(hex(register_value)), str(self.preadu.get_rx_attenuation(num)))
            update_text(self.records[num]['text'], str(self.preadu.get_rx_attenuation(nrx=num)))
            #update_text(self.records[num]['text'], str((register_value & 0b11111000) >> 3))
            if not self.board_version == "3.0":
                update_flag_lo_filter(self.records[num], self.preadu.is_lopass(nrx=num))
                update_flag_hi_filter(self.records[num], self.preadu.is_hipass(nrx=num))
                update_flag_termination(self.records[num], self.preadu.is_terminated(nrx=num))
            self.records[num]['value'].setFont(font_normal())
        if self.debug:
            for num in range(self.inputs):
                print(format(num, '02d'), format(self.preadu.get_register_value(nrx=num), '08b'), "ATT:",
                      self.preadu.get_rx_attenuation(nrx=num), ", LO:", self.preadu.is_lopass(nrx=num),
                      ", HI:", self.preadu.is_hipass(nrx=num), ", RF-ENABLED: ", self.preadu.is_terminated(nrx=num))

    def set_hi(self):
        for num in range(self.inputs):
            self.records[num]['lo'].setStyleSheet("background-color: rgb(255, 255, 0);")
            self.records[num]['hi'].setStyleSheet("background-color: rgb(0, 170, 0);")
            self.preadu.set_hipass(rx=num)
            #conf_value = ('0x' + self.records[num]['value'].text()).toInt(16)[0] & 0b11111011
            #conf_value = conf_value | 0b10
            self.records[num]['value'].setFont(font_bold())
            self.records[num]['value'].setText(hex(self.preadu.get_register_value(nrx=num))[2:])
            update_flag_lo_filter(self.records[num], self.preadu.is_lopass(rx=num))
            update_flag_hi_filter(self.records[num], self.preadu.is_hipass(rx=num))
            #update_flag(self.records[num], (conf_value & 0b111))

    def set_lo(self):
        for num in range(self.inputs):
            self.records[num]['hi'].setStyleSheet("background-color: rgb(255, 255, 0);")
            self.records[num]['lo'].setStyleSheet("background-color: rgb(0, 170, 0);")
            self.preadu.set_lopass(rx=num)
            #conf_value=('0x'+self.records[num]['value'].text()).toInt(16)[0] & 0b11111101
            #conf_value=conf_value | 0b100
            self.records[num]['value'].setFont(font_bold())
            self.records[num]['value'].setText(hex(self.preadu.get_register_value(nrx=num))[2:])
            update_flag_lo_filter(self.records[num], self.preadu.is_lopass(rx=num))
            update_flag_hi_filter(self.records[num], self.preadu.is_hipass(rx=num))
            #update_flag(self.records[num], (conf_value & 0b111) )

    def set_rf(self, num):
        if self.board_version < 3:
            if (self.preadu.get_register_value(nrx=num) & 1) == 1:
                self.preadu.set_register_value(nrx=num, value=(self.preadu.get_register_value(nrx=num) & 0b11111110))
                self.records[num]['value'].setFont(font_bold())
                self.records[num]['value'].setText(hex(self.preadu.get_register_value(nrx=num))[2:])
                update_flag_termination(self.records[num], False)
            else:
                self.preadu.set_register_value(nrx=num, value=(self.preadu.get_register_value(nrx=num) | 1))
                self.records[num]['value'].setFont(font_bold())
                self.records[num]['value'].setText(hex(self.preadu.get_register_value(nrx=num))[2:])
                update_flag_termination(self.records[num], True)

    def action_plus(self, num):
        valore = int(self.records[num]['text'].text()) + 1
        # print "Valore: ", valore
        if valore > 31:
            valore = 31
        self.preadu.set_rx_attenuation(nrx=num, att=bound(valore))
        self.records[num]['value'].setFont(font_bold())
        self.records[num]['value'].setText(hex(self.preadu.get_register_value(nrx=num))[2:])
        self.records[num]['text'].setText(str(self.preadu.get_rx_attenuation(nrx=num)))

    def action_minus(self, num):
        valore = int(self.records[num]['text'].text()) - 1
        if valore < 0:
            valore = 0
        self.preadu.set_rx_attenuation(nrx=num, att=bound(valore))
        self.records[num]['value'].setFont(font_bold())
        self.records[num]['value'].setText(hex(self.preadu.get_register_value(nrx=num))[2:])
        self.records[num]['text'].setText(str(self.preadu.get_rx_attenuation(nrx=num)))

    def action_rfoff(self, num):
        value = self.preadu.get_register_value(nrx=num) & 0b11111110
        self.preadu.set_register_value(nrx=num, value=value)
        self.records[num]['value'].setFont(font_bold())
        self.records[num]['value'].setText(hex(self.preadu.get_register_value(nrx=num))[2:])
        update_flag_termination(self.records[num], False)

    def action_rfon(self, num):
        value = self.preadu.get_register_value(nrx=num) | 1
        self.preadu.set_register_value(nrx=num, value=value)
        self.records[num]['value'].setFont(font_bold())
        self.records[num]['value'].setText(hex(self.preadu.get_register_value(nrx=num))[2:])
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
            self.preadu.set_rx_attenuation(nrx=num, att=(bound(valore)))
            self.records[num]['value'].setFont(font_bold())
            self.records[num]['value'].setText(hex(self.preadu.get_register_value(nrx=num))[2:])
            self.records[num]['text'].setText(str(self.preadu.get_rx_attenuation(nrx=num)))

    def readConfiguration(self, tpm=None):
        if tpm is None:
            tpm = self.tpm
        preaduConf = []
        if tpm is not None:
            tpm.tpm.tpm_preadu[0].read_configuration()  # TOP
            tpm.tpm.tpm_preadu[1].read_configuration()  # BOTTOM
            for i in range(32):
                fw_map = self.preadu.get_spi_conf(nrx=i)
                preadu_id = int(fw_map['preadu_id'])
                channel_filter = int(fw_map['channel_filter'])
                pol = fw_map['pol']
                value = self.tpm.tpm.tpm_preadu[preadu_id].channel_filters[channel_filter]
                preaduConf += [{'id': i,
                                'sn': "n/a",
                                'code': value,
                                'preadu_id': preadu_id,
                                'channel_filter': channel_filter,
                                'pol': pol,
                                'dsa': self.preadu.get_rx_attenuation(i),
                                'version': self.preadu.rx[i].version}]
        #print("\nConfiguration READ:")
        #for conf in preaduConf:
        #    print(conf)
        return preaduConf

    def apply_configuration(self):
        if self.tpm is not None:
            for i in range(CHANNELS):
                self.preadu.set_register_value(nrx=i, value=int("0x" + self.records[i]['value'].text(), 16))
            self.write_armed = True

    def write_configuration(self):
        self.Busy = True
        if self.tpm is not None:
            for i in range(32):
                value = self.preadu.get_register_value(nrx=i)
                fw_map = self.preadu.get_spi_conf(nrx=i)
                preadu_id = int(fw_map['preadu_id'])
                channel_filter = int(fw_map['channel_filter'])
                #print("PREADU ID: %d, CHAN-FILTER %02d, RMS-INDEX %d, CODE %d" % (spi_map[0], spi_map[1], i, value))
                self.tpm.tpm.tpm_preadu[preadu_id].channel_filters[channel_filter] = value
            for preadu_id in [1, 0]:
                self.tpm.tpm.tpm_preadu[preadu_id].write_configuration()
            self.reload()
        self.write_armed = False
        self.Busy = False

    def reload(self):
        conf = self.readConfiguration()
        if not conf == []:
            for i in range(32):
                self.preadu.set_register_value(nrx=i, value=conf[i]['code'])
        else:
            for i in range(32):
                self.preadu.set_register_value(nrx=i, value=255)
        self.updateForm()

    def setTpm(self, tpm):
        self.tpm = tpm
        self.reload()

    def set_preadu_version(self, board_type="3.0"):
        del self.preadu
        gc.collect()
        self.board_version = board_type
        self.rf_map = read_routing_table("./SignalMap/TPM_AAVS1.txt")
        if self.board_version == "1.0":
            self.preadu = preAduRf()
            print("RF PreADU without optical receivers")
        elif self.board_version == "1.1":
            self.preadu = preAduSadino()
            print("SADino preADU with Mixed RF and AAVS1 Like RF Rxs selected")
        elif self.board_version == "2.0":
            self.preadu = preAduAAVS1()
            print("AAVS1 PreADU with Optical WDM Receivers selected")
        elif self.board_version == "3.0":
            self.preadu = preAduAAVS3()
            self.rf_map = read_routing_table("./SignalMap/TPM_AAVS3.txt")
            print("New PreADU with Embedded Optical WDM Receivers selected")
        for spimap in self.rf_map:
            self.preadu.set_spi_conf(nrx=int(spimap[0]), preadu_id=int(spimap[3]), channel_filter=int(spimap[4]),
                                     pol=spimap[1], adu_in=spimap[0], tpm_in=spimap[2])

        self.adjustControls(board_type)
        self.reload()

    def adjustControls(self, board_type=0):
        if float(self.board_version.split(".")[0]) > 2:
            table_names = "ADU#  Code      Attenuation           Rx             Fibre       RMS           dBm"
            self.label_legend_1.setText(table_names)
            self.label_legend_2.setText(table_names)
            self.label_legend_3.setText(table_names)
            self.label_legend_4.setText(table_names)
            self.button_rfon.setVisible(False)
            self.button_rfoff.setVisible(False)
            for i in range(CHANNELS):
                self.records[i]['hi'].setVisible(False)
                self.records[i]['lo'].setVisible(False)
                self.records[i]['rf'].setVisible(True)
                self.records[i]['rf'].setText(self.rf_map[i][1])
                pos = self.records[i]['rf'].geometry()
                wdt = pos.width()
                self.records[i]['rf'].setGeometry((10 + 220 + (((i & 8) >> 3) * TABLE_HSPACE)),
                                                  pos.y(), pos.width(), pos.height())
                self.records[i]['of'].setText(self.rf_map[i][2])
                pos = self.records[i]['of'].geometry()
                wdt = pos.width()
                self.records[i]['of'].setGeometry((10 + 290 + (((i & 8) >> 3) * TABLE_HSPACE)),
                                                  pos.y(), pos.width(), pos.height())
                pos = self.records[i]['rms'].geometry()
                wdt = pos.width()
                self.records[i]['rms'].setGeometry(10 + 350 + (((i & 8) >> 3) * TABLE_HSPACE),
                                                   pos.y(), pos.width(), pos.height())
                pos = self.records[i]['power'].geometry()
                wdt = pos.width()
                self.records[i]['power'].setGeometry((10 + 400 + (((i & 8) >> 3) * TABLE_HSPACE)),
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
                self.records[i]['rf'].setText(self.rf_map[i][1])
                pos = self.records[i]['rf'].geometry()
                wdt = pos.width()
                self.records[i]['rf'].setGeometry((10 + 310 + (((i & 8) >> 3) * TABLE_HSPACE)),
                                                  pos.y(), pos.width(), pos.height())
                self.records[i]['of'].setText(self.rf_map[i][2])
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
