from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import Box2D as box2d
import actors
import modes
import random

class fwContactPoint:
    """
    Structure holding the necessary information for a contact point.
    All of the information is copied from the contact listener callbacks.
    """
    shape1 = None
    shape2 = None
    normal = None
    position = None
    velocity = None
    id  = None
    state = 0

class MyContactListener(box2d.b2ContactListener):
    physics = None
    def __init__(self): 
        super(MyContactListener, self).__init__() 
    def Add(self, point):
        """Handle add point"""
        if not self.physics:
            return
        cp          = fwContactPoint()
        cp.shape1   = point.shape1
        cp.shape2   = point.shape2
        cp.position = point.position.copy()
        cp.normal   = point.normal.copy()
        cp.id       = point.id
        self.physics.contacts.append(cp)
        
    def Persist(self, point):
        """Handle persist point"""

        pass
    def Remove(self, point):
        """Handle remove point"""
        pass
    def Result(self, point):
        """Handle results"""
        pass

class MyContactFilter(box2d.b2ContactFilter):
    def __init__(self):
        self.thrown = None
        super(MyContactFilter,self).__init__()
    def ShouldCollide(self, shape1, shape2):
        # Implements the default behavior of b2ContactFilter in Python
        if self.thrown:
            #Fire extinguisher doesn't collide with the player who threw it for a while
            if globals.time > self.thrown[1]:
                #expired
                self.thrown = None
            elif isinstance(shape1.userData,actors.FloatingFireExtinguisher) and shape2.userData is self.thrown[0]:
                print 'skipped'
                return False
            elif isinstance(shape2.userData,actors.FloatingFireExtinguisher) and shape1.userData is self.thrown[0]:
                print 'skipped1'
                return False
        print 'collision!',shape1 == shape1.userData.shape#,shape2
        filter1 = shape1.filter
        filter2 = shape2.filter
        if filter1.groupIndex == filter2.groupIndex and filter1.groupIndex != 0:
            return filter1.groupIndex > 0
 
        collides = (filter1.maskBits & filter2.categoryBits) != 0 and (filter1.categoryBits & filter2.maskBits) != 0
        return collides

class Physics(object):
    scale_factor = 0.05
    def __init__(self,parent):
        self.contact_listener = MyContactListener()
        self.contact_listener.physics = self
        self.contact_filter = MyContactFilter()
        self.contact_filter.physics = self
        self.parent = parent
        self.worldAABB=box2d.b2AABB()
        self.worldAABB.lowerBound = (-100,-globals.screen.y-100)
        self.worldAABB.upperBound = (100 + self.parent.absolute.size.x*self.scale_factor,100 + self.parent.absolute.size.y*self.scale_factor + 100)
        self.gravity = (0, 0)
        self.doSleep = True
        self.world = box2d.b2World(self.worldAABB, self.gravity, self.doSleep)
        self.world.SetContactListener(self.contact_listener)
        self.world.SetContactFilter(self.contact_filter)
        self.timeStep = 1.0 / 60.0
        self.velocityIterations = 10
        self.positionIterations = 8
        self.objects = []
    
    def AddObject(self,obj):
        self.objects.append(obj)

    def Step(self):
        self.contacts = []
        self.world.Step(self.timeStep, self.velocityIterations, self.positionIterations)
        
        for obj in self.objects:
            obj.PhysUpdate()

    def GetObjectAtPoint(self,pos):
        aabb = box2d.b2AABB()
        phys_pos = pos*self.scale_factor

        aabb.lowerBound.Set(phys_pos.x-0.1,phys_pos.y-0.1)
        aabb.upperBound.Set(phys_pos.x+0.1,phys_pos.y+0.1)
        (count,shapes) = self.world.Query(aabb,10)
        for shape in shapes:
            trans = box2d.b2XForm()
            trans.SetIdentity()
            p = phys_pos - Point(*shape.GetBody().position)
            if shape.TestPoint(trans,tuple(p)):
                return shape.userData
        return None

