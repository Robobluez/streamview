#!/usr/bin/env python3

import zmq
import math
import time
import random
import cv2
import numpy as np

context = zmq.Context()

sock_vid    = context.socket(zmq.PUB) # publish to whoever is listening
sock_vid.setsockopt(zmq.CONFLATE, 1)  # keep latest message only
sock_vid.bind("tcp://*:5550")         # send to port 5550 on local network interface

sock_graph    = context.socket(zmq.PUB) # publish to whoever is listening
sock_graph.setsockopt(zmq.CONFLATE, 1)  # keep latest message only
sock_graph.bind("tcp://*:5551")         # send to port 5551 on local network interface

idx = 1

print("Streaming. Interrupt to stop")

while True:

    graph =  \
        {    \
             "minimal graph" :   # graph name
            (
                { "min" : -1, "max" : 1}, # left scale range
                { "sin" : math.sin(math.radians(idx)) }, # single left side var
                {}, # no right scale range
                {}, # no right scale vars
                {}  # no data data variable
            ),
             "full graph" :   # graph name
            (
                {"min" : -1, "max" : 1}, # left scale range
                { # left scale vars
                   "sin" : math.sin(math.radians(idx)),
                   "cos" : math.cos(math.radians(idx))
                },
                {"min" : -20, "max" : 20}, # right scale range
                { "tan" : math.tan(math.radians(idx)) }, # right scale var
                {"idx" : idx} # data variable
            )
        }


    # prepare moving image
    win = np.full((240,240,3), 0, dtype=np.uint8)
    cv2.circle(win, (random.randrange(win.shape[1]), random.randrange(win.shape[0])),
        int(random.randrange(win.shape[0])/5), (255,0,255), -1)

    sock_graph.send_pyobj(graph) # stream graph data
    sock_vid.send_pyobj({"demo video" : win} )  # stream video data

    time.sleep(0.025)
    idx += 1
