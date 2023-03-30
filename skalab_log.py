import logging
from PyQt5 import QtWidgets, QtCore
import sys

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class QTextEditLogger(logging.Handler):
    def __init__(self, parent, level=logging.INFO, caption=None):
        super().__init__()
        self.widget = QtWidgets.QPlainTextEdit(parent)
        self.widget.setReadOnly(True)
        self.level = level
        self.caption = caption
        self.total = 0

    def emit(self, record):
        if (record.levelno == self.level) or (self.level == logging.INFO):
            msg = self.format(record)
            self.widget.appendPlainText(msg)
            if self.caption is not None:
                self.total = self.total + 1
                self.caption.setTabText(2, record.levelname[0] + record.levelname[1:].lower() +
                                        "s  cnt:%s" % str(self.total).rjust(3, " ") + " (*)")

    def clear(self):
        self.widget.clear()


class SkalabLog(QtWidgets.QMainWindow):
    """ SkaLab Log class """
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    def __init__(self, parent):
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
        self.qbutton_clear_log.setGeometry(QtCore.QRect(self.size.width() - 81, 13, 71, 22))
        self.qbutton_clear_log.setStatusTip("")
        self.qbutton_clear_log.setWhatsThis("")
        self.qbutton_clear_log.setToolTip(_translate("Form", "Clear Text on the Current Tab"))
        self.qbutton_clear_log.setText(_translate("Form", "Clear"))
        self.qbutton_clear_log.clicked.connect(self.clearLog)
        self.qbutton_reset_error_cnt = QtWidgets.QPushButton(self.wg)
        self.qbutton_reset_error_cnt.setGeometry(QtCore.QRect(self.size.width() - 181, 13, 71, 22))
        self.qbutton_reset_error_cnt.setToolTipDuration(-1)
        self.qbutton_reset_error_cnt.setStatusTip("")
        self.qbutton_reset_error_cnt.setObjectName("qbutton_reset_error_cnt")
        self.qbutton_reset_error_cnt.setToolTip(_translate("Form", "Reset Error Counter"))
        self.qbutton_reset_error_cnt.setText(_translate("Form", "Reset"))
        self.qbutton_reset_error_cnt.clicked.connect(self.resetCnt)
        self.qtabLog.currentChanged.connect(self.logChanged)
        #self.qtabLog.show()
        self.setLogs()

    def setLogs(self):
        self.logInfo = QTextEditLogger(self)
        self.logInfo.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(self.logInfo)
        self.logInfo.setLevel(logging.INFO)
        layoutInfo = QtWidgets.QVBoxLayout()
        layoutInfo.addWidget(self.logInfo.widget)
        self.tabLog.setLayout(layoutInfo)

        self.logWarning = QTextEditLogger(self, level=logging.WARNING)
        self.logWarning.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(self.logWarning)
        self.logWarning.setLevel(logging.WARNING)
        layoutWarning = QtWidgets.QVBoxLayout()
        layoutWarning.addWidget(self.logWarning.widget)
        self.tabWarning.setLayout(layoutWarning)

        self.logError = QTextEditLogger(self, level=logging.ERROR, caption=self.qtabLog)
        self.logError.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(self.logError)
        self.logError.setLevel(logging.ERROR)
        layoutError = QtWidgets.QVBoxLayout()
        layoutError.addWidget(self.logError.widget)
        self.tabError.setLayout(layoutError)

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
        self.qbutton_test.setGeometry(QtCore.QRect(300, 13, 71, 22))
        self.qbutton_test.clicked.connect(self.testLog)
        self.qbutton_test.setText("TEST")

    def testLog(self):
        logging.log(logging.INFO, "TESTING INFO")
        logging.log(logging.WARNING, "TESTING WARNING")
        logging.log(logging.ERROR, "TESTING ERROR")


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
    slog = SkalabLog(wg)
    slog.testFunc()
    wg.show()
    wg.raise_()
    sys.exit(app.exec_())
