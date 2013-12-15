from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import Box2D as box2d
import actors
import modes
import random

class Viewpos(object):
    follow_threshold = 0
    max_away = 250
    def __init__(self,point):
        self.pos = point
        self.NoTarget()
        self.follow = None
        self.follow_locked = False
        self.t = 0

    def NoTarget(self):
        self.target        = None
        self.target_change = None
        self.start_point   = None
        self.target_time   = None
        self.start_time    = None

    def Set(self,point):
        self.pos = point
        print self.pos
        #self.NoTarget()

    def SetTarget(self,point,t,rate=2,callback = None):
        #Don't fuck with the view if the player is trying to control it
        rate /= 4.0
        self.follow        = None
        self.follow_start  = 0
        self.follow_locked = False
        self.target        = point
        self.target_change = self.target - self.pos
        self.start_point   = self.pos
        self.start_time    = t
        self.duration      = self.target_change.length()/rate
        self.callback      = callback
        if self.duration < 200:
            self.duration  = 200
        self.target_time   = self.start_time + self.duration

    def Follow(self,t,actor):
        """
        Follow the given actor around.
        """
        self.follow        = actor
        self.follow_start  = t
        self.follow_locked = False

    def HasTarget(self):
        return self.target != None

    def Get(self):
        return self.pos

    def Skip(self):
        self.pos = self.target
        self.NoTarget()
        if self.callback:
            self.callback(self.t)
            self.callback = None

    def Update(self,t):
        try:
            return self.update(t)
        finally:
            self.pos = self.pos.to_int()

    def update(self,t):
        self.t = t
        if self.follow:
            if self.follow_locked:
                self.pos = self.follow.GetPos() - globals.screen*0.5
            else:
                #We haven't locked onto it yet, so move closer, and lock on if it's below the threshold
                fpos = self.follow.GetPos()*globals.tile_dimensions
                if not fpos:
                    return
                target = fpos - globals.screen*0.5
                diff = target - self.pos
                if diff.SquareLength() < self.follow_threshold:
                    self.pos = target
                    self.follow_locked = True
                else:
                    distance = diff.length()
                    if distance > self.max_away:
                        self.pos += diff.unit_vector()*(distance*1.02-self.max_away)
                        newdiff = target - self.pos
                    else:
                        self.pos += diff*0.02
                
        elif self.target:
            if t >= self.target_time:
                self.pos = self.target
                self.NoTarget()
                if self.callback:
                    self.callback(t)
                    self.callback = None
            elif t < self.start_time: #I don't think we should get this
                return
            else:
                partial = float(t-self.start_time)/self.duration
                partial = partial*partial*(3 - 2*partial) #smoothstep
                self.pos = (self.start_point + (self.target_change*partial)).to_int()

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
        #globals.sounds.thud.play()
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
        self.pushed = None
        self.collide = False
        super(MyContactFilter,self).__init__()
    def ShouldCollide(self, shape1, shape2):
        #print 'cf',shape1
        #print 'cf1',shape2
        # Implements the default behavior of b2ContactFilter in Python
        if self.collide:
            return True
        if isinstance(shape1.userData,actors.SaveBox):
            obj = shape2.userData
            if isinstance(obj,actors.FireExtinguisher):
                obj = obj.parent
            if isinstance(obj,actors.Player):
                shape1.userData.SaveAction(obj)
        elif isinstance(shape2.userData,actors.SaveBox):
            obj = shape1.userData
            if isinstance(obj,actors.FireExtinguisher):
                obj = obj.parent
            if isinstance(obj,actors.Player):
                shape2.userData.SaveAction(obj)
            
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
        if self.pushed:
            print self.pushed,globals.time
            if globals.time > self.pushed[2]:
                self.pushed = None
            elif shape1.userData is self.pushed[0] and shape2.userData is self.pushed[1] or \
                    shape1.userData is self.pushed[1] and shape2.userData is self.pushed[0]:
                print 'skipped2'
                return False
        #print 'collision!',shape1 == shape1.userData.shape#,shape2
        filter1 = shape1.filter
        filter2 = shape2.filter
        #print filter1.groupIndex,filter2.groupIndex
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
        self.max_zoom = 2.0
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
        self.dragging = None
        self.max_zoom = 2.0
        self.min_zoom = 0.5
        self.backdrop_texture = drawing.texture.Texture('starfield.png')
        #pygame.mixer.music.load('music.ogg')
        #self.music_playing = False
        super(GameView,self).__init__(Point(0,0),Point(2000,2000))
        tiles = (self.absolute.size.to_float())/self.backdrop_texture.size
        self.backdrop  = drawing.Quad(globals.backdrop_buffer,tc = numpy.array([(0,0),(0,tiles.y),(tiles.x,tiles.y),(tiles.x,0)]))
        self.backdrop.SetVertices(Point(0,0),
                                  self.absolute.size,
                                  drawing.constants.DrawLevels.grid)
        self.physics = Physics(self)
        #skip titles for development of the main game
        #self.mode = modes.Titles(self)
        self.players = []
        self.mode = modes.LevelOne(self)
        self.paused = False
        self.StartMusic()
        self.zoom = 1
        self.viewpos = Viewpos(Point(670,870))
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
        #drawing.ResetState()
        #drawing.Scale(self.zoom,self.zoom,1)
        #drawing.Translate(-self.viewpos.pos.x*1,-self.viewpos.pos.y*1,0)
        #drawing.DrawAll(globals.backdrop_buffer,self.backdrop_texture.texture)
        drawing.ResetState()
        drawing.Scale(self.zoom,self.zoom,1)
        drawing.Translate(-self.viewpos.pos.x,-self.viewpos.pos.y,0)
        drawing.DrawAll(globals.backdrop_buffer,self.backdrop_texture.texture)
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

    def AddPlayer(self,pos,fire_extinguisher = False,angle=0):
        bl = self.absolute.size*pos
        player = actors.Player(self.physics,bl,angle)
        if fire_extinguisher:
            player.EquipFireExtinguisher()
        self.players.append(player)
        if len(self.players) == 1:
            player.Select()
            self.selected_player = player

    def RemovePlayer(self,player):
        self.players = [p for p in self.players if p is not player]
        player.Destroy()
        if self.selected_player is player:
            self.selected_player = None
            self.NextPlayer()
        return

    def AddFireExtinguisher(self,fe):
        self.floating_objects.append(fe)
        #print 'a',pos,direction

    def MouseMotion(self,pos,rel,handled):
        #print 'mouse',pos
        #if self.selected_player != None:
        #    self.selected_player.MouseMotion()
        screen_pos = self.viewpos.Get() + (pos/self.zoom)
        screen_rel = rel/self.zoom
        self.mouse_pos = pos
        if self.dragging:
            self.viewpos.Set(self.dragging - (pos/self.zoom))
            self.ClampViewpos()
            self.dragging = self.viewpos.Get() + (pos/self.zoom)
        else:
            self.mode.MouseMotion(screen_pos,screen_rel)
        return super(GameView,self).MouseMotion(pos,screen_rel,handled)

    def MouseButtonDown(self,pos,button):
        #print 'mouse button down',pos,button
        screen_pos = self.viewpos.Get() + (pos/self.zoom)
        if button == 2:
            self.dragging = screen_pos
        else:
            self.mode.MouseButtonDown(screen_pos,button)
        return super(GameView,self).MouseButtonDown(pos,button)

    def MouseButtonUp(self,pos,button):
        #print 'mouse button up',pos,button
        screen_pos = self.viewpos.Get() + (pos/self.zoom)
        if button == 2:
            self.dragging = None
        elif button == 4 and not self.dragging:
            self.AdjustZoom(-0.5,pos)
        elif button == 5 and not self.dragging:
            self.AdjustZoom(+0.5,pos)
        else:
            self.mode.MouseButtonUp(screen_pos,button)
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

    def AdjustZoom(self,amount,pos):
        pos_coords = self.viewpos.Get() + (pos/self.zoom)
        oldzoom = self.zoom
        self.zoom -= (amount/10.0)
        if self.zoom < self.min_zoom:
            self.zoom = self.min_zoom
        if self.zoom > self.max_zoom:
            self.zoom = self.max_zoom
        print self.zoom
        
        #if we've zoomed so far out that we can see an edge of the screen, fix that
        top_left= Point(0,globals.screen.y/self.zoom)
        top_right = globals.screen/self.zoom
        bottom_right = Point(globals.screen.x/self.zoom,0)

        new_viewpos = self.viewpos.Get()
        if new_viewpos.y < 0:
            new_viewpos.y = 0

        if new_viewpos.x < 0:
            new_viewpos.x = 0
        
        #now the top left
        new_top_right = new_viewpos+top_right
        if new_top_right.y  > self.absolute.size.y:
            new_viewpos.y -= (new_top_right.y - self.absolute.size.y)

        if new_top_right.x > self.absolute.size.x:
            new_viewpos.x -= (new_top_right.x - self.absolute.size.x)
        print 'a',new_viewpos
        
        try:
            if new_viewpos.y < 0:
                raise ValueError

            if new_viewpos.x < 0:
                raise ValueError

            #now the top left
            new_top_right = new_viewpos+top_right
            if new_top_right.y  > self.absolute.size.y:
                raise ValueError

            if new_top_right.x > self.absolute.size.x:
                raise ValueError

        except ValueError:
            #abort! This is a bit shit but whatever
            self.zoom = oldzoom
            return

        new_pos_coords = self.viewpos.Get() + pos/self.zoom
        self.viewpos.Set(self.viewpos.Get() + (pos_coords - new_pos_coords))
        self.ClampViewpos()

    def ClampViewpos(self):
        if self.viewpos.pos.x < 0:
            self.viewpos.pos.x = 0
        if self.viewpos.pos.y < 0:
            self.viewpos.pos.y = 0
        if self.viewpos.pos.x > (self.absolute.size.x - (globals.screen.x/self.zoom)):
            self.viewpos.pos.x = (self.absolute.size.x - (globals.screen.x/self.zoom))
        if self.viewpos.pos.y > (self.absolute.size.y - (globals.screen.y/self.zoom)):
            self.viewpos.pos.y = (self.absolute.size.y - (globals.screen.y/self.zoom))
