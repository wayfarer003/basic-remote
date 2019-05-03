import pygame
import sys
import os
import math
import time
import pygame.freetype
import yaml
import twisted
from twisted.internet import protocol, reactor, task
from twisted.internet.protocol import DatagramProtocol
from twisted.internet.task import LoopingCall

import backends.Demo.demo as CS
import blebeacon as ble


# ---------- Globals ----------

Port=41794
master='127.0.0.1'
screen_size=(240,320)
idx=1

# System joins
## Analog
RSSI_JOIN=1000
TIME_JOIN=1001
BATTERY_JOIN=1002
## Digital
SCREEN_OFF_JOIN=1000

DESIRED_FPS = 30.0 # 30 frames per second

RSSIMAX=-45
RSSIMIN=-100
RSSIBARS=5

# ----------------------------

# Tell the RPi to use the TFT screen and that it's a touchscreen device

if os.name != "nt":
 os.putenv('SDL_VIDEODRIVER', 'fbcon')
 os.putenv('SDL_FBDEV'      , '/dev/fb1')
 os.putenv('SDL_MOUSEDRV'   , 'TSLIB')
 os.putenv('SDL_MOUSEDEV'   , '/dev/input/touchscreen')

# ----------------------------

obj_list={}         # list of objects
resource_list={}    # list of resources
page={}             # objs in a page
sys_objs_list={}    # system objs in project

join={}             # joins
analog_join={}      # input analog joins
serial_join={}      # input serial joins
join_press={}       # output digital joins
active_list={}      # list of button press zones
images={}           # list of images in active page

copy_analog_join={} # copy of analog joins


def error(string):
 print(string)
 sys.exit()

def val4(argb):
 a=int(argb[0])
 r=int(argb[1])
 g=int(argb[2])
 b=int(argb[3])
 return((r,g,b))

def val2(gb):
 g=int(gb[0])
 b=int(gb[1])
 return((g,b))

# Resources
# Text -- type
#  id: 21                # uniq id
#   type: 'text'         # type text
#   value: 'ROKU'        # text string
#   font: 'FreeSans.ttf' # font
#   fontsize: 14         # font size
#   style: 'strong'      # font style
#   ftcolor: (0xff,0xff,00,00)  # font color

# Fetch the resource list into a local dict index by the id
def process_resources(res):
 if res == '':
   return
 keys=dict.keys(res)
 for i in keys:
  resource_list[res[i]['id']]=res[i]

# Objects
# Button
# Legend
# Clock
# WiFi gauge
# Bar

def process_objects(objs):
 if objs == '':
   return
 keys=dict.keys(objs)
 for i in keys:
  obj_list[objs[i]['id']]=objs[i]

# ----------------------------
# System objs
# - At the moment these are just BLE beacons
# - Expectation is that this catagory will include other HW peripherals
# ----------------------------

def process_system_objects(objs):
 if objs == '':
   return
 keys=dict.keys(objs)
 for i in keys:
  sys_objs_list[objs[i]['mac']]=objs[i]
 return(sys_objs_list)

# ---------------
# read_project
# ---------------

def read_project(file):
 global ble_scan
 global master
 global Port
 global idx
 global screen_size

 with open(file, 'r') as fp:
    read_data = yaml.load(fp)

 if 'project' not in read_data:
  error('invalid project header')
 else:
  proj=read_data.get('project')

#*** Get project setup values ***
  master=proj.get('master', master)
  Port=int(proj.get('port', Port))
  idx=proj.get('idx',idx)

  (a,b)=screen_size
  (w,h)=proj.get('screen_size',[a,b])
  screen_size=(w,h)

# ----------------------------
  res=proj.get('resources','')
  process_resources(res)
  objs=proj.get('objects','')
  process_objects(objs)
  sys_objs_list=proj.get('systemObjs','')
  sys_objs_list=process_system_objects(sys_objs_list)
  ble_scan=ble.BLE_beacon(sys_objs_list)
  keys=dict.keys(proj)
  count=1

# ----------------------------
# Generate list of pages in project and insert their display list of objects
# ----------------------------

  for i in keys:
   if 'page' in i:
    view={}
    kview=dict.keys(proj[i]['view'])
    for j in kview:
      view[count]={'id':proj[i]['view'][j]['id'],'pos':proj[i]['view'][j]['pos']}
      if view[count]['id'] not in obj_list:
       error('Disp list with invalid object')
      count=count+1
    id=proj[i].get('join',0)
    page[id]=proj[i]
    page[id]['view']=view

