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
    static   = True
    health   = 500
    z_level  = 10
    def __init__(self,physics,bl,tr,tc = None):
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
        self.dead = True
        self.quad.Disable()

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
    def __init__(self,physics,bl,tr,tc):
        super(DynamicBox,self).__init__(physics,bl,tr,tc)

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

class PlayerArm(object):
    z_level = 11
    def __init__(self,parent,start,end):
        self.parent = parent
        self.start_object,self.start_pos = start
        self.end_object,self.end_pos = end
        self.quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords('debris.png'))
        
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

class FireExtinguisher(object):
    z_level = 12
    texture_name = 'fire_extinguisher_held.png'
    min_angle = 1.5
    max_angle = (math.pi*2)-min_angle
    def __init__(self,parent):
        self.parent = parent
        self.subimage          = globals.atlas.SubimageSprite(self.texture_name)
        self.quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords(self.texture_name))
        self.half_size = self.subimage.size*0.5*self.parent.physics.scale_factor
        self.bl = self.parent.midpoint*Point(0,3)-self.half_size
        self.middle = self.bl + self.half_size
        self.shape = self.parent.CreateShape(self.half_size,self.bl)
        self.angle = 0
        self.SetPositions()
        self.squirting = False

    def Squirt(self):
        self.squirting = True
        print 'squirting'

    def StopSquirting(self):
        self.squirting = False
        print 'stopped squirting'

    def SetPositions(self):
        bl = Point(*self.shape.vertices[0])
        tr = Point(*self.shape.vertices[2])
        size = tr - bl
        self.base_pos = bl + (size*Point(0.4,0.3))
        self.hose_pos = bl + (size*Point(1.0,0.8))
        #self.base_pos = self.bl + self.half_size*Point(0.3,0.05)
        #self.hose_pos = self.bl + self.half_size*Point(0.3,0.5)

    def PhysUpdate(self):
        if self.squirting:
            thrust = -0.5
            direction = self.parent.body.angle + self.angle + (math.pi/2)
            vector = cmath.rect(thrust,direction)
            print (vector.real,vector.imag),self.middle,self.parent.body.position
            print 'a',self.bl,self.half_size,self.angle
            self.parent.body.ApplyForce((vector.real,vector.imag),self.parent.body.GetWorldPoint(self.middle.to_vec()))
        for i,vertex in enumerate(self.shape.vertices):
            screen_coords = Point(*self.parent.body.GetWorldPoint(vertex))/self.parent.physics.scale_factor
            self.quad.vertex[self.parent.vertex_permutation[i]] = (screen_coords.x,screen_coords.y,self.z_level)
            
    def Rotate(self,angle):
        self.angle = angle%(math.pi*2)
        #if self.angle > self.min_angle and self.angle < self.max_angle:
        #    return 
        #print 'self.angle',self.angle
        self.shape.SetAsBox(self.half_size[0],self.half_size[1],self.bl.to_vec(),self.angle)
        self.SetPositions()

class Player(DynamicBox):
    texture_name          = 'astronaut_body.png'
    texture_name_fe       = 'astronaut_body_fe.png'
    selected_name         = 'selected.png'
    push_strength         = 300
    stretching_arm_length = 1.5
    resting_arm_length    = 0.9
    pushing_arm_length    = 0.8
    grab_angle            = 1.5
    z_level               = 12
    filter_id             = -1
    def __init__(self,physics,bl):
        self.arms              = []
        self.selected          = False
        self.unset             = None
        self.fire_extinguisher = None
        self.squirting         = False
        self.subimage          = globals.atlas.SubimageSprite(self.texture_name)
        self.texture_coords    = globals.atlas.TextureSpriteCoords(self.texture_name)
        self.selected_subimage = globals.atlas.SubimageSprite(self.selected_name)
        self.selected_texture_coords = globals.atlas.TextureSpriteCoords(self.selected_name)
        tr                     = bl + self.subimage.size
        super(Player,self).__init__(physics,bl,tr,self.texture_coords)
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

    def EquipFireExtinguisher(self):
        #Adding a new shape to ourselves
        self.fire_extinguisher = FireExtinguisher(self)
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
        super(Player,self).PhysUpdate()
        #Now update the position of the selected quad. No need to rotate it as it's a circle
        centre = Point(*self.body.GetWorldPoint([0,0]))/self.physics.scale_factor
        bl = centre - (self.selected_subimage.size/2)
        tr = bl + self.selected_subimage.size
        self.selected_quad.SetVertices(bl,tr,20)
        for arm in self.arms:
            arm.Update()
        if self.unset and globals.time >= self.unset[1]:
            self.ResetFilters()

        if self.fire_extinguisher:
            self.fire_extinguisher.PhysUpdate()

    def ResetFilters(self):
        #print 'resetting filters'
        self.unset[0].shape.filter.groupIndex = 0
        self.shape.filter.groupIndex = 0
        self.unset = None

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
            self.fire_extinguisher.Squirt()
        else:
            if button == globals.left_button and self.IsGrabbed():
                self.PreparePush()

    def MouseButtonUp(self,pos,button):
        if self.fire_extinguisher:
            self.fire_extinguisher.StopSquirting()
        else:
            if button == globals.left_button:
                if self.IsGrabbed():
                    self.Push()
                else:
                    obj = self.physics.GetObjectAtPoint(pos)
                    if obj and obj is not self:
                        self.Grab(obj,pos)
            elif button == globals.right_button:
                self.Ungrab()

    def Grab(self,obj,pos):
        #First we need to decide if we're close enough to grab it
        if self.joints:
            self.Ungrab()
        phys_pos = pos*self.physics.scale_factor
        centre = self.body.position
        diff = phys_pos - Point(centre[0],centre[1])
        if diff.SquareLength() > self.stretching_arm_length:
            #Maybe waggle arms here?
            return
        distance,angle = cmath.polar(complex(diff.x,diff.y))
        angle = (angle - (math.pi/2) - self.GetAngle())%(math.pi*2)
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
        for joint in self.joints:
            joint.length = self.pushing_arm_length
        #print 'prepare push'

    def Push(self):
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

        lam, normal, shape = self.physics.world.RaycastOne(cast_segment,True,None)
        if shape == self.shapeI:
            return
        if shape != obj.shapeI:
            return
        if abs(normal[0]) < 0.5 and abs(normal[1]) < 0.5:
            #print 'updating normal!',normal
            normal = Point(*(centre-front))
            normal/=normal.length()
            normal = normal.to_vec()
            
        if self.unset:
            self.ResetFilters()
        obj.shape.filter.groupIndex = self.filter_group
        self.shape.filter.groupIndex = self.filter_group
        self.unset = (obj,globals.time + 500)
        self.body.ApplyForce(normal*self.push_strength,centre)
        intersection_point = self.body.GetWorldPoint((front-centre)*lam)
        shape.userData.body.ApplyForce(-normal*self.push_strength,intersection_point) 
        #print 'force added!',normal*self.push_strength,centre

