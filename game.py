"""Game mechanics"""

import numpy as np
import time
import random
from config import Config
from geometry import Point, Rect
from physics import Body, Universe, Trajectory, SurfaceOrbit
from util import randomFloat, randomPointRect, log


class PlanetType:
    def __init__(self, name, radius, density, count):
        self.name = name
        self.radius = radius
        self.density = density
        self.count = count


class Planet(Body):
    """ Planet - a body where space ships can land.
    
    @radius       radius of planet
    @aVelocity    angular velocity
    @colStr       a template string for a Tkinter color, leaving one 
                  RGB-component to be filled dynamically.
    """
    
    def __init__(self, pos, pType, rotation):
        Body.__init__(self, 
                      type=pType.name,
                      pos=pos.copy(), 
                      radius=pType.radius, 
                      rotation=rotation, 
                      density=pType.density)
        self.type = pType
        
    def update(self, t): pass

    def __str__(self):
        return 'Planet(type={type}, pos=({x},{y}), rot={rot})'.format(
                type=self.type.name,
                x=self.pos.x,
                y=self.pos.y,
                rot=self.rotation)
        
    def logState(self, t):
        log('log', str(self))
        
    
class Ship:
    """Our space ship - yay!"""
    def __init__(self, body, angle, universe):
        self.universe = universe
        self.usedFuel = 0
        self.nLaunches = 0     # how many landings on a planet
        self.nLost = 0         # how often flown outside of universe rectangle
        self.paths = [body.orbit(0, angle)]

    @property
    def planet(self):
        if type(self.paths[-1]) is SurfaceOrbit:
            return self.paths[-1].body
        return None

    def speed(self):
        # TODO
        pass
    
    def land(self, t, planet, yAngle):
        orbit = planet.orbit(t, yAngle)
        self.paths.append(orbit)
        log('Ship', 'Landed on {}\nTime {}\nyAngle {}'.format(planet, t, yAngle))
        log('Ship', 'Orbit yAngle {}'.format(orbit.yAngleAt(t)))
        
    def launch(self, thrust, t):
        orbit = self.paths[-1]
        if type(orbit) is not SurfaceOrbit:
            log('Ship', 'Can not launch. Not in orbit')
            return
        
        pos, velocity = orbit.posVelocity(t)
        orbit.endTime = t
        log('Ship', 'Orbital velocity: ' + str(velocity))
        v = orbit.body.pos.vector(pos)
        v.scaleTo(thrust)
        log('Ship', 'Thrust vector: ' + str(v))
        v += velocity
        log('Ship', 'Acceleration: ' + str(v))
        
        traj = Trajectory(t, pos, v, 
                          self.universe, 
                          onHit=self.onHitBody, 
                          onOutOfRect=self.onOutOfUniverse)
        self.paths.append(traj)
        self.nLaunches += 1
        log('Ship', 'Launched at {}\nVelocity: {}\nStart orbit: {}'.format(t, v, orbit.body))
        
    def onHitBody(self, t, body, yAngle):
        self.land(t, body, yAngle)
    
    def onOutOfUniverse(self, t, pos):
        self.nLost += 1
        self.paths.pop()
        log('Ship', 'Moved out of visible universe at time {}'.format(t))
        
    def positionAt(self, t):
        # Fast path
        path = self.paths[-1]
        pos = path.positionAt(t)
        if pos is not None:
            return pos
        
        # So we are looking for a position in the past...
        for path in self.paths:
            if path.startTime <= t <= path.endTime:
                pos = path.positionAt(t)
                assert pos is not None
                return pos
            
        raise Exception('Failed to get ship position at time %s' % t)
        
    def update(self, t):
        path = self.paths[-1]
        if type(path) is Trajectory:
            path.update(t)
            
    def logState(self, t):
        log('log', str(self))
        
    def __str__(self):
        return 'Ship(fuel={fuel}, launches={launches}, lost={lost}, mov={mov})'.format(
                fuel=self.usedFuel,
                launches=self.nLaunches,
                lost=self.nLost,
                mov=str(self.paths[-1]))
        
 

