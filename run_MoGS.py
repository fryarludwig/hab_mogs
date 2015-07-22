""""
Changelog:
07/13/15 - KFL: Initial commit - committed all of previous work
				Added functionality for network status
				Refactored serial input to capture (almost) all messages
				Implemented and verified chat functionality
07/14/15 - KFL: Added option to silence serial port error popups
				Added ability to set precision
				Implemented speed and ascent calculation
				Added icons to maps
				Added chase mapping ability for all chase cars
"""

from __future__ import print_function

import sys
import serial
import datetime
import urllib2
import socket
import winsound
import xml.etree.ElementTree as ET
from math import *
from time import sleep
from PyQt4 import QtGui, QtCore
from PyQt4.QtWebKit import QWebView
from PyQt4.Qt import QWidget
from collections import OrderedDict

TELEMETRY_LOG_FILE_LOCATION = r"MoGS_telemetry_log.txt"
RADIO_LOG_FILE_LOCATION = r"MoGS_radio_log.txt"
GUI_LOG_FILE_LOCATION = r"MoGS_gui_log.txt"
SPOT_API_URL = r"https://api.findmespot.com/spot-main-web/consumer/rest-api/2.0/public/feed/00CFIiymlztJBFEN4cJOjNhlZSofClAxa/message.xml"

DISH = False
DISH_ADDRESS = "192.168.101.98"
DISH_PORT = 5003

if DISH:
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.connect((DISH_ADDRESS, DISH_PORT))

TEST_MODE = False  # Test mode pulls telemetry from file instead of radios

"""
PRIORITIES:

TODO: Altitude graph (Speed, Temp too?)
TODO: Add prediction plotting
TODO: Additional logging
"""

