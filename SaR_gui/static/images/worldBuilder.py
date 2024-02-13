import os
import sys
import itertools
from collections import OrderedDict
from itertools import product
from matrx import WorldBuilder
import numpy as np
from matrx.actions import MoveNorth, OpenDoorAction, CloseDoorAction, GrabObject
from matrx.actions.move_actions import MoveEast, MoveSouth, MoveWest
from matrx.agents import AgentBrain, HumanAgentBrain, SenseCapability
from matrx.grid_world import GridWorld, AgentBody
from actions1.customActions import RemoveObjectTogether, DropObject, Idle, CarryObject, Drop, CarryObjectTogether, DropObjectTogether
from matrx.actions.object_actions import RemoveObject
from matrx.objects import EnvObject
from matrx.world_builder import RandomProperty
from matrx.goals import WorldGoal
from agents1.BaselineAgent import BaselineAgent
from agents1.TutorialAgent import TutorialAgent
from agents1.PerformanceAgent import PerformanceAgent
from agents1.TrustAgent import TrustAgent
from agents1.WorkloadAgent import WorkloadAgent
from actions1.customActions import RemoveObjectTogether
from brains1.HumanBrain import HumanBrain
from loggers.action_logger import ActionLogger
from datetime import datetime
from loggers.message_logger import MessageLogger

tick_duration = 0.1
random_seed = 1
verbose = False
key_action_map = {
    }

# Some settings
nr_rooms = 9
room_colors = ['#0008ff', '#ff1500', '#0dff00']
wall_color = "#8a8a8a"
drop_off_color = "#1F262A"
block_size = 0.9
nr_teams = 1
agents_per_team = 2
human_agents_per_team = 1
agent_sense_range = np.inf  # the range with which agents detect other agents
block_sense_range = 2  # the range with which agents detect blocks
other_sense_range = np.inf  # the range with which agents detect other objects (walls, doors, etc.)
agent_memory_decay = 5  # we want to memorize states for seconds / tick_duration ticks
fov_occlusion = True

def add_drop_off_zones(builder, exp_version):
    if exp_version == "experiment":
        nr_drop_zones = 1
        for nr_zone in range(nr_drop_zones):
            builder.add_area((23,8), width=1, height=8, name=f"Drop off {nr_zone}", visualize_opacity=0.5, visualize_colour=drop_off_color, drop_zone_nr=nr_zone,
                is_drop_zone=True, is_goal_block=False, is_collectable=False) 
    if exp_version == "trial":
        nr_drop_zones = 1
        for nr_zone in range(nr_drop_zones):
            builder.add_area((17,7), width=1, height=4, name=f"Drop off {nr_zone}",visualize_opacity=0.5, visualize_colour=drop_off_color, drop_zone_nr=nr_zone,
                is_drop_zone=True, is_goal_block=False, is_collectable=False) 
            
def add_agents(builder, condition, exp_version):
    sense_capability = SenseCapability({AgentBody: agent_sense_range,
                                        CollectableBlock: block_sense_range,
                                        None: other_sense_range,
                                        ObstacleObject: 1})

    for team in range(nr_teams):
        team_name = f"Team {team}"
        # Add agents
        nr_agents = agents_per_team - human_agents_per_team
        for agent_nr in range(nr_agents):
            if exp_version=="experiment" and condition=="baseline":
                brain = BaselineAgent(slowdown=8)
            if exp_version=="experiment" and condition=="performance":
                brain = PerformanceAgent(slowdown=8)
            if exp_version=="experiment" and condition=="trust":
                brain = TrustAgent(slowdown=8)
            if exp_version=="experiment" and condition=="workload":
                brain = WorkloadAgent(slowdown=8)
            if exp_version=="trial" and condition=="tutorial":
                brain = TutorialAgent(slowdown=8)

            if exp_version=="experiment":
                loc = (22,11)
            else:
                loc = (16,8)
            builder.add_agent(loc, brain, team=team_name, name="RescueBot",customizable_properties = ['score','followed','ignored'], score=0,followed=0,ignored=0,
                              sense_capability=sense_capability, is_traversable=True, img_name="/images/robot-final4.svg", visualize_when_busy=True)

        # Add human agents
        for human_agent_nr in range(human_agents_per_team):
            brain = HumanBrain(max_carry_objects=1, grab_range=1, drop_range=0, remove_range=1, fov_occlusion=fov_occlusion)
            if exp_version=="experiment":
                loc = (22,12)
            else:
                loc = (16,9)
            builder.add_human_agent(loc, brain, team=team_name, name="Human",
                                    key_action_map=key_action_map, sense_capability=sense_capability, is_traversable=True, visualize_shape=1, visualize_colour='#9a9083', visualize_when_busy=False)

