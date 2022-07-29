import os
import configparser
import shutil
from PyQt5 import QtCore, QtGui, QtWidgets, uic


class SkalabBase(QtWidgets.QMainWindow):
    def __init__(self, App="", Profile="", Path="", parent=None):
        super().__init__()
        self.profile = {}
        self.wgProfile = uic.loadUi("skalab_profile.ui", parent)
        self.wgProfile.qbutton_load.clicked.connect(lambda: self.load())
        self.wgProfile.qbutton_saveas.clicked.connect(lambda: self.save_as_profile())
        self.wgProfile.qbutton_save.clicked.connect(lambda: self.save_profile())
        self.wgProfile.qbutton_delete.clicked.connect(lambda: self.delete_profile(self.wgProfile.qcombo_profile.currentText()))
        self.wgProfile.qbutton_browse.clicked.connect(lambda: self.browse())
        self.wgProfile.qbutton_clear.clicked.connect(lambda: self.clear())
        self.wgProfile.qbutton_apply.clicked.connect(lambda: self.apply())
        self.load_profile(App=App, Profile=Profile, Path=Path)
        self.wgProfile.qtable_conf.cellDoubleClicked.connect(self.editValue)

    def parseProfile(self, config=""):
        confparser = configparser.ConfigParser()
        confparser.read(config)
        return confparser

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

    def load_profile(self, App="", Profile="", Path=""):
        if not Profile == "":
            loadPath = Path + Profile + "/"
            fullPath = loadPath + App + ".ini"
            if os.path.exists(fullPath):
                print("Loading " + App + " Profile: " + Profile + " (" + fullPath + ")")
            else:
                print("\nThe " + Profile + " Profile for the App " + App +
                      " does not exist.\nGenerating a new one in " + fullPath + "\n")
                self.make_profile(App=App, Profile=Profile, Path=Path)
            self.wgProfile.qline_configuration_file.setText(fullPath)
            self.profileParser = self.parseProfile(fullPath)

            for s in self.profileParser.sections():
                if not s in self.profile.keys():
                    self.profile[s] = {}
                for k in self.profileParser._sections[s]:
                    val = self.profileParser._sections[s][k]
                    if '~' in val:
                        home = os.getenv("HOME")
                        val.replace('~', home)
                    self.profile[s][k] = self.profileParser._sections[s][k]

            self.populate_table_profile()
            self.updateProfileCombo(current=Profile)
            self.reload()

            #self.profile['Base']['profile'] = profile_name
            #self.profile['Base']['path'] = loadPath

            # self.wgProfile.qline_profile.setText(fullPath)
            #
            # if not self.profile.sections():
            #     msgBox = QtWidgets.QMessageBox()
            #     msgBox.setText("Cannot find this profile!")
            #     msgBox.setWindowTitle("Error!")
            #     msgBox.exec_()
            # else:
            #     self.config_file = self.profile['Init']['station_setup']
            #     self.wgProfile.qline_configfile.setText(self.config_file)
            #     self.populate_table_profile()
            #     if 'Extras' in self.profile.keys():
            #         if 'text_editor' in self.profile['Extras'].keys():
            #             self.text_editor = self.profile['Extras']['text_editor']

    # def reload_profile(self, profile):
    #     self.load_profile(profile=profile)
    #     if self.profile.sections():
    #         if self.profile['App']['subrack']:
    #             self.wgSubrack.load_profile(profile=self.profile['App']['subrack'])
    #
    def delete_profile(self, profile_name):
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Delete...",
                                                "Are you sure you want to delete the Profile '%s' ?" % profile_name,
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

        if result == QtWidgets.QMessageBox.Yes:
            if os.path.exists(self.profile['Base']['path'] + profile_name):
                shutil.rmtree(self.profile['Base']['path'] + profile_name)
                self.updateProfileCombo(current="")
                self.load_profile(App=self.profile['Base']['app'],
                                  Profile=self.wgProfile.qcombo_profile.currentText(),
                                  Path=self.profile['Base']['path'])


    # def make_skalab_profile(self, profile="Default", subrack="Default", live="Default", playback="Default", config=""):
    #     conf = configparser.ConfigParser()
    #     conf['App'] = {'subrack': subrack,
    #                    'live': live,
    #                    'playback': playback}
    #     conf['Init'] = {'station_setup': config}
    #     conf['Extras'] = {'text_editor': self.text_editor}
    #     if not os.path.exists(default_app_dir):
    #         os.makedirs(default_app_dir)
    #     conf_path = default_app_dir + profile
    #     if not os.path.exists(conf_path):
    #         os.makedirs(conf_path)
    #     conf_path = conf_path + "/skalab.ini"
    #     with open(conf_path, 'w') as configfile:
    #         conf.write(configfile)

    def make_profile(self, App="", Profile="", Path=""):
        if 'Base' not in self.profile.keys():
            self.profile = {'Base': {
                'app': App.lower(),
                'profile': Profile,
                'path': Path
            }}
        self.profile['Base']['profile'] = Profile
        conf = configparser.ConfigParser()
        for s in self.profile.keys():
            #print(s, ": ", self.profile[s], type(self.profile[s]))
            if type(self.profile[s]) == dict:
                #print("Creating Dict", s)
                conf[s] = {}
                for k in self.profile[s]:
                    #print("Adding ", k, self.profile[s][k])
                    conf[s][k] = str(self.profile[s][k])
            else:
                print("Malformed ConfigParser, found a non dict section!")
        if self.profile['Base']['path'] != "":
            if not os.path.exists(self.profile['Base']['path']):
                os.makedirs(self.profile['Base']['path'])
            if not os.path.exists(self.profile['Base']['path'] + Profile):
                os.makedirs(self.profile['Base']['path'] + Profile)
            fname = self.profile['Base']['path'] + Profile + "/" + self.profile['Base']['app'].lower() + ".ini"
            with open(fname, 'w') as configfile:
                conf.write(configfile)
            print("Saved Profile %s (%s)" % (Profile, fname))
        else:
            print("Profile Base Path cannot be empty!")

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
        key = self.wgProfile.qtable_conf.verticalHeaderItem(row)
        if key is not None:
            if not key.text() == " " and not "[" in key.text():
                self.wgProfile.qline_row.setText(str(row))
                self.wgProfile.qline_col.setText(str(col))
                self.wgProfile.qline_edit_key.setText(key.text())
                for s in self.profile.keys():
                    for k in self.profile[s].keys():
                        if k == key.text():
                            self.wgProfile.qline_edit_value.setText(self.profile[s][k])
                item = self.wgProfile.qtable_conf.item(row, col)
                if item:
                    self.wgProfile.qline_edit_newvalue.setText(item.text())
                    #print(row, col, item.text())

    def updateProfileCombo(self, current):
        profiles = []
        for d in os.listdir(self.profile['Base']['path']):
            if os.path.exists(self.profile['Base']['path'] + d + "/" + self.profile['Base']['app'] + ".ini"):
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
