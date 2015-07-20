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
import math
import urllib2
import xml.etree.ElementTree as ET
from time import sleep
from PyQt4 import QtGui, QtCore
from PyQt4.QtWebKit import QWebView
from PyQt4.Qt import QWidget
from collections import OrderedDict

TELEMETRY_LOG_FILE_LOCATION = r"MoGS_telemetry_log.txt"
RADIO_LOG_FILE_LOCATION = r"MoGS_radio_log.txt"
GUI_LOG_FILE_LOCATION = r"MoGS_gui_log.txt"
SPOT_API_URL = r"https://api.findmespot.com/spot-main-web/consumer/rest-api/2.0/public/feed/00CFIiymlztJBFEN4cJOjNhlZSofClAxa/message.xml"

TEST_MODE = False  # Test mode pulls telemetry from file instead of radios

"""
PRIORITIES:

TODO: Lower the serial baudrate
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
		self.currentLabelPosition = 0
		self.VERTICAL_SPACING = 25
		self.positionTelemetryList = []
		self.dataTelemetryList = []
		self.telemetryValuesToInclude = 5
		self.messagingListView = QtGui.QListView()
		self.messagingListViewModel = QtGui.QStandardItemModel(self.messagingListView)
		self.sendMessageEntryBox = QtGui.QLineEdit()
		self.notifyOnSerialError = True

		self.sendImageDialogWidget = QtGui.QDialog()
		self.imageToSendFileName = ""

		super(mogsMainWindow, self).__init__()
		self.commandStatusLabel = QtGui.QLabel()
		self.statusLabelList = {"balloon" : QtGui.QLabel("Balloon", self),
								"chase1" : QtGui.QLabel("Chase 1", self),
								"chase2" : QtGui.QLabel("Chase 2", self),
								"chase3" : QtGui.QLabel("Chase 3", self),
								"chase4" : QtGui.QLabel("Chase 4", self),
								"nps" : QtGui.QLabel("  NPS  ", self)}

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

		self.javaArrayPosition = {"balloon" : 0,
								"chase1" : 1,
								"chase2" : 2,
								"chase3" : 3,
								"chase4" : 4,
								"nps" : 5}

		self.spotToVehicleDictionary = {"SSAGSpot1" : "balloon",
										"SSAGSpot2" : "chase1",
										"SSAGSpot3" : "chase2",
										"SSAGSpot4" : "chase3",
										"SSAGSpot5" : "chase4",
										"NONE" : "nps"}

		self.palette = QtGui.QPalette()

		self.radioHandler = serialHandlerThread()
		self.radioHandler.balloonDataSignalReceived.connect(self.updateBalloonDataTelemetry)
		self.radioHandler.vehicleDataReceived.connect(self.updateChaseVehicleTelemetry)
		self.radioHandler.invalidSerialPort.connect(self.serialFailureDisplay)
		self.radioHandler.chatMessageReceived.connect(self.updateChat)
		self.radioHandler.heartbeatReceivedSignal.connect(self.updateActiveNetwork)
		# add the other handlers here
		self.radioHandler.start()
		self.initUI()

	"""
	Populates the widgets and the main GUI window.
	"""
	def initUI(self):
		window_x = 1200
		window_y = 700

		self.col = QtGui.QColor(0, 0, 0)
		self.vLayout = QtGui.QGridLayout()
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

		telemetryWidget = self.createTelemetryWidget()
		messagingWidget = self.createMessagingWidget()
		commandWidget = self.createCommandWidget()
		networkWidget = self.createNetworkWidget()

		self.vLayout.addWidget(telemetryWidget, 0, 0, 5, 1)
		self.vLayout.addWidget(messagingWidget, 5, 0, 5, 1)
		self.vLayout.addWidget(commandWidget, 11, 0, 3, 1)
		self.vLayout.addWidget(networkWidget, 14, 0, 1, 1)

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
		layout.setSpacing(0)

		# Set up labels
		messagingLabel = QtGui.QLabel("Latest Messages:", self)
		messagingLabel.setAlignment(QtCore.Qt.AlignCenter)

		sendMessageButton = QtGui.QPushButton("Send", self)
		sendMessageButton.clicked[bool].connect(self.sendMessage)

		self.messagingListView.setWrapping(True)
		self.messagingListView.setWordWrap(True)
		self.messagingListView.setSpacing(1)
		self.messagingListView.setMinimumSize(300, 300)
		self.messagingListView.setFlow(QtGui.QListView.LeftToRight)

		self.sendMessageEntryBox.setMaxLength(160)
		self.sendMessageEntryBox.returnPressed.connect(self.sendMessage)

		layout.addWidget(messagingLabel, 0, 0, 1, 9)
		layout.addWidget(self.messagingListView, 1, 0, 5, 9)
		layout.addWidget(self.sendMessageEntryBox, 6, 0, 1, 8)
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
		commandLabel = QtGui.QLabel("Command Response:", self)
		commandLabel.setAlignment(QtCore.Qt.AlignCenter)

		self.commandStatusLabel = QtGui.QLabel("No Commands have been sent", self)
		self.commandStatusLabel.setAlignment(QtCore.Qt.AlignCenter)

		# Set up buttons for GUI window
		comPortButton = QtGui.QPushButton('Settings', self)
		comPortButton.clicked.connect(self.changeSettings)

		streetMapButton = QtGui.QPushButton('Predictions', self)
		streetMapButton.clicked[bool].connect(self.openPredictionsDialog)

		resizeMapButton = QtGui.QPushButton('Resize Map', self)
		resizeMapButton.clicked[bool].connect(self.onResize)

		balloonReleaseButton = QtGui.QPushButton('Release Balloon', self)
		balloonReleaseButton.setStyleSheet("background-color: Salmon")
		balloonReleaseButton.clicked[bool].connect(self.confirmAndReleaseBalloon)

		satelliteViewButton = QtGui.QPushButton('Update SPOT', self)
		satelliteViewButton.clicked[bool].connect(self.updateSpotPositions)

		audioLinkButton = QtGui.QPushButton('Audio Link mode', self)
		audioLinkButton.setCheckable(True)

		layout.addWidget(commandLabel, 0, 0, 1, 3)
		layout.addWidget(self.commandStatusLabel, 1, 0, 1, 3)
		layout.addWidget(comPortButton, 2, 2)
		layout.addWidget(resizeMapButton, 2, 1)
		layout.addWidget(streetMapButton, 2, 0)
		layout.addWidget(balloonReleaseButton, 3, 1)
		layout.addWidget(audioLinkButton, 3, 2)
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
		layoutLabel = QtGui.QLabel("Latest Telemetry")
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

		# Set all to show that there is no connection yet
		for key, statusLabel in self.statusLabelList.items():
			statusLabel.setAlignment(QtCore.Qt.AlignCenter)
			statusLabel.setFont(networkFont)
			statusLabel.setStyleSheet("QFrame { background-color: Salmon }")

		layout.addWidget(layoutLabel, 0, 0, 1, 4)
		layout.addWidget(self.statusLabelList["balloon"], 1, 0, 1, 2)
		layout.addWidget(self.statusLabelList["nps"], 1, 2, 1, 2)
		layout.addWidget(self.statusLabelList["chase1"], 2, 0)
		layout.addWidget(self.statusLabelList["chase2"], 2, 1)
		layout.addWidget(self.statusLabelList["chase3"], 2, 2)
		layout.addWidget(self.statusLabelList["chase4"], 2, 3)

		self.updateActiveNetwork()

		return widget

	"""
	Logs and parses the telemetry string passed from the Radio class, then
	updates the GUI to display the values. On invalid packet the data is logged
	but the GUI is not updated.
	No return value
	"""
	def updateBalloonDataTelemetry(self, data):
		logTelemetry(data)
		self.statusLabelList["balloon"].setStyleSheet("QFrame { background-color: Green }")

		while (len(self.dataTelemetryList) > self.telemetryValuesToInclude):
			self.dataTelemetryList.pop(0)

		try:
			splitMessage = data.split(",")
			timestamp = splitMessage[0]
			if (len(timestamp) > 0):
				timestamp = timestamp[:2] + ":" + timestamp[2:4] + ":" + timestamp[4:6]
			latitude = splitMessage[1]
			longitude = splitMessage[2]
			altitude = splitMessage[3]
			voltage = splitMessage[4]
			innerTemp = splitMessage[5]
			outerTemp = splitMessage[6]
			batteryTemp = splitMessage[7]

			groundSpeed, ascentRate = self.calculateRates()

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
								self.javaArrayPosition["balloon"],
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
			print(splitMessage)
			callsign = splitMessage[0]
			timestamp = splitMessage[1]
			if (len(timestamp) > 0):
				timestamp = timestamp[:2] + ":" + timestamp[2:4] + ":" + timestamp[4:6]
			latitude = splitMessage[2]
			longitude = splitMessage[3]

			self.statusLabelList[callsign].setStyleSheet("QFrame { background-color: Green }")

			# Update the map to show new waypoint
			javascriptCommand = "addVehicleWaypoint({}, {}, {});".format(
								self.javaArrayPosition[callsign],
								latitude,
								longitude)
			print(javascriptCommand)
			self.theMap.documentElement().evaluateJavaScript(javascriptCommand)

		except:
			print("Failure to parse")
			logTelemetry("Invalid data packet - data was not processed.")

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
			self.radioHandler.releaseBalloonFlag = True
			self.commandStatusLabel.setText("Commanding balloon release. Waiting for confirmation...")
		else:
			print("Negative response - Not releasing balloon")
			self.commandStatusLabel.setText("Negative response - No command issued")

	"""
	Reads in text from the input box, and sends it out over the radio. Populates
	the QListView with the sent message as well.
	"""
	def sendMessage(self):
		userMessage = str(self.sendMessageEntryBox.text())
		self.radioHandler.userMessagesToSend.append(userMessage)
		self.sendMessageEntryBox.clear()

	"""
	Populates the chat box with the messages we've received
	"""
	def updateChat(self, message):
		itemToAdd = QtGui.QStandardItem(message)
		self.messagingListViewModel.insertRow(0, itemToAdd)
		self.messagingListView.setModel(self.messagingListViewModel)
		self.messagingListView.show()

	def serialFailureDisplay(self, message):
		if (self.notifyOnSerialError):
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
		self.imageToSendFileName = QtGui.QFileDialog.getOpenFileName(self)
		self.sendImageDialogWidget.raise_()
		self.sendImageDialogWidget.activateWindow()

	def openPredictionsDialog(self):
		windowLayout = QtGui.QGridLayout()
		self.sendImageDialogWidget = QtGui.QDialog()

		selectButton = QtGui.QPushButton("Send Image", self)
		selectButton.setDefault(True)
		selectButton.clicked.connect(self.sendImageDialogWidget.accept)
		cancelButton = QtGui.QPushButton("Cancel", self)
		cancelButton.clicked.connect(self.sendImageDialogWidget.reject)

		imageNameLabel = QtGui.QLabel("Image Name")
		imageSelectButton = QtGui.QPushButton("Select")

		imageSelectButton.clicked.connect(self.selectPredictionFileBrowser)

		windowLayout.addWidget(imageNameLabel, 2, 0)
		windowLayout.addWidget(imageSelectButton, 2, 1, 1, 2)
		windowLayout.addWidget(selectButton, 10, 1)
		windowLayout.addWidget(cancelButton, 10, 2)

		self.sendImageDialogWidget.setLayout(windowLayout)
		self.sendImageDialogWidget.setWindowTitle("Send Image")

		if (self.sendImageDialogWidget.exec_()):
			if (len(self.imageToSendFileName) > 0):
				try:
					imageFile = open(self.imageToSendFileName, "rb")
					self.radioHandler.imageToSend = (imageFile.read())
					self.radioHandler.imageReadyToSend = True
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

	def plotGpsCoordinates(self):
		return None

	def requestPayloadImage(self):
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
		selectCallsignComboBox.addItem("nps")
		selectCallsignComboBox.addItem("chase1")
		selectCallsignComboBox.addItem("chase2")
		selectCallsignComboBox.addItem("chase3")

		index = selectCallsignComboBox.findText(self.radioHandler.RADIO_CALLSIGN)
		selectCallsignComboBox.setCurrentIndex(index)

		radioPortPromptLabel = QtGui.QLabel("Radio Port")
		radioPortTextBox = QtGui.QLineEdit()
		radioPortTextBox.setText(self.radioHandler.RADIO_SERIAL_PORT)

		gpsPortPromptLabel = QtGui.QLabel("GPS Port")
		gpsPortTextBox = QtGui.QLineEdit()
		gpsPortTextBox.setText(self.radioHandler.GPS_SERIAL_PORT)

		gpsRatePromptLabel = QtGui.QLabel("GPS Rate (s)")
		gpsRateLineEdit = QtGui.QLineEdit(str(self.radioHandler.HEARTBEAT_INTERVAL))

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
		windowLayout.addWidget(gpsRatePromptLabel, 4, 0)
		windowLayout.addWidget(gpsRateLineEdit, 4, 1, 1, 2)
		windowLayout.addWidget(gpsPortPromptLabel, 5, 0)
		windowLayout.addWidget(gpsPortTextBox, 5, 1, 1, 2)
		windowLayout.addWidget(openDialogOnFailureCheckBox, 6, 1, 1, 2)

		windowLayout.addWidget(selectButton, 10, 1)
		windowLayout.addWidget(cancelButton, 10, 2)

		popupWidget.setLayout(windowLayout)
		popupWidget.setWindowTitle("Settings")

		if (popupWidget.exec_()):
			if (len(radioPortTextBox.text()) > 0 and
				str(radioPortTextBox.text()) != self.radioHandler.RADIO_SERIAL_PORT):
				self.radioHandler.RADIO_SERIAL_PORT = str(radioPortTextBox.text().replace("\n", ""))
				self.radioHandler.radioSerialPortChanged = True
			if (len(gpsPortTextBox.text()) > 0 and
				str(gpsPortTextBox.text()) != self.radioHandler.GPS_SERIAL_PORT):
				self.radioHandler.GPS_SERIAL_PORT = str(gpsPortTextBox.text().replace("\n", ""))
				self.radioHandler.gpsSerialPortChanged = True
			if (len(gpsRateLineEdit.text()) > 0 and
				str(gpsRateLineEdit.text()) != self.radioHandler.HEARTBEAT_INTERVAL):
				self.radioHandler.HEARTBEAT_INTERVAL = str(gpsRateLineEdit.text().replace("\n", ""))
			if not (str(selectCallsignComboBox.currentText()) == self.radioHandler.RADIO_CALLSIGN):
				self.radioHandler.activeNodes[self.radioHandler.RADIO_CALLSIGN] = False
				self.radioHandler.RADIO_CALLSIGN = str(selectCallsignComboBox.currentText())
				self.updateActiveNetwork()
			if (openDialogOnFailureCheckBox.isChecked()):
				self.notifyOnSerialError = True
			else:
				self.notifyOnSerialError = False
			self.telemetryValuesToInclude = int(precisionSpinBox.value())

		self.radioHandler.settingsWindowOpen = False

	def updateActiveNetwork(self):
		self.radioHandler.activeNodes[self.radioHandler.RADIO_CALLSIGN] = True

		for callsign, label in self.statusLabelList.items():
			if (self.radioHandler.activeNodes[callsign]):
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
			print (javascriptCommand)
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
			degrees_to_radians = math.pi / 180.0

			# phi = 90 - latitude
			phi1 = (90.0 - lat1) * degrees_to_radians
			phi2 = (90.0 - lat2) * degrees_to_radians

			# theta = longitude
			theta1 = long1 * degrees_to_radians
			theta2 = long2 * degrees_to_radians

			# Compute spherical distance from spherical coordinates.
			cos = (math.sin(phi1) * math.sin(phi2) * math.cos(theta1 - theta2) +
					 math.cos(phi1) * math.cos(phi2))
			arc = math.acos(cos)

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
	vehicleDataReceived = QtCore.pyqtSignal(object)
	invalidSerialPort = QtCore.pyqtSignal(object)
	chatMessageReceived = QtCore.pyqtSignal(object)
	heartbeatReceivedSignal = QtCore.pyqtSignal()

	def __init__(self):
		if (TEST_MODE):
			self.inputTestFile = open("test_telemetry.txt")
		QtCore.QThread.__init__(self)

		# self.HEARTBEAT_INTERVAL = 60
		self.HEARTBEAT_INTERVAL = 5
		self.RADIO_SERIAL_PORT = "COM4"
		self.RADIO_CALLSIGN = "chase1"
		self.RADIO_BAUDRATE = 9600
		self.radioSerial = None

		self.GPS_SERIAL_PORT = "COM3"
		self.GPS_BAUDRATE = 4800
		self.gpsSerial = None

		# Set up semaphore-like variables
		self.sendingSerialMessage = False
		self.validHeartbeatReceived = False

		self.activeNodes = {}
		self.activeNodes["chase1"] = False
		self.activeNodes["chase2"] = False
		self.activeNodes["chase3"] = False
		self.activeNodes["chase4"] = False
		self.activeNodes["balloon"] = False
		self.activeNodes["nps"] = False

		self.releaseBalloonFlag = False
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
			sleep(1)
			for line in self.inputTestFile:
				sleep(1)
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

			if (self.imageReadyToSend):
				self.sendImage()
				self.imageToSend = ""

			while (len(self.userMessagesToSend) > 0):
				formattedMessage = "chat," + self.userMessagesToSend[0]
				self.radioSerialOutput(formattedMessage)
				self.userMessagesToSend.pop(0)

			messageReceived = self.radioSerialInput()

			if (len(messageReceived) > 0):
				self.handleMessage(messageReceived)

			if (counter == 0):
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
				if (line[:3] == "HAB"):
					self.receivedHeartbeat("balloon")
					if (line[4:8] == "data"):
						self.balloonDataSignalReceived.emit(line[9:-1])
					elif(line[4:9] == "image"):
						self.parsePredictionMessage(line[10:])

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

				elif (line[:6] == "chase4"):
					self.receivedHeartbeat("chase4")
					if (line[7:11] == "chat"):
						self.chatMessageReceived.emit("Chase 4: " + line[12:])
					elif (line[7:11] == "data"):
						self.vehicleDataReceived.emit("chase4," + line[12:])
					elif(line[7:12] == "image"):
						print("Received image!")
						self.parsePredictionMessage(message[13:])

			logRadio("Handling message: " + line)

	def sendCurrentPosition(self):
		try:
			self.radioSerialOutput("data," + self.getFormattedGpsData(), True)
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
				self.activeNodes[key] = True

		self.heartbeatReceivedSignal.emit()

	# Sends a "heartbeat" signal to other radios to verify radio is currently
	# active on the network
	def sendHeartbeat(self):
		self.radioSerialOutput("alive")

	def sendReleaseCommand(self):
		print("Releasing balloon")
		counter = 10

		while (counter > 0):
			print("Attempt " + str(counter))
			counter -= 1
			self.radioSerialOutput("SSAGballoonRelease")
			sleep(0.1)
			self.radioSerialOutput("BRMconfirmed")
			sleep(0.1)


	def radioSerialInput(self):
		serialInput = ""

		try:
			if not (self.radioSerial.inWaiting()):
				sleep(1)
			while(self.radioSerial.inWaiting()):
				serialInput += self.radioSerial.readline()
			logRadio("Serial Input: " + serialInput)
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
			if (processSentMessage):
				self.handleMessage(self.RADIO_CALLSIGN + "," + line + ",END_TX\n")
			self.radioSerial.write(self.RADIO_CALLSIGN + "," + line + ",END_TX\n")
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

			if (formattedGpsString == "0,0,0"):
				print ("INVALID DATA STRINGS GIVEN")
			else:
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
		guiLogFile.write(line + "\n")
		guiLogFile.close
	except:
		print("WARNING: Unable to log GUI data")

def logRadio(line):
	try:
		radioLogFile = open(RADIO_LOG_FILE_LOCATION, "a")
		radioLogFile.write(line + "\n")
		radioLogFile.close
	except:
		print("WARNING: Unable to log radio operations data")

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
		var VEHICLES_TO_PLOT = 5
		var myCenter = new google.maps.LatLng(36.8623, -121.0413);
		
		var vehicleWaypointArray = [];
		var vehicleMarkerArray = [];
		var spotMarkerArray = [];
		
		var vehiclePathColors = ["#FF0000",
								"#007FFF",
								"#006600",
								"#FF9933",
								"#7F00FF"];
		
		var vehicleIconNames = ["balloon.png",
								"chase1.png",
								"chase2.png",
								"chase3.png",
								"chase4.png"];
		
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