def create_builder(exp_version, condition):
    # Set numpy's random generator
    np.random.seed(random_seed)

    # Create the goal
    if exp_version == "experiment":
        goal = CollectionGoal(max_nr_ticks=9600)
    if exp_version == "trial":
        goal = CollectionGoal(max_nr_ticks=10000000000)
    # Create our world builder
    if exp_version=="experiment":
        builder = WorldBuilder(shape=[25,24], tick_duration=tick_duration, run_matrx_api=True,
                           run_matrx_visualizer=False, verbose=verbose, simulation_goal=goal, visualization_bg_clr='#9a9083')
    else:
        builder = WorldBuilder(shape=[19,19], tick_duration=tick_duration, run_matrx_api=True,random_seed=random_seed,
                           run_matrx_visualizer=False, verbose=verbose, simulation_goal=goal, visualization_bg_clr='#9a9083')
    if exp_version=="experiment":
        current_exp_folder = datetime.now().strftime("exp_"+condition+"_at_time_%Hh-%Mm-%Ss_date_%dd-%mm-%Yy")
        logger_save_folder = os.path.join("experiment_logs", current_exp_folder)
        builder.add_logger(ActionLogger, log_strategy=1, save_path=logger_save_folder, file_name_prefix="actions_")
        builder.add_logger(MessageLogger, save_path=logger_save_folder, file_name_prefix="messages_")

    if exp_version == "trial":
        builder.add_room(top_left_location=(0, 0), width=19, height=19, name="world_bounds", wall_visualize_colour="#1F262A")
        # Create the rooms
        builder.add_room(top_left_location=(1,1), width=5, height=4, name='area 1', door_locations=[(3,4)],doors_open=True, wall_visualize_colour=wall_color, 
            with_area_tiles=True, area_visualize_colour=room_colors[0],area_visualize_opacity=0.0, door_open_colour='#9a9083', area_custom_properties={'doormat':(3,5)})
        builder.add_room(top_left_location=(7,1), width=5, height=4, name='area 2', door_locations=[(9,4)],doors_open=True, wall_visualize_colour=wall_color, 
            with_area_tiles=True, area_visualize_colour=room_colors[0],area_visualize_opacity=0.0,door_open_colour='#9a9083', area_custom_properties={'doormat':(9,5)})
        builder.add_room(top_left_location=(13,1), width=5, height=4, name='area 3', door_locations=[(15,4)],doors_open=True, wall_visualize_colour=wall_color, 
            with_area_tiles=True, area_visualize_colour=room_colors[0],area_visualize_opacity=0.0,door_open_colour='#9a9083', area_custom_properties={'doormat':(15,5)})
        builder.add_room(top_left_location=(1,7), width=5, height=4, name='area 4', door_locations=[(3,7)],doors_open=True, wall_visualize_colour=wall_color, 
            with_area_tiles=True, area_visualize_colour=room_colors[0],area_visualize_opacity=0.0,door_open_colour='#9a9083', area_custom_properties={'doormat':(3,6)})
        builder.add_room(top_left_location=(7,7), width=5, height=4, name='area 5', door_locations=[(9,7)],doors_open=True, wall_visualize_colour=wall_color, 
            with_area_tiles=True, area_visualize_colour=room_colors[0],area_visualize_opacity=0.0,door_open_colour='#9a9083', area_custom_properties={'doormat':(9,6)})
        builder.add_room(top_left_location=(1,13), width=5, height=4, name='area 6', door_locations=[(3,16)],doors_open=True, wall_visualize_colour=wall_color, 
            with_area_tiles=True, area_visualize_colour=room_colors[0],area_visualize_opacity=0.0,door_open_colour='#9a9083', area_custom_properties={'doormat':(3,17)})
        builder.add_room(top_left_location=(7,13), width=5, height=4, name='area 7', door_locations=[(9,16)],doors_open=True, wall_visualize_colour=wall_color, 
            with_area_tiles=True, area_visualize_colour=room_colors[0],area_visualize_opacity=0.0,door_open_colour='#9a9083', area_custom_properties={'doormat':(9,17)})
        builder.add_room(top_left_location=(13,13), width=5, height=4, name='area 8', door_locations=[(15,16)],doors_open=True, wall_visualize_colour=wall_color, 
            with_area_tiles=True, area_visualize_colour=room_colors[0],area_visualize_opacity=0.0,door_open_colour='#9a9083', area_custom_properties={'doormat':(15,17)})

        for loc in [(1,1),(2,1),(3,1),(4,1),(5,1),(1,2),(1,3),(1,4),(2,4),(4,4),(5,4),(5,3),(5,2),(7,1),(8,1),(9,1),(10,1),(11,1),(7,2),(7,3),(7,4),(8,4),(11,2),(11,3),(11,4),(10,4),
                    (13,1),(14,1),(15,1),(16,1),(17,1),(13,1),(14,1),(15,1),(16,1),(17,1),(13,2),(13,3),(13,4),(14,4),(16,4),(17,4),(17,3),(17,2),
                    (1,7),(1,8),(1,9),(1,10),(2,10),(3,10),(4,10),(5,10),(5,9),(5,8),(5,7),(4,7),(2,7),
                    (7,7),(7,8),(7,9),(7,10),(8,10),(9,10),(10,10),(11,10),(11,9),(11,8),(11,7),(10,7),(8,7),
                    (1,13),(2,13),(3,13),(4,13),(5,13),(1,14),(1,15),(1,16),(2,16),(4,16),(5,16),(5,15),(5,14),(5,13),
                    (7,13),(8,13),(9,13),(10,13),(11,13),(7,14),(7,15),(7,16),(8,16),(10,16),(11,16),(11,15),(11,14),
                    (13,13),(14,13),(15,13),(16,13),(17,13),(13,14),(13,15),(13,16),(14,16),(17,14),(17,15),(17,16),(16,16)]:
            builder.add_object(loc,'roof', EnvObject,is_traversable=True, is_movable=False, visualize_shape='img',img_name="/images/roof-final5.svg")

        builder.add_object((3,4), 'fire',ObstacleObject,visualize_shape='img',img_name="/images/fire2.svg", visualize_size=2, percentage_lel=5, weight=False)
        builder.add_object((3,8), 'fire',ObstacleObject,visualize_shape='img',img_name="/images/fire2.svg", visualize_size=1.75, percentage_lel=5, weight=False)
        #builder.add_object((2,9), 'fire',ObstacleObject,visualize_shape='img',img_name="/images/fire2.svg", visualize_size=1.25)
        builder.add_object((9,4),'iron',ObstacleObject,visualize_shape='img',img_name="/images/girder.svg",visualize_size=1, percentage_lel=False, weight=100)
        builder.add_object((3,7),'iron',ObstacleObject,visualize_shape='img',img_name="/images/girder.svg",visualize_size=1.25, percentage_lel=False, weight=200)
        builder.add_object((3,16),'fire',ObstacleObject,visualize_shape='img',img_name="/images/fire2.svg",visualize_size=3.5, percentage_lel=5, weight=False)
        builder.add_object((9,16),'iron',ObstacleObject,visualize_shape='img',img_name="/images/girder.svg",visualize_size=0.75, percentage_lel=False, weight=50)
        #builder.add_object((15,16),'stone',ObstacleObject,visualize_shape='img',img_name="/images/stone-small.svg",visualize_size=1.5)
        builder.add_object((9,7),'fire',ObstacleObject,visualize_shape='img',img_name="/images/fire2.svg",visualize_size=1.75, percentage_lel=5, weight=False)

        builder.add_object((8,2),'mildly injured elderly woman in area 2', callable_class=CollectableBlock, 
            visualize_shape='img',img_name="/images/mildly injured elderly woman.svg")
        builder.add_object((16,15),'mildly injured man in area 8', callable_class=CollectableBlock, 
            visualize_shape='img',img_name="/images/mildly injured man.svg")
        builder.add_object((3,9),'mildly injured elderly man in area 4', callable_class=CollectableBlock, 
            visualize_shape='img',img_name="/images/mildly injured elderly man.svg")
        #builder.add_object((2,14),'healthy girl in area 6', callable_class=CollectableBlock, 
        #    visualize_shape='img',img_name="/images/healthy girl.svg")
        builder.add_object((8,9),'mildly injured woman in area 5', callable_class=CollectableBlock, 
            visualize_shape='img',img_name="/images/mildly injured woman.svg")
        #builder.add_object((16,15),'mildly injured boy in area 8', callable_class=CollectableBlock, 
        #    visualize_shape='img',img_name="/images/mildly injured boy.svg")
        #builder.add_object((10,3),'healthy boy in area 2', callable_class=CollectableBlock, 
        #    visualize_shape='img',img_name="/images/healthy boy.svg")
        #builder.add_object((10,8),'healthy elderly man in area 5', callable_class=CollectableBlock, 
        #    visualize_shape='img',img_name="/images/healthy elderly man.svg")
        #builder.add_object((10,15),'healthy dog in area 7', callable_class=CollectableBlock, 
        #    visualize_shape='img',img_name="/images/healthy dog.svg")

        builder.add_object((17,7),name="Collect Block", callable_class=GhostBlock,visualize_shape='img',img_name="/images/mildly injured woman.svg",drop_zone_nr=0)
        builder.add_object((17,8),name="Collect Block", callable_class=GhostBlock,visualize_shape='img',img_name="/images/mildly injured elderly woman.svg",drop_zone_nr=0)
        builder.add_object((17,9),name="Collect Block", callable_class=GhostBlock,visualize_shape='img',img_name="/images/mildly injured man.svg",drop_zone_nr=0)
        builder.add_object((17,10),name="Collect Block", callable_class=GhostBlock,visualize_shape='img',img_name="/images/mildly injured elderly man.svg",drop_zone_nr=0)

        builder.add_object(location=[3,1], is_traversable=True, is_movable=False, name="area 01 sign", img_name="/images/sign01.svg", visualize_depth=110, visualize_size=0.5)
        builder.add_object(location=[9,1], is_traversable=True, is_movable=False, name="area 02 sign", img_name="/images/sign02.svg", visualize_depth=110, visualize_size=0.55)
        builder.add_object(location=[15,1], is_traversable=True, is_movable=False, name="area 03 sign", img_name="/images/sign03.svg", visualize_depth=110, visualize_size=0.55)
        builder.add_object(location=[3,10], is_traversable=True, is_movable=False, name="area 04 sign", img_name="/images/sign04.svg", visualize_depth=110, visualize_size=0.55)
        builder.add_object(location=[9,10], is_traversable=True, is_movable=False, name="area 05 sign", img_name="/images/sign05.svg", visualize_depth=110, visualize_size=0.55)
        builder.add_object(location=[3,13], is_traversable=True, is_movable=False, name="area 06 sign", img_name="/images/sign06.svg", visualize_depth=110, visualize_size=0.55)
        builder.add_object(location=[9,13], is_traversable=True, is_movable=False, name="area 07 sign", img_name="/images/sign07.svg", visualize_depth=110, visualize_size=0.55)
        builder.add_object(location=[15,13], is_traversable=True, is_movable=False, name="area 08 sign", img_name="/images/sign08.svg", visualize_depth=110, visualize_size=0.55)

        #builder.add_object(location=[9,0], is_traversable=True, name="keyboard sign", img_name="/images/keyboard-final.svg", visualize_depth=110, visualize_size=15)
    
    add_drop_off_zones(builder, exp_version)
    add_agents(builder, condition, exp_version)

    return builder