# ----------------------------
# Generate active press regions
# dict referenced by page join
# ----------------------------

    obj_zones={}
    for v in view:
     objid=view[v]['id']
     if obj_list[objid]['type'] == 'button':               # only add press region for button types
      if 'join' in obj_list[objid]:
       (x,y)=view[v]['pos']
       (w,h)=obj_list[objid]['size']
       obj_zones[v]={'rect':pygame.Rect(x, y, w, h),'join':obj_list[objid]['join']}
       active_list[id]=obj_zones

# ----------------------------
# add text to rectangle
# Rectable Pos, Size
# ----------------------------

def add_text(text,pos,size):
 if(text):
  (x,y)=pos
  (w,h)=size
  FONT = pygame.freetype.Font(text['font'], text['fontsize'])
  if('style' in text):
   if(text['style'] == 'strong'):
    FONT.strong=True
  color=val4(text['ftcolor'])
#  color=(r,g,b)
  indirect_join = text.get('indirect_text',0)
  value=text.get('value',"")
  if indirect_join != 0:                       # Indirect text join
    value=serial_join.get(indirect_join,value)   # fetch indirect text or default value
  (sx,sy,sw,sh)=FONT.get_rect(value)
  if(text['align'] == 'center'):
   loc=(x+int((w-sw)/2),y+int((h-sh)/2))
   pass
  elif (text['align'] == 'left'):
   loc=(x+sx+2,y+int((h-sh)/2))
  elif (text['align'] == 'right'):
   loc=(x+(w-sw-2),y+int((h-sh)/2))
  else:                         # invalid ; exit function
   return
   pass
  FONT.render_to(screen, loc, value, color)

# ----------------------------
# ***** Draw Routines ****
# ----------------------------

def put_image(screen, id, pos):
 if id != 0:
  rect = images[id].get_rect()
  rect = rect.move(pos)
  screen.blit(images[id], rect)

# rect button draw
# x,y ; w,h ; background color ; frame color ; frame thickness
def rect(screen,pos,size,bcolor,fcolor,fthick,text,image):
 if(fthick > 0):
  pygame.draw.rect(screen, bcolor, (pos,size), 0)
  put_image(screen, image, pos)
  ret=pygame.draw.rect(screen, fcolor, (pos,size), fthick)
 else:
  ret=pygame.draw.rect(screen, bcolor, (pos,size), 0)
  put_image(screen, image, pos)
 add_text(text,pos,size) 

# ----------------------------
# Oblong button
# ----------------------------
  
def oblong(screen,pos,size,bcolor,fcolor,fthick,text,image):
 if(fthick>0):
  pass
 else:
  (x,y)=pos
  (w,h)=size
  rad=int(h/2)
  lpos=(int(x+h/2),int(y+h/2))
  rpos=(int(x+w-h/2),int(y+h/2))
  rsize=(w-h,h)
  rectpos=(int(x+h/2),y)
 
  pygame.draw.circle(screen,bcolor,rpos,rad,0)
  pygame.draw.circle(screen,bcolor,lpos,rad,0)
  pygame.draw.rect(screen, bcolor, (rectpos, rsize),0)
  put_image(screen, image, pos)
  add_text(text,pos,size)

# ----------------------------
# Center Cross Hair
# ----------------------------
def xhair():
 pygame.draw.lines(screen, (255,0,0), False, [(0,320/2),(240,320/2)], 1)
 pygame.draw.lines(screen, (255,0,0), False, [(240/2,0),(240/2,320)], 1)

# ----------------------------
#  RSSI Gauge
# ----------------------------
def RSSI(screen,pos,size,scolor,ncolor,bcolor,sig):
 (x,y)=pos
 (w,h)=size
 bars=RSSIBARS
 xskip=2
 xpels=w/5
 barwidth=w/xpels
 ypels=(w/bars-xskip)

 sigstep=abs((RSSIMAX-RSSIMIN)/(bars-1))

 sigcount=RSSIMIN
 pygame.draw.rect(screen,bcolor, (pos,size),0)   #bounding box
 for i in range(0,bars):
  if sig >= RSSIMAX:
   pelcolor=scolor
  elif sig <= RSSIMIN:
   pelcolor=ncolor
  elif sigcount <= sig:
   pelcolor=scolor
  else:
   pelcolor=ncolor
  sigcount += sigstep
  pygame.draw.rect(screen, pelcolor,((x+i*xpels,y+ypels*(4-i)),(ypels,ypels+ypels*i)),0)

