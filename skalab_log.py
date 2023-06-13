import logging
import os.path
from logging.handlers import TimedRotatingFileHandler
from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import time
import datetime
from pathlib import Path
default_app_dir = str(Path.home()) + "/.skalab/LOG"
from threading import Thread


class QTextEditLogger(logging.Handler):
    def __init__(self, parent, level=logging.INFO, caption=None):
        super().__init__()
        self.widget = QtWidgets.QTextEdit(parent)
        self.widget.setFont(QtGui.QFont("Courier New", 10))
        self.widget.setStyleSheet("background-color: rgb(255, 255, 255);")
        self.widget.setReadOnly(True)
        self.level = level
        self.logname = ""
        self.caption = caption
        self.total = 0
        self.msgQueue = []

        html_header = "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" "
        html_header += "\"http://www.w3.org/TR/REC-html40/strict.dtd\"><html><head>"
        html_header += "<meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">p, li "
        html_header += "{ white-space: pre-wrap; }</style></head><body style=\" font-family:\"Courier\";"
        html_header += "font-size:11pt; font-weight:400; font-style:normal;\">"
        self.widget.insertHtml(html_header)

        # print("Start Thread Log: ", self.logname, ", Level:", self.level)

    def emit(self, record):
        self.msgQueue.append([record.levelno, record.levelname, self.format(record)])

    def clear(self):
        self.widget.clear()

    def updateBox(self, level, name, msg):
        if (level == self.level) or (self.level == logging.INFO):
            fancymsg = ""
            if level == logging.INFO:
                fancymsg += "\n<span style='font-weight:600; color:#22b80e;'>" + msg + "</span><br>"
            elif level == logging.ERROR:
                fancymsg += "\n<span style='font-weight:600; color:#ff0000;'>" + msg + "</span><br>"
            else:
                fancymsg += "\n<span style='font-weight:600; color:#ff7800;'>" + msg + "</span><br>"

            self.widget.insertHtml(fancymsg)
            self.widget.moveCursor(QtGui.QTextCursor.End)
            if self.caption is not None:
                self.total = self.total + 1
                self.caption.setTabText(2, name[0] + name[1:].lower() + "s  cnt:%s" % str(self.total).rjust(3, " ") + " (*)")


