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

class GameMode(Mode):
    shuttle_name = 'shuttle.png'
    debris_name  = 'debris.png'
    left_button  = 1
    right_button = 3
    def __init__(self,parent):
        self.parent = parent
        #try adding a box in the middle of the screen for fun
        self.items = []
        for name,pos in ((self.shuttle_name,self.parent.absolute.size*0.4),
                         (self.debris_name,self.parent.absolute.size*Point(0.3,0.3)),
                         (self.debris_name,self.parent.absolute.size*Point(0.3,0.6)),
                         (self.debris_name,self.parent.absolute.size*Point(0.6,0.3))):
            obj = parent.atlas.SubimageSprite(name)
            self.items.append(actors.DynamicBox(self.parent.physics,
                                                bl = pos,
                                                tr = pos + obj.size,
                                                tc = parent.atlas.TextureSpriteCoords(name)))
        self.parent.AddPlayer(Point(0.45,0.35), True)
        self.parent.AddPlayer(Point(0.60,0.25))

    def MouseButtonDown(self,pos,button):
        print 'mouse button down',pos,button
        if self.parent.selected_player != None:
            if button == self.left_button and self.parent.selected_player.IsGrabbed():
                self.parent.selected_player.PreparePush()

    def MouseButtonUp(self,pos,button):
        #print 'mouse button up',pos,button
        if self.parent.selected_player != None:
            if button == self.left_button:
                if self.parent.selected_player.IsGrabbed():
                    self.parent.selected_player.Push()
                else:
                    obj = self.parent.physics.GetObjectAtPoint(pos)
                    if obj and obj is not self.parent.selected_player:
                        self.parent.selected_player.Grab(obj,pos)
            elif button == self.right_button:
                self.parent.selected_player.Ungrab()

    def KeyUp(self,key):
        if key == pygame.K_TAB:
            self.parent.NextPlayer()
        

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
