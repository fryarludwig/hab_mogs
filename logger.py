
import datetime

TELEMETRY_LOG_FILE_LOCATION = r"MoGS_telemetry_log.txt"
RADIO_LOG_FILE_LOCATION = r"MoGS_radio_log.txt"
GUI_LOG_FILE_LOCATION = r"MoGS_gui_log.txt"

def logTelemetry(line):
	try:
		telemetryLogFile = open(TELEMETRY_LOG_FILE_LOCATION, "a")
		for newLine in line.split("\n"):
			telemetryLogFile.write(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) + ": " + newLine + "\n")
		telemetryLogFile.close
	except:
		print("WARNING: Unable to log telemetry data")

def logGui(line):
	try:
		guiLogFile = open(GUI_LOG_FILE_LOCATION, "a")
		for newLine in line.split("\n"):
			guiLogFile.write(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) + ": " + newLine + "\n")
		guiLogFile.close
	except:
		print("WARNING: Unable to log GUI data")

def logRadio(line):
	try:
		radioLogFile = open(RADIO_LOG_FILE_LOCATION, "a")
		for newLine in line.split("\n"):
			if (len(newLine) > 0):
				radioLogFile.write(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) + ": " + newLine + "\n")
		radioLogFile.close
	except:
		print("WARNING: Unable to log radio operations data")
