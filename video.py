import sys
import cv2
import time
import numpy as np
import math
import util

############################################################################
# Video
############################################################################
class Video(object):

    def __init__(self, name, canvas, box):
        self.canvas = canvas
        self.name = name
        self.lab = name
        self.box = box

    def update(self, img):
        self.box.tobox(img)

############################################################################
# VideoSet
############################################################################
class VideoSet(object):

    def __init__(self, canvas, box, cols = 3, hspacer = 2, vspacer = 2, videocolormodel = 'rgb'):
        self.canvas = canvas
        self.box = box
        self.cols = cols
        self.rows = 0
        self.videos = {}
        self.images = {}
        self.is_bgr = {}
        self.blocked = {}
        self.hspacer = hspacer
        self.vspacer = vspacer
        self.videocolormodel = videocolormodel
        self.redrawn = False # used by streamer - if videos are redrawn, graphs need to be redrawn as well 

    def is_likely_bgr(self, frame):
        r, g, b = cv2.split(frame)

        r_mean, r_std = cv2.meanStdDev(r)
        b_mean, b_std = cv2.meanStdDev(b)

        if b_mean > r_mean and b_std > r_std:
            return True  # Likely BGR

    ############################################################################
    # handle new incoming video image
    ############################################################################
    def update(self, name, img, wipemain): # handle new incoming video image
        if name in self.blocked:
            return
        if len(img.shape) == 2:
           self.images[name] = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if len(img.shape) == 3:
           if self.videocolormodel == 'auto':
              if not name in self.is_bgr:
                  self.is_bgr[name] = self.is_likely_bgr(img)
                  if not self.is_bgr[name]:
                      print("Setting RGB to BGR conversion for {}".format(name))
                      print("Use viewer command line options to manage color model conversion settings")
              if not self.is_bgr[name]:
                  self.images[name] = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
              else:
                  self.images[name] = img
           elif self.videocolormodel == 'rgb':
               self.images[name] = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
           else:
               self.images[name] = img

        # set flag when video display has resized - tells graph display to resize as well

        self.redrawn = True if (name not in self.videos and not name in self.blocked) else False

        if self.redrawn:
            wipemain()
            newvideos= {}
            height = self.redraw(name, oldvideos = self.videos, newvideos = newvideos)
            if not self.overflow:
               self.box.sizeme(height)
               self.videos = newvideos
            else:
               print("Cannot fit image - skipping: {}".format(name), file=sys.stderr)
               self.blocked[name] = True
               if len(self.videos) > 0:
                   wipemain()
                   height = self.redraw(None, oldvideos = self.videos, newvideos = self.videos)
                   self.box.sizeme(height)

        if name in self.videos and not name in self.blocked:
            self.videos[name].update(self.images[name])

    ############################################################################
    # rebuild video display - happens when we see new videos
    ############################################################################
    def redraw(self, newname, oldvideos, newvideos)  :
        self.overflow = False
        self.box.wipe()
        videonames = sorted(list(oldvideos.keys()) if newname is None else (list(oldvideos.keys()) + ([newname])), key = lambda k: (self.images[k].shape[0], k))
        self.rows = math.ceil(len(videonames) / self.cols)
        height = 0
        for row in range(0, self.rows):
            imgheight = max([self.images[videonames[i]].shape[0]
                for i in range(row * self.cols , min(len(videonames), (row+1) * self.cols))])
            rowbox = util.Box(None, "", self.box.sbxoffs(), self.box.sbyoffs() + height, self.box.sbwidth(), -1 * imgheight, # negative height : let box add the title height
                topbotmargin = 3, sidemargin = 3)
            w = math.floor(self.box.sbwidth()/self.cols) - self.hspacer
            h = rowbox.height
            for col in range(0, self.cols):
                idx = row * self.cols + col % self.cols
                if idx < len(videonames):
                   name = videonames[idx]
                   img = self.images[name]
                   box = util.Box(self.canvas, name, self.box.sbxoffs() + col * w + math.floor(self.hspacer/2) + (col*self.hspacer) , self.box.sbyoffs() + height, w, h,
                       topbotmargin = math.floor((h - rowbox.title_margin - img.shape[0])/2), sidemargin = math.floor((w - img.shape[1])/2))
                   if box.overflow is True:
                       self.overflow = True
                   newvideos[name] = Video(name, self.canvas, box)
            height += (rowbox.height + self.vspacer)
        return height

    def count(self):
       return len(self.videos)

    def flush(self):
        for name in self.videos.keys():
            self.videos[name].box.flush()