"""
Handles GUI operations, as well as all user input. 

TODO: AZ/EL plotting
TODO: Text messaging GPS, Altitude
TODO: Add command response updating
TODO: Audio link mode
TODO: Image transfer
"""
class mogsMainWindow(QtGui.QWidget):
	"""
	Creates the class variables and starts the GUI window
	"""
	def __init__(self):
		super(mogsMainWindow, self).__init__()
		self.commandStatusLabel = QtGui.QLabel()

		self.dataTelemetryList = []
		self.telemetryValuesToInclude = 5
		self.selectPrecisionDialogWidget = QtGui.QDialog()
		self.predictionFileName = ""

		self.messagingListView = QtGui.QListView()
		self.messagingListViewModel = QtGui.QStandardItemModel(self.messagingListView)
		self.sendMessageCallsign = QtGui.QLabel()
		self.sendMessageEntryBox = QtGui.QLineEdit()
		self.notifyOnSerialError = True

		self.radioConsoleWidget = QtGui.QWidget()
		self.radioConsoleListView = QtGui.QListView()
		self.radioConsoleListViewModel = QtGui.QStandardItemModel(self.radioConsoleListView)
		self.viewRadioConsoleButton = QtGui.QPushButton()
		self.radioConsoleIsOpen = False
		self.radioConsoleNumItems = 300

		self.callsignToString = {"hab"   : "Balloon",
								"chase1" : "Chase 1",
								"chase2" : "Chase 2",
								"chase3" : "Chase 3",
								"nps"    : "NPS"}

		self.statusLabelList = {"hab" : QtGui.QLabel("Balloon", self),
								"chase1" : QtGui.QLabel("Chase 1", self),
								"chase2" : QtGui.QLabel("Chase 2", self),
								"chase3" : QtGui.QLabel("Chase 3", self),
								"nps" : QtGui.QLabel("  NPS  ", self)}

		self.javaArrayPosition = {"hab" : 0,
								"chase1" : 1,
								"chase2" : 2,
								"chase3" : 3,
								"nps" : 4}

		self.spotToVehicleDictionary = {"SSAGSpot1" : "hab",
										"SSAGSpot2" : "chase1",
										"SSAGSpot3" : "chase2",
										"SSAGSpot4" : "chase3",
										"SSAGSpot5" : "nps"}

		self.telemetryLabelDictionary = OrderedDict()
		self.telemetryLabelDictionary["timestamp"] = QtGui.QLabel("None", self)
		self.telemetryLabelDictionary["altitude"] = QtGui.QLabel("None", self)
		self.telemetryLabelDictionary["speed"] = QtGui.QLabel("None", self)
		self.telemetryLabelDictionary["ascent"] = QtGui.QLabel("None", self)
		self.telemetryLabelDictionary["voltage"] = QtGui.QLabel("None", self)
		self.telemetryLabelDictionary["tempBattery"] = QtGui.QLabel("None", self)
		self.telemetryLabelDictionary["tempInside"] = QtGui.QLabel("None", self)
		self.telemetryLabelDictionary["tempOutside"] = QtGui.QLabel("None", self)
		self.telemetryLabelDictionary["gps"] = QtGui.QLabel("None", self)

		self.chaseVehicleGpsLabel = OrderedDict()
		self.chaseVehicleGpsLabel["chase1"] = [QtGui.QLabel(), QtGui.QLabel()]
		self.chaseVehicleGpsLabel["chase2"] = [QtGui.QLabel(), QtGui.QLabel()]
		self.chaseVehicleGpsLabel["chase3"] = [QtGui.QLabel(), QtGui.QLabel()]

		self.armBrmButton = QtGui.QPushButton()
		self.releaseBalloonButton = QtGui.QPushButton()
		self.balloonReleaseArmed = False
		self.balloonReleaseActivated = False

		self.palette = QtGui.QPalette()

		self.serialHandler = serialHandlerThread()
		self.serialHandler.balloonDataSignalReceived.connect(self.updateBalloonDataTelemetry)
		self.serialHandler.balloonAckReceived.connect(self.processBalloonCommandResponse)
		self.serialHandler.vehicleDataReceived.connect(self.updateChaseVehicleTelemetry)
		self.serialHandler.invalidSerialPort.connect(self.serialFailureDisplay)
		self.serialHandler.chatMessageReceived.connect(self.updateChat)
		self.serialHandler.radioConsoleUpdateSignal.connect(self.updateRadioConsole)
		self.serialHandler.updateNetworkStatusSignal.connect(self.updateActiveNetwork)
		# add the other handlers here
		self.serialHandler.start()

		self.dishHandler = dishHandlerThread()
		# self.dishHandler.start()

		self.initUI()


	"""
	Populates the widgets and the main GUI window.
	"""
	def initUI(self):
		window_x = 1200
		window_y = 700

		self.col = QtGui.QColor(0, 0, 0)
		self.vLayout = QtGui.QVBoxLayout()
		self.hLayout = QtGui.QHBoxLayout()

		self.vLayout.setSpacing(0)
		self.vLayout.setMargin(0)
		self.hLayout.setSpacing(0)
		self.hLayout.setMargin(0)

		mapWidget = QWidget()
		self.mapView = QWebView(mapWidget)
		self.mapView.setMinimumSize(window_x - 317, window_y)
		self.mapView.setMaximumSize(window_x, window_y)
		self.theMap = self.mapView.page().mainFrame()
		self.theMap.addToJavaScriptWindowObject('self', self)
		self.mapView.setHtml(googleMapsHtml)

		self.createRadioConsole()

		telemetryWidget = self.createTelemetryWidget()
		messagingWidget = self.createMessagingWidget()
		commandWidget = self.createCommandWidget()
		networkWidget = self.createNetworkWidget()

		self.vLayout.addWidget(telemetryWidget, 1)
		self.vLayout.addWidget(messagingWidget, 10)
		self.vLayout.addWidget(commandWidget, 1)
		self.vLayout.addWidget(networkWidget, 1)

		self.hLayout.addWidget(mapWidget, 1)
		self.hLayout.addLayout(self.vLayout, 0)

		self.setGeometry(150, 150, window_x, window_y)
		self.setWindowTitle('Mobile Ground Station (MoGS)')
		self.setLayout(self.hLayout)
		self.show()

		logGui("GUI created.")

	"""
	Resizes the MapView widget to fill the box.
	No return value.
	
	TODO: Call this function automatically when window is resized.
	"""
	def onResize(self):
		minX = self.vLayout.geometry().x()
		minY = self.vLayout.geometry().height()
		self.mapView.setMinimumSize(minX , minY)
		self.mapView.setMaximumSize(minX, minY)

	"""
	Populates a "Messaging" widget.
	Returns the widget, which is then added to the layout
	"""
	def createMessagingWidget(self):
		widget = QWidget()
		layout = QtGui.QGridLayout(widget)
		layout.setSpacing(3)

		# Set up labels
		sendMessageButton = QtGui.QPushButton("Send", self)
		sendMessageButton.clicked[bool].connect(self.sendMessage)

		self.messagingListView.setWrapping(True)
		self.messagingListView.setWordWrap(True)
		self.messagingListView.setSpacing(0)
		self.messagingListView.setMinimumSize(400, 300)
		self.messagingListView.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Maximum)

		self.sendMessageEntryBox.setMaxLength(180)
		self.sendMessageEntryBox.returnPressed.connect(self.sendMessage)

		self.sendMessageCallsign.setText(self.callsignToString[self.serialHandler.RADIO_CALLSIGN])
		self.sendMessageCallsign.setAlignment(QtCore.Qt.AlignCenter)

		layout.addWidget(self.messagingListView, 1, 0, 5, 9)
		layout.addWidget(self.sendMessageCallsign, 6, 0)
		layout.addWidget(self.sendMessageEntryBox, 6, 1, 1, 7)
		layout.addWidget(sendMessageButton, 6, 8)

		return widget

	"""
	Populates the "Command" section of the GUI.
	Returns the widget, which is then added to the layout
	"""
	def createCommandWidget(self):
		widget = QWidget()
		layout = QtGui.QGridLayout(widget)
		layout.setSpacing(3)

		# Set up labels
		self.commandStatusLabel = QtGui.QLabel("No Commands have been sent", self)
		self.commandStatusLabel.setAlignment(QtCore.Qt.AlignCenter)

		# Set up buttons for GUI window
		comPortButton = QtGui.QPushButton('Settings', self)
		comPortButton.clicked.connect(self.changeSettings)

		streetMapButton = QtGui.QPushButton('Predictions', self)
		streetMapButton.clicked[bool].connect(self.openPredictionsDialog)

		resizeMapButton = QtGui.QPushButton('Resize Map', self)
		resizeMapButton.clicked[bool].connect(self.onResize)

		self.armBrmButton = QtGui.QPushButton('Arm/Disarm BRM', self)
		self.armBrmButton.clicked.connect(self.armBalloonRelease)

		self.releaseBalloonButton = QtGui.QPushButton('Release Balloon', self)
		self.releaseBalloonButton.setStyleSheet("background-color: Salmon")
		self.releaseBalloonButton.clicked[bool].connect(self.confirmAndReleaseBalloon)
		self.releaseBalloonButton.setDisabled(True)

		satelliteViewButton = QtGui.QPushButton('Update SPOT', self)
		satelliteViewButton.clicked[bool].connect(self.updateSpotPositions)

		layout.addWidget(self.commandStatusLabel, 1, 0, 1, 3)
		layout.addWidget(comPortButton, 2, 2)
		layout.addWidget(resizeMapButton, 2, 1)
		layout.addWidget(streetMapButton, 2, 0)
		layout.addWidget(self.releaseBalloonButton, 3, 1)
		layout.addWidget(self.armBrmButton, 3, 2)
		layout.addWidget(satelliteViewButton, 3, 0)

		return widget

	"""
	Populates the "Telemetry" section of the GUI.
	Returns the widget, which is then added to the layout
	"""
	def createTelemetryWidget(self):
		widget = QWidget()
		layout = QtGui.QGridLayout(widget)
		layout.setSpacing(3)
		staticTelemetryLabels = []

		# Set up constant labels
		layoutLabel = QtGui.QLabel("Balloon")
		layoutLabel.setAlignment(QtCore.Qt.AlignCenter)

		rawGpsLabel = QtGui.QLabel("Latest Raw GPS")
		rawGpsLabel.setAlignment(QtCore.Qt.AlignCenter)

		staticTelemetryLabels.append(QtGui.QLabel("UTC Time", self))
		staticTelemetryLabels.append(QtGui.QLabel("Altitude", self))
		staticTelemetryLabels.append(QtGui.QLabel("Speed", self))
		staticTelemetryLabels.append(QtGui.QLabel("Ascent Rate", self))
		staticTelemetryLabels.append(QtGui.QLabel("Voltage", self))
		staticTelemetryLabels.append(QtGui.QLabel("Battery Temp", self))
		staticTelemetryLabels.append(QtGui.QLabel("Internal Temp", self))
		staticTelemetryLabels.append(QtGui.QLabel("External Temp", self))

		layout.addWidget(layoutLabel, 0, 0, 1, 2)
		layout.addWidget(rawGpsLabel, 9, 0, 1, 2)

		# Populate the static labels in the GUI
		counter = 1
		for label in staticTelemetryLabels:
			layout.addWidget(label, counter, 0)
			label.setAlignment(QtCore.Qt.AlignCenter)
			counter += 1

		# Populate the labels that will be updated with telemetry
		counter = 1
		for key, value in self.telemetryLabelDictionary.iteritems():
			value.setAlignment(QtCore.Qt.AlignCenter)
			if (key == "gps"):
				layout.addWidget(value, 10, 0, 1, 2)
			else:
				layout.addWidget(value, counter, 1)
			counter += 1

		counter = 1
		for key, value in self.chaseVehicleGpsLabel.iteritems():
			value[0].setAlignment(QtCore.Qt.AlignCenter)
			value[0].setText(self.callsignToString[key] + " - TIME")
			layout.addWidget(value[0], counter, 2)
			counter += 1

			value[1].setAlignment(QtCore.Qt.AlignCenter)
			value[1].setText("No GPS data yet")
			layout.addWidget(value[1], counter, 2)
			counter += 2

		widget.setMaximumSize(425, 185)
		widget.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
		return widget

	"""
	Populates the "Network" section of the GUI.
	Returns the widget, which is then added to the layout
	"""
	def createNetworkWidget(self):
		widget = QWidget()
		networkFont = QtGui.QFont()
		networkFont.setPointSize(11)
		networkFont.setBold(True)

		layout = QtGui.QGridLayout(widget)

		# Set up constant labels
		layoutLabel = QtGui.QLabel("Network Status")
		layoutLabel.setAlignment(QtCore.Qt.AlignCenter)

		self.viewRadioConsoleButton.clicked.connect(self.radioConsoleWidget.show)
		self.viewRadioConsoleButton.setText("View Console")

		# Set all to show that there is no connection yet
		for key, statusLabel in self.statusLabelList.items():
			statusLabel.setAlignment(QtCore.Qt.AlignCenter)
			statusLabel.setFont(networkFont)
			statusLabel.setStyleSheet("QFrame { background-color: Salmon }")

		layout.addWidget(layoutLabel, 0, 0, 1, 3)
		layout.addWidget(self.viewRadioConsoleButton, 1, 0)
		layout.addWidget(self.statusLabelList["hab"], 1, 1)
		layout.addWidget(self.statusLabelList["nps"], 1, 2)
		layout.addWidget(self.statusLabelList["chase1"], 2, 0)
		layout.addWidget(self.statusLabelList["chase2"], 2, 1)
		layout.addWidget(self.statusLabelList["chase3"], 2, 2)

		self.updateActiveNetwork()

		return widget

	"""
	Populates a "Console" widget.
	"""
	def createRadioConsole(self):
		layout = QtGui.QGridLayout(self.radioConsoleWidget)
		layout.setSpacing(0)

		# Set up labels
		radioConsoleCloseButton = QtGui.QPushButton("Close")
		radioConsoleCloseButton.clicked.connect(self.radioConsoleWidget.close)

		self.radioConsoleListView.setWrapping(True)
		self.radioConsoleListView.setWordWrap(True)
		self.radioConsoleListView.setSpacing(0)
		self.radioConsoleListView.setMinimumSize(600, 400)

		self.radioConsoleListViewModel.setRowCount(self.radioConsoleNumItems)

		layout.addWidget(self.radioConsoleListView, 1, 0, 10, 5)
		layout.addWidget(radioConsoleCloseButton, 11, 2)

		self.radioConsoleWidget.setLayout(layout)
		self.radioConsoleWidget.setWindowTitle("Radio Console Viewer")

	"""
	Populates and displays a "Console" widget.
	"""
	def updateRadioConsole(self, message):
		if (message[-1] == "\n" or message[-1] == "\r"):
			itemToAdd = QtGui.QStandardItem(datetime.datetime.now().strftime("%H:%M - ") + message[:-1])
		else:
			itemToAdd = QtGui.QStandardItem(datetime.datetime.now().strftime("%H:%M - ") + message)
		self.radioConsoleListViewModel.insertRow(0, itemToAdd)
		self.radioConsoleListViewModel.setRowCount(self.radioConsoleNumItems)
		self.radioConsoleListView.setModel(self.radioConsoleListViewModel)

	"""
	Logs and parses the telemetry string passed from the Radio class, then
	updates the GUI to display the values. On invalid packet the data is logged
	but the GUI is not updated.
	No return value
	"""
	def updateBalloonDataTelemetry(self, data):
		print(data)
		logTelemetry(data)
		self.statusLabelList["hab"].setStyleSheet("QFrame { background-color: Green }")

		while (len(self.dataTelemetryList) > self.telemetryValuesToInclude):
			self.dataTelemetryList.pop(0)

		try:
			splitMessage = data.split(",")
			timestamp = splitMessage[0]
			if (len(timestamp) > 0):
				timestamp = timestamp[:2] + ":" + timestamp[2:4] + ":" + timestamp[4:]
			latitude = splitMessage[1]
			longitude = splitMessage[2]
			altitude = splitMessage[3]
			voltage = splitMessage[4]
			innerTemp = splitMessage[5]
			outerTemp = splitMessage[6]
			batteryTemp = splitMessage[7]

			groundSpeed, ascentRate = self.calculateRates()

			# Update for the dish driving/pointing
			if DISH:
				if not (self.dishHandler.sleeping):
					try:
						(az, el) = self.dishHandler.compute_bearing(float(latitude),
																	float(longitude),
																	float(altitude))
						self.dishHandler.point(az, el)
					except:
						print("Error in computing or pointing")

			self.telemetryLabelDictionary["timestamp"].setText(timestamp)
			self.telemetryLabelDictionary["altitude"].setText(altitude)
			self.telemetryLabelDictionary["speed"].setText(groundSpeed)
			self.telemetryLabelDictionary["ascent"].setText(ascentRate)
			self.telemetryLabelDictionary["gps"].setText(latitude + ", " + longitude)
			self.telemetryLabelDictionary["voltage"].setText(voltage)
			self.telemetryLabelDictionary["tempInside"].setText(innerTemp)
			self.telemetryLabelDictionary["tempOutside"].setText(outerTemp)
			self.telemetryLabelDictionary["tempBattery"].setText(batteryTemp)

			# Update the map to show new waypoint
			javascriptCommand = "addVehicleWaypoint({}, {}, {});".format(
								self.javaArrayPosition["hab"],
								latitude,
								longitude)
			print(javascriptCommand)
			self.theMap.documentElement().evaluateJavaScript(javascriptCommand)

			self.dataTelemetryList.append([timestamp, altitude, latitude, longitude,
											voltage, innerTemp, outerTemp, batteryTemp])

		except:
			logTelemetry("Invalid data packet - data was not processed.")

	def updateChaseVehicleTelemetry(self, data):
		logTelemetry(data)

		try:
			splitMessage = data.split(",")
			callsign = splitMessage[0]
			timestamp = splitMessage[1]
			if (len(timestamp) > 0):
				timestamp = timestamp[:2] + ":" + timestamp[2:4]
			latitude = splitMessage[2]
			longitude = splitMessage[3]

			self.statusLabelList[callsign].setStyleSheet("QFrame { background-color: Green }")

			self.chaseVehicleGpsLabel[callsign][0].setText("{} - {}".format(self.callsignToString[callsign], timestamp))
			self.chaseVehicleGpsLabel[callsign][1].setText("{}, {}".format(latitude, longitude))

			# Update the map to show new waypoint
			javascriptCommand = "addVehicleWaypoint({}, {}, {});".format(
								self.javaArrayPosition[callsign],
								latitude,
								longitude)

			self.theMap.documentElement().evaluateJavaScript(javascriptCommand)

		except:
			print("Failure to parse")
			logTelemetry("Invalid data packet - data was not processed.")

	def processBalloonCommandResponse(self, message):
		if (message == "BRM_ARMED"):
			self.balloonReleaseArmed = True
			self.releaseBalloonButton.setDisabled(False)
			self.releaseBalloonButton.setStyleSheet("background-color: Green")
			self.commandStatusLabel.setText("Balloon release successfully armed")
		elif (message == "BRM_DISARMED"):
			self.balloonReleaseArmed = False
			self.releaseBalloonButton.setDisabled(True)
			self.releaseBalloonButton.setStyleSheet("background-color: Salmon")
			self.commandStatusLabel.setText("Balloon release is now disarmed")
		elif (message == "BRM_ACTIVATED"):
			self.balloonReleaseActivated = True
			self.commandStatusLabel.setText("Balloon release has been activated")
			self.armBrmButton.setText("Reset BRM")
			self.armBrmButton.clicked.disconnect()
			self.armBrmButton.clicked.connect(self.resetBalloonRelease)
		elif (message == "BRM_RESET"):
			self.balloonReleaseActivated = False
			self.commandStatusLabel.setText("Balloon release has been reset")
			self.armBrmButton.setText("Arm/Disarm BRM")
			self.armBrmButton.clicked.disconnect()
			self.armBrmButton.clicked.connect(self.armBalloonRelease)
			self.releaseBalloonButton.setStyleSheet("background-color: Salmon")
			self.releaseBalloonButton.setDisabled(True)
		else:
			self.commandStatusLabel.setText("Unknown command response received")
			print("Unknown: " + str(message))

	def armBalloonRelease(self):
		windowLayout = QtGui.QGridLayout()
		popupWidget = QtGui.QDialog()

		if (self.balloonReleaseArmed):
			confirmMessage = "Balloon Release Mechanism has been armed"
		else:
			confirmMessage = "Balloon Release Mechanism does not appear to be armed."

		armedLabel = QtGui.QLabel(confirmMessage)

		armButton = QtGui.QPushButton("ARM BRM", self)
		armButton.clicked.connect(popupWidget.accept)
		armButton.setCheckable(True)
		armButton.setChecked(False)
		disarmButton = QtGui.QPushButton("DISARM BRM", self)
		disarmButton.clicked.connect(popupWidget.accept)
		disarmButton.setCheckable(True)
		disarmButton.setChecked(False)
		cancelButton = QtGui.QPushButton("Cancel", self)
		cancelButton.setDefault(True)
		cancelButton.clicked.connect(popupWidget.reject)

		windowLayout.addWidget(armedLabel, 1, 0, 1, 3)

		windowLayout.addWidget(disarmButton, 10, 0)
		windowLayout.addWidget(armButton, 10, 1)
		windowLayout.addWidget(cancelButton, 10, 2)

		popupWidget.setLayout(windowLayout)
		popupWidget.setWindowTitle("Settings")

		if (popupWidget.exec_()):
			if (armButton.isChecked()):
				self.serialHandler.armBalloonFlag = True
				self.serialHandler.disarmBalloonFlag = False
				self.releaseBalloonButton.setDisabled(False)
				self.commandStatusLabel.setText("Sent arming command, waiting for response...")
			elif (disarmButton.isChecked()):
				self.serialHandler.disarmBalloonFlag = True
				self.serialHandler.armBalloonFlag = False
				self.releaseBalloonButton.setDisabled(True)
				self.releaseBalloonButton.setStyleSheet("background-color: Salmon")
				self.commandStatusLabel.setText("Sent command to disarm the BRM, waiting for response...")

	"""
	Shows popup window that confirms the release of the balloon.
	If not confirmed, does not release the balloon.
	If confirmed, sets the "releaseBalloonFlag" to true, which will be 
	handled by the Radio class on its next operation.
	"""
	def confirmAndReleaseBalloon(self):
		confirmStatement = "Would you like to activate the balloon release mechanism?"
		response = QtGui.QMessageBox.question(self, 'Confirmation',
				confirmStatement, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

		if (response == QtGui.QMessageBox.Yes):
			self.serialHandler.releaseBalloonFlag = True
			self.commandStatusLabel.setText("Commanding balloon release. Waiting for confirmation...")
		else:
			print("Negative response - Not releasing balloon")
			self.commandStatusLabel.setText("Negative response - No command issued")

	"""
	Shows popup window that confirms the release of the balloon.
	If not confirmed, does not release the balloon.
	If confirmed, sets the "releaseBalloonFlag" to true, which will be 
	handled by the Radio class on its next operation.
	"""
	def resetBalloonRelease(self):
		confirmStatement = "Are you sure you want to reset the BRM?"
		response = QtGui.QMessageBox.question(self, 'Confirmation',
				confirmStatement, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

		if (response == QtGui.QMessageBox.Yes):
			self.serialHandler.resetBalloonReleaseFlag = True
			self.commandStatusLabel.setText("Commanding BRM reset. Waiting for response...")

	"""
	Reads in text from the input box, and sends it out over the radio. Populates
	the QListView with the sent message as well.
	"""
	def sendMessage(self):
		userMessage = str(self.sendMessageEntryBox.text())
		self.serialHandler.userMessagesToSend.append(userMessage)
		self.sendMessageEntryBox.clear()

	"""
	Populates the chat box with the messages we've received
	"""
	def updateChat(self, message):
		itemToAdd = QtGui.QStandardItem(datetime.datetime.now().strftime("%H:%M - ") + message)
		self.messagingListViewModel.insertRow(0, itemToAdd)
		self.messagingListView.setModel(self.messagingListViewModel)
		self.messagingListView.show()
		winsound.PlaySound("media/chatSound.wav", winsound.SND_ASYNC)

	def serialFailureDisplay(self, message):
# 		if (self.notifyOnSerialError):
		if (False):
			QtGui.QMessageBox.question(self, "Error", message, QtGui.QMessageBox.Ok)
			self.changeSettings()

	def precisionSpinBoxHelp(self):
		helpString = ("To calculate the ascent rate and ground speed\n" +
						"we need to use at least two data points.\n\n" +
						"More data points gives a longer-running average.\n\n" +
						"Fewer data points gives us a more instantaneous\n" +
						"perspective.\n\n" +
						"Default setting is 5 data points, full range is 2-25")
		QtGui.QMessageBox.information(self, "Help", helpString, QtGui.QMessageBox.Ok)

	def selectPredictionFileBrowser(self):
		self.predictionFileName = QtGui.QFileDialog.getOpenFileName(self)
		self.selectPrecisionDialogWidget.raise_()
		self.selectPrecisionDialogWidget.activateWindow()

	def openPredictionsDialog(self):
		windowLayout = QtGui.QGridLayout()
		self.selectPrecisionDialogWidget = QtGui.QDialog()

		selectButton = QtGui.QPushButton("Send Image", self)
		selectButton.setDefault(True)
		selectButton.clicked.connect(self.selectPrecisionDialogWidget.accept)
		cancelButton = QtGui.QPushButton("Cancel", self)
		cancelButton.clicked.connect(self.selectPrecisionDialogWidget.reject)

		imageNameLabel = QtGui.QLabel("Image Name")
		imageSelectButton = QtGui.QPushButton("Select")

		imageSelectButton.clicked.connect(self.selectPredictionFileBrowser)

		windowLayout.addWidget(imageNameLabel, 2, 0)
		windowLayout.addWidget(imageSelectButton, 2, 1, 1, 2)
		windowLayout.addWidget(selectButton, 10, 1)
		windowLayout.addWidget(cancelButton, 10, 2)

		self.selectPrecisionDialogWidget.setLayout(windowLayout)
		self.selectPrecisionDialogWidget.setWindowTitle("Send Image")

		if (self.selectPrecisionDialogWidget.exec_()):
			if (len(self.predictionFileName) > 0):
				try:
					imageFile = open(self.predictionFileName, "rb")
					self.serialHandler.imageToSend = (imageFile.read())
					self.serialHandler.imageReadyToSend = True
				except:
					QtGui.QMessageBox.information(self, "Error", "Could not open image",
												 QtGui.QMessageBox.Ok)
			else:
				QtGui.QMessageBox.information(self, "Error", "No Image Selected",
											 QtGui.QMessageBox.Ok)

	def displayReceivedImage(self, fileName):
		windowLayout = QtGui.QGridLayout()
		popupWidget = QtGui.QDialog()

		popupWidget.setLayout(windowLayout)
		popupWidget.show()
		return None

	"""
	Opens a dialog to edit the current COM port in use. Sets the self.RADIO_SERIAL_PORT to 
	user-entered text.
	"""
	def changeSettings(self):
		windowLayout = QtGui.QGridLayout()
		popupWidget = QtGui.QDialog()

		selectCallsignLabel = QtGui.QLabel("Callsign")
		selectCallsignComboBox = QtGui.QComboBox()
		selectCallsignComboBox.addItem("hab")
		selectCallsignComboBox.addItem("nps")
		selectCallsignComboBox.addItem("chase1")
		selectCallsignComboBox.addItem("chase2")
		selectCallsignComboBox.addItem("chase3")

		index = selectCallsignComboBox.findText(self.serialHandler.RADIO_CALLSIGN)
		selectCallsignComboBox.setCurrentIndex(index)

		radioPortPromptLabel = QtGui.QLabel("Radio Port")
		radioPortTextBox = QtGui.QLineEdit()
		radioPortTextBox.setText(self.serialHandler.RADIO_SERIAL_PORT)

		gpsPortPromptLabel = QtGui.QLabel("GPS Port")
		gpsPortTextBox = QtGui.QLineEdit()
		gpsPortTextBox.setText(self.serialHandler.GPS_SERIAL_PORT)

		gpsRatePromptLabel = QtGui.QLabel("GPS Rate (s)")
		gpsRateLineEdit = QtGui.QLineEdit(str(self.serialHandler.HEARTBEAT_INTERVAL))

		precisionSpinBoxLabel = QtGui.QLabel("Rate Sensitivity")
		precisionSpinBoxHelpButton = QtGui.QPushButton("?")
		precisionSpinBoxHelpButton.clicked.connect(self.precisionSpinBoxHelp)

		precisionSpinBox = QtGui.QSpinBox()
		precisionSpinBox.setValue(self.telemetryValuesToInclude)
		precisionSpinBox.setRange(2, 25)
		precisionSpinBox.setMinimumSize(20, 20)
		precisionSpinBox.setAlignment(QtCore.Qt.AlignCenter)

		openDialogOnFailureCheckBox = QtGui.QCheckBox("Notify on serial error")
		if (self.notifyOnSerialError):
			openDialogOnFailureCheckBox.setChecked(True)

		selectButton = QtGui.QPushButton("Save Settings", self)
		selectButton.setDefault(True)
		selectButton.clicked.connect(popupWidget.accept)
		cancelButton = QtGui.QPushButton("Cancel", self)
		cancelButton.clicked.connect(popupWidget.reject)

		windowLayout.addWidget(selectCallsignLabel, 1, 0)
		windowLayout.addWidget(selectCallsignComboBox, 1, 1, 1, 2)
		windowLayout.addWidget(precisionSpinBoxLabel, 2, 0, 1, 1)
		windowLayout.addWidget(precisionSpinBox, 2, 1)
		windowLayout.addWidget(precisionSpinBoxHelpButton, 2, 2)
		windowLayout.addWidget(radioPortPromptLabel, 3, 0)
		windowLayout.addWidget(radioPortTextBox, 3, 1, 1, 2)
		windowLayout.addWidget(gpsPortPromptLabel, 4, 0)
		windowLayout.addWidget(gpsPortTextBox, 4, 1, 1, 2)
		windowLayout.addWidget(gpsRatePromptLabel, 5, 0)
		windowLayout.addWidget(gpsRateLineEdit, 5, 1, 1, 2)
		windowLayout.addWidget(openDialogOnFailureCheckBox, 6, 1, 1, 2)

		windowLayout.addWidget(selectButton, 10, 1)
		windowLayout.addWidget(cancelButton, 10, 2)

		popupWidget.setLayout(windowLayout)
		popupWidget.setWindowTitle("Settings")

		if (popupWidget.exec_()):
			if (len(radioPortTextBox.text()) > 0 and
				str(radioPortTextBox.text()) != self.serialHandler.RADIO_SERIAL_PORT):
				self.serialHandler.RADIO_SERIAL_PORT = str(radioPortTextBox.text().replace("\n", ""))
				self.serialHandler.radioSerialPortChanged = True
			if (len(gpsPortTextBox.text()) > 0 and
				str(gpsPortTextBox.text()) != self.serialHandler.GPS_SERIAL_PORT):
				self.serialHandler.GPS_SERIAL_PORT = str(gpsPortTextBox.text().replace("\n", ""))
				self.serialHandler.gpsSerialPortChanged = True
			if (len(gpsRateLineEdit.text()) > 0 and
				str(gpsRateLineEdit.text()) != self.serialHandler.HEARTBEAT_INTERVAL):
				self.serialHandler.HEARTBEAT_INTERVAL = int(gpsRateLineEdit.text().replace("\n", ""))
			if not (str(selectCallsignComboBox.currentText()) == self.serialHandler.RADIO_CALLSIGN):
				self.serialHandler.RADIO_CALLSIGN = str(selectCallsignComboBox.currentText())
				self.sendMessageCallsign.setText(self.callsignToString[self.serialHandler.RADIO_CALLSIGN])
				self.updateActiveNetwork()
			if (openDialogOnFailureCheckBox.isChecked()):
				self.notifyOnSerialError = True
			else:
				self.notifyOnSerialError = False
			self.telemetryValuesToInclude = int(precisionSpinBox.value())

		self.serialHandler.settingsWindowOpen = False

	def updateActiveNetwork(self):
		self.serialHandler.activeNodes[self.serialHandler.RADIO_CALLSIGN] = 3

		for callsign, label in self.statusLabelList.items():
			if (self.serialHandler.activeNodes[callsign] > 0):
				label.setStyleSheet("QFrame { background-color: Green }")
			else:
				label.setStyleSheet("QFrame { background-color: Salmon }")

	def updateSpotPositions(self):
		spotXmlFile = urllib2.urlopen(SPOT_API_URL)
		spotXmlData = spotXmlFile.read()
		spotXmlFile.close()

		spotData = ET.fromstring(spotXmlData)
		for message in spotData.iter("message"):
			name = message.find("messengerName").text
			lat = message.find("latitude").text
			long = message.find("longitude").text
			time = message.find("dateTime").text

			# Update the map to show new waypoint
			javascriptCommand = "addSpotMarker({}, {}, {});".format(
								self.javaArrayPosition[self.spotToVehicleDictionary[name]],
								lat,
								long)
			logGui(javascriptCommand)
			self.theMap.documentElement().evaluateJavaScript(javascriptCommand)

	def calculateRates(self):
		groundSpeed = "NONE"
		ascentRate = "NONE"

		if (len(self.dataTelemetryList) > 1):
			time1 = self.dataTelemetryList[0][0].split(":")
			time2 = self.dataTelemetryList[-1][0].split(":")

			alt1 = float(self.dataTelemetryList[0][1])
			alt2 = float(self.dataTelemetryList[-1][1])

			lat1 = float(self.dataTelemetryList[0][2])
			lat2 = float(self.dataTelemetryList[-1][2])

			long1 = float(self.dataTelemetryList[0][3])
			long2 = float(self.dataTelemetryList[-1][3])

			time1InSeconds = int(time1[0]) * 3600 + int(time1[1]) * 60 + int(time1[2])
			time2InSeconds = int(time2[0]) * 3600 + int(time2[1]) * 60 + int(time2[2])

			secondsTaken = time2InSeconds - time1InSeconds
			distanceTraveled = self.distance_on_unit_sphere(lat1, long1, lat2, long2)
			altitudeDifference = alt2 - alt1

			groundSpeed = "{:.2f}".format(distanceTraveled / secondsTaken)
			ascentRate = "{:.2f}".format(altitudeDifference / secondsTaken)

		return groundSpeed, ascentRate

	"""
	Found online at http://www.johndcook.com/blog/python_longitude_latitude/
	"""
	def distance_on_unit_sphere(self, lat1, long1, lat2, long2):
		returnValue = -1

		try:
			# Convert latitude and longitude to spherical coordinates in radians.
			degrees_to_radians = pi / 180.0

			# phi = 90 - latitude
			phi1 = (90.0 - lat1) * degrees_to_radians
			phi2 = (90.0 - lat2) * degrees_to_radians

			# theta = longitude
			theta1 = long1 * degrees_to_radians
			theta2 = long2 * degrees_to_radians

			# Compute spherical distance from spherical coordinates.
			cos = (sin(phi1) * sin(phi2) * cos(theta1 - theta2) +
					 cos(phi1) * cos(phi2))
			arc = acos(cos)

			# Multiple arc by radius of earth in miles
			returnValue = arc * 6378100

		except:
			returnValue = -1

		return returnValue


"""
Below is the radio handler
TX/RX operations, as well as RaspPi interfacing occurs below
"""
class serialHandlerThread(QtCore.QThread):
	balloonDataSignalReceived = QtCore.pyqtSignal(object)
	balloonAckReceived = QtCore.pyqtSignal(object)
	vehicleDataReceived = QtCore.pyqtSignal(object)
	invalidSerialPort = QtCore.pyqtSignal(object)
	chatMessageReceived = QtCore.pyqtSignal(object)
	radioConsoleUpdateSignal = QtCore.pyqtSignal(object)
	updateNetworkStatusSignal = QtCore.pyqtSignal()

	def __init__(self):
		if (TEST_MODE):
			self.inputTestFile = open("test_telemetry.txt", "r")
		QtCore.QThread.__init__(self)

		self.HEARTBEAT_INTERVAL = 5
		self.RADIO_SERIAL_PORT = "COM3"
		self.RADIO_CALLSIGN = "chase1"
		self.RADIO_BAUDRATE = 9600
		self.radioSerial = None

		self.GPS_SERIAL_PORT = "COM8"
		self.GPS_BAUDRATE = 4800
		self.gpsSerial = None

		# Set up semaphore-like variables
		self.sendingSerialMessage = False
		self.validHeartbeatReceived = False

		self.activeNodes = {}
		self.activeNodes["chase1"] = 0
		self.activeNodes["chase2"] = 0
		self.activeNodes["chase3"] = 0
		self.activeNodes["hab"] = 0
		self.activeNodes["nps"] = 0

		self.releaseBalloonFlag = False
		self.resetBalloonReleaseFlag = False
		self.armBalloonFlag = False
		self.disarmBalloonFlag = False

		self.settingsWindowOpen = False
		self.radioSerialPortChanged = False
		self.gpsSerialPortChanged = False
		self.serialBaudrateChanged = False

		self.userMessagesToSend = []
		self.imageToSend = ""
		self.imageReadyToSend = False
		self.imageOutputCounter = 0

	def run(self):
		counter = self.HEARTBEAT_INTERVAL

		if (TEST_MODE):
			for line in self.inputTestFile:
				sleep(1.5)
				self.handleMessage(line)

		self.openRadioSerialPort()
		self.openGpsSerialPort()
		self.sendHeartbeat()

		while(True):
			if (self.radioSerialPortChanged):
				self.openRadioSerialPort()
				self.radioSerialPortChanged = False

			if (self.gpsSerialPortChanged):
				self.openGpsSerialPort()
				self.gpsSerialPortChanged = False

			if (self.releaseBalloonFlag):
				self.sendReleaseCommand()
				self.releaseBalloonFlag = False

			if (self.resetBalloonReleaseFlag):
				self.sendResetBrmCommand()
				self.resetBalloonReleaseFlag = False

			if (self.armBalloonFlag):
				self.radioSerialOutput("cmd,ARM_BRM")
				self.armBalloonFlag = False

			if (self.disarmBalloonFlag):
				self.radioSerialOutput("cmd,DISARM_BRM")
				self.disarmBalloonFlag = False

			if (self.imageReadyToSend):
				self.sendImage()
				self.imageToSend = ""

			while (len(self.userMessagesToSend) > 0):
				formattedMessage = "chat," + self.userMessagesToSend[0]
				self.radioSerialOutput(formattedMessage, True)
				self.userMessagesToSend.pop(0)

			messageReceived = self.radioSerialInput()

			if (len(messageReceived) > 0):
				self.handleMessage(messageReceived)

			if (counter == 0):
				for key, value in self.activeNodes.items():
					self.activeNodes[key] -= 1
					if (self.activeNodes[key] <= 0):
						self.updateNetworkStatusSignal.emit()

				self.sendCurrentPosition()
				self.sendHeartbeat()
				counter = self.HEARTBEAT_INTERVAL
			else:
				counter -= 1

			logRadio(messageReceived + "\n")

	"""
	TODO: Refactor handleMessage to be more concise and clean
	"""
	# Performs an action based on the message sent to it
	# Returns True or False based on the success of that action
	def handleMessage(self, message):
		for line in message.split(',END_TX\n'):
			if (len(line) > 0):
				if (line[:3] == "hab"):
					self.receivedHeartbeat("hab")
					if (line[4:8] == "chat"):
						self.chatMessageReceived.emit("HAB: " + line[9:])
					if (line[4:8] == "data"):
						self.balloonDataSignalReceived.emit(line[9:-1])
					elif(line[4:7] == "ack"):
						self.balloonAckReceived.emit(line[8:])

				elif (line[:3] == "nps"):
					self.receivedHeartbeat("nps")
					if (line[4:8] == "chat"):
						self.chatMessageReceived.emit("NPS: " + line[9:])
					elif(line[4:9] == "image"):
						self.parsePredictionMessage(line[10:])

				elif (line[:6] == "chase1"):
					self.receivedHeartbeat("chase1")
					if (line[7:11] == "chat"):
						self.chatMessageReceived.emit("Chase 1: " + line[12:])
						print(line[11:12])
					elif (line[7:11] == "data"):
						self.vehicleDataReceived.emit("chase1," + line[12:])
					elif(line[7:12] == "image"):
						print("Received image!")
						self.parsePredictionMessage(message[13:])

				elif (line[:6] == "chase2"):
					self.receivedHeartbeat("chase2")
					if (line[7:11] == "chat"):
						self.chatMessageReceived.emit("Chase 2: " + line[12:])
					elif (line[7:11] == "data"):
						self.vehicleDataReceived.emit("chase2," + line[12:])
					elif(line[7:12] == "image"):
						print("Received image!")
						self.parsePredictionMessage(message[13:])

				elif (line[:6] == "chase3"):
					self.receivedHeartbeat("chase3")
					if (line[7:11] == "chat"):
						self.chatMessageReceived.emit("Chase 3: " + line[12:])
					elif (line[7:11] == "data"):
						self.vehicleDataReceived.emit("chase3," + line[12:])
					elif(line[7:12] == "image"):
						print("Received image!")
						self.parsePredictionMessage(message[13:])

			logRadio("Handling message: " + line)

	def sendCurrentPosition(self):
		try:
			gpsData = self.getFormattedGpsData()
			if (gpsData != "INVALID DATA"):
				self.radioSerialOutput("data," + gpsData, True)
		except:
			print("Unable to send current position")

	def sendImage(self):
		numPackets = len(self.imageToSend) / 1000
		currIndex = 0

		while(currIndex < numPackets):
			packet = self.imageToSend[currIndex * 1000 : (currIndex + 1) * 1000]
			self.radioSerialOutput("image," + packet)
			currIndex += 1

		self.radioSerialOutput("image,{}".format(self.imageToSend[numPackets * 1000 :-1]))

		self.imageReadyToSend = False

	def parsePredictionMessage(self, rawMessage):
		print("Decommutating...")
		parsedMessage = None
		try:
			parsedMessage = open("output{}.png".format(self.imageOutputCounter), "ab")
		except:
			parsedMessage = open("output{}.png".format(self.imageOutputCounter), "wb")

		parsedMessage.write(rawMessage)

		parsedMessage.close()

	# Takes a heartbeat signal and determines which node sent it out. That node
	# is set as currently active on the network
	def receivedHeartbeat(self, heartbeatSignalReceived):
		for key, value in self.activeNodes.items():
			if (heartbeatSignalReceived == key):
				self.activeNodes[key] = 3

		self.updateNetworkStatusSignal.emit()

	# Sends a "heartbeat" signal to other radios to verify radio is currently
	# active on the network
	def sendHeartbeat(self):
		self.radioSerialOutput("alive")

	def sendReleaseCommand(self):
		print("Releasing balloon")
		counter = 3

		while (counter > 0):
			print("Attempt " + str(counter))
			counter -= 1
			self.radioSerialOutput("cmd,SSAG_RELEASE_BALLOON")
			sleep(2)

	def sendResetBrmCommand(self):
		print("Resetting balloon")
		counter = 3

		while (counter > 0):
			print("Attempt " + str(counter))
			counter -= 1
			self.radioSerialOutput("cmd,RESET_BRM")
			sleep(2)

	def radioSerialInput(self):
		serialInput = ""

		try:
			if not (self.radioSerial.inWaiting()):
				sleep(0.75)

			while(self.radioSerial.inWaiting()):
				serialInput += self.radioSerial.readline()

			if (len(serialInput) > 0):
				self.radioConsoleUpdateSignal.emit(serialInput)

		except:
			if (self.settingsWindowOpen):
				sleep(1)
			else:
				self.invalidSerialPort.emit("Please enter a valid serial port")
				self.settingsWindowOpen = True
			logRadio("Unable to write to serial port on " + self.RADIO_SERIAL_PORT)
			print("Unable to open serial port for input on " + self.RADIO_SERIAL_PORT)

		return serialInput

	def radioSerialOutput(self, line, processSentMessage = False):
		try:
			preparedMessage = self.RADIO_CALLSIGN + "," + line + ",END_TX\n"
			if (processSentMessage):
				self.handleMessage(preparedMessage)

			self.radioConsoleUpdateSignal.emit(preparedMessage)
			self.radioSerial.write(preparedMessage)
		except:
			if (self.settingsWindowOpen):
				sleep(1)
			else:
				self.invalidSerialPort.emit("Please enter a valid serial port")
				self.settingsWindowOpen = True
			logRadio("Unable to write to serial port on " + self.RADIO_SERIAL_PORT)

	def openRadioSerialPort(self):
		try:
			self.radioSerial.close()
		except:
			logRadio("Unable to close serial port " + self.RADIO_SERIAL_PORT)

		try:
			self.radioSerial = serial.Serial(port = self.RADIO_SERIAL_PORT, baudrate = self.RADIO_BAUDRATE, timeout = 2)
		except:
			if (self.settingsWindowOpen):
				sleep(3)
			else:
				self.invalidSerialPort.emit("Radio serial port is invalid")
				self.settingsWindowOpen = True

	def gpsSerialInput(self):
		messageReceived = "NO_GPS_DATA\n"
		serialInput = ""
		retries = 10
		iterationsToWait = 100

		try:
			while (retries > 0 and iterationsToWait > 0):
				if (self.gpsSerial.inWaiting() > 0):  # If there's a buffer for us to read
					serialInput = self.gpsSerial.readline()
					if (serialInput[:6] == r"$GPGGA"):  # Makes sure this is the line we want
						break  # This is our stop
					else:
						# print("Discarding unused data: " + serialInput)
						serialInput = ""  # This is not the data we're looking for
						retries -= 1
				else:
					iterationsToWait -= 1

		except:
			print("Unable to read serial input: {0} at baud {1}".format(self.GPS_SERIAL_PORT, self.GPS_BAUDRATE))

		if (retries > 0 and iterationsToWait > 0):  # We found what we wanted
			messageReceived = serialInput

		return messageReceived

	def getFormattedGpsData(self):
		finalDataString = "INVALID DATA"
		rawGpsString = self.gpsSerialInput()

		logTelemetry(self.RADIO_CALLSIGN + rawGpsString)

		if (rawGpsString != "NO_GPS_DATA\n"):
			try:
				gpsSplit = rawGpsString.split(",")
				time = gpsSplit[1][:6]

				latitude = gpsSplit[2]
				degrees = float(latitude[:2])
				minutes = float(latitude[2:])

				if (gpsSplit[3] == "S"):
					latitude = "%4.5f" % (-1 * (degrees + (minutes / 60)))
				else:
					latitude = "%4.5f" % (degrees + (minutes / 60))

				longitude = gpsSplit[4]
				degrees = float(longitude[:3])
				minutes = float(longitude[3:])
				if (gpsSplit[5] == "W"):
					longitude = "%4.5f" % (-1 * (degrees + (minutes / 60)))
				else:
					longitude = "%4.5f" % (degrees + (minutes / 60))

				formattedGpsString = "{},{},{}".format(time, latitude, longitude)
			except:
				formattedGpsString = "0,0,0"

			if (formattedGpsString != "0,0,0"):
				finalDataString = formattedGpsString

		return finalDataString

	def openGpsSerialPort(self):
		try:
			self.gpsSerial.close()
		except:
			logRadio("Unable to close serial port " + self.GPS_SERIAL_PORT)

		try:
			self.gpsSerial = serial.Serial(port = self.GPS_SERIAL_PORT, baudrate = self.GPS_BAUDRATE, timeout = 2)
		except:
			if (self.settingsWindowOpen):
				sleep(3)
			else:
				self.invalidSerialPort.emit("GPS serial port cannot be opened")
				self.settingsWindowOpen = True

def logTelemetry(line):
	try:
		telemetryLogFile = open(TELEMETRY_LOG_FILE_LOCATION, "a")
		telemetryLogFile.write(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) + ": " + line + "\n")
		telemetryLogFile.close
	except:
		print("WARNING: Unable to log telemetry data")

def logGui(line):
	try:
		guiLogFile = open(GUI_LOG_FILE_LOCATION, "a")
		guiLogFile.write(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) + ": " + line + "\n")
		guiLogFile.close
	except:
		print("WARNING: Unable to log GUI data")

