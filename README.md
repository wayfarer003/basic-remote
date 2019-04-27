# basic touch-remote

Simple touch panel remote framework.
Uses a YAML file to create the page configuration.
The project has an example backend showing how one might create an interface to an external processor

touch-remote has been created in Python 2.5 and is designed to run on a rPi + pyTft panel.
A second hardware option is expected to be the yio-remote https://github.com/martonborzak/yio-remote by Marton Borzak as it uses the same basic hardware design.

It is also possible to test this project on a PC if the requirements are installed.  
Any physical buttons or other local hardware would be missing, however.

Requirements:
 - Python 2.5
 - pygame
 - twisted
 - pyyaml

Input and output signaling is based upon simple control signals to/from the external controller.
Three join types are supported.
External join numbers can currently take on values from 1-999.  Different join types can have the same number.
Defined join values are:
- Digital: 0/1
- Analog: 0-65535
- Serial: Text strings

System/local joins start at 1000 except for the case of physical buttons.  These are currently defined as:
- Analog:
    - 1000 - RSSI Strength
    - 1001 - Time in mins
    - 1002 - Battery gauge
- Digital:
    - 1    - Physical button 1
    - 2    - Physical button 2
    - 3    - Physical button 3
    - 4    - Physical button 4
    - 5    - Physical button 5
    - 6    - Physical button 6
    - 1000 - backlight on/off
    

Objects currently supported are:
- Page   : A page is a collection of objects that are displayed together.  Pages are only visible if the page join is active.
- Button : A button is an object that can emit or receive presses 
         : Buttons have an active and in-active state   
- RSSI   : A simple WiFi style graphic used to display WiFi values
- Clock  : 12/24 text clock 
- Gauge  : multi-digit number display XXXX, XXX.X, XX.XX, etc
- Bar    : right/left, up/down bar graph.  Fills up as analog value increases from Min -> Max value.

Objects can take on certain resources:
- Text
- Graphic




