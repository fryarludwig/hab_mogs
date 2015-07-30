
import serial
import time
from logger import *
from PyQt4 import QtGui, QtCore

"""
Below is the radio handler
TX/RX operations, as well as RaspPi interfacing occurs below
"""
class serialHandlerThread(QtCore.QThread):
	balloonDataSignalReceived = QtCore.pyqtSignal(object)
	balloonAckReceived = QtCore.pyqtSignal(object)
	balloonInitReceived = QtCore.pyqtSignal(object)
	vehicleDataReceived = QtCore.pyqtSignal(object)
	invalidSerialPort = QtCore.pyqtSignal(object)
	chatMessageReceived = QtCore.pyqtSignal(object)
	radioConsoleUpdateSignal = QtCore.pyqtSignal(object)
	updateNetworkStatusSignal = QtCore.pyqtSignal()

	def __init__(self):
		QtCore.QThread.__init__(self)
		self.TEST_MODE = False  # Test mode pulls telemetry from file instead of radios

		self.HEARTBEAT_INTERVAL = 5
		self.RADIO_SERIAL_PORT = "COM7"
		self.RADIO_CALLSIGN = "chase1"
		self.RADIO_BAUDRATE = 38400
		self.radioSerial = None

		self.GPS_SERIAL_PORT = "COM4"
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
		self.requestDiskSpaceFlag = False

		self.changeSnapshotIntervalFlag = False
		self.requestedSnapshotInterval = 30
		self.requestedSnapshotBurst = 5
		self.acknowledgedSnapshotInterval = 0
		self.acknowledgedSnapshotBurst = 0

		self.settingsWindowOpen = False
		self.radioSerialPortChanged = False
		self.gpsSerialPortChanged = False
		self.serialBaudrateChanged = False

		self.userMessagesToSend = []

		self.missionStartTime = time.time()
		self.lastHeartbeatTime = time.time()

	def run(self):
		counter = self.HEARTBEAT_INTERVAL

		if (self.TEST_MODE):
			self.inputTestFile = open("test_telemetry.txt", "r")
			for line in self.inputTestFile:
				print("IN TEST MODE")
				time.sleep(0.5)
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

			if (self.changeSnapshotIntervalFlag):
				self.sendSnapshotRequest()
				self.changeSnapshotIntervalFlag = False

			if (self.requestDiskSpaceFlag):
				self.sendDiskSpaceRequest()
				self.requestDiskSpaceFlag = False

			while (len(self.userMessagesToSend) > 0):
				formattedMessage = "chat," + self.userMessagesToSend[0]
				self.radioSerialOutput(formattedMessage, True)
				self.userMessagesToSend.pop(0)

			messageReceived = self.radioSerialInput()

			if (len(messageReceived) > 0):
				self.handleMessage(messageReceived)


			if ((time.time() - self.lastHeartbeatTime) > self.HEARTBEAT_INTERVAL):
				self.lastHeartbeatTime = time.time()

				for key, value in self.activeNodes.items():
					self.activeNodes[key] -= 1
					if (self.activeNodes[key] <= 0):
						self.updateNetworkStatusSignal.emit()

				if not (self.sendCurrentPosition()):
					self.sendHeartbeat()

			logRadio(messageReceived + "\n")

	# Performs an action based on the message sent to it
	# Returns True or False based on the success of that action
	def handleMessage(self, message):
		for line in message.split(',END_TX\n'):
			if (len(line) > 0):
				if (line[:3] == "hab"):
					self.receivedHeartbeat("hab")
					if(line[4:7] == "ack"):
						self.balloonAckReceived.emit(line[8:])
					elif (line[4:8] == "chat"):
						self.chatMessageReceived.emit("HAB: " + line[9:])
					elif (line[4:8] == "data"):
						self.balloonDataSignalReceived.emit(line[9:])
					elif (line[4:8] == "init"):
						self.balloonInitReceived.emit(line[9:])

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

				logTelemetry(line + ",END_TX")

	def sendCurrentPosition(self):
		success = False

		try:
			gpsData = self.getFormattedGpsData()
			if (gpsData != "INVALID DATA"):
				self.radioSerialOutput("data," + gpsData, True)
				success = True
		except:
			print("Unable to send current position")

		return success

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

	def sendSnapshotRequest(self):
		self.radioSerialOutput("cmd,SNAPSHOT," + str(self.requestedSnapshotBurst) +
							"," + str(self.requestedSnapshotInterval))

	def sendDiskSpaceRequest(self):
		self.radioSerialOutput("cmd,DISK_SPACE")

	def sendReleaseCommand(self):
		print("Releasing balloon")
		counter = 3

		while (counter > 0):
			print("Attempt " + str(counter))
			counter -= 1
			self.radioSerialOutput("cmd,SSAG_RELEASE_BALLOON")
			time.sleep(2)

	def sendResetBrmCommand(self):
		print("Resetting balloon")
		self.radioSerialOutput("cmd,RESET_BRM")

	def radioSerialInput(self):
		serialInput = ""

		try:
			if not (self.radioSerial.inWaiting()):
				time.sleep(0.75)

			while(self.radioSerial.inWaiting()):
				serialInput += self.radioSerial.readline()

			if (len(serialInput) > 0):
				self.radioConsoleUpdateSignal.emit(serialInput)

		except:
			if (not self.settingsWindowOpen):
				self.invalidSerialPort.emit("Please enter a valid serial port")
				self.settingsWindowOpen = True
			logRadio("Unable to write to serial port on " + str(self.RADIO_SERIAL_PORT))

		return serialInput

	def radioSerialOutput(self, line, processSentMessage = False):
		try:
			preparedMessage = self.RADIO_CALLSIGN + "," + line + ",END_TX\n"
			if (processSentMessage):
				self.handleMessage(preparedMessage)

			self.radioConsoleUpdateSignal.emit(preparedMessage)
			self.radioSerial.write(preparedMessage)
		except:
			if not (self.settingsWindowOpen):
				self.invalidSerialPort.emit("Please enter a valid serial port")
				self.settingsWindowOpen = True
			logRadio("Unable to write to serial port on " + self.RADIO_SERIAL_PORT)

	def openRadioSerialPort(self):
		try:
			self.radioSerial.close()
		except:
			logRadio("Unable to close serial port " + self.RADIO_SERIAL_PORT)

		try:
			self.radioSerial = serial.Serial(port = self.RADIO_SERIAL_PORT, baudrate = self.RADIO_BAUDRATE, timeout = 1)
		except:
			if not (self.settingsWindowOpen):
				self.invalidSerialPort.emit("Radio serial port is invalid")
				self.settingsWindowOpen = True

	def gpsSerialInput(self):
		messageReceived = "NO_GPS_DATA\n"
		serialInput = ""
		retries = 10
		iterationsToWait = 100

		try:
			self.gpsSerial.flushOutput()
			self.gpsSerial.flushInput()
			time.sleep(0.75)

			while (retries > 0 and iterationsToWait > 0):
				if (self.gpsSerial.inWaiting() > 0):  # If there's a buffer for us to read
					serialInput += self.gpsSerial.readline()
					if (serialInput[:6] == r"$GPGGA"):  # Makes sure this is the line we want
						break  # This is our stop
					else:
						# print("Discarding unused data: " + serialInput)
						serialInput = ""  # This is not the data we're looking for
						retries -= 1
				else:
					iterationsToWait -= 1

		except:
			if not (self.settingsWindowOpen):
				self.invalidSerialPort.emit("GPS serial port is invalid")
				self.settingsWindowOpen = True

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
				timestamp = gpsSplit[1][:6]

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

				formattedGpsString = "{},{},{}".format(timestamp, latitude, longitude)
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
			self.gpsSerial = serial.Serial(port = self.GPS_SERIAL_PORT, baudrate = self.GPS_BAUDRATE, timeout = 1)
		except:
			if not (self.settingsWindowOpen):
				self.invalidSerialPort.emit("GPS serial port cannot be opened")
				self.settingsWindowOpen = True
