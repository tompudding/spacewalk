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
            posv = box2d.b2Vec2()
            posv[0] = pos[0]
            posv[1] = pos[1]
            shape.SetAsBox(midpoint[0],midpoint[1],posv,0)
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
            self.quad.vertex[self.vertex_permutation[i]] = (screen_coords.x,screen_coords.y,10)

    def Damage(self,amount):
        self.health -= amount
        if self.health < 0:
            self.Destroy()

class Player(DynamicBox):
    texture_name          = 'astronaut_body.png'
    selected_name         = 'selected.png'
    push_strength         = 300
    stretching_arm_length = 1.1
    resting_arm_length    = 0.9
    pushing_arm_length    = 0.8
    grab_angle            = 1.5
    def __init__(self,physics,bl,fire_extinguisher):
        self.selected          = False
        self.subimage          = globals.atlas.SubimageSprite(self.texture_name)
        self.texture_coords    = globals.atlas.TextureSpriteCoords(self.texture_name)
        self.selected_subimage = globals.atlas.SubimageSprite(self.selected_name)
        self.selected_texture_coords = globals.atlas.TextureSpriteCoords(self.selected_name)
        tr                     = bl + self.subimage.size
        super(Player,self).__init__(physics,bl,tr,self.texture_coords)
        self.joint = None
        self.other_obj = None

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

    def Grab(self,obj,pos):
        #First we need to decide if we're close enough to grab it
        if self.joint:
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
        joint = box2d.b2DistanceJointDef()
        joint.Initialize(self.body,obj.body,self.body.GetWorldCenter(),tuple(phys_pos))
        joint.collideConnected = True
        joint.frequencyHz   = 4.0
        joint.dampingRatio  = 0.01
        joint.length = self.resting_arm_length
        self.joint = self.physics.world.CreateJoint(joint)
        self.other_obj = obj
        print self,'grappled'

    def IsGrabbed(self):
        return self.joint != None

    def Ungrab(self):
        if not self.IsGrabbed():
            return
        self.physics.world.DestroyJoint(self.joint)
        self.joint = None
        self.other_obj = None
        print 'ungrapple'

    def PreparePush(self):
        if not self.IsGrabbed():
            return
        self.joint.length = self.pushing_arm_length
        print 'prepare push'

    def Push(self):
        if not self.IsGrabbed():
            return
        obj = self.other_obj
        self.Ungrab()
        print 'pushing'
        #Push on another object. Equal and opposite forces and what not
        #Fire a ray from my player to the object. Where it meets is where the force should be applied
        centre = self.body.GetWorldPoint([0,self.midpoint[1]*1.1])
        front = self.body.GetWorldPoint([0,self.midpoint[1]*100])

        cast_segment=box2d.b2Segment()
        cast_segment.p1 = centre
        cast_segment.p2 = front

        lam, normal, shape = self.physics.world.RaycastOne(cast_segment,True,None)
        if shape == self.shapeI:
            return
        if shape != obj.shapeI:
            return
        self.body.ApplyForce(normal*self.push_strength,centre)
        intersection_point = self.body.GetWorldPoint((front-centre)*lam)
        shape.userData.body.ApplyForce(-normal*self.push_strength,intersection_point) 
        print 'force added!'