# ----------------------------
# Gauge
# Displays an analog gauge
#   XXXX, XXX.X, etc
# Takes an analog join and displays a value
# Styles 0 -- XXXX, 1 -- XXX.X, etc
# ----------------------------
def Gauge(screen,text,pos,size,bcolor,style,sig):
 txt=""
 if sig in analog_join:               # if no analog value, use default
  value=analog_join[sig]
  tail=text.get('tail','')
  f="%%.%df%%s"%(style)
  txt=f%(value/pow(10.0,style),tail)
  text['value']=txt
 else:
  pass
  
 rect(screen,pos,size,bcolor,[0,0,0,0],0,text,0)
 pass

# ----------------------------
# Bar
# Display an analog bar gauge
# Takes an analog join and creates a bar graph
# style - hbar-left, hbar-right :  Horizontal bar 0-pos on left or right
#       - vbar-top, vbar-bottom :  Vertical bar 0-pos at bottom or top
# min_value -- minimum value
# max_value -- maximum value
#  bar steps will be (max_value-min_value)/size
#  size will either be width or height minus 2x border size
# bcolor    -- background color
# fcolor    -- forground/bar color
# border    -- border color ; exclude for no border
# bthick    -- thickness in pixels of border ; exclude or zero for no border
# ----------------------------

def Bar(screen,pos,size,bcolor,fcolor,border,bthick,style,sig,max_value,min_value):
 start=(x,y)=pos
 (w,h)=size
 bar=(0,0)
 step=0
 
 if sig < min_value:
   bar=(0,0)
 elif sig > max_value:
   bar=(w,h)
 else:
  if style == 'hbar-left':
   start=(x,y)
   step=float(float(w)/float(max_value-min_value))
   bar=(int(sig*step),h)
  elif style == 'hbar-right':
   step=float(float(w)/float(max_value-min_value))
   bar=(int(sig*step),h)
   start=(int(x+w-sig*step+1),y)
  elif style == 'vbar-top':
   start=(x,y)
   step=float(float(h)/float(max_value-min_value))
   bar=(w,int(sig*step))
  else:                       # vbar-bottom
   step=float(float(h)/float(max_value-min_value))
   start=(x,int(y+h-sig*step))
   bar=(w,int(sig*step))

# print (sig,step, pos, size, start, bar)
 pygame.draw.rect(screen, bcolor, (pos, size), 0)  # draw background bar
 pygame.draw.rect(screen, fcolor, (start, bar), 0)

 if bthick > 0:           # draw border and adjust bars for border
  pygame.draw.rect(screen, border,(pos,size),bthick)

# ----------------------------
# Process list of images for a page
# ----------------------------

def build_img(filename, size):
 img = pygame.image.load(filename)
 img = pygame.transform.scale(img, size)
 return(img)

def process_images(pg):
 global images
 
 images={}
 for v in page[pg]['view']:
  obj_id=page[pg]['view'][v]['id']
  obj=obj_list[obj_id]
  obj_type=obj['type']
  obj_size=val2(obj['size'])
  print (v,obj_type,obj_size)
  if obj_type == 'button':
   act=obj['active']
   if 'image' in act:
    image_id=act['image']
    filename=resource_list[image_id]['imgfile']
    images[image_id]=build_img(filename,obj_size)

   act=obj['inactive']
   if 'image' in act:
    image_id=act['image']
    filename=resource_list[image_id]['imgfile']
    images[image_id]=build_img(filename,obj_size)
  else:
   if 'image' in obj:
    image_id=obj['image']
    filename=resource_list[image_id]['imgfile']
    images[image_id]=build_img(filename,obj_size)

 print ("images",images)

# ----------------------------
# Create the display list
# ----------------------------

active_pg = 0
 