class GameView(ui.RootElement):
    def __init__(self):
        self.selected_player = None
        self.floating_objects = []
        self.atlas = globals.atlas = drawing.texture.TextureAtlas('tiles_atlas_0.png','tiles_atlas.txt')
        self.game_over = False
        #pygame.mixer.music.load('music.ogg')
        #self.music_playing = False
        super(GameView,self).__init__(Point(0,0),globals.screen)
        self.physics = Physics(self)
        #skip titles for development of the main game
        #self.mode = modes.Titles(self)
        self.players = []
        self.mode = modes.GameMode(self)
        self.paused = False
        self.StartMusic()
        self.walls = [actors.StaticBox(self.physics,
                                       bl = Point(0,0),
                                       tr = Point(1,self.absolute.size.y)),
                      actors.StaticBox(self.physics,
                                       bl = Point(self.absolute.size.x,0),
                                       tr = Point(self.absolute.size.x+1,self.absolute.size.y)),
                      actors.StaticBox(self.physics,
                                       bl = Point(0,self.absolute.size.y),
                                       tr = Point(self.absolute.size.x,self.absolute.size.y+1)),
                      actors.StaticBox(self.physics,
                                       bl = Point(0,0),
                                       tr = Point(self.absolute.size.x,1)),
                      ]

    def StartMusic(self):
        pass
        #pygame.mixer.music.play(-1)
        #self.music_playing = True

    def Draw(self):
        #drawing.DrawAll(globals.backdrop_buffer,self.atlas.texture.texture)
        drawing.ResetState()
        #drawing.Translate(-self.viewpos.pos.x,-self.viewpos.pos.y,0)
        drawing.DrawAll(globals.quad_buffer,self.atlas.texture.texture)
        drawing.DrawAll(globals.nonstatic_text_buffer,globals.text_manager.atlas.texture.texture)
        
    def Update(self,t):
        if self.mode:
            self.mode.Update(t)

        if self.game_over:
            return

        #self.viewpos.Update(t)

        if not self.paused:
            self.physics.Step()
            
        self.t = t

    def GameOver(self):
        self.game_over = True
        self.mode = modes.GameOver(self)
        
    def KeyDown(self,key):
        self.mode.KeyDown(key)

    def KeyUp(self,key):
        if key == pygame.K_DELETE:
            if self.music_playing:
                self.music_playing = False
                pygame.mixer.music.set_volume(0)
            else:
                self.music_playing = True
                pygame.mixer.music.set_volume(1)
        self.mode.KeyUp(key)

    def AddPlayer(self,pos,fire_extinguisher = False):
        bl = self.absolute.size*pos
        player = actors.Player(self.physics,bl)
        if fire_extinguisher:
            player.EquipFireExtinguisher()
        self.players.append(player)
        if len(self.players) == 1:
            player.Select()
            self.selected_player = player

    def AddFireExtinguisher(self,fe):
        self.floating_objects.append(fe)
        #print 'a',pos,direction

    def MouseMotion(self,pos,rel,handled):
        #print 'mouse',pos
        #if self.selected_player != None:
        #    self.selected_player.MouseMotion()
        self.mode.MouseMotion(pos,rel)
        return super(GameView,self).MouseMotion(pos,rel,handled)

    def MouseButtonDown(self,pos,button):
        #print 'mouse button down',pos,button
        self.mode.MouseButtonDown(pos,button)
        return super(GameView,self).MouseButtonDown(pos,button)

    def MouseButtonUp(self,pos,button):
        #print 'mouse button up',pos,button
        self.mode.MouseButtonUp(pos,button)
        return super(GameView,self).MouseButtonUp(pos,button)

    def NextPlayer(self):
        if self.selected_player == None:
            if len(self.players) != 0:
                self.selected_player = self.players[0]
        else:
            current_index = self.players.index(self.selected_player)
            self.selected_player.Unselect()
            self.selected_player = self.players[(current_index + 1)%len(self.players)]
            self.selected_player.Select()
