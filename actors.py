import Box2D as box2d
from globals.types import Point
import globals
import ui
import drawing
import cmath
import math
import os
import game_view
import modes
import random

class StaticBox(object):
    isBullet = False
    mass     = 1
    filter_group = None
    static   = False
    health   = 500
    z_level  = 10
    def __init__(self,physics,bl,tr,tc = None,angle=0):
        #Hardcode the dirt texture since right now all static things are dirt. I know I know.
        self.dead = False
        self.tc = tc
        self.bl = bl
        self.tr = tr
        if tc != None:
            self.InitPolygons(tc)
            self.visible = True
        else:
            self.visible = False
        self.physics = physics
        self.bodydef = box2d.b2BodyDef()
        #This is inefficient, but it doesn't want to grab properly otherwise. Shitty hack but whatever
        self.bodydef.allowSleep = False
        self.midpoint = (tr - bl)*0.5*physics.scale_factor
        self.bodydef.position = tuple((bl*physics.scale_factor) + self.midpoint)
        self.bodydef.angle = angle
        self.shape = self.CreateShape(self.midpoint)
        if not self.static:
            self.shape.userData = self
        if self.filter_group != None:
            self.shape.filter.groupIndex = self.filter_group
        self.bodydef.isBullet = self.isBullet
        self.body = physics.world.CreateBody(self.bodydef)
        self.shape.density = self.mass
        self.shape.friction = 0.7
        self.shapeI = self.body.CreateShape(self.shape)
        self.child_joint = None
        self.parent_joint = None
        self.ExtraShapes()
        self.PhysUpdate()

    def ExtraShapes(self):
        pass

    def Destroy(self):
        if self.static:
            #Don't ever destroy static things
            return
        if self.dead:
            return
        if self.parent_joint:
            #We're attached, so get rid of that before killing us
            self.parent_joint.UnGrapple()
            self.parent_joint = None
        self.shape.ClearUserData()
        self.physics.world.DestroyBody(self.body)
        print 'destroyed body',self
        self.dead = True
        self.quad.Delete()

    def Damage(self,amount):
        #can't damage static stuff
        return

    def CreateShape(self,midpoint,pos = None):
        if self.dead:
            return
        shape = box2d.b2PolygonDef()
        if pos == None:
            shape.SetAsBox(*midpoint)
        else:
            shape.SetAsBox(midpoint[0],midpoint[1],pos.to_vec(),0)
        return shape

    def InitPolygons(self,tc):
        return

    def GetPos(self):
        if self.dead:
            return
        return Point(*self.body.position)/self.physics.scale_factor

    def GetAngle(self):
        if self.dead:
            return
        return self.body.angle

    def PhysUpdate(self):
        return


class DynamicBox(StaticBox):
    static = False
    health = 30
    vertex_permutation = (0,3,2,1)
    def __init__(self,physics,bl,tr,tc,angle=0):
        super(DynamicBox,self).__init__(physics,bl,tr,tc,angle)

        self.body.SetMassFromShapes()
        physics.AddObject(self)

    def InitPolygons(self,tc):
        if self.dead:
            return
        self.quad = drawing.Quad(globals.quad_buffer,tc = tc)

    def PhysUpdate(self):
        if self.dead:
            return
        #Just set the vertices

        for i,vertex in enumerate(self.shape.vertices):
            screen_coords = Point(*self.body.GetWorldPoint(vertex))/self.physics.scale_factor
            self.quad.vertex[self.vertex_permutation[i]] = (screen_coords.x,screen_coords.y,self.z_level)

    def Damage(self,amount):
        self.health -= amount
        if self.health < 0:
            self.Destroy()

class Debris(DynamicBox):
    texture_name = 'debris.png'
    def __init__(self,physics,bl,tr):
        self.tc = globals.atlas.TextureSpriteCoords(self.texture_name)
        super(Debris,self).__init__(physics,bl,tr,self.tc)

