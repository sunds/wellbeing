"""
The MIT License (MIT)
Copyright © 2020 David Sundstrom

Webapp controller functions
"""

from MicroWebSrv2 import *
import system

@WebRoute(GET, '/')
@WebRoute(GET, '/index.html')
def Redirect(microWebSrv2, request):
    request.Response.ReturnRedirect('/wellbeing.html')

@WebRoute(POST, '/api/setDateTime', name='SetDateTime')
def SetTime(microWebSrv2, request) :
    try:
        t = request.GetPostedJSONObject()
        c = system.Clock()
        c.setDateTime(t['year'],t['month'],t['monthDay'],t['hour'],t['minute'],t['second'],t['weekday'])
        request.Response.ReturnOk()
    except:
        request.Response.ReturnBadRequest()

@WebRoute(GET, '/api/getHistoricalData',  name="GetHistoricalData")
def GetHistoricalData(microWebSrv2, request):
    s = system.PumpManager.getManager()
    request.Response.ReturnOkJSON(s.getLogs(60))

@WebRoute(POST, '/api/setFault',  name="SetFault")
def SetFault(microWebSrv2, request):
    try:
        t = request.GetPostedJSONObject()
        s = system.PumpManager.getManager()
        s.setFault(fault=t['fault'])
        request.Response.ReturnOk()
    except:
        request.Response.ReturnBadRequest()

@WebRoute(GET, '/api/getConfig',  name="GetConfig")
def GetConfig(microWebSrv2, request):
    s = system.PumpManager.getManager()
    request.Response.ReturnOkJSON(s.getConfig())

@WebRoute(POST, '/api/setConfig',  name="SetConfig")
def SetConfig(microWebSrv2, request):
    try:
        t = request.GetPostedJSONObject()
        s = system.PumpManager.getManager()
        s.setConfig(maxCycles=t['maxCycles'],maxRuntime=t['maxRuntime'],minCurrent=t['minCurrent'])
        request.Response.ReturnOk()
    except:
        request.Response.ReturnBadRequest()

@WebRoute(PUT, '/api/reset',  name="Reset")
def SetFault(microWebSrv2, request):
    try:
        s = system.PumpManager.getManager()
        s.reset()
        request.Response.ReturnOk()
    except:
        request.Response.ReturnBadRequest()
