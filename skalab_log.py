import logging
import os.path
from logging.handlers import TimedRotatingFileHandler
from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import time
import datetime
from pathlib import Path
default_app_dir = str(Path.home()) + "/.skalab/LOG"


class QTextEditLogger(logging.Handler):
    def __init__(self, parent, level=logging.INFO, caption=None):
        super().__init__()
        self.widget = QtWidgets.QTextEdit(parent)
        self.widget.setFont(QtGui.QFont("Courier New", 10))
        self.widget.setStyleSheet("background-color: rgb(255, 255, 255);")
        self.widget.setReadOnly(True)
        self.level = level
        self.caption = caption
        self.total = 0

        html_header = "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" "
        html_header += "\"http://www.w3.org/TR/REC-html40/strict.dtd\"><html><head>"
        html_header += "<meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">p, li "
        html_header += "{ white-space: pre-wrap; }</style></head><body style=\" font-family:\"Courier\";"
        html_header += "font-size:11pt; font-weight:400; font-style:normal;\">"
        self.widget.insertHtml(html_header)

    def emit(self, record):
        print(record.levelno, "\t", self.format(record))
        # if (record.levelno == self.level) or (self.level == logging.INFO):
        msg = self.format(record)
        if record.levelno == logging.INFO:
            fancymsg = "\n<span style='font-weight:600; color:#22b80e;'>" + msg + "</span><br>"
        elif record.levelno == logging.ERROR:
            fancymsg = "\n<span style='font-weight:600; color:#ff0000;'>" + msg + "</span><br>"
        else:
            fancymsg = "\n<span style='font-weight:600; color:#ff7800;'>" + msg + "</span><br>"

        self.widget.insertHtml(fancymsg)
        self.widget.moveCursor(QtGui.QTextCursor.End)
        if self.caption is not None:
            self.total = self.total + 1
            self.caption.setTabText(2, record.levelname[0] + record.levelname[1:].lower() +
                                    "s  cnt:%s" % str(self.total).rjust(3, " ") + " (*)")

    def clear(self):
        self.widget.clear()


class SkalabLog(QtWidgets.QMainWindow):
    """ SkaLab Log class """
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
        #self.qtabLog.show()

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
        pname = Path(logname)
        pname.mkdir(parents=True, exist_ok=True)
        fname = logname + "/" + logname[logname.rfind("/") + 1:].lower() + \
                datetime.datetime.strftime(datetime.datetime.utcnow(), "_log_%Y-%m-%d_%H%M%S.txt")
        self.file_handler = TimedRotatingFileHandler(fname, when="h", interval=1, backupCount=180, utc=True)
        self.file_handler.setFormatter(formatter)
        self.file_handler.setLevel(logging.INFO)
        self.logger.addHandler(self.file_handler)

        self.logInfo = QTextEditLogger(self, level=logging.INFO)
        self.logInfo.setFormatter(formatter)
        self.logger.addHandler(self.logInfo)
        layoutInfo = QtWidgets.QVBoxLayout()
        layoutInfo.addWidget(self.logInfo.widget)
        self.tabLog.setLayout(layoutInfo)

        self.logWarning = QTextEditLogger(self, level=logging.WARNING)
        self.logWarning.setFormatter(formatter)
        self.logger.addHandler(self.logWarning)
        layoutWarning = QtWidgets.QVBoxLayout()
        layoutWarning.addWidget(self.logWarning.widget)
        self.tabWarning.setLayout(layoutWarning)

        self.logError = QTextEditLogger(self, level=logging.ERROR, caption=self.qtabLog)
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

    def testFunc(self):
        self.qbutton_test = QtWidgets.QPushButton(self.wg)
        self.qbutton_test.setGeometry(QtCore.QRect(300, 11, 71, 24))
        self.qbutton_test.clicked.connect(self.testLog)
        self.qbutton_test.setText("TEST")

    def testLog(self):
        self.logger.info("TESTING INFO")
        self.logger.warning("TESTING WARNING")
        self.logger.error("TESTING ERROR")


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
    slog.testFunc()
    wg.show()
    wg.raise_()
    sys.exit(app.exec_())
