# ble beacon functions
# fetch RSSI data from generic beacons
# fetch specific data from Ruuvi beacons
# https://github.com/ruuvi/ruuvi-sensor-protocols
# puts the results into specific analog joins
#
# Uses the bluepy interface which only works in Linux
# Also, this interface expects to see a BT device in the system
# Doesn't check for availablity

import os

if os.name != "nt":
 from bluepy.btle import Scanner, DefaultDelegate

# -----------------------------------------------------
def twos_complement(value,bitWidth):
	if value >= 2**bitWidth:
		raise ValueError("Value: {} out of range of {}-bit value.",format(value, bitWidth))
	else:
                mask=2**(bitWidth-1)
                return -1*int(value & mask) + int(value & ~mask)

# -----------------------------------------------------

if os.name == "nt":                 # the do nothing class for windows
 class BLE_beacon():
  def __init__(self,sysobjs):
   self.sysobjs=sysobjs
  
  def scan(self,analog_joins):
   return(analog_joins)
else:

# -------------------------------
# Beacon scan
# -------------------------------
 
 class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)


    def HandleDiscovery(self,dev,new_dev,new_dat):
        if new_dev:
            pass
        if new_dat:
            pass



 class BLE_beacon():
  def __init__(self,sysobjs):
    self.scanner = Scanner().withDelegate(ScanDelegate())
    self.sysobjs=sysobjs

  def insert(self, mac, label,value,join_list):
    join=self.sysobjs[mac].get(label,0)
    if join != 0:
     join_list[join]=value 
    return(join_list) 
 
  def process_beacon_generic(self, mac, rssi, analog_joins):
#    print(self.sysobjs)
    analog_joins=self.insert(mac, 'rssi_join', rssi, analog_joins)
    return (analog_joins)
  
  def process_beacon_ruuvie(self, mac, rssi, value, analog_joins):
#    print ("ruuvie",mac)
    format=int(value[4:6],16)
    analog_joins=self.insert(mac, 'rssi_join', rssi, analog_joins)
    if(format == 0x03):
     humidity=int(value[6:8],16)*5        # report as value * 10
     analog_joins=self.insert(mac, 'humidity_join', humidity, analog_joins)
     tempInt=twos_complement(int(value[8:10],16),8)
     tempFrac=int(value[10:12],16)
     temperature=tempInt*100+tempFrac	   # report as value * 100
     analog_joins=self.insert(mac, 'temp_join', temperature, analog_joins)
     pressure=int(value[12:16],16)		# report as (value - 50000)*100
     analog_joins=self.insert(mac, 'pressure_join', pressure, analog_joins)
     accel_X=twos_complement(int(value[16:20],16),16)
     analog_joins=self.insert(mac, 'accel_x_join', accel_X, analog_joins)
     accel_Y=twos_complement(int(value[20:24],16),16)
     analog_joins=self.insert(mac, 'accel_y_join', accel_Y, analog_joins)
     accel_Z=twos_complement(int(value[24:28],16),16)
     analog_joins=self.insert(mac, 'accel_z_join', accel_Z, analog_joins)
     battV=int(value[28:32],16)
     analog_joins=self.insert(mac, 'battery_join', battV, analog_joins)
     
     
    
    return(analog_joins)
    
  def scan(self,analog_joins):
    devices = self.scanner.scan(1.0)           # this call is blocking for t - Time in seconds
    for ii in devices:
     if ii.addr in self.sysobjs:
      for (adtype, desc, value) in ii.getScanData():    # return manufacture's key string if present
       if self.sysobjs[ii.addr]['type'] == 'ruuvie':	# user belives this is a ruuvie tag
        if adtype == 255:
         device=int(value[2:4]+value[0:2],16)
         if(device == 0x0499):				# check that manu code matches
            analog_joins=self.process_beacon_ruuvie(ii.addr, ii.rssi, value, analog_joins)
       else:
        if self.sysobjs[ii.addr]['type'] == 'bletag':	# check if type is generic ble tag
         analog_joins=self.process_beacon_generic(ii.addr, ii.rssi, analog_joins)
   
    return(analog_joins)
 