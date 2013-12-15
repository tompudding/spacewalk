from OpenGL.GL import *
import random
import numpy
import cmath
import math
import pygame

import ui
import globals
import drawing
import os
import copy
import actors

from globals.types import Point
import sys

class Mode(object):
    """ Abstract base class to represent game modes """
    def __init__(self,parent):
        self.parent = parent
    
    def KeyDown(self,key):
        pass
    
    def KeyUp(self,key):
        pass

    def MouseMotion(self,pos,rel):
        pass

    def MouseButtonDown(self,pos,button):
        return

    def MouseButtonUp(self,pos,button):
        return

    def Update(self,t):
        pass

class TitleStages(object):
    STARTED  = 0
    COMPLETE = 1
    TEXT     = 2
    SCROLL   = 3
    WAIT     = 4

class Titles(Mode):
    blurb = "SPACEWALK"
    def __init__(self,parent):
        self.parent          = parent
        self.start           = pygame.time.get_ticks()
        self.stage           = TitleStages.STARTED
        self.handlers        = {TitleStages.STARTED  : self.Startup,
                                TitleStages.COMPLETE : self.Complete}
        bl = self.parent.GetRelative(Point(0,0))
        tr = bl + self.parent.GetRelative(globals.screen)
        self.blurb_text = ui.TextBox(parent = self.parent,
                                     bl     = bl         ,
                                     tr     = tr         ,
                                     text   = self.blurb ,
                                     textType = drawing.texture.TextTypes.GRID_RELATIVE,
                                     colour = (1,1,1,1),
                                     scale  = 4)
        self.backdrop        = ui.Box(parent = globals.screen_root,
                                      pos    = Point(0,0),
                                      tr     = Point(1,1),
                                      colour = (0,0,0,0))
        self.backdrop.Enable()

    def KeyDown(self,key):
        self.stage = TitleStages.COMPLETE

    def Update(self,t):        
        self.elapsed = t - self.start
        self.stage = self.handlers[self.stage](t)

    def Complete(self,t):
        self.backdrop.Delete()
        self.blurb_text.Delete()
        self.parent.mode = GameOver(self.parent)

    def Startup(self,t):
        return TitleStages.STARTED

class LevelOne(Mode):
    shuttle_name = 'shuttle.png'
    debris_name  = 'debris.png'
    save_name  = 'debris_save.png'
    def __init__(self,parent):
        self.parent = parent
        
        self.items = []
        self.power_box = ui.PowerBar(globals.screen_root,
                                     pos = Point(0.45,0.05),
                                     tr = Point(0.55,0.1),
                                     level = 0.6,
                                     bar_colours = (drawing.constants.colours.green,
                                                    drawing.constants.colours.yellow,
                                                    drawing.constants.colours.red),
                                     border_colour = drawing.constants.colours.white)
        self.fe_level = ui.PowerBar(globals.screen_root,
                                    pos = Point(0.8,0.05),
                                    tr = Point(0.9,0.1),
                                    level = 1.0,
                                    bar_colours = (drawing.constants.colours.red,
                                                    drawing.constants.colours.yellow,
                                                    drawing.constants.colours.green),
                                    border_colour = drawing.constants.colours.white)
        self.fe_level.title = ui.TextBox(parent = self.fe_level,
                                         bl     = Point(-0.03,1.0),
                                         tr     = Point(1.1,1.5)    ,
                                         text   = 'Foam Level',
                                         scale  = 3)
        self.power_box.Disable()
        self.fe_level.Disable()
        self.help_box = ui.Box(globals.screen_root,
                               pos = Point(0.6,0.75),
                               tr = Point(1,1),
                               colour = drawing.constants.colours.black)
        self.help_box.title = ui.TextBox(parent = self.help_box,
                                         bl = Point(0.22,0.8),
                                         tr = Point(1,1),
                                         text ='Controls',
                                         scale = 4)
        p = 0.7
        self.help_box.help = []
        height = 0.1
        for i,(key,action) in enumerate((('left click','grab/push/spray'),
                                         ('left hold(while grabbed)','push'),
                                         ('right click','cancel/detach'),
                                         ('right hold(with item)','throw'),
                                         ('h','toggle help'),
                                         ('middle drag','move screen'),
                                         ('middle scroll','zoom'),
                                         ('space','reset'))):
            self.help_box.help.append(ui.TextBox(parent = self.help_box,
                                                 bl = Point(-0.2,p),
                                                 tr = Point(1.2,p+height),
                                                 text = ('%30s %s' % (key,action)),
                                                 scale = 3))
            p -= height
            
        self.help_box.Enable()
        #for name,pos in ((self.shuttle_name,globals.screen*2),
                         #(self.debris_name,globals.screen*Point(0.3,0.3)),
                         #(self.debris_name,globals.screen*Point(0.3,0.6)),
        #                 (self.debris_name,globals.screen*Point(0.6,0.3))):
        #    obj = parent.atlas.SubimageSprite(name)
        #    self.items.append(actors.DynamicBox(self.parent.physics,
        #                                        bl = pos,
        #                                        tr = pos + obj.size,
        #                                        tc = parent.atlas.TextureSpriteCoords(name)))
        self.ResetSceneOne()

    def ResetCurrentScene(self):
        self.current_scene()

    def ResetSceneOne(self):
        self.current_scene = self.ResetSceneOne
        for player in self.parent.players:
            player.Destroy()
        for item in self.items:
            item.Destroy()
        self.items = []
        self.parent.players = []
        
        pos = self.parent.absolute.size*Point(0.48,0.48)
        obj = self.parent.atlas.SubimageSprite(self.debris_name)
        self.items.append(actors.Debris(self.parent.physics,
                                            bl = pos,
                                            tr = pos + obj.size))

        pos = self.parent.absolute.size*Point(0.48,0.55)
        obj = self.parent.atlas.SubimageSprite(self.debris_name)
        self.items.append(actors.SaveBox(self.parent.physics,
                                         bl = pos,
                                         tr = pos + obj.size,
                                         cb = self.ResetSceneTwo))
        self.parent.AddPlayer(Point(0.482,0.47))
        #work out where it can grab it
        item = self.items[0]
        grab_pos = item.bl + (item.tr - item.bl)*Point(0.5,0.05)
        self.parent.selected_player.Grab(item,grab_pos)
        #Start the whole thing spinning
        item.body.ApplyTorque(80)
        
        i = 2
        item.body.ApplyImpulse((-i,0),item.body.position)
        self.parent.selected_player.body.ApplyImpulse((i,0),self.parent.selected_player.body.position)
        #self.parent.AddPlayer(Point(0.60,0.25)*(globals.screen.to_float()/self.parent.absolute.size))

    def ResetSceneTwo(self):
        self.current_scene = self.ResetSceneTwo
        for player in self.parent.players:
            player.Destroy()
        for item in self.items:
            item.Destroy()
        self.items = []
        self.parent.players = []

        pos = self.parent.absolute.size*Point(0.48,0.55)
        obj = self.parent.atlas.SubimageSprite(self.save_name)
        self.items.append(actors.SaveBox(self.parent.physics,
                                         bl = pos,
                                         tr = pos + obj.size,
                                         cb = None))
        pos = self.parent.absolute.size*Point(0.78,0.89)
        obj = self.parent.atlas.SubimageSprite(self.save_name)
        self.items.append(actors.SaveBox(self.parent.physics,
                                         bl = pos,
                                         tr = pos + obj.size,
                                         cb = self.ResetSceneThree))
        self.parent.AddPlayer(Point(0.48,0.57))
        self.parent.viewpos.pos = Point(687,1055)
        
        #self.parent.AddPlayer(Point(0.60,0.25)*(globals.screen.to_float()/self.parent.absolute.size))

    def ResetSceneThree(self):
        pass

    def MouseMotion(self,pos,rel):
        if self.parent.selected_player:
            self.parent.selected_player.MouseMotion(pos,rel)

    def MouseButtonDown(self,pos,button):
        #print 'mouse button down',pos,button
        if self.parent.selected_player != None:
            self.parent.selected_player.MouseButtonDown(pos,button)

    def MouseButtonUp(self,pos,button):
        #print 'mouse button up',pos,button
        if self.parent.selected_player != None:
            self.parent.selected_player.MouseButtonUp(pos,button)

    def KeyUp(self,key):
        if key == pygame.K_TAB:
            self.parent.NextPlayer()
        elif key == pygame.K_SPACE:
            self.ResetCurrentScene()
        elif key == pygame.K_h:
            if self.help_box.enabled:
                self.help_box.Disable()
            else:
                self.help_box.Enable()
        elif key == pygame.K_s:
            if self.current_scene == self.ResetSceneOne:
                self.ResetSceneTwo()

