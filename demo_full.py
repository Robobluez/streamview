#!/usr/bin/env python3

import cv2
import zmq
import math
import time
import util
import random
import numpy as np

##############################################################
# Grab frames from animated gif
##############################################################
class AnimatedGif:

    def __init__(self, name = 'ingenuity.gif', ratio = 1):
        self.ratio = ratio
        self.frames = {}
        self.idx = 0

        gif = cv2.VideoCapture(name)
        ret, frame = gif.read()
        while ret:
            ret, frame = gif.read()
            if not ret:
                break
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.frames[self.idx] = cv2.resize(frame, None, fx= ratio, fy= ratio, interpolation= cv2.INTER_LINEAR)
            self.idx += 1

    def getframe(self):
        self.idx = (self.idx + 1) % len(self.frames)
        return self.frames[self.idx]
          

##############################################################
# Monitor - push real time graph to message queue
##############################################################
class gMonitor(object):

    def __init__(self):
        self.sender = util.oMsg(zmq.Context(), util.MONITOR_GRAPH, host = "*", conflate = True)
        self.msg = {}

    def stack(self, name, leftscale, leftvars, rightscale, rightvars, datavars):
        if name in self.msg:
            self.sender.send(self.msg)
            self.msg = {}
        self.msg[name] = (leftscale, leftvars, rightscale, rightvars, datavars) 

##############################################################
# Monitor - push real time video to message queue
##############################################################
class vMonitor():
        
    def __init__(self):
        self.sender = util.oMsg(zmq.Context(), util.MONITOR_VIDEO, host = "*", conflate = True)
        self.msg = {}
            
    def stack(self, name, frame): # keep the latest for each window type
        if name in self.msg:
            self.sender.send(self.msg)
            self.msg = {}
        else:
            self.msg[name] = frame

##############################################################
# MAIN
##############################################################
if __name__ == '__main__':
    gmonitor = gMonitor()
    vmonitor = vMonitor()

    options_g = {}
    options_v = {}

    active_g = {}
    active_v = {}

    animations = {}

    graphs = {
        "twin scales I" : (
            {}, {"sin" : "math.sin(math.radians(idx))" , "cos" : "math.cos(math.radians(idx))" }, 
            {"min" : -2, "max" : 2} , {"sin*2" : "2*math.sin(math.radians(idx+10))" , "cos*2" : "2*math.cos(math.radians(idx+20))" },
            {}),
        "twin scales II" : (
            {} , {"sin" : "math.sin(math.radians(idx))" , "cos" : "math.cos(math.radians(idx))" },
            {"min" : -20, "max" : 20}, {"tan" : "math.tan(math.radians(idx))" },
            {}),
        "graph plus data variables" : (
            {} , {"sin" : "math.sin(math.radians(idx))" , "cos" : "math.cos(math.radians(idx))" },
            {}, {},
            { "degrees" : "idx % 360", "sin" : "math.sin(math.radians(idx))" , "cos" : "math.cos(math.radians(idx))" }),
        "data variables only" : (
            {},{},
            {},{},
            { "time" : "time.time()", "degrees" : "idx % 360", "sin" : "math.sin(math.radians(idx))" , "cos" : "math.cos(math.radians(idx))" }),
        "lots of graph variables" : (
            {}, { "sin1" : "math.sin(math.radians(idx))" , "sin2" : "math.sin(math.radians(idx+10))" , "sin3" : "math.sin(math.radians(idx+20))" ,
              "sin4" : "math.sin(math.radians(idx+30))", "sin5" : "math.sin(math.radians(idx+40))", "sin6" : "math.sin(math.radians(idx+50))"},
            {}, {},
            {})
    }

    videos = { # definition of video simulations ( size, gif name )
        "video simulation (small I) " : (0.4, 'ingenuity.gif'),
        "video simulation (small II) " : (0.4, 'ingenuity.gif'),
        "video simulation (small II) " : (0.4, 'ingenuity.gif'),
        "video simulation (medium I)" : (0.6, 'ingenuity.gif'),
        "video simulation (medium II)" : (0.6, 'ingenuity.gif'),
        "video simulation (medium III)" : (0.6, 'ingenuity.gif'),
        "video simulation (large)" : (0.8, 'ingenuity.gif')}

    for idx, (k, v) in zip(range(ord('a'), ord('a') +len(graphs)+1), graphs.items()):
        options_g[chr(idx)] = k

    for idx, (k, v) in zip(range(ord('A'), ord('A') + len(videos)+1), videos.items()):
        r, n = v
        animations[k] = AnimatedGif(name = n, ratio = r)
        options_v[chr(idx)] = k

    kb = util.KBHit() 

    print("\nUse stream viewer app to view the results\n")

    while True:

       print("Graphs:")
       for k, v in options_g.items():
           print("{} : {} {}".format(k, v, "[sending ..]" if options_g[k] in active_g else ''))
       print("Videos:")
       for k, v in options_v.items():
           print("{} : {} {}".format(k, v, "[sending ..]" if options_v[k] in active_v else ''))
       print()
       print("Enter selector for graph/video to stream or q to quit : ", end='', flush=True)

       while not kb.kbhit():
           time.sleep(0.025)

           idx = idx + 1

           for name in active_g.keys():
               lv =  {}
               rv =  {}
               dv =  {}
               leftscale, leftvars, rightscale, rightvars, datavars  = graphs[name]
               for k, v in leftvars.items():
                  lv[k] = eval(leftvars[k])
               for k, v in rightvars.items():
                  rv[k] = eval(rightvars[k])
               for k, v in datavars.items():
                  dv[k] = eval(datavars[k])
               gmonitor.stack(name, leftscale, lv, rightscale, rv, dv)

           for name in active_v.keys():
               active_v[name] = animations[name].getframe()
               vmonitor.stack(name, active_v[name])

       input = kb.getch()

       print(input)

       if (input == "q"): 
           break

       if input in options_g:
           active_g[options_g[input]] = ""

       if input in options_v:
           active_v[options_v[input]] = None
