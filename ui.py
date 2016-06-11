#!/usr/bin/env python

from PyQt4 import QtGui, QtCore  # Import the PyQt4 module we'll need
from PyQt4.QtCore import QThread, SIGNAL
import threading
import sys  # We need sys so that we can pass argv to QApplication

import design  # This file holds our MainWindow and all design related things
# it also keeps events etc that we defined in Qt Designer
import os  # For listing directory methods
import client

class UI(QtGui.QMainWindow, design.Ui_MainWindow):
    def __init__(self):
        # Explaining super is out of the scope of this article
        # So please google it if you're not familar with it
        # Simple reason why we use it here is that it allows us to
        # access variables, methods etc in the design.py file
        super(self.__class__, self).__init__()
        self.setupUi(self)  # This is defined in design.py file automatically
        # It sets up layout and widgets that are defined
        self.button_blur.clicked.connect(self.browse_folder)  # When the button is pressed
                                                            # Execute browse_folder function

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
    def __init__(self):
        """
        Make a new thread instance with the specified
        subreddits as the first argument. The subreddits argument
        will be stored in an instance variable called subreddits
        which then can be accessed by all other class instance functions

        :param subreddits: A list of subreddit names
        :type subreddits: list
        """
        super(self.__class__, self).__init__()        

    def run(self):
        client.run()

def usingQThread():
    app = QtCore.QCoreApplication([])
    thread = AThread()
    thread.finished.connect(app.exit)
    thread.start()
    sys.exit(app.exec_())
    
def main():
    app = QtGui.QApplication(sys.argv)  # A new instance of QApplication
    ui = UI()  
    ui.show()  
    # change to qthread?
    thread = ClientThread()
    thread.finished.connect(app.exit)
    thread.start()
    sys.exit(app.exec_())  # and execute the app


if __name__ == '__main__':  # if we're running file directly and not importing it
    main()  # run the main function
