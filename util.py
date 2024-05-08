import cv2
import sys
import zmq
import numpy as np
import math
import platform

from collections import deque

# import libraries needed for getch on *nix
try:
    import termios
    import atexit
    from select import select
except:
    pass

# import libraries needed for getch on 
try:
    import msvcrt
except:
    pass

############################################################################
# Predefined colors
############################################################################
class Colors(object):
    def __init__(self):

        self.color_d = { # https://wamingo.net/rgbbgr/ , https://www.rapidtables.com/web/color/RGB_Color.html
            'Red': (0, 0, 255),
            'Orange': (0, 165, 255),
            'Lead': (64, 64, 64),
            'Ultimate pink': (255, 86, 255),
            'Waystone green': (0, 192, 0),
            'Navy blue': (128, 0, 0) }

        self.colors = deque([v for (k, v) in self.color_d.items()])
        self.colors.reverse()

    def get(self):
       return self.colors.pop() if len(self.colors) > 0 else None

    def grey(self):
       return (180, 180, 180)

    def white(self):
       return (255, 255, 255)

    def silver(self):
       return (220, 220, 220)

    def dark_grey(self):
       return (100, 100, 100)

    def scale(self):
       return (25, 25, 25)


############################################################################
# Unbuffered keyboard handler - combines windows and *nix 
############################################################################
class KBHit:

    def __init__(self):
        self.system = platform.system()
        assert self.system == "Linux" or self.system == "Darwin" or self.system == "Windows"
        if self.system == "Linux" or self.system == "Darwin": 
            # Save the terminal settings
            self.fd = sys.stdin.fileno()
            self.new_term = termios.tcgetattr(self.fd)
            self.old_term = termios.tcgetattr(self.fd)

            # New terminal setting unbuffered
            self.new_term[3] = (self.new_term[3] & ~termios.ICANON & ~termios.ECHO)
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)

            # Support normal-terminal reset at exit
            atexit.register(self.set_normal_term)

    def set_normal_term(self):
        if self.system == "Linux" or self.system == "Darwin": 
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)

    def __del__(self):
        self.set_normal_term()
            
    def getch(self):
        if self.system == "Linux" or self.system == "Darwin": 
            return sys.stdin.read(1)
        if self.system == "Windows":
            return msvcrt.getch().decode()

    def kbhit(self):
        if self.system == "Linux" or self.system == "Darwin": 
            dr,dw,de = select([sys.stdin], [], [], 0)
            return dr != []
        if self.system == "Windows":
            return msvcrt.kbhit()

    def quit(self):
        return (self.kbhit() and self.getch() == 'q')

