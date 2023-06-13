import os
import configparser
import shutil
from PyQt5 import QtCore, QtGui, QtWidgets, uic


class SkalabBase(QtWidgets.QMainWindow):
    def __init__(self, App="", Profile="", Path="", parent=None):
        super().__init__()
        self.connected = False
        self.profile = {}
        self.wgProfile = uic.loadUi("Gui/skalab_profile.ui", parent)
        self.wgProfile.qbutton_load.clicked.connect(lambda: self.load())
        self.wgProfile.qbutton_saveas.clicked.connect(lambda: self.save_as_profile())
        self.wgProfile.qbutton_save.clicked.connect(lambda: self.save_profile())
        self.wgProfile.qbutton_delete.clicked.connect(
            lambda: self.delete_profile(self.wgProfile.qcombo_profile.currentText()))
        self.wgProfile.qbutton_browse.clicked.connect(lambda: self.browse())
        self.wgProfile.qbutton_clear.clicked.connect(lambda: self.clear())
        self.wgProfile.qbutton_apply.clicked.connect(lambda: self.apply())
        self.load_profile(App=App, Profile=Profile, Path=Path)
        self.wgProfile.qtable_conf.cellDoubleClicked.connect(self.editValue)

    # def parseProfile(self, config=""):
    #     confparser = configparser.ConfigParser()
    #     confparser.read(config)
    #     return confparser

    def load(self):
        if not self.connected:
            self.load_profile(App=self.profile['Base']['app'],
                              Profile=self.wgProfile.qcombo_profile.currentText(),
                              Path=self.profile['Base']['path'])

        else:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setText("Please switch to OFFLINE first!")
            msgBox.setWindowTitle("Error!")
            msgBox.exec_()

    def reload(self):
        # If needed, this will be overridden by children for custom post load
        pass

    def readConfig(self, fname):
        profile = {}
        confparser = configparser.ConfigParser()
        confparser.optionxform = str
        confparser.read(fname)
        for s in confparser.sections():
            if not s in profile.keys():
                profile[s] = {}
            for k in confparser._sections[s]:
                val = confparser._sections[s][k]
                if '~' in val:
                    home = os.getenv("HOME")
                    val = val.replace('~', home)
                profile[s][k] = val
        return profile

    def writeConfig(self, profileConfig, fname):
        conf = configparser.ConfigParser()
        conf.optionxform = str
        for s in profileConfig.keys():
            # print(s, ": ", self.profile[s], type(self.profile[s]))
            if type(profileConfig[s]) == dict:
                # print("Creating Dict", s)
                conf[s] = {}
                for k in profileConfig[s]:
                    # print("Adding ", k, self.profile[s][k])
                    conf[s][k] = str(profileConfig[s][k])
            else:
                print("Malformed ConfigParser, found a non dict section!")
        with open(fname, 'w') as f:
            conf.write(f)

    def load_profile(self, App="", Profile="", Path=""):
        if not Profile == "":
            loadPath = Path + Profile + "/"
            fullPath = loadPath + App.lower() + ".ini"
            if os.path.exists(fullPath):
                print("Loading " + App + " Profile: " + Profile + " (" + fullPath + ")")
            else:
                print("\nThe " + Profile + " Profile for the App " + App +
                      " does not exist.\nGenerating a new one in " + fullPath + "\n")
                self.make_profile(App=App, Profile=Profile, Path=Path)
            self.wgProfile.qline_configuration_file.setText(fullPath)
            self.profile = self.readConfig(fullPath)
            self.clear()
            self.populate_table_profile()
            self.updateProfileCombo(current=Profile)
            self.reload()

    def delete_profile(self, profile_name):
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Delete...",
                                                "Are you sure you want to delete the Profile '%s' for the App '%s'?" % (
                                                    profile_name, self.profile['Base']['app']),
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

        if result == QtWidgets.QMessageBox.Yes:
            print("Removing", self.profile['Base']['path'] + profile_name + "/" + self.profile['Base']['app'])
            if os.path.exists(self.profile['Base']['path'] + profile_name + "/" + self.profile['Base']['app'] + ".ini"):
                # shutil.rmtree(self.profile['Base']['path'] + profile_name + "/" + self.profile['Base']['app'] + ".ini")
                os.remove(self.profile['Base']['path'] + profile_name + "/" + self.profile['Base']['app'] + ".ini")
                self.updateProfileCombo(current="")
                self.load_profile(App=self.profile['Base']['app'],
                                  Profile=self.wgProfile.qcombo_profile.currentText(),
                                  Path=self.profile['Base']['path'])

    def make_profile(self, App="", Profile="", Path=""):
        """
            This method is called to generate a Profile File from scratch or to save changes
        """
        fname = Path + Profile + "/" + App.lower() + ".ini"
        if not os.path.exists(fname):
            defFile = "./Templates/" + App.lower() + ".ini"
            if os.path.exists(defFile):
                self.profile = self.readConfig(defFile)
                print("Copying the Template File", defFile)
                print(self.readConfig(defFile))
                if not os.path.exists(Path[:-1]):
                    os.makedirs(Path[:-1])
                if not os.path.exists(Path + Profile):
                    os.makedirs(Path + Profile)
                self.writeConfig(self.profile, fname)
                self.populate_table_profile()
            else:
                msgBox = QtWidgets.QMessageBox()
                msgBox.setIcon(QtWidgets.QMessageBox.Critical)
                msgBox.setText("The Template for the " +
                               App.upper() +
                               " Profile file is not available.\n" +
                               "Please, check it out from the repo.")
                msgBox.setWindowTitle("Error!")
                msgBox.exec_()
        profile = self.readTableProfile()
        profile['Base']['Profile'] = Profile
        self.writeConfig(profile, fname)

    def save_profile(self):
        self.make_profile(App=self.profile['Base']['app'],
                          Profile=self.profile['Base']['profile'],
                          Path=self.profile['Base']['path'])
        self.load_profile(App=self.profile['Base']['app'],
                          Profile=self.profile['Base']['profile'],
                          Path=self.profile['Base']['path'])

    def save_as_profile(self):
        text, ok = QtWidgets.QInputDialog.getText(self, 'Profiles', 'Enter a Profile name:')
        if ok:
            self.make_profile(App=self.profile['Base']['app'],
                              Profile=text,
                              Path=self.profile['Base']['path'])
            self.load_profile(App=self.profile['Base']['app'],
                              Profile=text,
                              Path=self.profile['Base']['path'])

    def populate_table_profile(self):
        self.wgProfile.qtable_conf.clearSpans()
        self.wgProfile.qtable_conf.setGeometry(QtCore.QRect(640, 20, 481, 821))
        self.wgProfile.qtable_conf.setObjectName("qtable_conf")
        self.wgProfile.qtable_conf.setColumnCount(1)
        self.wgProfile.qtable_conf.setWordWrap(True)

        total_rows = len(self.profile.keys())
        for i in self.profile.keys():
            total_rows = total_rows + len(self.profile[i]) + 1
        self.wgProfile.qtable_conf.setRowCount(total_rows)

        item = QtWidgets.QTableWidgetItem("Profile: " + self.profile['Base']['profile'])
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        item.setFont(font)
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        self.wgProfile.qtable_conf.setHorizontalHeaderItem(0, item)

        item = QtWidgets.QTableWidgetItem(" ")
        item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        self.wgProfile.qtable_conf.setVerticalHeaderItem(0, item)

        q = 0
        for i in self.profile.keys():
            item = QtWidgets.QTableWidgetItem("[" + i + "]")
            item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            font = QtGui.QFont()
            font.setBold(True)
            font.setWeight(75)
            item.setFont(font)
            self.wgProfile.qtable_conf.setVerticalHeaderItem(q, item)
            item = QtWidgets.QTableWidgetItem(" ")
            item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wgProfile.qtable_conf.setItem(q, 0, item)
            q = q + 1
            for k in self.profile[i]:
                item = QtWidgets.QTableWidgetItem(k)
                item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wgProfile.qtable_conf.setVerticalHeaderItem(q, item)
                item = QtWidgets.QTableWidgetItem(self.profile[i][k])
                item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.wgProfile.qtable_conf.setItem(q, 0, item)
                q = q + 1
            item = QtWidgets.QTableWidgetItem(" ")
            item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wgProfile.qtable_conf.setVerticalHeaderItem(q, item)
            item = QtWidgets.QTableWidgetItem(" ")
            item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.wgProfile.qtable_conf.setItem(q, 0, item)
            q = q + 1

        self.wgProfile.qtable_conf.horizontalHeader().setStretchLastSection(True)
        self.wgProfile.qtable_conf.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgProfile.qtable_conf.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.wgProfile.qtable_conf.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.wgProfile.qtable_conf.setGeometry(QtCore.QRect(30, 140, 741, min((20 + total_rows * 30), 700)))

    def editValue(self, row, col):
        # Base keys cannot be edited
        if row > 4:
            key = self.wgProfile.qtable_conf.verticalHeaderItem(row)
            if key is not None:
                if not key.text() == " " and not "[" in key.text():
                    self.wgProfile.qline_row.setText(str(row))
                    self.wgProfile.qline_col.setText(str(col))
                    self.wgProfile.qline_edit_key.setText(key.text())
                    NewIndex = self.wgProfile.qtable_conf.currentIndex().siblingAtColumn(0)
                    self.wgProfile.qline_edit_value.setText(NewIndex.data())
                    item = self.wgProfile.qtable_conf.item(row, col)
                    if item:
                        self.wgProfile.qline_edit_newvalue.setText(item.text())
                        # print(row, col, item.text())

    def readTableProfile(self):
        profile = {}
        section = ''
        for r in range(self.wgProfile.qtable_conf.rowCount()):
            key = self.wgProfile.qtable_conf.verticalHeaderItem(r)
            if key is not None:
                if not key.text() == " ":
                    if "[" in key.text():
                        section = key.text()[1:-1]
                        profile[section] = {}
                    else:
                        profile[section][key.text()] = self.wgProfile.qtable_conf.item(r, 0).text()
        return profile

    def updateProfileCombo(self, current):
        profiles = []
        for d in os.listdir(self.profile['Base']['path']):
            if os.path.exists(self.profile['Base']['path'] + d + "/" + self.profile['Base']['app'].lower() + ".ini"):
                profiles += [d]
        if profiles:
            self.wgProfile.qcombo_profile.clear()
            for n, p in enumerate(profiles):
                self.wgProfile.qcombo_profile.addItem(p)
                if current == p:
                    self.wgProfile.qcombo_profile.setCurrentIndex(n)

    def browse(self):
        if 'file' in self.wgProfile.qline_edit_key.text():
            fd = QtWidgets.QFileDialog()
            fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
            options = fd.options()
            base_path = self.wgProfile.qline_edit_value.text()
            base_path = base_path[:base_path.rfind("/")]
            result = fd.getOpenFileName(caption="Select a Station Config File...",
                                        directory=base_path,
                                        options=options)[0]
            self.wgProfile.qline_edit_newvalue.setText(result)
        if 'path' in self.wgProfile.qline_edit_key.text():
            fd = QtWidgets.QFileDialog()
            fd.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
            fd.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
            options = fd.options()
            base_path = self.wgProfile.qline_edit_value.text()
            base_path = base_path[:base_path.rfind("/")]
            result = fd.getExistingDirectory(caption="Select a Station Config File...",
                                             directory=base_path,
                                             options=options)
            self.wgProfile.qline_edit_newvalue.setText(result)

    def clear(self):
        self.wgProfile.qline_edit_key.setText("")
        self.wgProfile.qline_edit_value.setText("")
        self.wgProfile.qline_edit_newvalue.setText("")
        self.wgProfile.qline_row.setText("")
        self.wgProfile.qline_col.setText("")

    def apply(self):
        item = QtWidgets.QTableWidgetItem(self.wgProfile.qline_edit_newvalue.text())
        item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        item.setFont(font)
        self.wgProfile.qtable_conf.setItem(int(self.wgProfile.qline_row.text()),
                                           int(self.wgProfile.qline_col.text()),
                                           item)