class CollectableBlock(EnvObject):
    def __init__(self, location, name, visualize_shape, img_name):
        super().__init__(location, name, is_traversable=True, is_movable=True,
                         visualize_shape=visualize_shape,img_name=img_name,
                         visualize_size=block_size, class_callable=CollectableBlock,
                         is_drop_zone=False, is_goal_block=False, is_collectable=True)

class ObstacleObject(EnvObject):
    def __init__(self, location, name, percentage_lel, weight, visualize_shape, img_name, visualize_size):
        super().__init__(location, name, percentage_lel=percentage_lel, weight=weight, is_traversable=False, is_movable=True,
                         visualize_shape=visualize_shape,img_name=img_name,
                         visualize_size=visualize_size, class_callable=ObstacleObject,
                         is_drop_zone=False, is_goal_block=False, is_collectable=False)

class GhostBlock(EnvObject):
    def __init__(self, location, drop_zone_nr, name, visualize_shape, img_name):
        super().__init__(location, name, is_traversable=True, is_movable=False,
                         visualize_shape=visualize_shape, img_name=img_name,
                         visualize_size=block_size, class_callable=GhostBlock,
                         visualize_depth=110, drop_zone_nr=drop_zone_nr, visualize_opacity=0.5,
                         is_drop_zone=False, is_goal_block=True, is_collectable=False)


