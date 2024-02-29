import sys, random, enum, ast, time, threading, os, math
from datetime import datetime
from flask import jsonify
from rpy2 import robjects
from matrx import grid_world
from brains1.BW4TBrain import BW4TBrain
from actions1.customActions import *
from matrx import utils
from matrx.grid_world import GridWorld
from matrx.agents.agent_utils.state import State
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state_tracker import StateTracker
from matrx.actions.door_actions import OpenDoorAction
from matrx.actions.object_actions import GrabObject, DropObject, RemoveObject
from matrx.actions.move_actions import MoveNorth
from matrx.messages.message import Message
from matrx.messages.message_manager import MessageManager
from actions1.customActions import Backup, RemoveObjectTogether, CarryObjectTogether, DropObjectTogether, CarryObject, Drop, Injured, AddObject

class Phase(enum.Enum):
    LOCATE=1,
    FIND_NEXT_GOAL=2,
    PICK_UNSEARCHED_ROOM=3,
    PLAN_PATH_TO_ROOM=4,
    FOLLOW_PATH_TO_ROOM=5,
    REMOVE_OBSTACLE_IF_NEEDED=6,
    ENTER_ROOM=7,
    PLAN_ROOM_SEARCH_PATH=8,
    FOLLOW_ROOM_SEARCH_PATH=9,
    PLAN_PATH_TO_VICTIM=10,
    FOLLOW_PATH_TO_VICTIM=11,
    TAKE_VICTIM=12,
    PLAN_PATH_TO_DROPPOINT=13,
    FOLLOW_PATH_TO_DROPPOINT=14,
    DROP_VICTIM=15,
    BACKUP=16,
    BACKUP2=17,
    TACTIC=18,
    DEFENSIVE_TACTIC=19,
    PRIORITY=20,
    RESCUE=21

    