class SaveBox(Debris):
    texture_name = 'debris_save.png'

    def __init__(self,physics,bl,tr,cb,final=False):
        self.players_to_remove = []
        self.final = final
        if cb != None:
            #hack to make it hard to move them
            self.mass = 100
        self.cb = cb
        if self.cb == None:
            self.texture_name = 'debris_dull.png'
        self.triggered = False
        super(SaveBox,self).__init__(physics,bl,tr)

    def PhysUpdate(self):
        super(SaveBox,self).PhysUpdate()
        if self.cb != None:
            for player in self.players_to_remove:
                globals.game_view.RemovePlayer(player)
            self.players_to_remove = []
            if self.triggered:
                func = self.cb
                self.cb = None
                func()

    def SaveAction(self,player):
        print 'Saveaction!'
        if self.cb != None and self.triggered == False:
            #This gets called inside the world step, which means bad things. Defer action until later
            self.players_to_remove.append(player)
            if self.final or len(globals.game_view.players) == 1:
                self.triggered = True

class PlayerArm(object):
    z_level = 11
    def __init__(self,parent,start,end):
        self.parent = parent
        self.start_object,self.start_pos = start
        self.end_object,self.end_pos = end
        self.quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords('arm.png'))
        
    def Update(self):
        vertices = []
        for i,(obj,vertex) in enumerate(((self.start_object,self.start_pos-Point(0.1,0)),
                                         (self.start_object,self.start_pos+Point(0.1,0)),
                                         (self.end_object,self.end_pos+Point(0.1,0)),
                                         (self.end_object,self.end_pos-Point(0.1,0)))):
            screen_coords = Point(*obj.body.GetWorldPoint(vertex.to_vec()))/self.parent.physics.scale_factor
            self.quad.vertex[i] = (screen_coords.x,screen_coords.y,self.z_level)

    def SetHand(self,obj,pos):
        self.end_object = obj
        self.end_pos    = pos
        self.Update()

    def Destroy(self):
        self.quad.Delete()

class FloatingFireExtinguisher(DynamicBox):
    texture_name = 'fire_extinguisher_side.png'
    max_level = 1000
    def __init__(self,parent,fe,power,create_data = None):
        self.parent = parent
        if fe == None:
            pos,self.level = create_data
        else:
            pos = Point(*self.parent.body.GetWorldPoint(fe.base_pos.to_vec()))/self.parent.physics.scale_factor
            direction = fe.GetDirection()
            self.level = fe.level
        self.subimage  = globals.atlas.SubimageSprite(self.texture_name)
        self.texture_coords = globals.atlas.TextureSpriteCoords(self.texture_name)
        self.half_size = self.subimage.size*0.5
        self.bl        = pos + self.half_size*Point(-1,0.3)
        self.middle    = self.bl + self.half_size
        self.tr        = self.middle + self.half_size
        self.middle    = self.bl + self.half_size
        super(FloatingFireExtinguisher,self).__init__(self.parent.physics,self.bl,self.tr,self.texture_coords)
        globals.game_view.mode.fe_level.SetBarLevel(float(self.level)/self.max_level)
        #Add a force in the appropriate direction, as well as in the opposite direction on our player
        if fe != None:
            fe.SetPositions()
            thrust = power
            vector_fe = cmath.rect(thrust,direction)
            vector_guy = cmath.rect(-thrust,direction)
            bl_phys = fe.base_pos
            bl_world = self.parent.body.GetWorldPoint(bl_phys.to_vec())
            print vector_guy.real,vector_guy.imag,bl_world,self.parent.body.position
            self.parent.body.ApplyForce((vector_guy.real,vector_guy.imag),bl_world)
            self.body.SetLinearVelocity(self.parent.body.GetLinearVelocity())
            #Now let's apply the impulse to counteract that velocity we've just imparted
            momentum = -(self.parent.body.GetLinearVelocity()*self.body.GetMass())
            impulse = momentum/self.parent.body.GetMass()
            self.parent.body.ApplyImpulse(impulse,self.parent.body.position)
            self.body.ApplyForce((vector_fe.real,vector_fe.imag),bl_world)
        