def logRadio(line):
	try:
		radioLogFile = open(RADIO_LOG_FILE_LOCATION, "a")
		radioLogFile.write(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) + ": " + line + "\n")
		radioLogFile.close
	except:
		print("WARNING: Unable to log radio operations data")

class dishHandlerThread(QtCore.QThread):
	def __init__(self):
		QtCore.QThread.__init__(self)

		self.old_az = -1
		self.new_az = self.old_az

		self.old_el = -1
		self.new_el = self.old_el

		self.firstRun = True
		self.sleeping = False

	def degrees(self, rad):
		return rad * 180.0 / pi

	def compute_bearing(self, blat, blon, balt):
		# Spanagel's coordinates
		llat = 36.595156
		llon = -121.876073
		lalt = 25

		Rearth = 3958.76

		llat_rad = llat * pi / 180.0
		llon_rad = llon * pi / 180.0
		blat_rad = blat * pi / 180.0
		blon_rad = blon * pi / 180.0
		dlon_rad = blon_rad - llon_rad
		lalt_mi = 0.000621371192 * lalt
		balt_mi = 0.000621371192 * balt

		a = (cos(blat_rad) * sin(dlon_rad)) ** 2
		b = (cos(llat_rad) * sin(blat_rad) - sin(llat_rad) * cos(blat_rad) * cos(dlon_rad)) ** 2
		c = sin(llat_rad) * sin(blat_rad) + cos(llat_rad) * cos(blat_rad) * cos(dlon_rad)
		sab = sqrt((a + b))

		dist = Rearth * atan2(sab, c)
		dist_km = dist * 1.609344
		el = atan((balt_mi - lalt_mi) / dist) * 180.0 / pi

		dx = cos(llat_rad) * sin(blat_rad) - sin(llat_rad) * cos(blat_rad) * cos(dlon_rad)
		dy = sin(dlon_rad) * cos(blat_rad)
		az = (self.degrees(atan2(dy, dx)) + 360) % 360

		return (az, el)

	def close(self):
		sock.send("AS;ES;\n")  # standby
		sock.close()

	def point(self, az, el):

		# Update positions
		self.new_az = az
		self.new_el = el

		if self.firstRun:
			self.old_az = self.new_az
			self.old_el = self.new_el
			self.firstRun = False

		# Set some hard values for the dish
		minEl = 0
		minAz = 1
		maxEl = 90
		maxAz = 359

		# Correct out-of-range AZ or ELs
		el = el if el > minEl else minEl
		el = el if el < maxEl else maxEl
		az = az if az > minAz else minAz
		az = az if az < maxAz else maxAz

		az_err = abs(self.new_az - self.old_az)
		el_err = abs(self.new_el - self.old_el)

		if  az_err >= 0.5 or el_err >= 0.5:
			try:
				sock.send("AM%0.2f;EM%0.2f;\n" % (az, el))
				print("Pointing to %03d %03d" % (az, el))

				# print("Sleeping %f" % max(az_err,el_err)*4 + 1)
				sleep(.9)
				sock.send("AS;ES;\n")  # standby
				self.old_az = self.new_az
				self.old_el = self.new_el

			except:
				print("Can't update position to dish ACU")
				self.close()

