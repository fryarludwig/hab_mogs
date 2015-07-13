import sys
from time import sleep
from PyQt4 import QtGui, QtCore
from run_MoGS import *

RADIO_LOG_FILE_LOCATION = r"C:\Users\Kenneth\Desktop\MoGS_radio_log.txt"

class radioThread(QtCore.QThread):
	balloonDataSignalReceived = QtCore.pyqtSignal(object)
	
	def __init__(self):
		self.logFile = open(RADIO_LOG_FILE_LOCATION, "a")
		QtCore.QThread.__init__(self)
		
		self.RADIO_CALLSIGN = "Chase1"
		self.SERIAL_PORT = "COM3"
		self.BAUDRATE = 9600
		
		self.SHORT_SLEEP_DURATION = 0.05
		self.LONG_SLEEP_DURATION = 1
		self.HEARTBEAT_INTERVAL = 100
		
		# Set up semaphore-like variables
		self.sendingSerialMessage = False
		self.validHeartbeatReceived = False
		self.chase1Alive = False
		self.chase2Alive = False
		self.chase3Alive = False
		self.npsAlive = False
		self.balloonAlive = False
		
	
	def run(self):
		counter = self.HEARTBEAT_INTERVAL
		
		while(True):
			messageToLog = self.RADIO_CALLSIGN + " log: "
			
			#self.verifyRadioConnection()
			
			while (self.sendingSerialMessage):
				print("Sleeping for SHORT_DURATION")
				sleep(self.SHORT_SLEEP_DURATION)
				
			messageReceived = radioSerialInput(self.SERIAL_PORT, self.BAUDRATE)
			self.handleMessage(messageReceived)
			
			if (counter == 0):
				self.sendingSerialMessage = True
				self.sendHeartbeat(self.RADIO_CALLSIGN)
				self.sendingSerialMessage = False
				counter = self.HEARTBEAT_INTERVAL
			else:
				counter -= 1
			
			self.logFile.write(messageToLog)

	# Performs an action based on the message sent to it
	# Returns True or False based on the success of that action
	def handleMessage(self, message):
		self.balloonDataSignalReceived.emit(message)
		return None

	# Determines if the current radio is connected to the network. If no nodes
	# are active, attempts to reconnect radio to network
	def verifyRadioConnection(self):
		radioConnectionVerified = self.networkConnected()
		
		if not (radioConnectionVerified):
			print("Unable to verify network connectivity")
			
			if (self.validHeartbeatReceived):
				radioConnectionVerified = True
			
			if (not radioConnectionVerified):
				retries = 10
				self.sendHeartbeat(self.RADIO_CALLSIGN)
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
			print("Invalid heartbeat received. LOGGING ERROR")
		else:
			self.validHeartbeatReceived = True
		
	# Sends a "heartbeat" signal to other radios to verify radio is currently
	# active on the network
	def sendHeartbeat(self, callsign):
		radioSerialOutput(self.SERIAL_PORT, self.BAUDRATE, callsign + "=alive")

	# Returns True if any other nodes are active on the network
	# Returns False if no other nodes have been discovered yet
	def networkConnected(self):
		return (self.balloonAlive or
				self.npsAlive or
				self.chase1Alive or
				self.chase2Alive or
				self.chase3Alive)
		



def transmitTelemetry():
# 	Transmit Telemetry
# 		Open file with current timestamp
# 		Transmit entire contents in 5s increments
# 		Close file
# 		Return to main loop
	return None

def changeBalloonConfiguration(config = "slave"):
# 		Send "set_config=master" command
# 		Change to chase vehicles to slave
# 		Wait for confirmation
# 			If no confirmation, revert to master
	return None

def sendReleaseCommand():
# 		Send repeated "release" signals for 10s
# 		Wait for confirmation
# 		If no confirmation:
# 			Signal to GS
# 			Spam for 10s again
# 			Continue? Abort attempt?
	return None

def transmitPicture():
# 		Send "transfer_picture"
# 		Wait for picture
# 		If no picture:
# 			Report failure
	return None

def reportStateOfHealth():
# 		Send "report_health"
# 		Wait for response
	return None

def editTelemetryRate(rate = "1"):
# 	Change sensor rates
# 		Send "camera/tx/etc_rate=RATE"
# 		Wait for confirmation
# 		If no confirmation:
# 			Report failure
	return None

def listen(timeToListen = "5"):
# 	Listen for telemetry
# 		Listen for input
# 		Parse packet
# 		Overlay on Lat/Lon grid
# 		Place background map
	return None


def radioSerialInput(port, baudrate):
	message = ["No messages received."]
	counter = 10
	serialInput = []
	
	ser=serial.Serial(port, baudrate, timeout = 3)
	
	sleep(2)
	
	while (ser.inWaiting() > 0 and counter > 0):
		serialInput.append(ser.readline())
		counter -= 1
	
	if (len(serialInput) > 0):
		message = serialInput
	
	ser.close()
	return message

def radioSerialOutput(port, baudrate, line):
	success = False
	
	ser = None
	try:
		ser=serial.Serial(port, baudrate, timeout = 2)
		line = ser.write(line)
		success = True
		
	except:
		success = False
	
	try:
		ser.close()
	except:
		print("Unable to close serial port")
	
	return success