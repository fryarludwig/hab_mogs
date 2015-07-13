""""
Changelog:
07/13/15 - KFL: Initial commit - committed all of previous work
"""


from __future__ import print_function

import sys
import serial
import datetime
from time import sleep
from PyQt4 import QtGui, QtCore
from PyQt4.QtWebKit import QWebView
from PyQt4.Qt import QWidget
from collections import OrderedDict

TELEMETRY_LOG_FILE_LOCATION = r"MoGS_telemetry_log.txt"
RADIO_LOG_FILE_LOCATION = r"MoGS_radio_log.txt"
GUI_LOG_FILE_LOCATION = r"MoGS_gui_log.txt"

TEST_MODE = False

"""
Handles GUI operations, as well as all user input. 
TODO: Add altitude graph
TODO: Add temperature graph
TODO: Add speed graph
TODO: Add offline mode
TODO: Add radio verification
TODO: Add heartbeats
TODO: Add command response updating
TODO: Add unit tests
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
		self.messagingListView = QtGui.QListView()
		self.messagingListViewModel = QtGui.QStandardItemModel(self.messagingListView)
		self.sendMessageEntryBox = QtGui.QLineEdit()
		
		super(mogsMainWindow, self).__init__()
		self.commandStatusLabel = QtGui.QLabel()
		self.statusLabelList = {"balloon" : QtGui.QLabel("Balloon", self),
								"chase1" : QtGui.QLabel("Chase 1", self),
								"chase2" : QtGui.QLabel("Chase 2", self),
								"chase3" : QtGui.QLabel("Chase 3", self),
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
		
		self.palette = QtGui.QPalette()
		
		self.radioHandler = radioThread()
		self.radioHandler.balloonDataSignalReceived.connect(self.updateBalloonDataTelemetry)
		self.radioHandler.invalidSerialPort.connect(self.changeSettings)
		self.radioHandler.chatMessageReceived.connect(self.updateChat)
		# add the other handlers here
		self.radioHandler.start()
		self.initUI()
		
	"""
	Populates the widgets and the main GUI window.
	"""
	def initUI(self):
		window_x = 1400
		window_y = 800

		self.col = QtGui.QColor(0, 0, 0)
		self.vLayout = QtGui.QGridLayout()
		self.hLayout = QtGui.QHBoxLayout()
		
		self.vLayout.setSpacing(0)
		self.vLayout.setMargin(0)
		self.hLayout.setSpacing(0)
		self.hLayout.setMargin(0)
		
		mapWidget = QWidget()
		self.mapView = QWebView(mapWidget)
		self.mapView.setMinimumSize(window_x - 250, window_y)
		self.mapView.setMaximumSize(window_x - 250, window_y)
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
		self.mapView.setMinimumSize(minX + 20, minY + 10)
		self.mapView.setMaximumSize(minX + 20, minY + 10)
	
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
		messagingLabel.setAlignment(QtCore.Qt.AlignHCenter)
		
		sendMessageButton = QtGui.QPushButton("Send", self)
		sendMessageButton.clicked[bool].connect(self.sendMessage)
		
		self.messagingListView.setWrapping(True)
		self.messagingListView.setWordWrap(True)
		self.messagingListView.setSpacing(1)
		self.messagingListView.setMinimumSize(300, 300)
		self.messagingListView.setFlow(QtGui.QListView.LeftToRight)
		
		self.sendMessageEntryBox.setMaxLength(256)
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
		commandLabel.setAlignment(QtCore.Qt.AlignHCenter)
		
		self.commandStatusLabel = QtGui.QLabel("No Commands have been sent", self)
		self.commandStatusLabel.setAlignment(QtCore.Qt.AlignHCenter)
		
		# Set up buttons for GUI window
		comPortButton = QtGui.QPushButton('Settings', self)
		comPortButton.clicked.connect(self.changeSettings)
		
		streetMapButton = QtGui.QPushButton('Street Map', self)
		streetMapButton.clicked[bool].connect(self.setMapToStreet)

		resizeMapButton = QtGui.QPushButton('Resize Map', self)
		resizeMapButton.clicked[bool].connect(self.onResize)
		
		balloonReleaseButton = QtGui.QPushButton('Release Balloon', self)
		balloonReleaseButton.setStyleSheet("background-color: Salmon")
		balloonReleaseButton.clicked[bool].connect(self.confirmAndReleaseBalloon)
		
		satelliteViewButton = QtGui.QPushButton('Satellite View', self)
		satelliteViewButton.clicked[bool].connect(self.setMapToSatellite)

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
		layoutLabel.setAlignment(QtCore.Qt.AlignHCenter)
		
		rawGpsLabel = QtGui.QLabel("Latest Raw GPS")
		rawGpsLabel.setAlignment(QtCore.Qt.AlignHCenter)
		
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
			label.setAlignment(QtCore.Qt.AlignHCenter)
			counter += 1
		
		# Populate the labels that will be updated with telemetry
		counter = 1
		for key, value in self.telemetryLabelDictionary.iteritems():
			value.setAlignment(QtCore.Qt.AlignHCenter)
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
		layoutLabel.setAlignment(QtCore.Qt.AlignHCenter)
		
		# Set all to show that there is no connection yet
		for key, statusLabel in self.statusLabelList.items():
			statusLabel.setAlignment(QtCore.Qt.AlignHCenter)
			statusLabel.setFont(networkFont)
			if (key == self.radioHandler.RADIO_CALLSIGN):
				statusLabel.setStyleSheet("QFrame { background-color: Green }")
			else:
				statusLabel.setStyleSheet("QFrame { background-color: Salmon }")
		
		layout.addWidget(layoutLabel, 0, 0, 1, 3)
		layout.addWidget(self.statusLabelList["balloon"], 1, 0, 1, 2)
		layout.addWidget(self.statusLabelList["nps"], 1, 2)
		layout.addWidget(self.statusLabelList["chase1"], 2, 0)
		layout.addWidget(self.statusLabelList["chase2"], 2, 1)
		layout.addWidget(self.statusLabelList["chase3"], 2, 2)
		
		return widget
	
	"""
	Logs and parses the telemetry string passed from the Radio class, then
	updates the GUI to display the values. On invalid packet the data is logged
	but the GUI is not updated.
	No return value
	
	TODO: Calculate ground speed
	TODO: Calculate ascent rate
	"""
	def updateBalloonDataTelemetry(self, data):
		logTelemetry(data)
		data.replace("\n", "")
		
		self.statusLabelList["balloon"].setStyleSheet("QFrame { background-color: Green }")
		
		if (len(self.dataTelemetryList) > 25):
			self.dataTelemetryList.pop()
			
		try:
			splitMessage = data.split(",")
			timestamp = splitMessage[1]
			if (len(timestamp) > 0):
				timestamp = timestamp[:2] + ":" + timestamp[2:4] + ":" + timestamp[4:6]
			latitude = splitMessage[2].replace(".", "")
			if (len(latitude) > 0):
				latitude = latitude[:2] + "." + latitude[2:]
			longitude = splitMessage[3].replace(".", "")
			if (len(longitude) > 0):
				longitude = longitude[:4] + "." + longitude[4:]
			altitude = splitMessage[4]
			voltage = splitMessage[5]
			innerTemp = splitMessage[6]
			outerTemp = splitMessage[7]
			batteryTemp = splitMessage[8]
			
			self.telemetryLabelDictionary["timestamp"].setText(timestamp)
			self.telemetryLabelDictionary["altitude"].setText(altitude)
			self.telemetryLabelDictionary["speed"].setText("CalculateSpeed")
			self.telemetryLabelDictionary["ascent"].setText("CalulateAscent")
			self.telemetryLabelDictionary["gps"].setText(latitude + ", " + longitude)
			self.telemetryLabelDictionary["voltage"].setText(voltage)
			self.telemetryLabelDictionary["tempInside"].setText(innerTemp)
			self.telemetryLabelDictionary["tempOutside"].setText(outerTemp)
			self.telemetryLabelDictionary["tempBattery"].setText(batteryTemp)
			
			# Update the map to show new waypoint
			javascriptCommand = "addBalloonWaypoint({}, {});".format(
								latitude,
								longitude)
			self.theMap.documentElement().evaluateJavaScript(javascriptCommand)
			
			self.dataTelemetryList.append(data)
		
		except:
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
		userMessage = str(self.sendMessageEntryBox.text()).replace("\n", "")
		itemToAdd = QtGui.QStandardItem(self.radioHandler.RADIO_CALLSIGN + ": " + userMessage)
		self.messagingListViewModel.insertRow(0, itemToAdd)
		self.messagingListView.setModel(self.messagingListViewModel)
		self.messagingListView.show()
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
		self.sendMessageEntryBox.clear()
	
	"""
	Opens a dialog to edit the current COM port in use. Sets the self.SERIAL_PORT to 
	user-entered text.
	"""
	def changeSettings(self):
		windowLayout = QtGui.QGridLayout()
		popupWidget = QtGui.QDialog()
		
		portTextBox = QtGui.QLineEdit()
		portTextBox.setText(self.radioHandler.SERIAL_PORT)
		comPortPromptLabel = QtGui.QLabel("COM Port")
		
		selectCallsignLabel = QtGui.QLabel("Callsign")
		selectCallsignComboBox = QtGui.QComboBox()
		selectCallsignComboBox.addItem(self.radioHandler.RADIO_CALLSIGN)
		if not (self.radioHandler.RADIO_CALLSIGN == "nps"):
			selectCallsignComboBox.addItem("nps")
		if not (self.radioHandler.RADIO_CALLSIGN == "chase1"):
			selectCallsignComboBox.addItem("chase1")
		if not (self.radioHandler.RADIO_CALLSIGN == "chase2"):
			selectCallsignComboBox.addItem("chase2")
		if not (self.radioHandler.RADIO_CALLSIGN == "chase3"):
			selectCallsignComboBox.addItem("chase3")
		
		selectButton = QtGui.QPushButton("Save Settings", self)
		selectButton.clicked.connect(popupWidget.accept)
		cancelButton = QtGui.QPushButton("Cancel", self)
		cancelButton.clicked.connect(popupWidget.reject)
		
		windowLayout.addWidget(comPortPromptLabel, 1, 0)
		windowLayout.addWidget(portTextBox, 1, 1, 1, 2)
		windowLayout.addWidget(selectCallsignLabel, 3, 0)
		windowLayout.addWidget(selectCallsignComboBox, 3, 1, 1, 2)
		
		windowLayout.addWidget(selectButton, 4, 1)
		windowLayout.addWidget(cancelButton, 4, 2)
		
		popupWidget.setLayout(windowLayout)
		popupWidget.setWindowTitle("Settings")
		
		if (popupWidget.exec_()):
			if (len(portTextBox.text()) > 0):
				self.radioHandler.SERIAL_PORT = str(portTextBox.text().replace("\n", ""))
			if not (str(selectCallsignComboBox.currentText()) == self.radioHandler.RADIO_CALLSIGN):
				self.radioHandler.RADIO_CALLSIGN = str(selectCallsignComboBox.currentText())
				
		self.radioHandler.settingsWindowOpen = False
		
	
	def setMapToSatellite(self):
		javascriptCommand = "switchToSatelliteView()"
		self.theMap.evaluateJavaScript(javascriptCommand)
		
	def setMapToStreet(self):
		javascriptCommand = "switchToStreetView()"
		self.theMap.evaluateJavaScript(javascriptCommand)


"""
Below is the radio handler
TX/RX operations, as well as RaspPi interfacing occurs below
"""
class radioThread(QtCore.QThread):
	balloonDataSignalReceived = QtCore.pyqtSignal(object)
	invalidSerialPort = QtCore.pyqtSignal(object)
	chatMessageReceived = QtCore.pyqtSignal(object)
	
	def __init__(self):
		if (TEST_MODE):
			self.inputTestFile = open("test_telemetry.txt")
		QtCore.QThread.__init__(self)
		
		self.HEARTBEAT_INTERVAL = 100
		self.SERIAL_PORT = "COM4"
		self.RADIO_CALLSIGN = "chase2"
		self.BAUDRATE = 9600
		
		# Set up semaphore-like variables
		self.sendingSerialMessage = False
		self.validHeartbeatReceived = False
		self.chase1Alive = False
		self.chase2Alive = False
		self.chase3Alive = False
		self.npsAlive = False
		self.balloonAlive = False
		
		self.releaseBalloonFlag = False
		self.settingsWindowOpen = False
		
		self.userMessagesToSend = []
		
	
	def run(self):
		counter = self.HEARTBEAT_INTERVAL
		
		if (TEST_MODE):
			sleep(1)
			while (True):
				for line in self.inputTestFile:
					sleep(1)
					self.handleMessage(line)
		
		while(True):
			if (self.releaseBalloonFlag):
				self.sendReleaseCommand()
				self.releaseBalloonFlag = False
			
			while (len(self.userMessagesToSend) > 0):
				self.radioSerialOutput("chat," + self.userMessagesToSend[0])
				self.userMessagesToSend.pop()
			
			#self.verifyRadioConnection()
			
			messageReceived = self.radioSerialInput()
			
			if (len(messageReceived) > 0):
				self.handleMessage(messageReceived)
			
			if (counter == 0):
				self.sendingSerialMessage = True
				self.sendHeartbeat()
				self.sendingSerialMessage = False
				counter = self.HEARTBEAT_INTERVAL
			else:
				counter -= 1
			
			logRadio(messageReceived + "\n")

	# Performs an action based on the message sent to it
	# Returns True or False based on the success of that action
	def handleMessage(self, message):
		for line in message.split('\n'):
			if (len(line) > 0):
				if (line[:3] == "HAB"):
					self.receivedHeartbeat("balloon")
					if (line[4:8] == "data"):
						self.balloonDataSignalReceived.emit(line[4:-1])
				elif ("chat" in line):
					self.chatMessageReceived.emit(line)
			logRadio("Handling message: " + line)

	# Determines if the current radio is connected to the network. If no nodes
	# are active, attempts to reconnect radio to network
	def verifyRadioConnection(self):
		radioConnectionVerified = self.networkConnected()
		
		if not (radioConnectionVerified):
			logRadio("Unable to verify network connectivity")
			
			if (self.validHeartbeatReceived):
				radioConnectionVerified = True
			
			if (not radioConnectionVerified):
				retries = 10
				self.sendHeartbeat()
				while not (self.networkConnected() and retries >= 0):
					sleep(self.SHORT_SLEEP_DURATION)
			
		return radioConnectionVerified

	# Takes a heartbeat signal and determines which node sent it out. That node
	# is set as currently active on the network
	def receivedHeartbeat(self, heartbeatSignalReceived):
		validHeartbeatCallsign = True
		
		if (heartbeatSignalReceived == "balloon"):
			self.balloonAlive = True
		elif (heartbeatSignalReceived == "nps"):
			self.npsAlive = True
		elif (heartbeatSignalReceived == "chase1"):
			self.chase1Alive = True
		elif (heartbeatSignalReceived == "chase2"):
			self.chase2Alive = True
		elif (heartbeatSignalReceived == "chase3"):
			self.chase3Alive = True
		else:
			validHeartbeatCallsign = False
		
		if not (validHeartbeatCallsign):
			logTelemetry("Invalid heartbeat received. LOGGING ERROR")
		else:
			self.validHeartbeatReceived = True
		
	# Sends a "heartbeat" signal to other radios to verify radio is currently
	# active on the network
	def sendHeartbeat(self):
		self.radioSerialOutput("alive")

	# Returns True if any other nodes are active on the network
	# Returns False if no other nodes have been discovered yet
	def networkConnected(self):
		return (self.balloonAlive or
				self.npsAlive or
				self.chase1Alive or
				self.chase2Alive or
				self.chase3Alive)
		
	def sendReleaseCommand(self):
		print("Releasing balloon")
		response = "No Response"
		counter = 10
		
		while (counter > 0):
			print("Attempt " + str(counter))
			counter -= 1
			self.radioSerialOutput("releaseBalloonNow")
			sleep(0.1)
			response = self.radioSerialInput()
			if ("HAB,released" in response):
				print("Confirmed - HAB Released!")
				break
		return None
	
	def passTelemetryToGui(self, telemetryLine):
		self.balloonDataSignalReceived.emit(telemetryLine)

	def radioSerialInput(self):
		serialInput = ""
		
		ser = None
		try:
			ser=serial.Serial(port = self.SERIAL_PORT, baudrate = self.BAUDRATE, timeout = 2)
			if not (ser.inWaiting()):
				sleep(1)
			while(ser.inWaiting()):
				serialInput += ser.readline()
				print (serialInput)
			logRadio("Serial Input: " + serialInput)
			ser.close()
		except:
			if (self.settingsWindowOpen):
				sleep(1)
			else:
				self.invalidSerialPort.emit("Please enter a valid serial port")
				self.settingsWindowOpen = True
			logRadio("Unable to write to serial port on " + self.SERIAL_PORT)
			print("Unable to open serial port for input on " + self.SERIAL_PORT)
			
		return serialInput
	
	def radioSerialOutput(self, line):
		ser = None
		
		try:
			ser=serial.Serial(port = self.SERIAL_PORT, baudrate = self.BAUDRATE, timeout = 2)
			line = ser.write(self.RADIO_CALLSIGN + "," + line + "\n")
			ser.close()
		except:
			if (self.settingsWindowOpen):
				sleep(1)
			else:
				self.invalidSerialPort.emit("Please enter a valid serial port")
				self.settingsWindowOpen = True
			logRadio("Unable to write to serial port on " + self.SERIAL_PORT)
			print("Unable to write to serial port on " + self.SERIAL_PORT)

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
      var myCenter = new google.maps.LatLng(36.8623, -121.0413);
      var balloonWaypointArray = [];
    
      function initialize() 
      {
        var mapOptions = 
        {
          center: myCenter,
          zoom: 11,
          mapTypeId: google.maps.MapTypeId.ROADMAP
        };

        map = new google.maps.Map(document.getElementById('map-canvas'), mapOptions);
      }
          
      function addBalloonWaypoint(lat, lng)
      {
      	balloonWaypointArray.push(new google.maps.LatLng(lat, lng))
      	
		var line = new google.maps.Polyline
		({
		  path:balloonWaypointArray,
		  strokeColor:"#0000FF",
		  strokeOpacity:0.8,
		  strokeWeight:2,
		  map:map
		});
      }
      
      function switchToSatelliteView()
      {
	   map.setMapTypeId(google.maps.MapTypeId.HYBRID);
      }
      
      function switchToStreetView()
      {
	   map.setMapTypeId(google.maps.MapTypeId.ROADMAP);
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