def process_disp_list() :
 global active_pg

 for pg in page:
  if join.get(pg,0) == 1:
   if active_pg != pg:
    active_pg = pg
    process_images(pg)                  # process the images on this page
   for v in page[pg]['view']:
    obj_id=page[pg]['view'][v]['id']
    obj_pos=val2(page[pg]['view'][v]['pos'])
    obj=obj_list[obj_id]
    obj_type=obj['type']
    obj_size=val2(obj['size'])
    obj_join=obj.get('join',0)
    obj_analog_join=obj.get('analog_join',0)
    image=obj.get('image',0)

    if obj_type == 'button':              # process a button
     button_style=obj['style']
     if join.get(obj_join,0) == 1:
       act=obj['active']
     else:
       act=obj['inactive']

     bcolor=val4(act['bcolor'])
     border=val4(act['border'])
     text=resource_list[act['text']]

     if 'image' in act:
      image=act['image']
     else:
      image=0
 
     if button_style == 'oblong':
      oblong(screen,obj_pos,obj_size,bcolor,border,0,text,image)
     elif button_style == 'rect':
      rect(screen,obj_pos,obj_size,bcolor,border,0,text,image)
     else:
      error ('unknown button style');
    if obj_type == 'RSSI':                # process the RSSI Gauge
     sig=analog_join.get(obj_analog_join,-1000)    # Analog join updates async
     scolor=val4(obj['scolor'])
     ncolor=val4(obj['ncolor'])
     bcolor=val4(obj['bcolor'])
     RSSI(screen,obj_pos,obj_size,scolor,ncolor,bcolor,sig)

    if obj_type == 'CLOCK':
      sig=analog_join.get(obj_analog_join,-100)    # Analog join updates async
      text=resource_list[obj['text']]
      bcolor=val4(obj['bcolor'])
      hr=sig/60
      min=sig-(hr*60)
      if sig < 0:
       text['value']="--:--"
      else: 
       if obj['style'] == '12hr':
        if(hr == 0):
         text['value']="12:%02d am"%(min)
        elif(hr == 12):
         text['value']="12:%02d pm"%(min)
        elif(hr > 12):
         text['value']="%02d:%02d pm"%(hr-12,min)
        else:
         text['value']="%02d:%02d am"%(hr,min)
       else:
        text['value']="%02d:%02d"%(hr,min) 
      rect(screen,obj_pos,obj_size,bcolor,[0,0,0,0],0,text,image)

    if obj_type == 'gauge':                     # add a gauge object
     text=resource_list[obj['text']]
     bcolor=val4(obj['bcolor'])
     style=obj.get('style',0)
     Gauge(screen,text,obj_pos,obj_size,bcolor,style,obj_analog_join)
    
    if obj_type == 'bar':                     # add a bar object
     bcolor=val4(obj['bcolor'])
     fcolor=val4(obj['fcolor'])
     border=val4(obj.get('border',[0,0,0,0]))
     bthick=obj.get('bthick',0)
     style=obj.get('style','hbar-left')
     sig=analog_join.get(obj_analog_join,0)    # Analog join updates async
     max_value=obj.get('max_value',65535)      # maximum value
     min_value=obj.get('min_value',0)          # minimum value
    
     Bar(screen,obj_pos,obj_size,bcolor,fcolor,border,bthick,style,sig,max_value,min_value)

    if page[pg].get('x-hair',0):                # Draw cross-hair on page if true
     xhair()
   return (pg)

# rect(screen, (0,0),(240,32),blue, yellow,0,text) 
# oblong(screen, (88,80),(64,32), yellow,black,0,text)
# text={'value':'ROKU','font':'FreeSans.ttf','fontsize':14,'ftcolor': (0xff,0,00,00),'align':'center','style':'strong'} 

# ----------------------------
# Send join to remote side if not local system join
# ----------------------------

def emit_digital_join(join,state):
 if join < 1000:
  Remote_Act.DigitalOut(join, state) 
 else:
  process_system_joins(join,state)

def clear_project():
 obj_list={}
 resource_list={}
 page={}
 join={}
 join_press={}
 active_list={}          # list of button zones


# ----------------------------
#  Remote -- Remote control   ----------------
# ----------------------------

class Remote_net(CS.DemoProtocol):

 def __init__(self,myIP,controllerIP,Slot):
  
#  self.proto=proto
  self.Slot=Slot
  self.IP=myIP
  self.controllerIP=controllerIP
  self.SeqNum=0
  self.Output_SeqNum=0

# ----------------------------
# Incoming joins from remote processor
# ----------------------------

 def AnalogIn(self, AnalogSig, AnalogValue):
  global analog_join
  
  analog_join[AnalogSig]=AnalogValue 


 def DigitalIn(self, DigitalSig, DigitalValue): 
  global join

  join[DigitalSig+1]=DigitalValue

 def SerialIn(self, SerialSig, SerialValue):
  global serial_join

  serial_join[SerialSig]=SerialValue

# ----------------------------
# Write joins to remote processor
# ----------------------------


 def AnalogOut(self, Sig, value):
  self.AnalogWrite(Sig, value, self.Slot)

 def SerialOut(self, Sig, data):
  pass

 def DigitalOut(self, Sig, data):
  print("DigOut",Sig,data)
  self.DigitalWrite(Sig-1, data, self.Slot)