class Game:
    """Main class for the game"""

    def __init__(self, settings):
        self.settings = settings
        self.universe = None
        self.startPlanet = None     # planet where ship starts
        self.targetPlanet = None    # planet where we want to go to
        self.ship = None
        self.startTime = 0
        self.endTime = np.Inf       # game time when game ended
        self.lastUpdate = 0         # game time of last update
        
        self.planetTypes = {
                'normal': PlanetType('normal', 
                                     radius=settings.planetRadiusNormal,
                                     density=settings.planetDensityNormal,
                                     count=settings.nNormalPlanets),
                'small': PlanetType('small',
                                    radius=settings.planetRadiusSmall,
                                    density=settings.planetDensitySmall,
                                    count=settings.nSmallPlanets),
                'large': PlanetType('large',
                                    radius=settings.planetRadiusLarge,
                                    density=settings.planetDensityLarge,
                                    count=settings.nLargePlanets),
                'black': PlanetType('black',
                                    radius=settings.planetRadiusBlack,
                                    density=settings.planetDensityBlack,
                                    count=settings.nBlackPlanets)
        }

    def build(self):
        log('Game', 'Building new game')
        log('Game', 'Creating planets')
        pg = PlanetGenerator(self.planetTypes, self.settings)
        pg.run()
        self.universe = Universe(pg.planets, Config.uniRect, self.settings.gravityConstant)
        self.startPlanet = pg.startPlanet
        self.targetPlanet = pg.targetPlanet
        log('Game', 'Creating ship')
        self.ship = Ship(self.startPlanet, 0, self.universe)
        
    def start(self):
        """Start a new game
            @t       start time
        """
        log('Game', 'Starting new game')
        
        # List of trajectories of the ship
        self.trajectories = []
        self.startTime = time.perf_counter()
    
    def launchShip(self, gt, thrust):
        """Launches a ship at game time gt with thrust thrust"""
        if self.ship.planet is not None:
            self.ship.launch(thrust, gt)
        else:
            log('Game', 'Can not launch ship when not on planet')
    
    def update(self, gt):
        self.ship.update(gt)
        # for body in self.universe.bodies:
        #    body.update(t)
        self.lastUpdate = gt
            
    def logState(self, t):
        #for planet in self.universe.bodies:
        #    planet.logState(t)
        self.ship.logState(t)
            

class PlanetGenerator:
    """Helper class to create planets
    
    There are quite a few things to consider here:
      *) the starting planet must be the leftmost planet
      *) the target planet must be the rightmost planet
      *) two planets must not be too close together
      *) planets should be (somewhat) evenly distributed (no clusters)
      *) planets should not sit right at the edge of the frame
    
         +-----+-------------------------------------+-----+
         |     |                                     |     |
         |     |            planet area              |     |
         |     |                                     |     |
         |     |                                     |     |
         |   <-----start area          target area----->   |
         |     |                                     |     |
         +-----+-------------------------------------+-----+
    """
    
    def __init__(self, planetTypes, settings):
        self.pTypes = planetTypes
        self.settings = settings
        self.uniRect = Config.uniRect
        self.wStartArea = Config.startAreaWidth
        self.wTargetArea = Config.targetAreaWidth
        self.spread = settings.planetSpread
        r = self.uniRect
        self.planetRect = Rect(r.xmin + self.wStartArea,
                               r.ymin,
                               r.xmax - self.wTargetArea,
                               r.ymax)
        self.planets = None
        self.startPlanet = None
        self.targetPlanet = None
        
    def randomPlanetRotation(self):
        aSpeed = self.settings.planetRotation
        aSpeed *= random.uniform(0.5, 1.5)
        aSpeed *= random.choice((-1, 1))
        return aSpeed
        
    def run(self):
        log('PlanetGenerator', 'Creating planets')
        self.createStartAndTarget()
        
        for tries in range(5):
            self.planets = [self.startPlanet, self.targetPlanet]
            # Better to try larger planets first
            if not self.addPlanets(self.pTypes['large']):
                continue
            if not self.addPlanets(self.pTypes['normal']):
                continue
            if not self.addPlanets(self.pTypes['small']):
                continue
            if self.addPlanets(self.pTypes['black']):
                return
        raise Exception("Failed to create planets")

    def createStartAndTarget(self):
        ur = self.uniRect
        # make sure the start planet is not right at the top or bottom 
        pos = Point(self.uniRect.xmin + self.wStartArea/2,
                    randomFloat(ur.ymin + ur.height()*0.2, 
                                ur.ymax - ur.height()*0.2))
        self.startPlanet = Planet(pos, 
                                  self.pTypes['normal'],
                                  self.randomPlanetRotation())
    
        # make sure the start planet is not right at the top or bottom 
        pos = Point(ur.xmax - self.wTargetArea/2,
                    randomFloat(ur.ymin + ur.height()*0.2, 
                                ur.ymax - ur.height()*0.2))

        self.targetPlanet = Planet(pos, 
                                   self.pTypes['normal'], 
                                   self.randomPlanetRotation())
        
    # Helper function to find a random position for a planet
    def findPosition(self, rect, pRadius):
        for i in range(1000):
            pos = randomPointRect(rect)
            success = True
            for p in self.planets:
                if pos.distance(p.pos) < (pRadius + p.radius)*self.spread:
                    success = False
                    break
            if success:
                log('PlanetGenerator', '{} tries to find empty space'.format(i + 1))
                return pos
        return None # failed to find a position
    
    # Helper function to add planets of a given type
    def addPlanets(self, pt):
        log('PlanetGenerator', 'Creating {n} {s} planets (radius: {r})'.format(
                n=pt.count, s=pt.name, r=pt.radius))
        pr = self.planetRect
        dr = pt.radius*self.spread
        rect = Rect(pr.xmin + dr, pr.ymin + dr,
                    pr.xmax - dr, pr.ymax - dr)
        for n in range(pt.count):
            pos = self.findPosition(rect, pt.radius)
            if pos is not None:
                p = Planet(pos, pt, self.randomPlanetRotation())
                self.planets.append(p)
                log('PlanetGenerator', 'Created {} planet at ({}, {})'.format(pt.name, pos.x, pos.y))
            else:
                return False
        return True


            
            

                
        

    