class GameOver(Mode):
    blurb = "GAME OVER"
    def __init__(self,parent):
        self.parent          = parent
        self.blurb           = self.blurb
        self.blurb_text      = None
        self.handlers        = {TitleStages.TEXT    : self.TextDraw,
                                TitleStages.SCROLL  : self.Wait,
                                TitleStages.WAIT    : self.Wait}
        self.backdrop        = ui.Box(parent = globals.screen_root,
                                      pos    = Point(0,0),
                                      tr     = Point(1,1),
                                      colour = (0,0,0,0.6))
        
        bl = self.parent.GetRelative(Point(0,0))
        tr = bl + self.parent.GetRelative(globals.screen)
        self.blurb_text = ui.TextBox(parent = globals.screen_root,
                                     bl     = bl         ,
                                     tr     = tr         ,
                                     text   = self.blurb ,
                                     textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                     scale  = 3)

        self.start = None
        self.blurb_text.EnableChars(0)
        self.stage = TitleStages.TEXT
        self.played_sound = False
        self.skipped_text = False
        self.letter_duration = 20
        self.continued = False
        #pygame.mixer.music.load('end_fail.mp3')
        #pygame.mixer.music.play(-1)

    def Update(self,t):
        if self.start == None:
            self.start = t
        self.elapsed = t - self.start
        self.stage = self.handlers[self.stage](t)
        if self.stage == TitleStages.COMPLETE:
            raise sys.exit('Come again soon!')

    def Wait(self,t):
        return self.stage

    def SkipText(self):
        if self.blurb_text:
            self.skipped_text = True
            self.blurb_text.EnableChars()

    def TextDraw(self,t):
        if not self.skipped_text:
            if self.elapsed < (len(self.blurb_text.text)*self.letter_duration) + 2000:
                num_enabled = int(self.elapsed/self.letter_duration)
                self.blurb_text.EnableChars(num_enabled)
            else:
                self.skipped_text = True
        elif self.continued:
            return TitleStages.COMPLETE
        return TitleStages.TEXT

    def KeyDown(self,key):
        #if key in [13,27,32]: #return, escape, space
        if not self.skipped_text:
            self.SkipText()
        else:
            self.continued = True

    def MouseButtonDown(self,pos,button):
        self.KeyDown(0)
        return False,False
