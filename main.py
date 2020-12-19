"""
The MIT License (MIT)
Copyright © 2020 David Sundstrom

Embedded well pump runtime monitor and metrics web application

"""

from MicroWebSrv2 import *
from microDNSSrv import MicroDNSSrv
import network
import system
import controller # required to register web routes

webSockets = []
global ws_lock
ws_lock = allocate_lock()

SSID = "wellbeing"
IP="192.168.4.1"
PORT=80

## Enable Wifi as Access Point
ap = network.WLAN(network.AP_IF)
ap.config(essid=SSID)
ap.ifconfig([IP, '255.255.255.0', IP, IP])
ap.active(True)

## Enable DNS server. Don't make it captive as that throws up dialogs on computers.
dns = MicroDNSSrv.Create({ '*well*' : IP })

## Enable WebServer, default AP IP is 192.168.4.1
mws2 = MicroWebSrv2()
mws2.RootPath = 'www'
mws2.BindAddress = (IP, PORT)
mws2.SetNormalConfig()
mws2.AddDefaultPage("wellbeing.html")

def webSocketAccept(microWebSrv2, webSocket):
    global webSockets
    with ws_lock:
        webSockets.append(webSocket)
        webSocket.OnClosed = webSocketClosed

def webSocketClosed(webSocket):
    global webSockets
    with ws_lock:
        webSockets.remove(webSocket)

def readingCallback(status):
    global webSockets
    with ws_lock:
        for ws in webSockets:
            ws.SendTextMessage(status)

# Loads the WebSockets module globally and configure it,
wsMod = MicroWebSrv2.LoadModule('WebSockets')
wsMod.OnWebSocketAccepted = webSocketAccept
wsMod.WaitFrameTimeoutSec = 60 * 60
system.PumpManager.getManager().setCallback(readingCallback)

mws2.StartManaged()

# Main program loop.
# See https://github.com/jczic/MicroWebSrv2/issues/56 for why this is coded as it is
try :
    system.PumpManager.getManager().run()
except KeyboardInterrupt :
    mws2.Stop()
