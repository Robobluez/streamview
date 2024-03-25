#!/usr/bin/env python3

import os
import sys

import cv2
import zmq
import time
import numpy as np

import video
import graph
import util

import argparse

############################################################################
# Streamview main class - manages inputs, videos, graphs, video creation 
############################################################################
class Streamview(object):

    def __init__(self, kb, leadertxt, image_msg, graph_msg, canvas_h, canvas_w, fps, createvideo,
        videopath, videocolormodel,graphcols, videocols):

       self.leadertxt     = leadertxt
       self.kb            = kb
       self.fps           = fps
       self.image_msg     = image_msg
       self.graph_msg      = graph_msg
       self.createvideo   = createvideo
       self.videocolormodel = videocolormodel
       self.videopath     = videopath
       self.graphcols     = graphcols
       self.videocols     = videocols
       self.videohandle   = None
       self.basetime      = None
       self.lastsnapped   = 0
           
       self.canvas = np.full((canvas_h, canvas_w, 3), (255,255,255), dtype=np.uint8)
       self.box = util.Box(self.canvas, None, 0, 0, canvas_w, canvas_h)

       self.ibox = util.Box(self.canvas, None, self.box.sbxoffs(), self.box.sbyoffs(), self.box.sbwidth(), 0)
       self.videos = video.VideoSet(self.canvas,self.ibox, cols=videocols, videocolormodel = self.videocolormodel)
       self.dbox = util.Box(self.canvas, None, self.box.sbxoffs(), self.box.sbyoffs(), self.box.sbwidth(), self.box.sbheight())
       self.panels = graph.Panels(self.canvas, self.dbox, cols=graphcols)

       self.leader()

       if self.createvideo:
           if not os.path.exists("./{}".format(self.videopath)):
               os.makedirs(self.videopath)
           self.videohandle = cv2.VideoWriter("{}/video-{}-{}.mp4".format(self.videopath, time.strftime("%Y%m%d"),
                time.strftime("%H%M")), cv2.VideoWriter_fourcc(*'mp4v'), float(fps), (self.canvas.shape[1], self.canvas.shape[0]))

    def leader(self, fontsize = 0.8, fonttype = 2):
        (label_width, label_height), baseline = cv2.getTextSize(self.leadertxt, fonttype, fontsize, 1)
        self.box.print(self.leadertxt, int(0.5 * self.box.sbwidth()) - int(0.5 * label_width), int(0.5 * self.box.sbheight()),
            fonttype, fontsize, color = 0, tocanvas = True)
  
    def __del__(self): # destructor - needed to release video handle & flush video
       if self.createvideo and self.videohandle is not None:
           self.videohandle.release()

    def process_snapshot(self): # generate & display monitor image
        self.videos.flush()
        self.panels.flush()
        if self.createvideo:
            self.videohandle.write(self.canvas)
        cv2.imshow("streaming data viewer", self.canvas)
        cv2.waitKey(1)

    def snap(self):
        if self.basetime is None:
            self.basetime = time.time()
        snapped = round((time.time() - self.basetime)*self.fps)
        if snapped > self.lastsnapped:
           self.lastsnapped = snapped
           self.process_snapshot()

    ##########################################################################
    # main loop
    ##########################################################################
    def run(self):

      while not self.kb.quit():
  
         graph_msg = self.graph_msg.read() # check for data message
         if graph_msg is not None:
            for name in graph_msg.keys(): 
               self.panels.update(name, graph_msg[name])

         image_msg = self.image_msg.read()  # check for image message
         if image_msg is not None:
            for name, image in image_msg.items():
               self.videos.update(name, image, self.box.wipe)
               if self.videos.redrawn:
                  isize = self.videos.box.height
                  self.dbox = util.Box(self.canvas, None, self.box.sbxoffs(), self.box.sbyoffs()+isize, self.box.sbwidth(), self.box.sbheight() - isize)
                  self.panels = graph.Panels(self.canvas, self.dbox, cols=self.graphcols)
                  self.redrawn = False

         self.snap()
   
############################################################################
# main
############################################################################
if __name__ == "__main__":

   parser = argparse.ArgumentParser(description='View streaming video and graph data')
   parser.add_argument('-width', help="pixel width width of viewer window", type=int, default=800)
   parser.add_argument('-height', help="pixel height of viewer window", default=680, type=int)
   parser.add_argument('-createvideo', help="save viewer data as video", action='store_true', default=True)
   parser.add_argument('-videopath', help="saved video output directory", default='FILES')
   parser.add_argument('-fps', help="frame rendering speed. applies to both screen rendering and saved video", type=int, default=25)
   parser.add_argument('-videocolormodel', help="color subpixel order in video input", default='rgb', choices=['bgr','rgb','auto'])
   parser.add_argument('-gh', '--graphhost', help='name or address of graph message host', default='localhost')
   parser.add_argument('-gp', '--graphport', help='port number of graph data messags', type=int, default=5551)
   parser.add_argument('-vh', '--videohost', help='name or address of video message host', default='localhost')
   parser.add_argument('-vp', '--videoport', help='port number of video messages', type=int, default=5550)
   parser.add_argument('-gc', '--graphcols', help='number of graph columns', default=1, type=int, choices=range(1, 6))
   parser.add_argument('-vc', '--videocols', help='number of video columns', default=2, type=int, choices=range(1, 6))

   args = parser.parse_args()

   if ((args.height < 100) or ((args.width / args.graphcols) < 100) or ((args.width / args.videocols) < 100)):
       print("display area too small -  set height and column width to 100px or larger", file=sys.stderr)
       exit(0)

   print()
   parser.print_usage()
   print("\nSettings:\n")
   for arg in vars(args):
     print ("{:<12}= {}".format(arg, getattr(args, arg)))
   print("\nEnter 'q' to stop")

   # conflate=true: let new incoming video images overwrite any unprocessed messades in queue. in case we cannot keep up
   image_msg = util.iMsg(zmq.Context(), args.videoport, host=args.videohost, conflate = True) # dict: name : image

   # conflate=false: let incoming data messages queue up. only relevant when imdisplay is being resized and queue processing is suspended.
   #    in all other cases we have no issue keeping up
   graph_msg = util.iMsg(zmq.Context(), args.graphport, host=args.graphhost, conflate = False) # dict arrray: [ name : tuple ]

   sv = Streamview(util.KBHit(),
        leadertxt    = "Waiting for streaming data ..",
        image_msg    = image_msg,
        graph_msg    = graph_msg,
        fps          = args.fps,
        canvas_w     = args.width,
        canvas_h     = args.height,
        createvideo  = args.createvideo,
        videopath    = args.videopath,
        videocolormodel= args.videocolormodel,
        graphcols    = args.graphcols,
        videocols    = args.videocols).run()