googleMapsHtml = """
<!DOCTYPE html>
<html>
	<head>
	<style>
		html, body, #map-canvas {
		height: 100%;
		margin: 0px;
		padding: 0px
		}
	</style>
	<script src="https://maps.googleapis.com/maps/api/js?v=3.exp&sensor=false&libraries=drawing"></script>
	<script>
		var map;
		var VEHICLES_TO_PLOT = 4
		var myCenter = new google.maps.LatLng(36.8623, -121.0413);
		
		var vehicleWaypointArray = [];
		var vehicleMarkerArray = [];
		var spotMarkerArray = [];
		
		var vehiclePathColors = ["#FF0000",
								"#007FFF",
								"#006600",
								"#FF9933"];
		
		var vehicleIconNames = ["balloon.png",
								"chase1.png",
								"chase2.png",
								"chase3.png"];
		
		for (i = 0; i < VEHICLES_TO_PLOT; i++)
		{
			vehicleWaypointArray.push([]);
			vehicleMarkerArray.push(new google.maps.Marker());
		}
		
		var iconBase = "http://fryarludwig.com/wp-content/uploads/2015/07/"
		
		function initialize() 
		{
			var mapOptions = 
			{
				center: myCenter,
				zoom: 9,
				mapTypeId: google.maps.MapTypeId.ROADMAP
			};
	
			map = new google.maps.Map(document.getElementById('map-canvas'), mapOptions);
		}
				
		function addVehicleWaypoint(index, lat, lng)
		{
			var vehiclePosition = new google.maps.LatLng(lat, lng);
			vehicleWaypointArray[index].push(vehiclePosition);
			
			vehicleMarkerArray[index].setMap(null);
			
			vehicleMarkerArray[index] = new google.maps.Marker(
												{position:vehiclePosition,
												icon: iconBase + vehicleIconNames[index],
												map:map});
												
			vehicleMarkerArray[index].setMap(map);
			
			var line = new google.maps.Polyline
			({
				path:vehicleWaypointArray[index],
				strokeColor:vehiclePathColors[index],
				strokeOpacity:0.8,
				strokeWeight:2,
				map:map
			});
		}		
					
		function addSpotMarker(index, lat, lng)
		{
			var spotMarkerPosition = new google.maps.LatLng(lat, lng);
			
			spotMarker = new google.maps.Marker({position:spotMarkerPosition,
												title:"SPOT",
												icon: iconBase + vehicleIconNames[index],
												map:map});
			
			spotMarker.setMap(map);
		}
		
		
		google.maps.event.addDomListener(window, 'load', initialize);

	</script>
	</head>
	<body>
	<div id="map-canvas"></div>
	</body>
</html>
"""


if __name__ == '__main__':
	logRadio("\n\nStarting Radio log\n")
	logGui("\n\nStarting GUI log\n")
	logTelemetry("\n\nStarting telemetry log\n")
	app = QtGui.QApplication(sys.argv)
	ex = mogsMainWindow()
	sys.exit(app.exec_())
