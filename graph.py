import sys
import cv2
import time
import math
import numpy as np
import util

############################################################################
# Left or right side panel with y-axis values 
############################################################################
class Scale(object):
    def __init__(self, scaledef, box, pos, fontsize = 0.3, fonttype = 2):
        self.scaledef = scaledef
        self.box      = box
        self.fontsize = fontsize
        self.fonttype = fonttype
        self.pos      = pos # position: 0 is left, 1 is right
        self.idx      = 0
        
        (label_width, self.label_height), baseline = cv2.getTextSize("0123456789", self.fonttype, self.fontsize, 1)

        self.minv = min(self.scaledef.get('min', -1), self.scaledef.get('max', 1))
        self.maxv = max(self.scaledef.get('max', 1), self.scaledef.get('max', 1))
        self.label = self.scaledef.get('label', "")

        self.labelvals = self.autolabels()
        self.labelstepcnt = len(self.labelvals)-1
        self.labelcnt = len(self.labelvals)

        assert self.labelstepcnt > 0

        # calculate pix offset for each label value. correct sbheight for label_height
        self.steppix = [ int(i * (self.gridheight() / self.labelstepcnt)+self.gridmargin()) for i in range(0, self.labelcnt)]
   
        self.initscale()

    def gridmargin(self):
        return int(self.label_height)

    def gridheight(self):
        return int(self.box.sbheight() - 2 * self.gridmargin())

    def initscale(self):
        # print rotated scale label
        (label_width, label_height), baseline = cv2.getTextSize(self.label, self.fonttype, 1.3 * self.fontsize, 1)
        offs_x = max(0, int(self.box.sbheight()/2 - label_width/2))
        offs_y = label_height if self.pos == 0 else self.box.sbwidth() - 2 # - label_height
        self.box.print(self.label, offs_x, offs_y, self.fonttype, 1.3 * self.fontsize, (120,120,120), rotation = 90) # clockwise 

        # now, print scale values
        for i, label in zip(self.steppix, self.labelvals):
           (label_width, label_height), baseline = cv2.getTextSize(label, self.fonttype, self.fontsize, 1)
           offs_x = 2 if self.pos == 1 else max(0, self.box.sbwidth()- label_width - 2)
           offs_y = self.box.sbheight() - i + int(label_height/2) 
           self.box.print(label, offs_x, offs_y, self.fonttype, self.fontsize, (120,120,120))
           self.box.win[:,-1 if self.pos == 0 else 0] = 120

    def autolabels(self):  
        labcntprefs = np.array([1, 2, 3, 5, 10, 20])
        labelcnt = labcntprefs[np.where((labcntprefs < round((0.6 * self.gridheight())/self.label_height)) == True)[0][-1]] # preferred max number of labels, given the height

        unitprefs = np.array([1, 2, 5, 10]) # preferred label stepsize
        diff= (self.maxv - self.minv)/labelcnt

        while True:
           if diff< min(unitprefs):
               unitprefs  = unitprefs / 10
           elif diff> max(unitprefs):
               unitprefs = unitprefs * 10
           else:
               step = unitprefs[np.argmax(unitprefs >= diff)]
               break
        return {} if labelcnt <= 1 else ["{:0.4g}".format(i*step) for i in range(math.floor(self.minv/step), math.ceil(self.maxv/step)+1)]

    def initgrid(self, roller, color):
        roller[:,::-10] = color.grey() # vert grid 
        roller[:,::-20] = color.silver() # vert grid 
        for i in range(0, self.labelcnt, 1): 
           offs_y = self.steppix[i]
           roller[offs_y,:] = color.silver() if i % 2 == 0 else color.grey() # hor grid

    def rollgrid(self, roller, color):
        if self.idx % 20 == 0:
           roller[:,-1] = color.silver() # vert grid - last column
        elif self.idx % 10 == 0:
           roller[:,-1] = color.grey() # vert grid - last column
        else:
           for i in range(0, self.labelcnt, 1):
              offs_y = self.steppix[i]
              roller[offs_y,-1] = color.silver() if i % 2 == 0 else color.grey() # hor grid
        self.idx += 1

    def getdef(self):
        return self.minv, self.maxv, self.labelstepcnt, self.steppix, self.gridheight(), self.gridmargin()

    def flush(self):
        self.box.flush()