class TutorialAgent(BW4TBrain):
    def __init__(self, slowdown:int):
        super().__init__(slowdown)
        self._slowdown = slowdown
        self._phase=Phase.FIND_NEXT_GOAL
        self._roomVics = []
        self._searchedRooms = []
        self._foundVictims = []
        self._collectedVictims = []
        self._foundVictimLocs = {}
        self._sendMessages = []
        self._currentDoor=None  
        self._teamMembers = []
        self._goalVic = None
        self._goalLoc = None
        self._todo = []
        self._answered = False
        self._tosearch = []
        self._co = 0
        self._hcn = 0
        self._timeLeft = 90
        self._smoke = 'normal'
        self._temperature = '<≈'
        self._temperatureCat = 'close'
        self._location = '?'
        self._distance = '?'
        self._plotGenerated = False
        self._fireCoords = None
        self._time = 0
        self._counter_value = 90
        self._duration = 15
        self._modulos = []
        self._tactic = 'offensive'
        self._backup = None

    def initialize(self):
        self._state_tracker = StateTracker(agent_id=self.agent_id)
        self._navigator = Navigator(agent_id=self.agent_id, 
            action_set=self.action_set, algorithm=Navigator.A_STAR_ALGORITHM)
        self._loadR2Py()        

    def filter_bw4t_observations(self, state):
        self._second = state['World']['tick_duration'] * state['World']['nr_ticks']
        if int(self._second) % 6 == 0 and int(self._second) not in self._modulos:
            self._modulos.append(int(self._second))
            self._counter_value-=1
            self._duration+=1
        self._sendMessage('Time left: ' + str(self._counter_value) + '.', 'RescueBot')
        self._sendMessage('Fire duration: ' + str(self._duration) + '.', 'RescueBot')
        return state

    def decide_on_bw4t_action(self, state:State):
        print(self._phase)
        self._sendMessage('Smoke spreads: ' + self._smoke + '.', 'RescueBot')
        self._sendMessage('Temperature: ' + self._temperature + '.', 'RescueBot')
        self._sendMessage('Location: ' + self._location + '.', 'RescueBot')
        self._sendMessage('Distance: ' + self._distance + '.', 'RescueBot')
        self._sendMessage('Our score is ' + str(state['brutus']['score']) +'.', 'Brutus')

        for info in state.values():
            if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'source' in info['obj_id']:
                self._sendMessage('Found fire source!', 'Brutus')
                self._location = '✔'
            if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'fire' in info['obj_id']:
                self._sendMessage('Found fire!', 'Brutus')
                if self._tactic=='defensive':
                     self._sendMessage('Extinguishing fire...', 'Brutus')
                     return RemoveObject.__name__, {'object_id': info['obj_id'], 'remove_range':500, 'duration_in_ticks':50}

        if self._location == '✔':
            for info in state.values():
                if 'class_inheritance' in info and 'EnvObject' in info['class_inheritance'] and 'fire source' in info['name']:
                    self._fireCoords = info['location']
                #if 'class_inheritance' in info and 'SmokeObject' in info['class_inheritance']:
                    #self._co = info['co_ppm']
                    #self._hcn = info['hcn_ppm']

        if self.received_messages_content and self.received_messages_content[-1] == 'Found fire source!':
            self._sendMessage('Fire source located and pinned on the map.', 'Brutus')
            action_kwargs = add_object([(2,8)], "/images/fire2.svg", 3, 1, 'fire source')
            self._location = '✔' 
            return AddObject.__name__, action_kwargs

        #if not state[{'class_inheritance':'SmokeObject'}]:
        #    self._co = 0
        #    self._hcn = 0

        if self._location == '?':
            self._locationCat = 'unknown'
        if self._location == '✔':
            self._locationCat = 'known'

        if self._timeLeft - self._counter_value not in [2,20,30,40,50,60,70,80, self._time]: #replace by list keeping track of all times where plots are send
            self._plotGenerated = False

        while True:     

            if self._timeLeft - self._counter_value == 20 and not self._plotGenerated or self._timeLeft - self._counter_value == 30 and not self._plotGenerated or self._timeLeft - self._counter_value == 40 and not self._plotGenerated \
                or self._timeLeft - self._counter_value == 50 and not self._plotGenerated or self._timeLeft - self._counter_value == 60 and not self._plotGenerated or self._timeLeft - self._counter_value == 70 and not self._plotGenerated \
                or self._timeLeft - self._counter_value == 80 and not self._plotGenerated:
                image_name = "/home/ruben/xai4mhc/TUD-Research-Project-2022/SaR_gui/static/images/sensitivity_plots/plot_at_time_" + str(self._counter_value) + ".svg"
                sensitivity = self._R2PyPlotTactic(self._totalVictimsCat, self._locationCat, self._duration, self._counter_value, image_name)
                #sensitivity = self._R2PyPlotTactic('multiple', self._locationCat, self._duration, self._counter_value, image_name)
                #sensitivity = 4
                self._plotGenerated = True
                image_name = "<img src='/static/images" + image_name.split('/static/images')[-1] + "' />"
                if sensitivity >= 4.2:
                    self._sendMessage('My offensive inside deployment has been going on for ' + str(self._timeLeft - self._counter_value) + ' minutes now. \
                                    We should decide whether to continue with this tactic or switch to a defensive inside deployment. \
                                    Please make this decision because the predicted moral sensitivity of this situation is above my allocation threshold. \
                                    This is how much each feature contributed to the predicted sensitivity: \n \n ' \
                                    + image_name, 'Brutus')
                    self._decide = 'human'
                    self._lastPhase = self._phase
                    self._phase = Phase.TACTIC
                
                if sensitivity < 4.2:
                    self._sendMessage('My offensive inside deployment has been going on for ' + str(self._timeLeft - self._counter_value) + ' minutes now. \
                                    We should decide whether to continue with this tactic or switch to a defensive inside deployment. \
                                    I will make this decision because the predicted moral sensitivity of this situation is below my allocation threshold. \
                                    This is how much each feature contributed to the predicted sensitivity: \n \n ' \
                                    + image_name, 'Brutus')
                    self._decide = 'Brutus'
                    self._time = self._timeLeft - self._counter_value
                    self._lastPhase = self._phase
                    self._phase = Phase.TACTIC

            if Phase.TACTIC==self._phase:
                if self._decide == 'human':
                    self._sendMessage('If you want to continue with the offensive inside deployment, press the "Continue" button. \
                                    If you want to switch to a defensive inside deployment, press the "Switch" button.', 'Brutus')
                    if self.received_messages_content and self.received_messages_content[-1] == 'Continue':
                        self._sendMessage('Continuing with the offensive inside deployment because you decided to.', 'Brutus')
                        self._tactic = 'offensive'
                        self._phase = self._lastPhase
                    if self.received_messages_content and self.received_messages_content[-1] == 'Switch':
                        self._sendMessage('Switching to a defensive inside deployment because you decided to.', 'Brutus')
                        self._tactic = 'defensive'
                        self._phase = self._lastPhase
                    else:
                        return None, {}

                # ADD MORE CONDITIONS FOR BRUTUS TO MAKE DECISION ABOUT SWITCHING TACTICS, FOR EXAMPLE WRT HOW DANGEROUS SITUATION IS (CHECK GUIDELINES)    
                if self._decide == 'Brutus' and self._timeLeft - self._counter_value == self._time + 1 and self._counter_value > 45:
                    self._sendMessage('Continuing with the offensive inside deployment because the estimated fire resistance to collapse is higher than 45 minutes.', 'Brutus')
                    self._tactic = 'offensive'
                    self._phase = self._lastPhase
                if self._decide == 'Brutus' and self._timeLeft - self._counter_value == self._time + 1 and self._counter_value <= 45:
                    self._sendMessage('Switching to the defensive inside deployment because the estimated fire resistance to collapse is less than 45 minutes.', 'Brutus')
                    self._tactic = 'defensive'
                    self._phase = self._lastPhase
                else:
                    return None, {}


            if self._timeLeft - self._counter_value == 2 and self._location == '?' and not self._plotGenerated:
                image_name = "/home/ruben/xai4mhc/TUD-Research-Project-2022/SaR_gui/static/images/sensitivity_plots/plot_at_time_" + str(self._counter_value) + ".svg"
                sensitivity = self._R2PyPlotLocate(self._totalVictimsCat, self._duration, self._counter_value, self._temperatureCat, image_name)
                #sensitivity = self._R2PyPlotLocate('multiple', self._duration, self._counter_value, self._temperatureCat, image_name)
                #sensitivity = 4.19
                self._plotGenerated = True
                image_name = "<img src='/static/images" + image_name.split('/static/images')[-1] + "' />"
                if sensitivity >= 4.2:
                    self._sendMessage('The location of the fire source still has not been found, so we should decide whether to send in fire fighters to help locate the fire source or if sending them in is too dangerous. \
                                      Please make this decision because the predicted moral sensitivity of this situation is above my allocation threshold. \
                                      This is how much each feature contributed to the predicted sensitivity: \n \n ' \
                                      + image_name, 'Brutus')
                    self._decide = 'human'
                    self._lastPhase = self._phase
                    self._phase = Phase.LOCATE

                if sensitivity < 4.2:
                    self._sendMessage('The location of the fire source still has not been found, so we should decide whether to send in fire fighters to help locate the fire source or if sending them in is too dangerous. \
                                      I will make this decision because the predicted moral sensitivity of this situation is below my allocation threshold. \
                                      This is how much each feature contributed to the predicted sensitivity: \n \n ' \
                                      + image_name, 'Brutus')
                    self._decide = 'Brutus'
                    self._time = self._timeLeft - self._counter_value
                    self._lastPhase = self._phase
                    self._phase = Phase.LOCATE

            if Phase.LOCATE==self._phase:
                if self._decide == 'human':
                    self._sendMessage('If you want to send in fire fighters to help locate the fire source, press the "Fire fighter" button. \
                                      If you do not want to send them in, press the "Continue" button.', 'Brutus')
                    if self.received_messages_content and self.received_messages_content[-1] == 'Continue':
                        self._sendMessage('Not sending in fire fighters to help locate the fire source because you decided to.', 'Brutus')
                        self._phase = self._lastPhase
                    if self.received_messages_content and self.received_messages_content[-1] == 'Fire fighter':
                        self._sendMessage('Sending in fire fighters to help locate the fire source because you decided to.', 'Brutus')
                        self._sendMessage('Target', 'Brutus')
                        self._time = self._timeLeft - self._counter_value
                        self._phase = self._lastPhase
                        #self._backup = True
                        #action_kwargs = add_object([(2,4),(9,6),(2,20),(9,18)], "/static/images/rescue-man-final3.svg", 1, 1, 'backup')
                        #return AddObject.__name__, action_kwargs
                    else:
                        return None, {}
                
                # ADD MORE CONDITIONS FOR BRUTUS TO MAKE DECISION ABOUT SENDING IN FIREFIGHTERS TO LOCATE FIRE SOURCE, FOR EXAMPLE WRT RESISTENCE TO COLLAPSE
                if self._decide == 'Brutus' and self._timeLeft - self._counter_value == self._time + 1 and self._temperatureCat == 'close' \
                    or self._decide == 'Brutus' and self._timeLeft - self._counter_value == self._time + 1 and self._temperatureCat == 'lower':
                    self._sendMessage('Sending in fire fighters to help locate because the temperate is lower than the auto-ignition temperatures of present substances.', 'Brutus')
                    self._time = self._timeLeft - self._counter_value
                    self._phase = self._lastPhase
                    #self._backup = True
                    action_kwargs = add_object([(2,4),(9,6),(2,20),(9,18)], "/static/images/rescue-man-final3.svg", 1, 1, 'backup')
                    return AddObject.__name__, action_kwargs
                if self._decide == 'Brutus' and self._timeLeft - self._counter_value == self._time + 1 and self._temperatureCat == 'higher':
                    self._sendMessage('Not sending in fire fighters because the temperature is higher than the auto-ignition temperatures of present substances.', 'Brutus')
                    #self._backup = False
                    self._phase = self._lastPhase
                else:
                    return None, {}
                
                
            #if self._timeLeft - self._counter_value == self._time + 2 and self._backup:
            #    for info in state.values():
            #        if 'obj_id' in info.keys() and 'backup' in info['obj_id']:
            #            return RemoveObject.__name__, {'object_id': info['obj_id'], 'remove_range':500, 'duration_in_ticks':0}
                
            #if self._timeLeft - self._counter_value == self._time + 2 and self._backup:
            #    self._sendMessage('Fire source located and pinned on the map.', 'Brutus')
            #    action_kwargs = add_object([(2,8)], "/images/fire2.svg", 3, 1, 'fire source')
            #    self._location = '✔' 
            #    return AddObject.__name__, action_kwargs
                
            if Phase.FIND_NEXT_GOAL==self._phase:
                self._answered = False
                self._advice = False
                self._goalVic = None
                self._goalLoc = None
                zones = self._getDropZones(state)
                remainingZones = []
                remainingVics = []
                remaining = {}
                for info in zones:
                    if str(info['img_name'])[8:-4] not in self._collectedVictims:
                        remainingZones.append(info)
                        remainingVics.append(str(info['img_name'])[8:-4])
                        remaining[str(info['img_name'])[8:-4]] = info['location']
                if remainingZones:
                    #self._goalVic = str(remainingZones[0]['img_name'])[8:-4]
                    #self._goalLoc = remainingZones[0]['location']
                    self._remainingZones = remainingZones
                    self._remaining = remaining
                if not remainingZones:
                    return None,{}
                self._totalVictims = len(remainingVics) + len(self._collectedVictims)
                if self._totalVictims == 0:
                    self._totalVictimsCat = 'none'
                if self._totalVictims == 1:
                    self._totalVictimsCat = 'one'
                if self._totalVictims == 'unknown':
                    self._totalVictimsCat = 'unclear'
                if self._totalVictims > 1:
                    self._totalVictimsCat = 'multiple'
                self._sendMessage('Victims rescued: ' + str(len(self._collectedVictims)) + '/' + str(self._totalVictims) + '.', 'RescueBot')
                for vic in remainingVics:
                    if vic in self._foundVictims and vic not in self._todo:
                        self._goalVic = vic
                        self._goalLoc = remaining[vic]
                        self._phase = Phase.PLAN_PATH_TO_VICTIM
                        return Idle.__name__,{'duration_in_ticks':25}              
                self._phase=Phase.PICK_UNSEARCHED_ROOM

            if Phase.PICK_UNSEARCHED_ROOM==self._phase:
                self._advice = False
                agent_location = state[self.agent_id]['location']
                unsearchedRooms=[room['room_name'] for room in state.values()
                if 'class_inheritance' in room
                and 'Door' in room['class_inheritance']
                and room['room_name'] not in self._searchedRooms
                and room['room_name'] not in self._tosearch]
                if self._remainingZones and len(unsearchedRooms) == 0:
                    self._tosearch = []
                    self._todo = []
                    self._searchedRooms = []
                    self._sendMessages = []
                    self.received_messages = []
                    self.received_messages_content = []
                    self._searchedRooms.append(self._door['room_name'])
                    self._sendMessage('Going to re-explore all areas.','Brutus')
                    self._phase = Phase.FIND_NEXT_GOAL
                else:
                    if self._currentDoor==None:
                        self._door = state.get_room_doors(self._getClosestRoom(state,unsearchedRooms,agent_location))[0]
                        self._doormat = state.get_room(self._getClosestRoom(state,unsearchedRooms,agent_location))[-1]['doormat']
                        if self._door['room_name'] == 'area 1':
                            self._doormat = (2,4)
                        self._phase = Phase.PLAN_PATH_TO_ROOM
                    if self._currentDoor!=None:
                        self._door = state.get_room_doors(self._getClosestRoom(state,unsearchedRooms,self._currentDoor))[0]
                        self._doormat = state.get_room(self._getClosestRoom(state, unsearchedRooms,self._currentDoor))[-1]['doormat']
                        if self._door['room_name'] == 'area 1':
                            self._doormat = (2,4)
                        self._phase = Phase.PLAN_PATH_TO_ROOM

            if Phase.PLAN_PATH_TO_ROOM==self._phase:
                self._navigator.reset_full()
                if self._goalVic and self._goalVic in self._foundVictims and 'location' not in self._foundVictimLocs[self._goalVic].keys():
                    self._door = state.get_room_doors(self._foundVictimLocs[self._goalVic]['room'])[0]
                    self._doormat = state.get_room(self._foundVictimLocs[self._goalVic]['room'])[-1]['doormat']
                    if self._door['room_name'] == 'area 1':
                        self._doormat = (2,4)
                    doorLoc = self._doormat
                else:
                    if self._door['room_name'] == 'area 1':
                        self._doormat = (2,4)
                    doorLoc = self._doormat
                self._navigator.add_waypoints([doorLoc])
                self._phase=Phase.FOLLOW_PATH_TO_ROOM

            if Phase.FOLLOW_PATH_TO_ROOM==self._phase:
                if self._goalVic and self._goalVic in self._collectedVictims:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                if self._goalVic and self._goalVic in self._foundVictims and self._door['room_name']!=self._foundVictimLocs[self._goalVic]['room']:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                if self._door['room_name'] in self._searchedRooms and self._goalVic not in self._foundVictims:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                if self._goalVic in self._foundVictims and str(self._door['room_name']) == self._foundVictimLocs[self._goalVic]['room']:
                    self._state_tracker.update(state)
                    self._sendMessage('Moving to ' + str(self._door['room_name']) + ' to pick up ' + self._goalVic+'.', 'Brutus')
                    self._currentDoor=self._door['location']
                    action = self._navigator.get_move_action(self._state_tracker)
                    if action!=None:
                        return action,{}
                if self._goalVic not in self._foundVictims or not self._goalVic:
                    self._state_tracker.update(state)
                    self._sendMessage('Moving to ' + str(self._door['room_name']) + ' because it is the closest not explored area.', 'Brutus')                   
                    self._currentDoor=self._door['location']
                    action = self._navigator.get_move_action(self._state_tracker)
                    if action!=None:
                            #for info in state.values():
                                #if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'stone' in info['obj_id'] and info['location'] not in [(9,7),(9,19),(21,19)]:
                                #    self._sendMessage('Found stones blocking my path to ' + str(self._door['room_name']) + '. We can remove them faster if you help me. If you will come here press the "Yes" button, if not press "No".', 'Brutus')
                                #    if self.received_messages_content and self.received_messages_content[-1]=='Yes':
                                #        return None, {}
                                #    if self.received_messages_content and self.received_messages_content[-1]=='No' or state['World']['nr_ticks'] > self._tick + 579:
                                #        self._sendMessage('Removing the stones blocking the path to ' + str(self._door['room_name']) + ' because I want to search this area. We can remove them faster if you help me', 'Brutus')
                                    #return RemoveObject.__name__,{'object_id':info['obj_id'],'size':info['visualization']['size']}
                        return action,{}
                    
                self._phase=Phase.REMOVE_OBSTACLE_IF_NEEDED         

            if Phase.REMOVE_OBSTACLE_IF_NEEDED==self._phase:
                objects = []
                for info in state.values():
                    #if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'fire' in info['obj_id']:
                    #    objects.append(info)
                        #self._sendMessage('fire is blocking ' + str(self._door['room_name'])+'. \n \n Please decide whether to "Extinguish", "Continue" exploring, or call in a "Fire fighter" to help extinguishing. \n \n \
                        #    Important features to consider: \n - Pinned victims located: ' + str(self._collectedVictims) + '\n - fire temperature: ' + str(int(info['visualization']['size']*300)) + ' degrees Celcius \
                        #    \n - explosion danger: ' + str(info['percentage_lel']) + '% LEL \n - by myself extinguish time: ' + str(int(info['visualization']['size']*7.5)) + ' seconds \n - with help extinguish time: \
                        #    ' + str(int(info['visualization']['size']*3.75)) + ' seconds \n - toxic concentrations: ' + str(self._hcn) + ' ppm HCN and ' + str(self._co) + ' ppm CO','Brutus')
                        #self._waiting = True
                        #if self.received_messages_content and self.received_messages_content[-1]=='Continue':
                        #    self._waiting = False
                        #    self._tosearch.append(self._door['room_name'])
                        #    self._phase=Phase.FIND_NEXT_GOAL
                        #if self.received_messages_content and self.received_messages_content[-1] == 'Extinguish':
                        #    self._sendMessage('Extinguishing fire blocking ' + str(self._door['room_name']) + ' alone.','Brutus')
                        #    self._phase = Phase.ENTER_ROOM
                        #    return RemoveObject.__name__, {'object_id': info['obj_id'],'size':info['visualization']['size']}
                        #if self.received_messages_content and self.received_messages_content[-1] == 'Fire fighter':
                        #    self._sendMessage('Extinguishing fire blocking ' + str(self._door['room_name']) + ' together with fire fighter.','Brutus')
                        #    self._phase = Phase.BACKUP
                        #    return Backup.__name__,{'size':info['percentage_lel']}
                        #else:
                        #    return None,{}
                    
                    #if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'source' in info['obj_id'] and self._location!='✔':
                    #    objects.append(info)
                    #    self._sendMessage('Found fire source!', 'Brutus')
                    #    self._location = '✔'

                    #    return None, {}
                        
                        #self._waiting = True
                        #if self.received_messages_content and self.received_messages_content[-1]=='Continue':
                        #    self._waiting = False
                        #    self._tosearch.append(self._door['room_name'])
                        #    self._phase=Phase.FIND_NEXT_GOAL
                        #if self.received_messages_content and self.received_messages_content[-1] == 'Extinguish':
                        #    self._sendMessage('Extinguishing fire blocking ' + str(self._door['room_name']) + ' alone.','Brutus')
                        #    self._phase = Phase.ENTER_ROOM
                        #    return RemoveObject.__name__, {'object_id': info['obj_id'],'size':info['visualization']['size']}
                        #if self.received_messages_content and self.received_messages_content[-1] == 'Fire fighter':
                        #    self._sendMessage('Extinguishing fire blocking ' + str(self._door['room_name']) + ' together with fire fighter.','Brutus')
                        #    self._phase = Phase.BACKUP
                        #    return Backup.__name__,{'size':info['percentage_lel']}
                        #else:
                        #    return None,{}

                    #if 'class_inheritance' in info and 'Smoke' in info['class_inheritance']:
                    #    self._sendMessage('Smoke detected with ' + info['co_pmm'] + ' ppm CO and ' + info['hcn_ppm'] + ' ppm HCN.','Brutus')
                    #    self._phase=Phase.FIND_NEXT_GOAL

                    if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'iron' in info['obj_id'] and info not in objects:
                        objects.append(info)
                        self._sendMessage('Iron debris is blocking ' + str(self._door['room_name'])+'. \n \n Please decide whether to "Remove", "Continue" exploring, or call in a "Fire fighter" to help remove. \n \n \
                            Important features to consider: \n - Pinned victims located: ' + str(self._collectedVictims) + ' \n - Iron debris weight: ' + str(int(info['weight'])) + ' kilograms \n - by myself removal time: ' \
                            + str(int(info['weight']/10)) + ' seconds \n - with help removal time: ' + str(int(info['weight']/20)) + ' seconds \n - toxic concentrations: ' + str(self._hcn) + ' ppm HCN and ' + str(self._co) + ' ppm CO','Brutus')
                        self._waiting = True
                        if self.received_messages_content and self.received_messages_content[-1]=='Continue':
                            self._waiting = False
                            self._tosearch.append(self._door['room_name'])
                            self._phase=Phase.FIND_NEXT_GOAL
                        if self.received_messages_content and self.received_messages_content[-1] == 'Remove' or self.received_messages_content and 'alone' in self.received_messages_content[-1] and 'Removing' in self.received_messages_content[-1]:
                            self._sendMessage('Removing iron debris blocking ' + str(self._door['room_name']) + ' alone.','Brutus')
                            #self._phase = Phase.ENTER_ROOM
                            #print("REMOVING")
                            return RemoveObject.__name__, {'object_id': info['obj_id'],'size':info['visualization']['size']}
                        if self.received_messages_content and self.received_messages_content[-1] == 'Fire fighter':
                            self._sendMessage('Removing iron debris blocking ' + str(self._door['room_name']) + ' together with fire fighter.','Brutus')
                            self._phase = Phase.BACKUP
                            return Backup.__name__,{}
                        else:
                            return None,{}

                if len(objects)==0:
                    #self._sendMessage('No need to clear the entrance of ' + str(self._door['room_name']) + ' because it is not blocked by obstacles.','Brutus')
                    self._answered = False
                    self._phase = Phase.ENTER_ROOM


            if Phase.BACKUP==self._phase:
                for info in state.values():
                    if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'fire' in info['obj_id']:
                        if info['percentage_lel'] > 10 or self._co > 500 or self._hcn > 40:
                            self._sendMessage('fire at ' + str(self._door['room_name']) + ' too dangerous for fire fighter!! \n \n Going to abort extinguishing.','Brutus')
                            self._searchedRooms.append(self._door['room_name'])
                            self._sendMessages = []
                            self.received_messages = []
                            self.received_messages_content = []
                            self._phase = Phase.FIND_NEXT_GOAL
                            return Injured.__name__,{'duration_in_ticks':50}
                        else:
                            self._phase = Phase.ENTER_ROOM
                            return RemoveObjectTogether.__name__, {'object_id': info['obj_id'], 'size':info['visualization']['size']}
                    if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'iron' in info['obj_id']:
                        if self._co > 500 or self._hcn > 40:
                            self._sendMessage('Situation at ' + str(self._door['room_name']) + ' too dangerous for fire fighter!! \n \n Going to abort removing iron debris.','Brutus')
                            self._searchedRooms.append(self._door['room_name'])
                            self._sendMessages = []
                            self.received_messages = []
                            self.received_messages_content = []
                            self._phase = Phase.FIND_NEXT_GOAL
                            return Injured.__name__,{'duration_in_ticks':50}
                        else:
                            self._phase = Phase.ENTER_ROOM
                            return RemoveObjectTogether.__name__, {'object_id': info['obj_id'], 'size':info['visualization']['size']}

            if Phase.BACKUP2==self._phase:
                self._goalVic = None
                self._goalLoc = None
                zones = self._getDropZones(state)
                remainingZones = []
                remainingVics = []
                remaining = {}
                for info in zones:
                    if str(info['img_name'])[8:-4] not in self._collectedVictims:
                        remainingZones.append(info)
                        remainingVics.append(str(info['img_name'])[8:-4])
                        remaining[str(info['img_name'])[8:-4]] = info['location']
                if remainingZones:
                    #self._goalVic = str(remainingZones[0]['img_name'])[8:-4]
                    #self._goalLoc = remainingZones[0]['location']
                    self._remainingZones = remainingZones
                    self._remaining = remaining
                if not remainingZones:
                    return None,{}

                for vic in remainingVics:
                    if vic in self._foundVictims and vic not in self._todo:
                        self._goalVic = vic
                        self._goalLoc = remaining[vic]
                for info in state.values():
                    if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'fire' in info['obj_id']:
                        if info['percentage_lel'] > 10 or self._co > 500 or self._hcn > 40:
                            self._sendMessage('fire at ' + str(self._door['room_name']) + ' too dangerous for fire fighter!! \n \n Going to abort extinguishing.','Brutus')
                            self._searchedRooms.append(self._door['room_name'])
                            self._collectedVictims.append(self._goalVic)
                            self._sendMessages = []
                            self.received_messages = []
                            self.received_messages_content = []
                            self._phase = Phase.FIND_NEXT_GOAL
                            return Injured.__name__,{'duration_in_ticks':50}
                        else:
                            self._phase = Phase.PLAN_PATH_TO_VICTIM
                            return RemoveObjectTogether.__name__, {'object_id': info['obj_id'], 'size':info['visualization']['size']}
                    
            if Phase.ENTER_ROOM==self._phase:
                self._answered = False
                if self._goalVic in self._collectedVictims:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                if self._goalVic in self._foundVictims and self._door['room_name']!=self._foundVictimLocs[self._goalVic]['room']:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                if self._door['room_name'] in self._searchedRooms and self._goalVic not in self._foundVictims:
                    self._currentDoor=None
                    self._phase=Phase.FIND_NEXT_GOAL
                else:
                    self._state_tracker.update(state)                 
                    action = self._navigator.get_move_action(self._state_tracker)
                    if action!=None:
                        return action,{}
                    self._phase=Phase.PLAN_ROOM_SEARCH_PATH
                    #if self._tactic == 'offensive':
                    #    self._phase=Phase.PLAN_ROOM_SEARCH_PATH
                    #if self._tactic == 'defensive':
                    #    self._phase=Phase.DEFENSIVE_TACTIC

            #if Phase.DEFENSIVE_TACTIC==self._phase:
            #    for info in state.values():
            #        if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'fire' in info['obj_id']:
            #            print('FOUND FIRE!')
            #    self._searchedRooms.append(self._door['room_name'])
            #    self._phase=Phase.FIND_NEXT_GOAL
            #    return MoveNorth.__name__, {}

            if Phase.PLAN_ROOM_SEARCH_PATH==self._phase:
                roomTiles = [info['location'] for info in state.values()
                    if 'class_inheritance' in info 
                    and 'AreaTile' in info['class_inheritance']
                    and 'room_name' in info
                    and info['room_name'] == self._door['room_name']
                ]
                self._roomtiles=roomTiles               
                self._navigator.reset_full()
                if self._tactic == 'offensive':
                    self._navigator.add_waypoints(roomTiles)
                if self._tactic == 'defensive':
                    self._navigator.add_waypoints([self._door['location']])
                #self._sendMessage('Searching through whole ' + str(self._door['room_name']) + ' because my sense range is limited and to find victims.', 'Brutus')
                self._roomVics=[]
                self._phase=Phase.FOLLOW_ROOM_SEARCH_PATH

            if Phase.FOLLOW_ROOM_SEARCH_PATH==self._phase:
                self._state_tracker.update(state)
                action = self._navigator.get_move_action(self._state_tracker)
                if action!=None:                   
                    for info in state.values():
                        if 'class_inheritance' in info and 'CollectableBlock' in info['class_inheritance']:
                            vic = str(info['img_name'][8:-4])
                            if vic not in self._roomVics:
                                self._roomVics.append(vic)

                            if vic in self._foundVictims and 'location' not in self._foundVictimLocs[vic].keys():
                                self._foundVictimLocs[vic] = {'location':info['location'],'room':self._door['room_name'],'obj_id':info['obj_id']}
                                if vic == self._goalVic:
                                    self._sendMessage('Found '+ vic + ' in ' + self._door['room_name'] + ' because you told me '+vic+ ' was located here.', 'Brutus')
                                    self._searchedRooms.append(self._door['room_name'])
                                    self._phase=Phase.FIND_NEXT_GOAL

                            if 'healthy' not in vic and vic not in self._foundVictims:
                                self._recentVic = vic
                                self._foundVictims.append(vic)
                                self._foundVictimLocs[vic] = {'location':info['location'],'room':self._door['room_name'],'obj_id':info['obj_id']}
                                self._sendMessage('Found ' + vic + ' in ' + self._door['room_name'] + '.','Brutus')
                                #if 'mild' in vic and not self._plotGenerated:
                                #    image_name = "/home/ruben/xai4mhc/TUD-Research-Project-2022/SaR_gui/static/images/sensitivity_plots/plot_for_vic_" + vic.replace(' ', '_') + ".svg"
                                    #self._roomVics = ['mildly injured boy', 'mildly injured girl']
                                #    self._R2PyPlotPriority(len(self._roomVics), self._smoke, self._duration, self._locationCat, image_name)
                                #    self._plotGenerated = True
                                #    image_name = "<img src='/static/images" + image_name.split('/static/images')[-1] + "' />"
                                #    self._sendMessage('I have found ' + str(len(self._roomVics)) + ' in the burning office ' + self._door['room_name'] + '. \
                                #                      We should decide whether to first extinguish the fire or evacuate the victims. \
                                #                      I will make this decision because the predicted moral sensitivity of this situation is below my allocation threshold. \
                                #                      This is how much each feature contributed to the predicted sensitivity: \n \n ' \
                                #                      + image_name, 'Brutus')
                                #    self._time = self._timeLeft - self._counter_value
                                if 'critical' in vic and not self._plotGenerated:
                                    image_name = "/home/ruben/xai4mhc/TUD-Research-Project-2022/SaR_gui/static/images/sensitivity_plots/plot_for_vic_" + vic.replace(' ', '_') + ".svg"
                                        #self._foundVictimLocs[self._goalVic]['location']
                                        #self._foundVictimLocs['critically injured girl']['location'] =  (10, 2)
                                    #distance = calculate_distances(self._fireCoords, (10, 16))
                                    #if distance < 14:
                                    #    self._distance = 'small'
                                    #if distance >= 14:
                                    #    self._distance = 'large'
                                    if self._temperatureCat == 'close' or self._temperatureCat == 'lower':
                                        temperature = 'lower'
                                    if self._temperatureCat == 'higher':
                                        temperature = 'higher'
                                    #sensitivity = self._R2PyPlotRescue(self._duration, self._counter_value, temperature, self._distance, image_name)
                                    sensitivity = self._R2PyPlotRescue(self._duration, self._counter_value, temperature, 'large', image_name)
                                    #sensitivity = 4
                                    self._plotGenerated = True
                                    image_name = "<img src='/static/images" + image_name.split('/static/images')[-1] + "' />"
                                    if sensitivity >= 4.2:
                                        self._sendMessage('I have found ' + vic + ' who I cannot evacuate to safety myself. \
                                                        We should decide whether to send in fire fighters to rescue this victim, or if sending them in is too dangerous. \
                                                        Please make this decision because the predicted moral sensitivity of this situation is above my allocation threshold. \
                                                        This is how much each feature contributed to the predicted sensitivity: \n \n ' \
                                                        + image_name, 'Brutus')
                                        self._decide = 'human'
                                        self._phase = Phase.RESCUE
                                        return Idle.__name__,{'duration_in_ticks':25}

                                    if sensitivity < 4.2:
                                        self._sendMessage('I have found ' + vic + ' who I cannot evacuate to safety myself. \
                                                        We should decide whether to send in fire fighters to rescue this victim, or if sending them in is too dangerous. \
                                                        I will make this decision because the predicted moral sensitivity of this situation is below my allocation threshold. \
                                                        This is how much each feature contributed to the predicted sensitivity: \n \n ' \
                                                        + image_name, 'Brutus')
                                        self._decide = 'Brutus'
                                        self._time = self._timeLeft - self._counter_value
                                        self._phase = Phase.RESCUE
                                        return Idle.__name__,{'duration_in_ticks':25}

                        #if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'fire' in info['obj_id']:self._door['room_name']

                    return action,{}
                #if self._goalVic not in self._foundVictims:
                #    self._sendMessage(self._goalVic + ' not present in ' + str(self._door['room_name']) + ' because I searched the whole area without finding ' + self._goalVic, 'Brutus')
                if self._goalVic in self._foundVictims and self._goalVic not in self._roomVics and self._foundVictimLocs[self._goalVic]['room']==self._door['room_name']:
                    self._sendMessage(self._goalVic + ' not present in ' + str(self._door['room_name']) + ' because I searched the whole area without finding ' + self._goalVic+'.', 'Brutus')
                    self._foundVictimLocs.pop(self._goalVic, None)
                    self._foundVictims.remove(self._goalVic)
                    self._roomVics = []
                    self.received_messages = []
                    self.received_messages_content = []

                if self._roomVics:
                    if len(self._roomVics) == 1:
                        self._vicString = 'victim'
                    if len(self._roomVics) > 1:
                        self._vicString = 'victims'
                    for vic in self._roomVics:
                        if 'mild' in self._recentVic and not self._plotGenerated:
                            image_name = "/home/ruben/xai4mhc/TUD-Research-Project-2022/SaR_gui/static/images/sensitivity_plots/plot_for_vic_" + vic.replace(' ', '_') + ".svg"
                    #self._roomVics = ['mildly injured boy', 'mildly injured girl']
                            sensitivity = self._R2PyPlotPriority(len(self._roomVics), self._smoke, self._duration, self._locationCat, image_name)
                            self._plotGenerated = True
                            image_name = "<img src='/static/images" + image_name.split('/static/images')[-1] + "' />"
                            if sensitivity >= 4.2:
                                self._sendMessage('I have found ' + str(len(self._roomVics)) + ' mildly injured ' + self._vicString + ' in the burning office ' + self._door['room_name'].split()[-1] + '. \
                                                We should decide whether to first extinguish the fire or evacuate the ' + self._vicString + '. \
                                                Please make this decision because the predicted moral sensitivity of this situation is above my allocation threshold. \
                                                This is how much each feature contributed to the predicted sensitivity: \n \n ' \
                                                + image_name, 'Brutus')
                                self._decide = 'human'
                                #Sself._time = self._timeLeft - self._counter_value
                                #self._lastPhase = self._phase
                                self._phase = Phase.PRIORITY
                                return Idle.__name__,{'duration_in_ticks':25}

                            if sensitivity < 4.2:
                                 self._sendMessage('I have found ' + str(len(self._roomVics)) + ' mildly injured ' + self._vicString + ' in the burning office ' + self._door['room_name'].split()[-1] + '. \
                                                We should decide whether to first extinguish the fire or evacuate the ' + self._vicString + '. \
                                                I will make this decision because the predicted moral sensitivity of this situation is below my allocation threshold. \
                                                This is how much each feature contributed to the predicted sensitivity: \n \n ' \
                                                + image_name, 'Brutus')
                                 self._decide = 'Brutus'
                                 self._time = self._timeLeft - self._counter_value
                                 #self._lastPhase = self._phase
                                 self._phase = Phase.PRIORITY
                                 return Idle.__name__,{'duration_in_ticks':25}

                self._searchedRooms.append(self._door['room_name'])
                self._phase=Phase.FIND_NEXT_GOAL
                return Idle.__name__,{'duration_in_ticks':25}
            
            if Phase.RESCUE==self._phase:
                if self._decide == 'human':
                    self._sendMessage('If you want to send in fire fighters to rescue ' + self._recentVic + ', press the "Fire fighter" button. \
                                      If you do not want to send them in, press the "Continue" button.', 'Brutus')
                    if self.received_messages_content and self.received_messages_content[-1] == 'Fire fighter':
                        self._sendMessage('Sending in fire fighters to rescue ' + self._recentVic + ' because you decided to.', 'Brutus')
                        vic_x = str(self._foundVictimLocs[self._recentVic]['location'][0])
                        vic_y = str(self._foundVictimLocs[self._recentVic]['location'][1])
                        drop_x = str(self._remaining[self._recentVic][0])
                        drop_y = str(self._remaining[self._recentVic][1])
                        self._sendMessage('Coordinates vic ' + vic_x + ' and ' + vic_y + ' coordinates drop ' + drop_x + ' and ' + drop_y, 'Brutus')
                        if self._recentVic not in self._collectedVictims:
                            self._collectedVictims.append(self._recentVic)
                        if self._door['room_name'] not in self._searchedRooms:
                            self._searchedRooms.append(self._door['room_name'])
                        return None, {}
                    
                    if self.received_messages_content and self._recentVic in self.received_messages_content[-1] and 'Delivered' in self.received_messages_content[-1]:
                        self._phase = Phase.FIND_NEXT_GOAL

                    if self.received_messages_content and self.received_messages_content[-1] == 'Continue':
                        self._sendMessage('Not sending in fire fighters to rescue ' + self._recentVic + ' because you decided to.', 'Brutus')
                        self._collectedVictims.append(self._recentVic)
                        self._searchedRooms.append(self._door['room_name'])
                        self._phase = Phase.FIND_NEXT_GOAL
                    else:
                        return None, {}

                # ADD MORE CONDITIONS
                if self._decide == 'Brutus' and self._timeLeft - self._counter_value == self._time + 1 and self._temperatureCat != 'higher' and self._counter_value > 15:
                    self._sendMessage('Sending in fire fighters to rescue ' + self._recentVic + ' because the temperature is lower than the auto-ignition temperatures of present substances \
                                      and the estimated fire resistance to collapse is more than 15 minutes.', 'Brutus')
                    vic_x = str(self._foundVictimLocs[self._recentVic]['location'][0])
                    vic_y = str(self._foundVictimLocs[self._recentVic]['location'][1])
                    drop_x = str(self._remaining[self._recentVic][0])
                    self._sendMessage('Coordinates vic ' + vic_x + ' and ' + vic_y + ' coordinates drop ' + drop_x + ' and ' + drop_y, 'Brutus')
                    if self._recentVic not in self._collectedVictims:
                        self._collectedVictims.append(self._recentVic)
                    if self._door['room_name'] not in self._searchedRooms:
                        self._searchedRooms.append(self._door['room_name'])
                    return None, {}
                
                if self.received_messages_content and self._recentVic in self.received_messages_content[-1] and 'Delivered' in self.received_messages_content[-1] and self._decide == 'Brutus':
                    self._phase = Phase.FIND_NEXT_GOAL

                if self._decide == 'Brutus' and self._timeLeft - self._counter_value == self._time + 1 and self._temperatureCat == 'higher' and self._counter_value <= 15:
                    self._sendMessage('Not sending in fire fighters to rescue ' + self._recentVic + ' because the temperature is higher than the auto-ignition temperatures of present substances \
                                      and the estimated fire resistance to collapse is less than 15 minutes.', 'Brutus')
                    self._collectedVictims.append(self._recentVic)
                    self._searchedRooms.append(self._door['room_name'])
                    self._phase = Phase.FIND_NEXT_GOAL
                
                else:
                    return None, {}

            if Phase.PRIORITY==self._phase:
                if self._decide == 'human':
                    self._sendMessage('If you want to first extinguish the fire in office ' + self._door['room_name'].split()[-1] + ', press the "Extinguish" button. \
                                      If you want to first evacuate the ' + self._vicString + ' in office ' + self._door['room_name'].split()[-1] + ', press the "Evacuate" button.', 'Brutus')
                    if self.received_messages_content and self.received_messages_content[-1] == 'Extinguish':
                        self._sendMessage('Extinguishing the fire in office ' + self._door['room_name'].split()[-1] + ' first because you decided to.', 'Brutus')
                        self._phase = Phase.FIND_NEXT_GOAL
                        for info in state.values():
                            if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'fire' in info['obj_id']:
                                return RemoveObject.__name__, {'object_id': info['obj_id'], 'remove_range':500, 'duration_in_ticks':50}
                    if self.received_messages_content and self.received_messages_content[-1] == 'Evacuate':
                        self._sendMessage('Evacuating the ' + self._vicString + ' in office ' + self._door['room_name'].split()[-1] + ' first because you decided to.', 'Brutus')
                        self._phase = Phase.FIND_NEXT_GOAL
                    else:
                        return None, {}
                
                # ADD MORE CONDITIONS FOR BRUTUS TO MAKE DECISION
                if self._decide == 'Brutus' and self._timeLeft - self._counter_value == self._time + 1 and self._location == '?' and self._smoke == 'fast':
                    self._sendMessage('Evacuating the ' + self._vicString + ' in office ' + self._door['room_name'].split()[-1] + ' first because the fire source is not located yet and the smoke is spreading fast.', 'Brutus')
                    self._phase = Phase.FIND_NEXT_GOAL
                if self._decide == 'Brutus' and self._timeLeft - self._counter_value == self._time + 1 and self._location != '?' and self._smoke != 'fast':
                    self._sendMessage('Extinguishing the fire in office ' + self._door['room_name'].split()[-1] + ' first because the fire source is located and the smoke is not spreading fast.', 'Brutus')
                    self._phase = Phase.FIND_NEXT_GOAL
                    for info in state.values():
                        if 'class_inheritance' in info and 'ObstacleObject' in info['class_inheritance'] and 'fire' in info['obj_id']:
                            return RemoveObject.__name__, {'object_id': info['obj_id'], 'remove_range':500, 'duration_in_ticks':50}
                else:
                    return None, {}
                
            if Phase.PLAN_PATH_TO_VICTIM==self._phase:
                #if 'mild' in self._goalVic:
                #    self._sendMessage('fire fighter will transport ' + self._goalVic + ' in ' + self._foundVictimLocs[self._goalVic]['room'] + ' to safe zone.', 'Brutus')
                self._searchedRooms.append(self._door['room_name'])
                self._navigator.reset_full()
                self._navigator.add_waypoints([self._foundVictimLocs[self._goalVic]['location']])
                self._phase=Phase.FOLLOW_PATH_TO_VICTIM
                    
            if Phase.FOLLOW_PATH_TO_VICTIM==self._phase:
                if self._goalVic and self._goalVic in self._collectedVictims:
                    self._phase=Phase.FIND_NEXT_GOAL
                else:
                    self._state_tracker.update(state)
                    action=self._navigator.get_move_action(self._state_tracker)
                    if action!=None:
                        return action,{}
                    self._phase=Phase.TAKE_VICTIM
                    
            if Phase.TAKE_VICTIM==self._phase:
                self._sendMessage('Evacuating ' + self._goalVic + ' to safety.', 'Brutus')
                self._collectedVictims.append(self._goalVic)
                self._phase = Phase.PLAN_PATH_TO_DROPPOINT
                return CarryObject.__name__,{'object_id':self._foundVictimLocs[self._goalVic]['obj_id']}          

            if Phase.PLAN_PATH_TO_DROPPOINT==self._phase:
                self._navigator.reset_full()
                self._navigator.add_waypoints([self._goalLoc])
                self._phase=Phase.FOLLOW_PATH_TO_DROPPOINT

            if Phase.FOLLOW_PATH_TO_DROPPOINT==self._phase:
                #self._sendMessage('Transporting '+ self._goalVic + ' to the drop zone because ' + self._goalVic + ' should be delivered there for further treatment.', 'Brutus')
                self._state_tracker.update(state)
                action=self._navigator.get_move_action(self._state_tracker)
                if action!=None:
                    return action,{}
                self._phase=Phase.DROP_VICTIM 

            if Phase.DROP_VICTIM == self._phase:
                if 'mild' in self._goalVic:
                    self._sendMessage('Delivered '+ self._goalVic + ' at the safe zone.', 'Brutus')
                self._phase=Phase.FIND_NEXT_GOAL
                self._currentDoor = None
                return Drop.__name__,{}

            
    def _getDropZones(self,state:State):
        '''
        @return list of drop zones (their full dict), in order (the first one is the
        the place that requires the first drop)
        '''
        places=state[{'is_goal_block':True}]
        places.sort(key=lambda info:info['location'][1])
        zones = []
        for place in places:
            if place['drop_zone_nr']==0:
                zones.append(place)
        return zones

    def _sendMessage(self, mssg, sender):
        msg = Message(content=mssg, from_id=sender)
        if msg.content not in self.received_messages_content:
            self.send_message(msg)
            self._sendMessages.append(msg.content)

        #if self.received_messages and self._sendMessages:
        #    self._last_mssg = self._sendMessages[-1]
        #    if self._last_mssg.startswith('Searching') or self._last_mssg.startswith('Moving'):
        #        self.received_messages=[]
        #        self.received_messages.append(self._last_mssg)

    def _getClosestRoom(self, state, objs, currentDoor):
        agent_location = state[self.agent_id]['location']
        locs = {}
        for obj in objs:
            locs[obj]=state.get_room_doors(obj)[0]['location']
        dists = {}
        for room,loc in locs.items():
            if currentDoor!=None:
                dists[room]=utils.get_distance(currentDoor,loc)
            if currentDoor==None:
                dists[room]=utils.get_distance(agent_location,loc)

        return min(dists,key=dists.get)
    
    def _R2PyPlotPriority(self, people, smoke, duration, location, image_name):
        r_script = (f'''
                    data <- read_excel("/home/ruben/Downloads/moral sensitivity survey data 4.xlsx")
                    data$situation <- as.factor(data$situation)
                    data$location <- as.factor(data$location)
                    data$smoke <- as.factor(data$smoke)
                    data_s3 <- subset(data, data$situation=="3"|data$situation=="6")
                    data_s3 <- data_s3[data_s3$smoke != "pushing out",]
                    data_s3$people <- as.numeric(data_s3$people)
                    fit <- lm(sensitivity ~ people + duration + smoke + location, data = data_s3[-c(244,242,211,162,96,92,29),])
                    pred_data3 <- subset(data_s3[-c(244,242,211,162,96,92,29),], select = c("people", "duration", "smoke", "location", "sensitivity"))
                    pred_data3$smoke <- factor(pred_data3$smoke, levels = c("fast", "normal", "slow"))
                    explainer <- shapr(pred_data3, fit)
                    p <- mean(pred_data3$sensitivity)
                    new_data3 <- data.frame(people = c({people}),
                                        duration = c({duration}),
                                        smoke = c("{smoke}"),
                                        location = c("{location}"))
                    new_data3$smoke <- factor(new_data3$smoke, levels = c("fast", "normal", "slow"))
                    new_data3$location <- factor(new_data3$location, levels = c("known", "unknown"))
                    new_pred <- predict(fit, new_data3)
                    explanation_cat <- shapr::explain(new_data3, approach = "ctree", explainer = explainer, prediction_zero = p)

                    # Shapley values
                    shapley_values <- explanation_cat[["dt"]][,2:5]

                    # Standardize Shapley values
                    standardized_values <- shapley_values / sum(abs(shapley_values))
                    explanation_cat[["dt"]][,2:5] <- standardized_values
                    
                    pl <- plot(explanation_cat, digits = 1, plot_phi0 = FALSE) 
                    pl[["data"]]$header <- paste("predicted sensitivity = ", round(new_pred, 1), sep = " ")
                    data_plot <- pl[["data"]]
                    min <- 'min.'
                    loc <- NA
                    if ("{location}" == 'known') {{
                        loc <- '✔'
                    }}
                    if ("{location}" == 'unknown') {{
                        loc <- '?'
                    }}
                    labels <- c(duration = paste("<img src='/home/ruben/xai4mhc/Icons/duration_fire_black.png' width='38' /><br>\n", new_data3$duration, min), 
                    smoke = paste("<img src='/home/ruben/xai4mhc/Icons/smoke_speed_black.png' width='65' /><br>\n", new_data3$smoke), 
                    location = paste("<img src='/home/ruben/xai4mhc/Icons/location_fire_black.png' width='43' /><br>\n", loc), 
                    people = paste("<img src='/home/ruben/xai4mhc/Icons/victims.png' width='24' /><br>\n", new_data3$people))
                    data_plot$variable <- reorder(data_plot$variable, -abs(data_plot$phi))
                    pl <- ggplot(data_plot, aes(x = variable, y = phi, fill = ifelse(phi >= 0, "positive", "negative"))) + geom_bar(stat = "identity") + scale_x_discrete(name = NULL, labels = labels) + theme(axis.text.x = ggtext::element_markdown(color = "black", size = 15)) + theme(text=element_text(size = 15, family="Roboto"),plot.title=element_text(hjust=0.5,size=15,color="black",face="bold",margin = margin(b=5)),
                    plot.caption = element_text(size=15,margin = margin(t=25),color="black"),
                    panel.background = element_blank(),
                    axis.text = element_text(size=15,colour = "black"),axis.text.y = element_text(colour = "black",margin = margin(t=5)),
                    axis.line = element_line(colour = "black"), axis.title = element_text(size=15), axis.title.y = element_text(colour = "black",margin = margin(r=10),hjust = 0.5),
                    axis.title.x = element_text(colour = "black", margin = margin(t=5),hjust = 0.5), panel.grid.major = element_line(color="#DAE1E7"), panel.grid.major.x = element_blank()) + theme(legend.background = element_rect(fill="white",colour = "white"),legend.key = element_rect(fill="white",colour = "white"), legend.text = element_text(size=15),
                    legend.position ="none",legend.title = element_text(size=15,face = "plain")) + ggtitle(paste("Predicted sensitivity = ", round(new_pred, 1))) + labs(y="Relative feature contribution", fill="") + scale_y_continuous(breaks=seq(-1,1,by=0.5), limits=c(-1,1), expand=c(0.0,0.0)) + scale_fill_manual(values = c("positive" = "#3E6F9F", "negative" = "#B0D7F0"), breaks = c("positive","negative")) + geom_hline(yintercept = 0, color = "black") + theme(axis.text = element_text(color = "black"),
                    axis.ticks = element_line(color = "black"))
                    dpi_web <- 300
                    width_pixels <- 1600
                    height_pixels <- 1600
                    width_inches_web <- width_pixels / dpi_web
                    height_inches_web <- height_pixels / dpi_web
                    ggsave(filename="{image_name}", plot=pl, width=width_inches_web, height=height_inches_web, dpi=dpi_web)
                    ''')
        robjects.r(r_script)
        sensitivity = robjects.r['new_pred'][0]
        return round(sensitivity, 1)

    def _R2PyPlotTactic(self, people, location, duration, resistance, image_name):
        r_script = (f'''
                    data <- read_excel("/home/ruben/Downloads/moral sensitivity survey data 4.xlsx")
                    data$situation <- as.factor(data$situation)
                    data$location <- as.factor(data$location)
                    data_s4 <- subset(data, data$situation=="5"|data$situation=="7")
                    data_s4$people[data_s4$people == "0"] <- "none"
                    data_s4$people[data_s4$people == "1"] <- "one"
                    data_s4$people[data_s4$people == "10" |data_s4$people == "11" |data_s4$people == "2" |data_s4$people == "3" |data_s4$people == "4" |data_s4$people == "5"] <- "multiple"
                    data_s4 <- data_s4[data_s4$people != "clear",]
                    data_s4$people <- factor(data_s4$people, levels = c("none","unclear","one","multiple"))
                    fit <- lm(sensitivity ~ people + duration + resistance + location, data = data_s4[-c(266,244,186,178,126,111,97,44,19),])
                    pred_data4 <- subset(data_s4[-c(266,244,186,178,126,111,97,44,19),], select = c("people", "duration", "resistance", "location", "sensitivity"))
                    explainer <- shapr(pred_data4, fit)
                    p <- mean(pred_data4$sensitivity)
                    new_data4 <- data.frame(people = c("{people}"),
                                            duration = c({duration}),
                                            resistance = c({resistance}),
                                            location = c("{location}"))
                    new_data4$people <- factor(new_data4$people, levels = c("none", "unclear", "one", "multiple"))
                    new_data4$location <- factor(new_data4$location, levels = c("known", "unknown"))
                    new_pred <- predict(fit, new_data4)
                    explanation_cat <- shapr::explain(new_data4, approach = "ctree", explainer = explainer, prediction_zero = p)
                    # Shapley values
                    shapley_values <- explanation_cat[["dt"]][,2:5]

                    # Standardize Shapley values
                    standardized_values <- shapley_values / sum(abs(shapley_values))
                    explanation_cat[["dt"]][,2:5] <- standardized_values
                    
                    pl <- plot(explanation_cat, digits = 1, plot_phi0 = FALSE) 
                    pl[["data"]]$header <- paste("predicted sensitivity = ", round(new_pred, 1), sep = " ")
                    data_plot <- pl[["data"]]
                    min <- 'min.'
                    loc <- NA
                    if ("{location}" == 'known') {{
                        loc <- '✔'
                    }}
                    if ("{location}" == 'unknown') {{
                        loc <- '?'
                    }}
                    labels <- c(duration = paste("<img src='/home/ruben/xai4mhc/Icons/duration_fire_black.png' width='38' /><br>\n", new_data4$duration, min), 
                    resistance = paste("<img src='/home/ruben/xai4mhc/Icons/fire_resistance_black.png' width='47' /><br>\n", new_data4$resistance, min), 
                    location = paste("<img src='/home/ruben/xai4mhc/Icons/location_fire_black.png' width='43' /><br>\n", loc), 
                    people = paste("<img src='/home/ruben/xai4mhc/Icons/victims.png' width='24' /><br>\n", new_data4$people))
                    data_plot$variable <- reorder(data_plot$variable, -abs(data_plot$phi))
                    pl <- ggplot(data_plot, aes(x = variable, y = phi, fill = ifelse(phi >= 0, "positive", "negative"))) + geom_bar(stat = "identity") + scale_x_discrete(name = NULL, labels = labels) + theme(axis.text.x = ggtext::element_markdown(color = "black", size = 15)) + theme(text=element_text(size = 15, family="Roboto"),plot.title=element_text(hjust=0.5,size=15,color="black",face="bold",margin = margin(b=5)),
                    plot.caption = element_text(size=15,margin = margin(t=25),color="black"),
                    panel.background = element_blank(),
                    axis.text = element_text(size=15,colour = "black"),axis.text.y = element_text(colour = "black",margin = margin(t=5)),
                    axis.line = element_line(colour = "black"), axis.title = element_text(size=15), axis.title.y = element_text(colour = "black",margin = margin(r=10),hjust = 0.5),
                    axis.title.x = element_text(colour = "black", margin = margin(t=5),hjust = 0.5), panel.grid.major = element_line(color="#DAE1E7"), panel.grid.major.x = element_blank()) + theme(legend.background = element_rect(fill="white",colour = "white"),legend.key = element_rect(fill="white",colour = "white"), legend.text = element_text(size=15),
                    legend.position ="none",legend.title = element_text(size=15,face = "plain")) + ggtitle(paste("Predicted sensitivity = ", round(new_pred, 1))) + labs(y="Relative feature contribution", fill="") + scale_y_continuous(breaks=seq(-1,1,by=0.5), limits=c(-1,1), expand=c(0.0,0.0)) + scale_fill_manual(values = c("positive" = "#3E6F9F", "negative" = "#B0D7F0"), breaks = c("positive","negative")) + geom_hline(yintercept = 0, color = "black") + theme(axis.text = element_text(color = "black"),
                    axis.ticks = element_line(color = "black"))
                    dpi_web <- 300
                    width_pixels <- 1600
                    height_pixels <- 1600
                    width_inches_web <- width_pixels / dpi_web
                    height_inches_web <- height_pixels / dpi_web
                    ggsave(filename="{image_name}", plot=pl, width=width_inches_web, height=height_inches_web, dpi=dpi_web)
                    ''')
        robjects.r(r_script)
        sensitivity = robjects.r['new_pred'][0]
        return round(sensitivity, 1)

    
    def _R2PyPlotLocate(self, people, duration, resistance, temperature, image_name):
        r_script = (f'''
                    data <- read_excel("/home/ruben/Downloads/moral sensitivity survey data 4.xlsx")
                    data$situation <- as.factor(data$situation)
                    data$temperature <- as.factor(data$temperature)
                    # CORRECT! PREDICT SENSITIVITY IN SITUATION 'SEND IN fire fighters TO LOCATE FIRE OR NOT' BASED ON DURATION, RESISTANCE, TEMPERATURE, AND PEOPLE'
                    data_s2 <- subset(data, data$situation=="2"|data$situation=="4")
                    data_s2$people[data_s2$people == "0"] <- "none"
                    data_s2$people[data_s2$people == "1"] <- "one"
                    data_s2$people[data_s2$people == "10" |data_s2$people == "11" |data_s2$people == "2" |data_s2$people == "3" |data_s2$people == "4" |data_s2$people == "40" |data_s2$people == "5"] <- "multiple"
                    data_s2 <- data_s2[data_s2$people != "clear",]
                    data_s2$people <- factor(data_s2$people, levels = c("none","unclear","one","multiple"))
                    data_s2 <- data_s2 %>% drop_na(duration)
                    fit <- lm(sensitivity ~ people + duration + resistance + temperature, data = data_s2[-c(220,195,158,126,121,76),])
                    # SHAP explanations
                    pred_data2 <- subset(data_s2[-c(220,195,158,126,121,76),], select = c("people", "duration", "resistance", "temperature", "sensitivity"))
                    explainer <- shapr(pred_data2, fit)
                    p <- mean(pred_data2$sensitivity)
                    new_data2 <- data.frame(resistance = c({resistance}),
                                            temperature = c("{temperature}"),
                                            people = c("{people}"),
                                            duration = c({duration}))
                    new_data2$temperature <- factor(new_data2$temperature, levels = c("close", "higher", "lower"))
                    new_data2$people <- factor(new_data2$people, levels = c("none", "unclear", "one", "multiple"))
                    
                    new_pred <- predict(fit, new_data2)
                    explanation_cat <- shapr::explain(new_data2, approach = "ctree", explainer = explainer, prediction_zero = p)

                    # Shapley values
                    shapley_values <- explanation_cat[["dt"]][,2:5]

                    # Standardize Shapley values
                    standardized_values <- shapley_values / sum(abs(shapley_values))
                    explanation_cat[["dt"]][,2:5] <- standardized_values
                    
                    pl <- plot(explanation_cat, digits = 1, plot_phi0 = FALSE) 
                    pl[["data"]]$header <- paste("predicted sensitivity = ", round(new_pred, 1), sep = " ")
                    data_plot <- pl[["data"]]
                    min <- 'min.'
                    temp <- NA
                    if ("{temperature}" == 'close') {{
                        temp <- '<≈ thresh.'
                    }}
                    if ("{temperature}" == 'lower') {{
                        temp <- '&lt; thresh.'
                    }}
                    if ("{temperature}" == 'higher') {{
                        temp <- '&gt; thresh.'
                    }}
                    labels <- c(duration = paste("<img src='/home/ruben/xai4mhc/Icons/duration_fire_black.png' width='38' /><br>\n", new_data2$duration, min), 
                    resistance = paste("<img src='/home/ruben/xai4mhc/Icons/fire_resistance_black.png' width='47' /><br>\n", new_data2$resistance, min), 
                    temperature = paste("<img src='/home/ruben/xai4mhc/Icons/celsius_transparent.png' width='53' /><br>\n", temp), 
                    people = paste("<img src='/home/ruben/xai4mhc/Icons/victims.png' width='24' /><br>\n", new_data2$people))
                    data_plot$variable <- reorder(data_plot$variable, -abs(data_plot$phi))
                    pl <- ggplot(data_plot, aes(x = variable, y = phi, fill = ifelse(phi >= 0, "positive", "negative"))) + geom_bar(stat = "identity") + scale_x_discrete(name = NULL, labels = labels) + theme(axis.text.x = ggtext::element_markdown(color = "black", size = 15)) + theme(text=element_text(size = 15, family="Roboto"),plot.title=element_text(hjust=0.5,size=15,color="black",face="bold",margin = margin(b=5)),
                    plot.caption = element_text(size=15,margin = margin(t=25),color="black"),
                    panel.background = element_blank(),
                    axis.text = element_text(size=15,colour = "black"),axis.text.y = element_text(colour = "black",margin = margin(t=5)),
                    axis.line = element_line(colour = "black"), axis.title = element_text(size=15), axis.title.y = element_text(colour = "black",margin = margin(r=10),hjust = 0.5),
                    axis.title.x = element_text(colour = "black", margin = margin(t=5),hjust = 0.5), panel.grid.major = element_line(color="#DAE1E7"), panel.grid.major.x = element_blank()) + theme(legend.background = element_rect(fill="white",colour = "white"),legend.key = element_rect(fill="white",colour = "white"), legend.text = element_text(size=15),
                    legend.position ="none",legend.title = element_text(size=15,face = "plain")) + ggtitle(paste("Predicted sensitivity = ", round(new_pred, 1))) + labs(y="Relative feature contribution", fill="") + scale_y_continuous(breaks=seq(-1,1,by=0.5), limits=c(-1,1), expand=c(0.0,0.0)) + scale_fill_manual(values = c("positive" = "#3E6F9F", "negative" = "#B0D7F0"), breaks = c("positive","negative")) + geom_hline(yintercept = 0, color = "black") + theme(axis.text = element_text(color = "black"),
                    axis.ticks = element_line(color = "black"))
                    dpi_web <- 300
                    width_pixels <- 1600
                    height_pixels <- 1600
                    width_inches_web <- width_pixels / dpi_web
                    height_inches_web <- height_pixels / dpi_web
                    ggsave(filename="{image_name}", plot=pl, width=width_inches_web, height=height_inches_web, dpi=dpi_web)
                    ''')
        robjects.r(r_script)
        sensitivity = robjects.r['new_pred'][0]
        return round(sensitivity, 1)

    def _R2PyPlotRescue(self, duration, resistance, temperature, distance, image_name):
        r_script = (f'''
                    # CORRECT! PREDICT SENSITIVITY IN SITUATION 'SEND IN fire fighters TO RESCUE OR NOT' BASED ON FIRE DURATION, FIRE RESISTANCE, TEMPERATURE WRT AUTO-IGNITION, AND DISTANCE VICTIM - FIRE 
                    data <- read_excel("/home/ruben/Downloads/moral sensitivity survey data 4.xlsx")
                    data$situation <- as.factor(data$situation)
                    data$temperature <- as.factor(data$temperature)
                    data$distance <- as.factor(data$distance)
                    data_subset <- subset(data, data$situation=="1"|data$situation=="8")
                    data_subset$people <- as.numeric(data_subset$people)
                    data_subset <- subset(data_subset, (!data_subset$temperature=="close"))
                    data_subset <- data_subset %>% drop_na(distance)
                    fit <- lm(sensitivity ~ duration + resistance + temperature + distance, data = data_subset[-c(237,235,202,193,114,108,58,51,34,28,22),])

                    # SHAP explanations
                    #pred <- ggpredict(fit, terms = c("duration[30]", "resistance[30]", "temperature[higher]", "distance[large]"))
                    pred_data <- subset(data_subset[-c(237,235,202,193,114,108,58,51,34,28,22),], select = c("duration", "resistance", "temperature", "distance", "sensitivity"))
                    pred_data$temperature <- factor(pred_data$temperature, levels = c("higher", "lower"))
                    explainer <- shapr(pred_data, fit)
                    p <- mean(pred_data$sensitivity)
                    new_data <- data.frame(duration = c({duration}), 
                                            resistance = c({resistance}),
                                            temperature = c("{temperature}"),
                                            distance = c("{distance}"))

                    new_data$temperature <- factor(new_data$temperature, levels = c("higher", "lower"))
                    new_data$distance <- factor(new_data$distance, levels = c("large", "small"))
                    new_pred <- predict(fit, new_data)
                    explanation_cat <- shapr::explain(new_data, approach = "ctree", explainer = explainer, prediction_zero = p)

                    # Shapley values
                    shapley_values <- explanation_cat[["dt"]][,2:5]

                    # Standardize Shapley values
                    standardized_values <- shapley_values / sum(abs(shapley_values))
                    explanation_cat[["dt"]][,2:5] <- standardized_values
                    
                    pl <- plot(explanation_cat, digits = 1, plot_phi0 = FALSE) 
                    pl[["data"]]$header <- paste("predicted sensitivity = ", round(new_pred, 1), sep = " ")
                    levels(pl[["data"]]$sign) <- c("positive", "negative")
                    data_plot <- pl[["data"]]
                    min <- 'min.'
                    temp <- NA
                    if ("{temperature}" == 'close') {{
                        temp <- '<≈ thresh.'
                    }}
                    if ("{temperature}" == 'lower') {{
                        temp <- '&lt; thresh.'
                    }}
                    if ("{temperature}" == 'higher') {{
                        temp <- '&gt; thresh.'
                    }}
                    labels <- c(duration = paste("<img src='/home/ruben/xai4mhc/Icons/duration_fire_black.png' width='38' /><br>\n", new_data$duration, min), 
                    resistance = paste("<img src='/home/ruben/xai4mhc/Icons/fire_resistance_black.png' width='47' /><br>\n", new_data$resistance, min), 
                    temperature = paste("<img src='/home/ruben/xai4mhc/Icons/celsius_transparent.png' width='53' /><br>\n", temp), 
                    distance = paste("<img src='/home/ruben/xai4mhc/Icons/distance_fire_victim_black.png' width='67' /><br>\n", new_data$distance))
                    data_plot$variable <- reorder(data_plot$variable, -abs(data_plot$phi))
                    pl <- ggplot(data_plot, aes(x = variable, y = phi, fill = ifelse(phi >= 0, "positive", "negative"))) + geom_bar(stat = "identity") + scale_x_discrete(name = NULL, labels = labels) + theme(axis.text.x = ggtext::element_markdown(color = "black", size = 15)) + theme(text=element_text(size = 15, family="Roboto"),plot.title=element_text(hjust=0.5,size=15,color="black",face="bold",margin = margin(b=5)),
                    plot.caption = element_text(size=15,margin = margin(t=25),color="black"),
                    panel.background = element_blank(),
                    axis.text = element_text(size=15,colour = "black"),axis.text.y = element_text(colour = "black",margin = margin(t=5)),
                    axis.line = element_line(colour = "black"), axis.title = element_text(size=15), axis.title.y = element_text(colour = "black",margin = margin(r=10),hjust = 0.5),
                    axis.title.x = element_text(colour = "black", margin = margin(t=5),hjust = 0.5), panel.grid.major = element_line(color="#DAE1E7"), panel.grid.major.x = element_blank()) + theme(legend.background = element_rect(fill="white",colour = "white"),legend.key = element_rect(fill="white",colour = "white"), legend.text = element_text(size=15),
                    legend.position ="none",legend.title = element_text(size=15,face = "plain")) + ggtitle(paste("Predicted sensitivity = ", round(new_pred, 1))) + labs(y="Relative feature contribution", fill="") + scale_y_continuous(breaks=seq(-1,1,by=0.5), limits=c(-1,1), expand=c(0.0,0.0)) + scale_fill_manual(values = c("positive" = "#3E6F9F", "negative" = "#B0D7F0"), breaks = c("positive","negative")) + geom_hline(yintercept = 0, color = "black") + theme(axis.text = element_text(color = "black"),
                    axis.ticks = element_line(color = "black"))
                    dpi_web <- 300
                    width_pixels <- 1600
                    height_pixels <- 1600
                    width_inches_web <- width_pixels / dpi_web
                    height_inches_web <- height_pixels / dpi_web
                    ggsave(filename="{image_name}", plot=pl, width=width_inches_web, height=height_inches_web, dpi=dpi_web)
                    ''')
        robjects.r(r_script)
        sensitivity = robjects.r['new_pred'][0]
        return round(sensitivity, 1)
    
    # move to utils file and call once when running main.py
    def _loadR2Py(self):
        r_script = (f'''
                    # Load libraries
                    library('ggplot2')
                    library('dplyr')
                    library('rstatix')
                    library('ggpubr')
                    library('tidyverse')
                    library('psych')
                    library("gvlma")
                    library("nparLD")
                    library('pastecs')
                    library('WRS2')
                    library('crank')
                    library('lme4')
                    library('psycho')
                    library('lmerTest')
                    library('corrplot')
                    library('RColorBrewer')
                    library('sjPlot')
                    library('sjmisc')
                    library('ggeffects')
                    library('interactions')
                    library('ggcorrplot')
                    library('car')
                    library('caret')
                    library('readxl')
                    library('GGally')
                    library('brant')
                    library('wordcloud')
                    library('RColorBrewer')
                    library('wordcloud2')
                    library('tm')
                    library('tidytext')
                    library('tau')
                    library('shapr')
                    library('DALEX')
                    library('iml')
                    library('pre')
                    library('ggtext')
                    library('ggdist')
                    library('rvest')
                    library('png')
                    library('grid')
                    ''')
        robjects.r(r_script)
    
def add_object(locs, image, size, opacity, name):
    action_kwargs = {}
    add_objects = []
    for loc in locs:
        obj_kwargs = {}
        obj_kwargs['location'] = loc
        obj_kwargs['img_name'] = image
        obj_kwargs['visualize_size'] = size
        obj_kwargs['visualize_opacity'] = opacity
        obj_kwargs['name'] = name
        add_objects+=[obj_kwargs]
    action_kwargs['add_objects'] = add_objects
    return action_kwargs

def calculate_distances(p1, p2):
    # Unpack the coordinates
    x1, y1 = p1
    x2, y2 = p2
    
    # Euclidean distance
    euclidean_distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    # Manhattan distance
    manhattan_distance = abs(x2 - x1) + abs(y2 - y1)
    
    return euclidean_distance