
import socket
from time import sleep
from math import *
from PyQt4 import QtGui, QtCore

DISH = False
DISH_ADDRESS = "192.168.101.98"
DISH_PORT = 5003

class dishHandlerThread(QtCore.QThread):
	def __init__(self):
		QtCore.QThread.__init__(self)
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.connect(DISH_ADDRESS, DISH_PORT)

		self.old_az = -1
		self.new_az = self.old_az

		self.old_el = -1
		self.new_el = self.old_el

		self.firstRun = True

	def degrees(self, rad):
		return rad * 180.0 / pi

	def compute_bearing(self, blat, blon, balt):
		# Spanagel's coordinates
		llat = 36.594947
		llon = -121.874647
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
		el = atan((balt_mi - lalt_mi) / dist) * 180.0 / pi

		dx = cos(llat_rad) * sin(blat_rad) - sin(llat_rad) * cos(blat_rad) * cos(dlon_rad)
		dy = sin(dlon_rad) * cos(blat_rad)
		az = (self.degrees(atan2(dy, dx)) + 360) % 360

		return (az, el)

	def close(self):
		self.sock.send("AS;ES;\n")  # standby
		self.sock.close()


	def point(self, az, el):

		# Update positions
		self.new_az = az
		self.new_el = el

		if self.firstRun:
			self.sock.send("SQ\n")
			data = self.sock.recv(1024)
			temp = data.split(",")
			dish_az = temp[0].split("=")[1]
			dish_el = temp[1].split("=")[1]
			dish_az = float(dish_az)
			dish_el = float(dish_el)
			print("Current dish position %03d %03d" % (dish_az, dish_el))
			self.old_az = dish_az
			self.old_el = dish_el
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
				self.sock.send("AM%0.2f;EM%0.2f;\n" % (az, el))
				print("Pointing to %03d %03d" % (az, el))

				# print("Sleeping %f" % max(az_err,el_err)*4 + 1)
				sleep(max(az_err, el_err) / 4 + 5)
				self.sock.send("AS;ES;\n")  # standby
				self.old_az = self.new_az
				self.old_el = self.new_el

			except:
				print("Can't update position to dish ACU")
				self.close()