############################################################################
# Data graph
############################################################################
class Graph(object):

    def __init__(self, name, leftscale, rightscale, box, gfontsize = 0.4, dfontsize = 0.35, fonttype = 2):
        self.box = box
        self.gfontsize = gfontsize
        self.dfontsize = dfontsize
        self.fonttype = fonttype
        self.name = name
        self.leftscale = leftscale
        self.rightscale = rightscale
        self.datavars = {}
        self.leftvars = {}
        self.rightvars = {}
        self.skipvars = {}

        self.box.forcewin()

        self.color = util.Colors()

        self.basetime = None
        self.basepix = 0
        self.lastlapsed = 0

        self.leftscale.initgrid(self.box.win, self.color) # paint grid using left scale properties

    def flushglabels(self):
       offset_xl = 2
       offset_xr = 0
       offset_y = 0

       for (k, v) in {**self.leftvars}.items():
          (label_width, label_height), baseline = cv2.getTextSize(k, self.fonttype, self.gfontsize, 1)
          if (offset_xl + label_width) > self.box.sbwidth(): # don't paint outside the box
              break
          self.box.print(k, offset_xl, offset_y + label_height, self.fonttype, self.gfontsize,
              v.color if v is not None else 0, tocanvas = True)
          offset_xl += label_width + 2

       offset_xr = self.box.sbwidth() - 2
       for (k, v) in {**self.rightvars}.items():
          (label_width, label_height), baseline = cv2.getTextSize(k, self.fonttype, self.gfontsize, 1)
          if (offset_xr - label_width) < offset_xl: # don't paint over leftvars
              break
          self.box.print(k, offset_xr - label_width, offset_y + label_height, self.fonttype, self.gfontsize,
              v.color if v is not None else 0, tocanvas = True)
          offset_xr -= (label_width + 2)
    
    def flushdlabels(self):
       width = 0
       height = 0

       for (k, v) in {**self.datavars}.values():
           (label_width, label_height), baseline = cv2.getTextSize(k, self.fonttype, self.dfontsize, 1)
           width = max(width, label_width)
           height = max(height, label_height)

       offs_y = 3 * height

       for (k, v) in {**self.datavars}.values():
           if (height + offs_y) >= self.box.sbheight(): # don't paint outside the box
               break
           self.box.print(k, 2, offs_y, self.fonttype, self.dfontsize, (120,120,120), tocanvas = True)
           self.box.print("= {}".format(v), 5 + width, offs_y, self.fonttype, self.dfontsize, (120,120,120), tocanvas = True)
           offs_y += int(1.6 * height)

    def draw_xtime(self):
        if self.basetime is None:
            self.basetime = time.time()
        if self.basepix > 0:
           self.basepix -= 1
        lapsed = round((time.time() - self.basetime))
        if lapsed > self.lastlapsed:
           self.lastlapsed = lapsed
           if self.basepix == 0:
               label = "{:d}:{:d}:{:02d}".format(lapsed // 3600, lapsed // 60, lapsed % 60) if lapsed > 3600 else "{:d}:{:02d}".format(lapsed // 60, lapsed % 60)
               (label_width, label_height), baseline = cv2.getTextSize(label, self.fonttype, 0.3, 1)
               self.box.print(label, self.box.sbwidth() - label_width, self.box.sbheight() - 2, self.fonttype, 0.3, (120,120,120))
               self.basepix = int(label_width * 1.4)

    def gupdate(self, msg, scale, vars): 
        for (k, v)  in msg.items():
            if not k in vars: # we haven't see this var before
                color = self.color.get()
                if color is None: # we ran out of colors
                    if not k in self.skipvars: # if we are not skipping this var already, we will now
                        print("Too many graph variables in {} - skipping {}".format(self.name, k), file=sys.stderr)
                        self.skipvars[k] = "" # add var to skip list
                    continue
                vars[k] = GraphVar(k, scale, color)
        for (k, v) in reversed(msg.items()): # reversed, draw the first vars last so they are on top
            if k in vars:
                vars[k].update(self.box.win, [v] if np.isscalar(v) else v)

    def dupdate(self, msg):
        for (k, v)  in msg.items():
           self.datavars[k] = (k, "{: .2f}".format(v)) # set ( and format ) data var value

    def rollgraph(self): # use np.roll for efficient graph updates
        self.box.win = np.roll(self.box.win, -1, axis=1)
        self.box.win[:,-1] = self.color.white()
        self.leftscale.rollgrid(self.box.win, self.color)
        self.draw_xtime()

    def update(self, lmsg, rmsg, dmsg): # process new message ( = new graph and data values )
        self.gupdate(lmsg, self.leftscale, self.leftvars)
        self.gupdate(rmsg, self.rightscale, self.rightvars)
        self.dupdate(dmsg)
        self.rollgraph()

    def flush(self):
        self.leftscale.flush()
        self.rightscale.flush()
        self.box.flush()
        self.flushglabels()
        self.flushdlabels()

############################################################################
# Graph Var
############################################################################
class GraphVar(object):

    def __init__(self, name, scale, color):
        self.name = name
        self.color = color
        self.scale = scale
        self.prev_vlist = None

        self.minv, self.maxv, self.labelstepcnt, self.steppix, self.gridheight, self.gridmargin = scale.getdef()

    def num_to_range(self, num, inMin, inMax, outMin, outMax):
        return int(outMin + (float(num - inMin) / float(inMax - inMin) * (outMax - outMin)))

    def update(self, roller, vlist):
        if self.prev_vlist is None:
           self.prev_vlist = vlist.copy()
           for i in range(0, len(vlist)):
              self.prev_vlist[i] = None
        for i in range(0, len(vlist)):
           v = vlist[i]
           if v < self.minv or v > self.maxv:
               continue
           vn = self.num_to_range(v, self.minv, self.maxv, self.gridheight, 0) + self.gridmargin
           pn = self.prev_vlist[i]
           if self.prev_vlist[i] is not None:
               roller[min(vn, pn): max(vn, pn)+1, -1] = self.color # smoothen graph by connecting prev and current value
           self.prev_vlist[i] = vn

############################################################################
# Data panel ( = scale + graph + right )
############################################################################
class Panel(object):

    def __init__(self, name, canvas, ldef, rdef, box, scalewidth=36):
        self.box = box
        self.canvas = canvas
        self.leftscalewidth = scalewidth # if bool(ldef) is not False else 0 # updated - let's always have left scale
        self.rightscalewidth = scalewidth # if bool(rdef) is not False else 0 # updated - let's always have right scale
        self.leftscale = Scale(ldef, self.leftscalebox(box), pos = 0)
        self.rightscale = Scale(rdef, self.rightscalebox(box), pos = 1)
        self.graph = Graph(name, self.leftscale, self.rightscale, self.graphbox(box))

    def leftscalebox(self, box):
        return util.Box(self.canvas, None, box.sbxoffs(), box.sbyoffs(), self.leftscalewidth, box.sbheight(), topbotmargin = 1, fill = 240) # 200)

    def rightscalebox(self, box):
        return util.Box(self.canvas, None, box.sbxoffs() + box.sbwidth() - self.rightscalewidth,
            box.sbyoffs(),self.rightscalewidth, box.sbheight(), topbotmargin = 1, fill = 240) # 200)

    def graphbox(self, box):
        return util.Box(self.canvas, None, box.sbxoffs() + self.leftscale.box.width, box.sbyoffs(),
            box.sbwidth() - (self.leftscale.box.width+self.rightscale.box.width), box.sbheight(),
            topbotmargin = 1)

    def update(self, lmsg, rmsg, dmsg): 
        self.graph.update(lmsg, rmsg, dmsg)

    def flush(self): 
        self.box.flush()
        self.graph.flush()

############################################################################
# Manage Set of graphs
############################################################################
class Panels(object):

    def __init__(self, canvas, box, cols = 2, minrowheight = 64):
        self.box    = box
        self.canvas = canvas
        self.panels = {}
        self.ldefs = {}
        self.rdefs = {}
        self.cols  = cols
        self.rows  = 0
        self.blocked = {}
        self.minrowheight = minrowheight

    def update(self, name, message):

        if self.cols == 0:
            return

        if name in self.blocked:
            return

        try:
            ldef, lmsg, rdef, rmsg, dmsg = message
        except:
            print("Graph data error for {} - check format".format(name), file=sys.stderr)

        if name not in self.panels and not name in self.blocked:
            if (len(self.panels.keys()) == (self.rows * self.cols)) and math.floor(self.box.sbheight() / (self.rows+1)) < self.minrowheight:
                print("Cannot fit graph - skipping: {}".format(name), file=sys.stderr)
                self.blocked[name] = True
            else:
                self.ldefs[name] = ldef
                self.rdefs[name] = rdef
                self.redraw(name)

        if name in self.panels and not name in self.blocked:
            self.panels[name].update(lmsg, rmsg, dmsg)

    def redraw(self, name):
        self.box.wipe()
        panelnames  = sorted(list(self.panels.keys()) + ([name]))
        self.panels = {}
        self.rows = math.ceil(len(panelnames) / self.cols)
        while True:
            panelheight = math.floor(self.box.sbheight() / self.rows)
            if panelheight < self.minrowheight and self.rows > 0:
                self.rows -= 1
                continue
            break
        for row in range(0, self.rows):
            rowbox = util.Box(None, None, self.box.sbxoffs(), self.box.sbyoffs() + row * panelheight, self.box.sbwidth(), panelheight,
            topbotmargin = 0, sidemargin = 0)
            w = math.floor(rowbox.sbwidth()/self.cols)
            h = rowbox.sbheight()
            for col in range(0, self.cols):
                idx = row * self.cols + col % self.cols
                if idx < len(panelnames):
                   name = panelnames[idx]
                   box = util.Box(self.canvas, name, rowbox.sbxoffs() + col * w, rowbox.sbyoffs(), w, h, border = True)
                   self.panels[name] = Panel(name, self.canvas, self.ldefs[name], self.rdefs[name], box)

    def count(self): 
        return len(self.panels)

    def flush(self): 
        for name in self.panels.keys():
           self.panels[name].flush()
