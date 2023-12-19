# https://stable-baselines3.readthedocs.io/en/master/guide/custom_env.html
import random
from typing import Any

import gymnasium as gym
from gymnasium.spaces import MultiDiscrete, Dict, MultiBinary, Box


from src.funcs import create_distance_matrix, filler, multi_disc
import numpy as np

class WienEnv(gym.Env):
	metadata = {"render_modes": ["human"], "render_fps": 30}

	def __init__(self, place_count: int = 30, vehicle_count: int = 10, package_count: int = 10):
		"""
		Custom Environment that follows gym interface. This Wien Environment creates a space for the vehicle routing problem within specific places in vienna.
		:param place_count: number of places to use, out of the 80 total

		"""
		assert 1 <= place_count <= 80, print('only 80 places available')

		super().__init__()

		self.clock = 0
		self.place_count = place_count
		self.vehicle_count = vehicle_count
		self.package_count = package_count
		self.total_travel = 0
		self.distance_matrix = create_distance_matrix()

		# initial values for environment itself. This will also be returned during self.step()
		self.environment, _ = self.reset()

		max_distance = np.amax(self.distance_matrix)  # 91

		self.observation_space = Dict({
			'distances': Box(low=0, high=max_distance, shape=(80, 80), dtype=int),

			'v_id': multi_disc(vehicle_count, vehicle_count+1),
			'v_available': MultiBinary(vehicle_count),
			'v_transit_start': multi_disc(vehicle_count, place_count),
			'v_transit_end': multi_disc(vehicle_count, place_count, True),
			'v_transit_remaining': multi_disc(vehicle_count, max_distance),
			'v_has_package': multi_disc(vehicle_count, package_count, True),

			'p_id': multi_disc(package_count, package_count+1),
			'p_location_current': multi_disc(package_count, place_count),
			'p_location_target':  multi_disc(package_count, place_count),
			'p_carrying_vehicle': multi_disc(package_count, vehicle_count, True),
			'p_delivered': MultiBinary(package_count),

		})

		# possible values are in the range of the number of locations
		self.action_space = MultiDiscrete(vehicle_count * [place_count])

	def step(self, action) -> tuple[dict, int, bool, bool, dict[str, Any]]:
		"""
		Run one timestep of the environment’s dynamics using the agent actions. First the vehicle location dispatch decisions are assigned to each vehicle where a dispatch is valid (the vehicle is available). When a vehicle is dispatched its remaining transit time is also calculated. Second each vehicle that is in transit is progressed by 1 unit.

		:param action: place for each vehicle to go to in the format MultiDiscrete(vehicle_count * [place_count])
		:return: observation, reward, terminated, truncated, info
		"""
		assert action.size == self.vehicle_count
		for dispatch_location in action:
			assert dispatch_location in range(self.place_count)
		self.clock += 1

		for v, vehicle_decision in enumerate(action):
			def vehi(key): return self.environment[key][v]
			def vehi_set(key, val): self.environment[key][v] = val

			if vehi('v_transit_remaining') == 0:
				vehi_set('v_transit_end', vehicle_decision)
				vehi_set(
					'v_transit_remaining',
					self.distance_matrix[vehi('v_transit_start')][vehicle_decision]
				)

		# progress each vehicle
		for v in range(self.vehicle_count):
			if self.environment['v_transit_remaining'][v] > 0:
				self.environment['v_transit_remaining'][v] -= 1
				self.total_travel += 1

		return (
			self.environment,
			self.automate_packages(),  # drop off & pick up any packages
			all(self.environment['p_delivered']),
			False,
			{'time': self.clock},
		)

	def reset(self, seed=None, verbose=False) -> tuple:
		"""
		Sets the environment back to its original state. The environment object is re-initialized with random vehicle & package positions to be delivered.
		:param verbose: print out package location data
		:return: dict { environment, info }
		"""
		self.clock = 0
		self.total_travel = 0

		environment_object = {
			'distances': create_distance_matrix(),

			'v_id': np.array(range(1, self.vehicle_count+1)),
			'v_available': filler(self.vehicle_count, True),
			'v_transit_start': filler(
				self.vehicle_count, self.place_count, True
			),
			'v_transit_end': filler(self.vehicle_count),
			'v_transit_remaining': filler(self.vehicle_count, 0),
			'v_has_package': filler(self.vehicle_count),

			'p_id': np.array(range(1, self.package_count+1)),
			'p_location_current': filler(
				self.package_count, self.place_count, True
			),
			'p_location_target': filler(self.package_count),
			'p_carrying_vehicle': filler(self.package_count),
			'p_delivered': filler(self.package_count, False)
		}

		if verbose:
			print(
				f"\ncurr: {len(environment_object['p_location_current'])}"
				f"\ntarg: {len(environment_object['p_location_target'])}"
			)

		# fill target destinations with something other than their starting location
		for p, place in enumerate(environment_object['p_location_current']):
			valid_values = list(range(self.place_count))
			valid_values.remove(place)
			if verbose:
				print(f'\nindex: {p}')
			environment_object['p_location_target'][p] = random.choice(valid_values)

		return (
			environment_object,
			{  # extra info
				'test': 'test'
			}
		)

	def automate_packages(self):
		"""
		automatically pick up packages when vehicle passes over, automatically drop off at location
		:return: number of packages that have been delivered for reward function
		"""
		reward = 0
		for p in range(self.package_count):

			# helper functions to shorten navigation of the object environment dictionary
			def pack(key): return self.environment[key][p]
			def pack_set(key, val): self.environment[key][p] = val

			# set any packages to delivered if they are in their target location
			if pack('p_location_current') == pack('p_location_target') and not pack('p_delivered'):
				pack_set('p_delivered', True)

			# undelivered package currently not on a vehicle
			if not pack('p_delivered') and pack('p_carrying_vehicle') == 0:
				# make sure vehicles fulfill any request at any location if possible
				for v in range(self.vehicle_count):
					def vehi(key): return self.environment[key][v]
					def vehi_set(key, val): self.environment[key][v] = val

					# if an available vehicle passes by, pick up the package
					if (vehi('v_available') and
						vehi('v_transit_start') == pack('p_location_current') and
						vehi('v_transit_remaining') == 0
					):
						vehi_set('v_available', False)
						vehi_set('v_has_package', p)
						pack_set('p_carrying_vehicle', v)

			# if a package is not delivered but on a vehicle, check if it has been delivered
			elif not pack('p_delivered') and pack('p_carrying_vehicle') != 0:

				# same helper functions as before, but now the index is its carrying vehicle
				def vehi(key):
					return self.environment[key][pack('p_carrying_vehicle')]
				def vehi_set(key, val):
					self.environment[key][pack('p_carrying_vehicle')] = val

				# check if package could be delivered
				if (vehi('v_transit_start') == pack('p_location_target') and
					vehi('v_transit_remaining') == 0
				):
					pack_set('p_carrying_vehicle', 0)
					pack_set('p_delivered', True)
					vehi_set('v_available', True)
					vehi_set('v_has_package', 0)
					reward += 1

		return reward


#test = WienEnv(20).reset(verbose=True)