############################################################################
# Box coordinate & margin handling
############################################################################
class Box(object):
    def __init__(self, canvas, name, xoffs, yoffs, width, height, topbotmargin = 0, sidemargin = 0, fill = 255, fontsize = 0.4, border = False):

        self.canvas  = canvas
        self.name    = name
        self.xoffs   = xoffs   # x offset within main canvas
        self.yoffs   = yoffs   # y offset within main canvas
        self.width   = width   # box width
        self.fill    = fill
        self.fontsize = fontsize
        self.titled  = False
        self.overflow = False
        self.win      = None
        self.border   = border
 
        if border:
            topbotmargin += 3
            sidemargin += 3
 
        (_, text_h), _ = cv2.getTextSize("()", 2, self.fontsize, 1) # use fixed text for height so title_margin is not dependent on the actual text
        self.title_margin = (text_h+4) if (self.name is not None)  else 0

        # if height is negative: use if as sbheight, and calculate the resulting height
        # if height is positive: use if as outide height, and calculate the resulting sbheight
        height = (abs(height) + self.title_margin + 2 * topbotmargin ) if height < 0 else height

        self.calc(height, topbotmargin, sidemargin)

    def calc(self, height, topbotmargin, sidemargin):
        self.height       = height
        self.title_margin = min(self.height, self.title_margin)
        self.topbotmargin = max(0, min(topbotmargin, math.floor((self.height - self.title_margin)/2))) # topbotmargin  needs to allow for title_margin
        self.sidemargin   = min(sidemargin, int(self.width/2))

        if self.canvas is not None and ((self.yoffs + self.height > self.canvas.shape[0]) or (self.xoffs + self.width > self.canvas.shape[1]) or self.sidemargin < 0):
            self.overflow = True

    def sizeme(self, height):
        self.calc(height, self.topbotmargin, self.sidemargin)

    def print(self, txt, x, y, fonttype, fontsize, color, tocanvas = False, rotation = 0):
        assert self.overflow is False
        if tocanvas:
           self.print_low(self.canvas, txt, (x + self.sbxoffs(), y + self.sbyoffs()), fonttype, fontsize, color, rotation)
        else:
           if self.win is None and self.canvas is not None and self.sbwidth() > 0 and self.sbheight() > 0:
               self.win = np.full((self.sbheight(), self.sbwidth(), 3), (self.fill, self.fill, self.fill), dtype=np.uint8)
           if self.win is not None:
              self.print_low(self.win, txt, (x, y), fonttype, fontsize, color, rotation)

    def print_low(self, win, txt, coord, fonttype, fontsize, color, rotation):
       if rotation:
          rot = cv2.rotate(win, cv2.ROTATE_90_CLOCKWISE) 
          cv2.putText(rot, txt, coord, fonttype, fontsize, color, 1, cv2.LINE_AA)
          win[:,:,:] = cv2.rotate(rot, cv2.ROTATE_90_COUNTERCLOCKWISE)
       else:
           cv2.putText(win, txt, coord, fonttype, fontsize, color, 1, cv2.LINE_AA)

    def forcewin(self): # force win into existence. needed for windows that don't use box.print 
        self.win = np.full((self.sbheight(), self.sbwidth(), 3), (self.fill, self.fill, self.fill), dtype=np.uint8)

    def wipe(self):
        assert self.overflow is False
        if self.canvas is not None:
            self.canvas[self.yoffs : self.yoffs + self.height, self.xoffs : self.xoffs + self.width,:] = 255

    def tobox(self, win):
        assert self.overflow is False
        if self.canvas is not None:
            self.win = win

    def shrinktext(self):
        shrinkfontsize = self.fontsize
        while True:
            (name_w, _), _ = cv2.getTextSize(self.name, 2, shrinkfontsize, 1) 
            if name_w < self.width:
                break
            shrinkfontsize *= 0.98
        return name_w, shrinkfontsize

    def flush(self):
        assert self.overflow is False
        if self.canvas is not None and self.win is not None:
            self.canvas[self.sbyoffs() : self.sbyoffs() + self.win.shape[0], self.sbxoffs() : self.sbxoffs() + self.win.shape[1]] = self.win
        if self.canvas is not None:
           if not self.titled and self.title_margin > 0: # put title at top, horizontally centered
               name_w, shrinkfontsize = self.shrinktext()
               cv2.putText(self.canvas, self.name, (self.xoffs + max(0, int(self.width/2 - name_w/2)), self.sbyoffs() - 3), 2, shrinkfontsize, (120,120,120), 1, cv2.LINE_AA)
               self.titled = True
           # grid lines
        if self.border and self.canvas is not None:
           assert self.topbotmargin > 0 
           assert self.sidemargin > 0

           #print("xoffs", self.xoffs, "yoffs", self.yoffs, "width", self.width, "height", self.height)

           #print(1+self.yoffs,                    1+self.xoffs, "-", -1+self.xoffs+self.width)
           self.canvas[1+self.yoffs,              1+self.xoffs:-1+self.xoffs+self.width] = (200,200,200)

           #print(-1+self.yoffs+self.height-1,       1+self.xoffs, "-", -1+self.xoffs+self.width)
           self.canvas[-1+self.yoffs+self.height-1,1+self.xoffs:-1+self.xoffs+self.width] = (200,200,200)

           #print(1+self.yoffs, "-",  1+self.yoffs+self.height,1+self.xoffs)
           self.canvas[1+self.yoffs: 1+self.yoffs+self.height,1+self.xoffs] = (200,200,200)

           #print(      -1+self.yoffs, "-",   -1+self.yoffs+self.height,-1+self.xoffs + self.width-1)
           self.canvas[1+self.yoffs: -1+self.yoffs+self.height,-1+self.xoffs + self.width-1] = (200,200,200)

    def sbyoffs(self): 
        return self.yoffs + self.topbotmargin + self.title_margin
    def sbxoffs(self): # 
        return self.xoffs + self.sidemargin
    def sbheight(self): 
        return self.height - (2 * self.topbotmargin) - self.title_margin
    def sbwidth(self): # 
        return self.width - (2 * self.sidemargin)

MONITOR_VIDEO    = 5550  # image based monitoring messages
MONITOR_GRAPH    = 5551  # data based monitoring messages

class iMsg(object):
    def __init__(self, context, queue, host="127.0.0.1", fltr="", conflate=False):
        self.context = context
        self.sock = self.context.socket(zmq.SUB)
        if conflate == True:
            self.sock.setsockopt(zmq.CONFLATE, 1)  # latest 1 message
        self.sock.connect("tcp://{}:{}".format(host, queue))
        self.sock.setsockopt_string(zmq.SUBSCRIBE, fltr)

    def read(self):
        try:
            message = self.sock.recv_pyobj(flags=zmq.NOBLOCK)
        except:
            return None
        else:
            return message

class oMsg(object):
    def __init__(self, context, queue, host = "127.0.0.1", conflate=False):
        self.context = context
        self.sock = self.context.socket(zmq.PUB)
        if conflate == True:
            self.sock.setsockopt(zmq.CONFLATE, 1)  # latest 1 message
        self.sock.bind("tcp://{}:{}".format(host, queue))

    def send(self, m):
        self.sock.send_pyobj(m, protocol = 2) # use protocol 2 so we are compatible with ROS & python2