# ----------------------------

def update_analog_values(join_list):
 for ii in join_list:
  if ii < 1000:
   if join_list[ii] != copy_analog_join.get(ii,0):
    Remote_Act.AnalogOut(ii,join_list[ii])
    copy_analog_join[ii]=join_list[ii]

# -------------------------
# Update slow joins
# These are values that should update slowly either due to processing time or HW
# -------------------------

def update_slow_system_joins():
 global analog_join

# RSSI value
 if os.name != "nt":
  with open('/proc/net/wireless') as f:
   content = f.read().splitlines()
  f.close()
  analog_join[RSSI_JOIN]=int(float(content[2].split()[3]))
 else:
  analog_join[RSSI_JOIN]=0

# Remote time in mins
 tm=time.localtime() 
 analog_join[TIME_JOIN]=tm[3]*60+tm[4] 

# ----------------------------
# update values 
def update_fast_system_joins():
 update_analog_values(analog_join)
 
def process_system_joins(join,state):
 if join == SCREEN_OFF_JOIN:
  pass


# ---------------------
# Process system objects
# This runs in a seperate thread due to blocking by ble library
# ---------------------
def SystemObjs():	
 global analog_join
 analog_join=ble_scan.scan(analog_join)

def test_drawing():
 red=(255,0,0)
 green=(0,255,0)
 blue=(0,0,255)
 black=(0,0,0)


# ---------------- Main Loop -------------------------

active_join=0
frame_count=0
projectage=0
down_x, down_y = 0,0
 
def game_tick():
 global frame_count
 global active_list
 global active_join
 global join
 global projectage
 global down_x, down_y


 update_fast_system_joins()
# process_system_joins()
# print (join) 
 screen.fill((0,0,0))
 apg=process_disp_list() 
 for event in pygame.event.get():
    if event.type == pygame.QUIT:
     pygame.quit(); sys.exit();
    if(event.type is pygame.MOUSEBUTTONDOWN):
      down_x,down_y = pygame.mouse.get_pos()        # Fetch the mouse position
#      print ("dx: %d dy: %d\n"%(down_x,down_y))
      active_join = 0
      al=active_list[apg]
      for i in al:
       if al[i]['rect'].collidepoint(event.pos):
        active_join=al[i]['join']
        emit_digital_join(active_join,True)
    if(event.type is pygame.MOUSEBUTTONUP):
        down_x, down_y = 0, 0
        if active_join != 0:
            emit_digital_join(active_join,False)
#    join[active_join]=0
    if down_x or down_y:
        cur_x, cur_y = pygame.mouse.get_pos()
        delta_x = cur_x - down_x
        delta_y = cur_y - down_y
#        if abs(delta_x) > 10 or abs(delta_y > 10):
#            print ("x: %d y: %d\n"%(delta_x,delta_y))
        
 if frame_count == 100:
  update_slow_system_joins()
  tmpage = os.stat(filename).st_mtime
  if tmpage != projectage:
   screen.fill((0,0,0))
   clear_project()
   read_project(filename)
   projectage = tmpage
   active_pg = 0
  frame_count = 0
 else:
  frame_count = frame_count + 1
 test_drawing()

 pygame.display.update()
# pygame.time.wait(10)


# ----------------------------
# Program entry
# ----------------------------
  
filename = 'Project1.yaml'

pygame.init()
screen = pygame.display.set_mode((240,320))
pygame.mouse.set_visible(False)
read_project(filename)
   
#-----------------------------------------------------
# Define the actors

myIP='192.168.160.217'
controllerIP='192.168.160.202'
mySlot=0x15

# ----------------------------
# Define actors here
# Some network protocols allow for multi-processor support
# ----------------------------
 
Remote_Act=Remote_net(myIP, controllerIP, mySlot)

# ----------------------------
# Setup slot to actor mapping
# Also, send wakeup message to remote processor(s)
# Slot, IP, actor
# ----------------------------

remotes={mySlot:{'IP':controllerIP,'Act':Remote_Act}}
Remote_Act.SetupRemotes(remotes,Port)

# Set up a looping call every 1/30th of a second to run the remote tick
# This is being driven by twisted

tick = LoopingCall(game_tick)
tick.start(1.0 / DESIRED_FPS).addErrback(twisted.python.log.err)

sysobjs_tick = LoopingCall(SystemObjs)
sysobjs_tick.start(1.0).addErrback(twisted.python.log.err)

#reactor.listenUDP(Port, Remote_Act)   # uncomment if creating an actual network protocol
reactor.run()