class FireExtinguisher(object):
    z_level = 12
    texture_name = 'fire_extinguisher_held.png'
    min_angle = 1.5
    max_angle = (math.pi*2)-min_angle
    max_level = 1000
    def __init__(self,parent,level = None):
        self.parent = parent
        self.dead = False
        self.subimage  = globals.atlas.SubimageSprite(self.texture_name)
        self.quad      = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords(self.texture_name))
        self.half_size = self.subimage.size*0.5*self.parent.physics.scale_factor
        self.bl        = self.parent.midpoint*Point(0.3,2.4)-self.half_size
        self.middle    = self.bl + self.half_size
        self.shape     = self.parent.CreateShape(self.half_size,self.bl)
        self.shape.userData = self
        self.shapeI    = self.parent.body.CreateShape(self.shape)
        self.angle     = 0
        self.level     = self.max_level if level == None else level
        self.SetPositions()
        self.squirting = False
        self.UpdateLevel(0)

    def Squirt(self):
        self.squirting = True
        print 'squirting'

    def StopSquirting(self):
        self.squirting = False
        print 'stopped squirting'

    def SetPositions(self):
        #bl = Point(*self.shape.vertices[0])
        #tr = Point(*self.shape.vertices[2])
        #size = tr - bl
        #self.base_pos = bl + (size*Point(0.4,0.3))
        #self.hose_pos = bl + (size*Point(1.0,0.8))
        centre = self.parent.body.position
        angle  = self.parent.body.angle + (math.pi/2)
        vector = cmath.rect(self.parent.midpoint[1]*1.1,angle)
        self.base_pos = Point(*self.parent.body.GetLocalPoint((centre[0] + vector.real,centre[1] + vector.imag)))
        vector = cmath.rect(self.parent.midpoint[1]*1.5,self.GetDirection())
        self.hose_pos = Point(*self.parent.body.GetLocalPoint((centre[0] + vector.real,centre[1] + vector.imag)))
        #self.base_pos = self.bl + self.half_size*Point(0.3,0.05)
        #self.hose_pos = self.bl + self.half_size*Point(0.3,0.5)

    def UpdateLevel(self,adjust):
        if self.level <= 0:
            return False
        self.level += adjust
        globals.game_view.mode.fe_level.SetBarLevel(float(self.level)/self.max_level)
        return True

    def PhysUpdate(self):
        if self.dead:
            return
        if self.squirting:
            if not self.UpdateLevel(-1):
                self.StopSquirting()
                return
            thrust = -0.5
            vector = cmath.rect(thrust,self.GetDirection())
            self.parent.body.ApplyForce((vector.real,vector.imag),self.parent.body.GetWorldPoint(self.middle.to_vec()))
        for i,vertex in enumerate(self.shape.vertices):
            screen_coords = Point(*self.parent.body.GetWorldPoint(vertex))/self.parent.physics.scale_factor
            self.quad.vertex[self.parent.vertex_permutation[i]] = (screen_coords.x,screen_coords.y,self.z_level)

    def GetDirection(self):
        return self.parent.body.angle + self.angle + (math.pi/2)
            
    def Rotate(self,angle):
        self.angle = angle%(math.pi*2)
        #if self.angle > self.min_angle and self.angle < self.max_angle:
        #    return 
        #print 'self.angle',self.angle
        self.shape.SetAsBox(self.half_size[0],self.half_size[1],self.bl.to_vec(),self.angle)
        self.SetPositions()

    def Destroy(self):
        if not self.dead:
            self.shape.ClearUserData()
            self.parent.body.DestroyShape(self.shapeI)
            self.quad.Delete()
            self.dead = True

