# Demo network
# implement a simple feedback path

class DemoProtocol():
    addr=[] 
    remotes=[]
    Slot=0

    def SetupRemotes(self,remotelist,port):
        self.remotes=remotelist
        self.Slot in self.remotes
        slot=self.Slot

        if self.remotes[slot]['Act'] != '':
         self.remotes[slot]['Act'].DigitalIn(29, True)  # enable demo page
        
    def AnalogWrite(self, Sig, value, slot):
        if self.remotes[slot]['Act'] != '':
         self.remotes[slot]['Act'].AnalogIn(Sig,value)
        pass

    def DigitalWrite(self, Sig, value, slot):
        if self.remotes[slot]['Act'] != '':
         self.remotes[slot]['Act'].DigitalIn(Sig, value)
        pass
      
    def startProtocol(self):
        pass

#self.remotes[slot]['Act'].SerialIn