class SkalabLog(QtWidgets.QMainWindow):
    """ SkaLab Log class """
    signalLogInfo = QtCore.pyqtSignal()
    signalLogWarning = QtCore.pyqtSignal()
    signalLogError = QtCore.pyqtSignal()

    def __init__(self, parent, logname=None, profile=None):
        super().__init__(parent=None)
        self.wg = parent
        self.qtabLog = QtWidgets.QTabWidget(self.wg)
        self.size = self.wg.geometry()
        self.qtabLog.setGeometry(QtCore.QRect(10, 10, self.size.width() - 10, self.size.height() - 10))
        _translate = QtCore.QCoreApplication.translate
        self.qtabLog.setAutoFillBackground(False)
        self.qtabLog.setStyleSheet("")
        self.tabLog = QtWidgets.QWidget(self.wg)
        self.tabLog.setStyleSheet("")
        self.qtabLog.addTab(self.tabLog, "")
        self.qtabLog.setTabText(self.qtabLog.indexOf(self.tabLog), _translate("Form", "Log   "))
        self.tabWarning = QtWidgets.QWidget()
        self.qtabLog.addTab(self.tabWarning, "")
        self.qtabLog.setTabText(self.qtabLog.indexOf(self.tabWarning), _translate("Form", "Warnings   "))
        self.tabError = QtWidgets.QWidget()
        self.qtabLog.addTab(self.tabError, "")
        self.qtabLog.setTabText(self.qtabLog.indexOf(self.tabError), _translate("Form", "Errors   cnt: 0  "))
        self.qbutton_clear_log = QtWidgets.QPushButton(self.wg)
        self.qbutton_clear_log.setGeometry(QtCore.QRect(self.size.width() - 81, 11, 71, 24))
        self.qbutton_clear_log.setStatusTip("")
        self.qbutton_clear_log.setWhatsThis("")
        self.qbutton_clear_log.setToolTip(_translate("Form", "Clear Text on the Current Tab"))
        self.qbutton_clear_log.setText(_translate("Form", "Clear"))
        self.qbutton_clear_log.clicked.connect(self.clearLog)
        self.qbutton_reset_error_cnt = QtWidgets.QPushButton(self.wg)
        self.qbutton_reset_error_cnt.setGeometry(QtCore.QRect(self.size.width() - 181, 11, 71, 24))
        self.qbutton_reset_error_cnt.setToolTipDuration(-1)
        self.qbutton_reset_error_cnt.setStatusTip("")
        self.qbutton_reset_error_cnt.setObjectName("qbutton_reset_error_cnt")
        self.qbutton_reset_error_cnt.setToolTip(_translate("Form", "Reset Error Counter"))
        self.qbutton_reset_error_cnt.setText(_translate("Form", "Reset"))
        self.qbutton_reset_error_cnt.clicked.connect(self.resetCnt)
        self.qtabLog.currentChanged.connect(self.logChanged)

        if logname is not None:
            self.logger = logging.getLogger(logname)
        else:
            self.logger = logging.getLogger('root')
        formatter = logging.Formatter("%(asctime)-25s %(levelname)s - %(threadName)s - %(message)s")
        logging.Formatter.converter = time.gmtime
        self.logger.handlers = []

        # Set file handler
        logname = default_app_dir + "/log"
        if profile is not None:
            if 'log' in profile[profile['Base']['app']].keys():
                logname = profile[profile['Base']['app']]['log']
                if not logname[-1] == "/":
                    logname = logname + "/"
                logname = logname + profile['Base']['app']
        else:
            profile = {'Base': {'app': "TEST"}}
            logname = "TEST"
        pname = Path(logname)
        pname.mkdir(parents=True, exist_ok=True)
        fname = logname + "/" + logname[logname.rfind("/") + 1:].lower() + \
                datetime.datetime.strftime(datetime.datetime.utcnow(), "_log_%Y-%m-%d_%H%M%S.txt")
        self.file_handler = TimedRotatingFileHandler(fname, when="h", interval=1, backupCount=180, utc=True)
        self.file_handler.setFormatter(formatter)
        self.file_handler.setLevel(logging.INFO)
        self.logger.addHandler(self.file_handler)

        self.logInfo = QTextEditLogger(self, level=logging.INFO)
        self.logInfo.logname = profile['Base']['app']
        self.logInfo.setFormatter(formatter)
        self.logger.addHandler(self.logInfo)
        layoutInfo = QtWidgets.QVBoxLayout()
        layoutInfo.addWidget(self.logInfo.widget)
        self.tabLog.setLayout(layoutInfo)

        self.logWarning = QTextEditLogger(self, level=logging.WARNING)
        self.logWarning.logname = profile['Base']['app']
        self.logWarning.setFormatter(formatter)
        self.logger.addHandler(self.logWarning)
        layoutWarning = QtWidgets.QVBoxLayout()
        layoutWarning.addWidget(self.logWarning.widget)
        self.tabWarning.setLayout(layoutWarning)

        self.logError = QTextEditLogger(self, level=logging.ERROR, caption=self.qtabLog)
        self.logError.logname = profile['Base']['app']
        self.logError.setFormatter(formatter)
        self.logger.addHandler(self.logError)
        layoutError = QtWidgets.QVBoxLayout()
        layoutError.addWidget(self.logError.widget)
        self.tabError.setLayout(layoutError)

        # Set console handler
        # self.console_handler = logging.StreamHandler(stream=sys.stdout)
        # self.console_handler.setFormatter(formatter)
        # self.console_handler.setLevel(logging.INFO)
        # self.logger.addHandler(self.console_handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.logger.info("Log File: " + fname)
        self.logger.info("Logging Time is set to UTC")

        self.stopThread = False
        self.procWriteLog = Thread(target=self.procLog)
        self.procWriteLog.start()
        self.signalLogInfo.connect(self.writeLogInfo)
        self.signalLogWarning.connect(self.writeLogWarning)
        self.signalLogError.connect(self.writeLogError)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def logChanged(self):
        if "(*)" in self.qtabLog.tabText(self.qtabLog.currentIndex()):
            self.qtabLog.setTabText(self.qtabLog.currentIndex(), self.qtabLog.tabText(self.qtabLog.currentIndex())[:-3])

    def clearLog(self):
        if self.qtabLog.currentIndex() == 0:
            self.logInfo.clear()
        elif self.qtabLog.currentIndex() == 1:
            self.logWarning.clear()
        else:
            self.logError.clear()

    def resetCnt(self):
        self.logError.total = 0
        self.qtabLog.setTabText(2, "Errors  cnt:  0")

    def stopLog(self):
        self.stopThread = True

    def testFunc(self):
        self.qbutton_test = QtWidgets.QPushButton(self.wg)
        self.qbutton_test.setGeometry(QtCore.QRect(300, 11, 71, 24))
        self.qbutton_test.clicked.connect(self.testLog)
        self.qbutton_test.setText("TEST")

    def testLog(self):
        self.logger.info("TESTING INFO")
        self.logger.warning("TESTING WARNING")
        self.logger.error("TESTING ERROR")

    def testClose(self):
        self.qbutton_close = QtWidgets.QPushButton(self.wg)
        self.qbutton_close.setGeometry(QtCore.QRect(400, 11, 131, 24))
        self.qbutton_close.clicked.connect(self.stopLog)
        self.qbutton_close.setText("TERMINATE")

    def procLog(self):
        while True:
            if not self.stopThread:
                if self.logInfo.msgQueue:
                    self.signalLogInfo.emit()
                if self.logWarning.msgQueue:
                    self.signalLogWarning.emit()
                if self.logError.msgQueue:
                    self.signalLogError.emit()
                time.sleep(0.01)
            else:
                #print("Stopping Thread Log: ", self.logname, ", Level:", self.level)
                break

    def writeLogInfo(self):
        if self.logInfo.msgQueue:
            l, n, m = self.logInfo.msgQueue[0]
            self.logInfo.msgQueue = self.logInfo.msgQueue[1:]
            self.logInfo.updateBox(l, n, m)

    def writeLogWarning(self):
        if self.logWarning.msgQueue:
                l, n, m = self.logWarning.msgQueue[0]
                self.logWarning.msgQueue = self.logWarning.msgQueue[1:]
                self.logWarning.updateBox(l, n, m)

    def writeLogError(self):
        if self.logError.msgQueue:
            l, n, m = self.logError.msgQueue[0]
            self.logError.msgQueue = self.logError.msgQueue[1:]
            self.logError.updateBox(l, n, m)


if __name__ == "__main__":
    from optparse import OptionParser
    from sys import argv

    parser = OptionParser(usage="usage: %skalab_log [options]")
    parser.add_option("--profile", action="store", dest="profile",
                      type="str", default="Default", help="Test")
    (opt, args) = parser.parse_args(argv[1:])

    app = QtWidgets.QApplication(sys.argv)
    wg = QtWidgets.QMainWindow()
    wg.resize(1000, 600)

    if not os.path.exists(default_app_dir):
        os.mkdir(default_app_dir)
    fname = default_app_dir + "/testlog"

    slog = SkalabLog(parent=wg, logname=__name__)
    # slog.signalLogInfo.connect(slog.writeLogInfo)
    # slog.signalLogWarning.connect(slog.writeLogWarning)
    # slog.signalLogError.connect(slog.writeLogError)
    slog.testFunc()
    slog.testClose()
    wg.show()
    wg.raise_()
    sys.exit(app.exec_())
