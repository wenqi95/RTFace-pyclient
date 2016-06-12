#!/usr/bin/env python

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import QThread, SIGNAL, pyqtSignal
from PyQt4.QtGui import QPixmap, QImage, QMessageBox, QVBoxLayout
import threading
import sys  # We need sys so that we can pass argv to QApplication

import design  # This file holds our MainWindow and all design related things
# it also keeps events etc that we defined in Qt Designer
import os  # For listing directory methods
import client
import numpy as np
import re
import pdb

class UI(QtGui.QMainWindow, design.Ui_MainWindow):
    def __init__(self):
        # Explaining super is out of the scope of this article
        # So please google it if you're not familar with it
        # Simple reason why we use it here is that it allows us to
        # access variables, methods etc in the design.py file
        super(self.__class__, self).__init__()
        self.setupUi(self)  # This is defined in design.py file automatically

        # It sets up layout and widgets that are defined
        self.button_blur.clicked.connect(self.generate_whitelist)
        self.button_train.setCheckable(True)
        self.button_train.clicked.connect(self.toggle_train)
        self.vbox_trainedpeople = QVBoxLayout()
        self.groupBox_trainedpeople.setFlat(True)
        self.groupBox_trainedpeople.setLayout(self.vbox_trainedpeople)
        self.name_list=[]
        
        # self.frame=None
        # self.timer = QtCore.QTimer()
        # self.timer.timeout.connect(self.nextFrameSlot)
        # self.timer.start(1000./1) # fps = 10
        
    # def nextFrameSlot(self):
    #    if self.frame != None:
    #        img = QImage(self.frame, self.frame.shape[1], self.frame.shape[0], QtGui.QImage.Format_RGB888)
    #        pix = QPixmap.fromImage(img)
    #        print 'frame {} image {} pix {}'.format(self.frame, img, pix)
    #        self.label_image.setPixmap(pix)           

    def only_char(self, strg, search=re.compile(r'[^a-zA-Z0-9.]').search):
        return not bool(search(strg))    

    def get_name(self):
        name=str(self.textEdit.toPlainText())
        if len(name)>0 and self.only_char(name):
            self.textEdit.clear()
            return name
        else:
            return None

    # def add_name_to_ui(self,name):
    #     if name not in self.name_list:
    #         row = QtGui.QListWidgetItem() 
    #         Create widget
    #         widget = QtGui.QWidget()
    #         widgetText =  QtGui.QRadioButton(name, widget)
    #         Add widget to QListWidget list
    #         self.listview_trainedpeople.addItem(row)
    #         self.listview_trainedpeople.setItemWidget(row, widget)
    #         self.name_list.append(name)

    def add_name_to_ui(self,name):
        if name not in self.name_list:
            cb =  QtGui.QCheckBox(name)
            self.vbox_trainedpeople.addWidget(cb)
            self.name_list.append(name)
            
    def toggle_train(self):
        # if not in training
        if not client.train:
            name=self.get_name()
            if name != None:
                client.start_train(name)
                self.button_train.setChecked(True)                
            else:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setText("Please Enter a valid name (only characters allowed)")
                msg.setWindowTitle("Error")
                msg.exec_()
                self.button_train.setChecked(False)                            
        else:
            added_name=client.stop_train()
            self.add_name_to_ui(added_name)
            self.button_train.setChecked(False)            
    
    def set_image(self, frame):
        img = QImage(frame, frame.shape[1], frame.shape[0], QtGui.QImage.Format_RGB888)
        pix = QPixmap.fromImage(img)
        self.label_image.setPixmap(pix)           

    def generate_whitelist(self):
        cnt=self.vbox_trainedpeople.count()
        new_whitelist=[]
        for i in range(0,cnt):
            item=self.vbox_trainedpeople.itemAt(i).widget()
            if item.isChecked():
                new_whitelist.append(str(item.text()))
        client.whitelist=new_whitelist
        print 'client new whitelist: {}'.format(client.whitelist)

    def browse_folder(self):
        self.listview_trainedpeople.clear() # In case there are any existing elements in the list
        directory = QtGui.QFileDialog.getExistingDirectory(self,
                                                           "Pick a folder")
        # execute getExistingDirectory dialog and set the directory variable to be equal
        # to the user selected directory

        if directory: # if user didn't pick a directory don't continue
            for file_name in os.listdir(directory): # for all files, if any, in the directory
                row = QtGui.QListWidgetItem() 
                #Create widget
                widget = QtGui.QWidget()
                widgetText =  QtGui.QRadioButton(file_name, widget)
#                widgetLayout = QtGui.QHBoxLayout()
#                widgetLayout.addWidget(widgetText)
#                widgetLayout.addWidget(widgetButton)
#                widgetLayout.addStretch()
#                widgetLayout.setSizeConstraint(QtGui.QLayout.SetFixedSize)
#                widget.setLayout(widgetLayout)  
#                row.setSizeHint(widget.sizeHint())
                
                #Add widget to QListWidget list
                self.listview_trainedpeople.addItem(row)
                self.listview_trainedpeople.setItemWidget(row, widget)
#                self.listview_trainedpeople.addItem(file_name)  # add file to the listWidget


class ClientThread(QThread):
    sig_frame_available = pyqtSignal(object)
    
    def __init__(self):
        super(self.__class__, self).__init__()
        self._stop = threading.Event()        

    def run(self):
        client.run(self.sig_frame_available)

    def stop(self):
        client.alive=False
        self._stop.set()
        
def main():
    app = QtGui.QApplication(sys.argv)
    ui = UI()        
    ui.show()
    clientThread = ClientThread()
    clientThread.sig_frame_available.connect(ui.set_image)
    clientThread.finished.connect(app.exit)
    clientThread.start()
    
    sys.exit(app.exec_())  # and execute the app

    
if __name__ == '__main__':  # if we're running file directly and not importing it
    main()  # run the main function