class Player(DynamicBox):
    texture_name          = 'astronaut_body.png'
    texture_name_fe       = 'astronaut_body_fe.png'
    selected_name         = 'selected.png'
    push_strength         = 200
    throw_strength         = 100
    stretching_arm_length = 1.5
    resting_arm_length    = 0.9
    pushing_arm_length    = 0.8
    grab_angle            = 1.5
    z_level               = 12
    filter_id             = -1
    max_push_duration     = 2000
    def __init__(self,physics,bl,angle=0):
        self.dead              = False
        self.arms              = []
        self.selected          = False
        self.unset             = None
        self.fire_extinguisher = None
        self.push_start        = None
        self.squirting         = False
        self.subimage          = globals.atlas.SubimageSprite(self.texture_name)
        self.texture_coords    = globals.atlas.TextureSpriteCoords(self.texture_name)
        self.selected_subimage = globals.atlas.SubimageSprite(self.selected_name)
        self.selected_texture_coords = globals.atlas.TextureSpriteCoords(self.selected_name)
        tr                     = bl + self.subimage.size
        super(Player,self).__init__(physics,bl,tr,self.texture_coords,angle)
        self.joints    = []
        self.other_obj = None
        self.filter_group = Player.filter_id
        Player.filter_id -= 1
        self.resting_hand_positions = (self.midpoint*Point(0.8,1),
                                       self.midpoint*Point(-0.8,1))
        self.current_hand_positions = self.resting_hand_positions
        self.shoulders = (self.midpoint*Point(0.8,0),
                          self.midpoint*Point(-0.8,0))
        self.arms      = [PlayerArm(self,(self,self.shoulders[0]),(self,self.resting_hand_positions[0])),
                          PlayerArm(self,(self,self.shoulders[1]),(self,self.resting_hand_positions[1]))]

    def EquipFireExtinguisher(self,level = None):
        #Adding a new shape to ourselves
        self.fire_extinguisher = FireExtinguisher(self,level)
        self.current_hand_positions = (self.fire_extinguisher.base_pos,self.fire_extinguisher.hose_pos)
        self.arms[0].SetHand(self,self.fire_extinguisher.base_pos)
        self.arms[1].SetHand(self,self.fire_extinguisher.hose_pos)

    # def ExtraShapes(self):
    #     #Players have arms
    #     box_size = self.tr - self.bl
    #     arm_bl = box_size*Point(0.8,0.5)*0.5*self.physics.scale_factor
    #     arm_tr = arm_bl + box_size*Point(0.05,1)*0.5*self.physics.scale_factor
    #     arm_midpoint = (arm_tr - arm_bl)
    #     self.arm = self.CreateShape(arm_midpoint,arm_bl)
    #     self.armI = self.body.CreateShape(self.arm)
        
    def InitPolygons(self,tc):
        super(Player,self).InitPolygons(tc)
        #The selected quad uses different tcs...
        #self.arm_quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords('debris.png'))
        self.selected_quad = drawing.Quad(globals.quad_buffer,tc = self.selected_texture_coords)
        if not self.selected:
            self.selected_quad.Disable()

    def PhysUpdate(self):
        if self.dead:
            return
        super(Player,self).PhysUpdate()
        #Now update the position of the selected quad. No need to rotate it as it's a circle
        centre = Point(*self.body.GetWorldPoint([0,0]))/self.physics.scale_factor
        bl = centre - (self.selected_subimage.size/2)
        tr = bl + self.selected_subimage.size
        self.selected_quad.SetVertices(bl,tr,20)
        if self.push_start != None:
            level = float(globals.time - self.push_start)/self.max_push_duration
            if level <= 1.0:
                globals.game_view.mode.power_box.SetBarLevel(level)
        for arm in self.arms:
            arm.Update()
        if self.unset and globals.time >= self.unset[1]:
            self.ResetFilters()

        if self.fire_extinguisher:
            self.fire_extinguisher.PhysUpdate()

    def ResetFilters(self):
        #print 'resetting filters'
        #self.unset[0].shape.filter.groupIndex = 0
        #self.shape.filter.groupIndex = 0
        #self.unset = None
        pass

       # for i,vertex in enumerate(self.arm.vertices):
       #     screen_coords = Point(*self.body.GetWorldPoint(vertex))/self.physics.scale_factor
       #     self.arm_quad.vertex[self.vertex_permutation[i]] = (screen_coords.x,screen_coords.y,11)

    def Select(self):
        if not self.selected:
            self.selected = True
            self.selected_quad.Enable()

    def Unselect(self):
        if self.selected:
            self.selected = False
            self.selected_quad.Disable()
            globals.game_view.mode.power_box.Disable()
            self.push_start = None

    def throw_fire_extinguisher(self,pos):
        self.physics.contact_filter.thrown = (self,globals.time+1000)
        if not self.fire_extinguisher:
            return
        power = ((globals.game_view.mode.power_box.power_level)**2)*self.throw_strength
        globals.game_view.mode.power_box.Disable()
        self.push_start = None
        self.fire_extinguisher.Destroy()
        #self.shape.filter.groupIndex = self.filter_group
        #print self.shape.filter.groupIndex
        fe = FloatingFireExtinguisher(self,self.fire_extinguisher,power)
        #Need to have the fe and us not collide for a short while
        
        #self.unset = (fe,globals.time+5000)
        globals.game_view.AddFireExtinguisher(fe)
        
        self.fire_extinguisher = None
        self.current_hand_positions = self.resting_hand_positions
        for i in 0,1:
            self.arms[i].SetHand(self,self.current_hand_positions[i])

    def MouseMotion(self,pos,rel):
        #print pos
        #pass
        if self.fire_extinguisher:
            #print pos
            phys_pos = pos*self.physics.scale_factor
            centre = self.body.GetWorldPoint(self.fire_extinguisher.middle.to_vec())
            diff = phys_pos - Point(centre[0],centre[1])
            distance,angle = cmath.polar(complex(diff.x,diff.y))
            angle = (angle - (math.pi/2) - self.GetAngle())%(math.pi*2)
            self.fire_extinguisher.Rotate(angle)
            self.arms[0].SetHand(self,self.fire_extinguisher.base_pos)
            self.arms[1].SetHand(self,self.fire_extinguisher.hose_pos)

    def MouseButtonDown(self,pos,button):
        if self.fire_extinguisher:
            if button == globals.left_button:
                self.fire_extinguisher.Squirt()
            elif button == globals.right_button:
                self.PrepareThrow()
        else:
            if button == globals.left_button and self.IsGrabbed():
                self.PreparePush()

    def MouseButtonUp(self,pos,button):
        if self.fire_extinguisher:
            if button == globals.left_button:
                self.fire_extinguisher.StopSquirting()
            elif button == globals.right_button:
                self.throw_fire_extinguisher(pos)
        else:
            if button == globals.left_button:
                if self.IsGrabbed() and self.push_start:
                    self.Push()
                else:
                    obj = self.physics.GetObjectAtPoint(pos)
                    if obj and obj is not self:
                        self.Grab(obj,pos)
            elif button == globals.right_button:
                if self.push_start:
                    #just cancel the push start
                    self.push_start = None
                    globals.game_view.mode.power_box.Disable()
                else:
                    self.Ungrab()

    def Grab(self,obj,pos):
        #First we need to decide if we're close enough to grab it
        if self.joints:
            self.Ungrab()
        phys_pos = pos*self.physics.scale_factor
        centre = self.body.position
        diff = phys_pos - Point(centre[0],centre[1])
        print 'jim',diff.SquareLength()
        if diff.SquareLength() > self.stretching_arm_length:
            #Maybe waggle arms here?
            return
        distance,angle = cmath.polar(complex(diff.x,diff.y))
        angle = (angle - (math.pi/2) - self.GetAngle())%(math.pi*2)
        #You can catch a fire extinguisher from any angle
        if isinstance(obj,FloatingFireExtinguisher):
            print 'caught it!'
            #Need to add an impulse to this badger
            vel = obj.body.GetLinearVelocity()
            mass = obj.body.GetMass()
            momentum = vel*obj.body.GetMass()
            impulse = momentum/self.body.GetMass()
            self.body.ApplyImpulse(impulse,self.body.position)
            obj.Destroy()
            
            self.EquipFireExtinguisher(obj.level)
            return

        if not (angle < self.grab_angle or (math.pi*2-angle) < self.grab_angle):
            return
        for shoulder in self.shoulders:
            joint = box2d.b2DistanceJointDef()
            joint.Initialize(self.body,obj.body,self.body.GetWorldPoint(shoulder.to_vec()),tuple(phys_pos))
            joint.collideConnected = True
            joint.frequencyHz   = 4.0
            joint.dampingRatio  = 0.01
            joint.length = self.resting_arm_length
            self.joints.append(self.physics.world.CreateJoint(joint))
        self.other_obj = obj
        other_local_pos = Point(*obj.body.GetLocalPoint(phys_pos.to_vec()))
        self.arms[0].SetHand(obj,other_local_pos)
        self.arms[1].SetHand(obj,other_local_pos)
        #print self,'grappled'

    def IsGrabbed(self):
        return len(self.joints) != 0

    def Ungrab(self):
        if not self.IsGrabbed():
            return
        globals.game_view.mode.power_box.Disable()
        self.push_start = None
        for joint in self.joints:
            self.physics.world.DestroyJoint(joint)
        self.joints = []
        self.other_obj = None
        for i in 0,1:
            self.arms[i].SetHand(self,self.current_hand_positions[i])
        #print 'ungrapple'

    def PreparePush(self):
        if not self.IsGrabbed():
            return
        globals.game_view.mode.power_box.Enable()
        globals.game_view.mode.power_box.SetBarLevel(0)
        self.push_start = globals.time
        for joint in self.joints:
            joint.length = self.pushing_arm_length
        #print 'prepare push'

    def PrepareThrow(self):
        globals.game_view.mode.power_box.Enable()
        globals.game_view.mode.power_box.SetBarLevel(0)
        self.push_start = globals.time

    def Push(self):
        power = ((globals.game_view.mode.power_box.power_level)**2)*self.push_strength
        print globals.game_view.mode.power_box.power_level,power
        globals.game_view.mode.power_box.Disable()
        
        self.push_start = None
        if not self.IsGrabbed():
            return
        obj = self.other_obj
        self.Ungrab()
        print 'pushing'
        #Push on another object. Equal and opposite forces and what not
        #Fire a ray from my player to the object. Where it meets is where the force should be applied
        centre = self.body.GetWorldPoint([0,self.midpoint[1]*1.01])
        front = self.body.GetWorldPoint([0,self.midpoint[1]*100])

        cast_segment=box2d.b2Segment()
        cast_segment.p1 = centre
        cast_segment.p2 = front

        #This is a hack. My contact filtering messes up with rays, so turn it off for the duration of the ray cast
        self.physics.contact_filter.collide = True
        try:
            lam, normal, shape = self.physics.world.RaycastOne(cast_segment,True,None)
        finally:
            self.physics.contact_filter.collide = False
        if shape == self.shapeI:
            return
        if shape != obj.shapeI:
            return
        if abs(normal[0]) < 0.5 and abs(normal[1]) < 0.5:
            #print 'updating normal!',normal
            normal = Point(*(centre-front))
            normal/=normal.length()
            normal = normal.to_vec()

        #self.physics.contact_filter.pushed = (self,obj,globals.time+500)
        print power
        self.body.ApplyForce(normal*power,centre)
        intersection_point = self.body.GetWorldPoint((front-centre)*lam)
        shape.userData.body.ApplyForce(-normal*power,intersection_point) 
        #print 'force added!',normal*self.push_strength,centre


    def Destroy(self):
        print 'player destroy!',self.dead
        if self.dead:
            return
        if self.fire_extinguisher:
            self.fire_extinguisher.Destroy()
        self.Ungrab()
        super(Player,self).Destroy()
        for arm in self.arms:
            arm.Destroy()
        self.selected_quad.Delete()
        self.dead = True