class CollectionGoal(WorldGoal):
    '''
    The goal for BW4T world (the simulator), so determines
    when the simulator should stop.
    '''
    def __init__(self, max_nr_ticks:int):
        '''
        @param max_nr_ticks the max number of ticks to be used for this task
        '''
        super().__init__()
        self.max_nr_ticks = max_nr_ticks

        # A dictionary of all drop locations. The keys is the drop zone number, the value another dict.
        # This dictionary contains as key the rank of the to be collected object and as value the location
        # of where it should be dropped, the shape and colour of the block, and the tick number the correct
        # block was delivered. The rank and tick number is there so we can check if objects are dropped in
        # the right order.
        self.__drop_off:dict = {}
        self.__drop_off_zone:dict = {}

        # We also track the progress
        self.__progress = 0
        self.__score = 0
    
    def score(self, grid_world: GridWorld):
        return self.__score

    def goal_reached(self, grid_world: GridWorld):
        if grid_world.current_nr_ticks >= self.max_nr_ticks:
            return True
        return self.isBlocksPlaced(grid_world)

    def isBlocksPlaced(self, grid_world:GridWorld):
        '''
        @return true if all blocks have been placed in right order
        '''

        if self.__drop_off =={}:  # find all drop off locations, its tile ID's and goal blocks
            self.__find_drop_off_locations(grid_world)

        # Go through each drop zone, and check if the blocks are there in the right order
        is_satisfied, progress = self.__check_completion(grid_world)

        # Progress in percentage
        self.__progress = progress / sum([len(goal_blocks)\
            for goal_blocks in self.__drop_off.values()])

        return is_satisfied

    def progress(self, grid_world:GridWorld):
        if self.__drop_off =={}:  # find all drop off locations, its tile ID's and goal blocks
            self.__find_drop_off_locations(grid_world)

        # Go through each drop zone, and check if the blocks are there in the right order
        is_satisfied, progress = self.__check_completion(grid_world)

        # Progress in percentage
        self.__progress = progress / sum([len(goal_blocks)\
            for goal_blocks in self.__drop_off.values()])
        return self.__progress

    def __find_drop_off_locations(self, grid_world):

        goal_blocks = {}  # dict with as key the zone nr and values list of ghostly goal blocks
        all_objs = grid_world.environment_objects
        for obj_id, obj in all_objs.items():  # go through all objects
            if "drop_zone_nr" in obj.properties.keys():  # check if the object is part of a drop zone
                zone_nr = obj.properties["drop_zone_nr"]  # obtain the zone number
                if obj.properties["is_goal_block"]:  # check if the object is a ghostly goal block
                    if zone_nr in goal_blocks.keys():  # create or add to the list
                        goal_blocks[zone_nr].append(obj)
                    else:
                        goal_blocks[zone_nr] = [obj]

        self.__drop_off_zone:dict = {}
        self.__drop_off:dict = {}
        for zone_nr in goal_blocks.keys():  # go through all drop of zones and fill the drop_off dict
            # Instantiate the zone's dict.
            self.__drop_off_zone[zone_nr] = {}
            self.__drop_off[zone_nr] = {}

            # Obtain the zone's goal blocks.
            blocks = goal_blocks[zone_nr].copy()

            # The number of blocks is the maximum the max number blocks to collect for this zone.
            max_rank = len(blocks)

            # Find the 'bottom' location
            bottom_loc = (-np.inf, -np.inf)
            for block in blocks:
                if block.location[1] > bottom_loc[1]:
                    bottom_loc = block.location

            # Now loop through blocks lists and add them to their appropriate ranks
            for rank in range(max_rank):
                loc = (bottom_loc[0], bottom_loc[1]-rank)

                # find the block at that location
                for block in blocks:
                    if block.location == loc:
                        # Add to self.drop_off
                        self.__drop_off_zone[zone_nr][rank] = [loc, block.properties['img_name'][8:-4], None]
                        for i in self.__drop_off_zone.keys():
                            self.__drop_off[i] = {}
                            vals = list(self.__drop_off_zone[i].values())
                            vals.reverse()
                            for j in range(len(self.__drop_off_zone[i].keys())):
                                self.__drop_off[i][j] = vals[j]

    def __check_completion(self, grid_world):
        # Get the current tick number
        curr_tick = grid_world.current_nr_ticks

        # loop through all zones, check the blocks and set the tick if satisfied
        for zone_nr, goal_blocks in self.__drop_off.items():
            # Go through all ranks of this drop off zone
            for rank, block_data in goal_blocks.items():
                loc = block_data[0]  # the location, needed to find blocks here
                shape = block_data[1]  # the desired colour
                tick = block_data[2]

                # Retrieve all objects, the object ids at the location and obtain all BW4T Blocks from it
                all_objs = grid_world.environment_objects
                obj_ids = grid_world.get_objects_in_range(loc, object_type=EnvObject, sense_range=0)
                blocks = [all_objs[obj_id] for obj_id in obj_ids
                          if obj_id in all_objs.keys() and "is_collectable" in all_objs[obj_id].properties.keys()]
                blocks = [b for b in blocks if b.properties["is_collectable"]]

                # Check if there is a block, and if so if it is the right one and the tick is not yet set, then set the
                # current tick.
                if len(blocks) > 0 and blocks[0].properties['img_name'][8:-4] == shape and \
                        tick is None:
                    self.__drop_off[zone_nr][rank][2] = curr_tick
                    if 'critical' in blocks[0].properties['img_name'][8:-4]:
                        self.__score+=6
                    if 'mild' in blocks[0].properties['img_name'][8:-4]:
                        self.__score+=3
                # if there is no block, reset its tick to None

                elif len(blocks) == 0:
                    if self.__drop_off[zone_nr][rank][2] != None:
                        self.__drop_off[zone_nr][rank][2] = None
                        if rank in [0,1,2,3]:
                            self.__score-=6
                        if rank in [4,5,6,7]:
                            self.__score-=3
                    #self.__score

        # Now check if all blocks are collected in the right order
        is_satisfied = True
        progress = 0
        for zone_nr, goal_blocks in self.__drop_off.items():
            zone_satisfied = True
            ticks = [goal_blocks[r][2] for r in range(len(goal_blocks))]  # list of ticks in rank order

            # check if all ticks are increasing
            for tick in ticks:
                if tick is not None:
                    progress += 1
            if None in ticks:
                zone_satisfied = False
            # update our satisfied boolean
            is_satisfied = is_satisfied and zone_satisfied
        agent = grid_world.registered_agents['rescuebot']
        agent.change_property('score',self.__score)

        return is_satisfied, progress
