from typing import Any
from gymnasium.spaces import MultiDiscrete
import pandas as pd
import numpy as np

def create_distance_matrix(buffer: int = 2) -> np.array:
	"""
	Uses the travel times file to generate a matrix of the distances between them, rounded to the nearest integer + 2
	:param buffer: increase all values by a certain amount before assigning to matrix. The default value is 2 minutes as an approximate time it takes to pickup/unload a package
	:return: numpy array of shape (80, 80)
	"""

	distances = pd.read_csv(
		'../data/travel_times/wien_travel_times.csv',
		sep = ';',
		encoding = "ISO-8859-1"
	)

	distances = distances[distances['mode'] == 'bicycling']

	dist_matrix = np.zeros((80, 80), dtype=int)

	for place1 in range(80):
		for place2 in range(place1+1, 80):
			# set both values on both sides of the diagonal
			dist_matrix[place1, place2], dist_matrix[place2, place1] = 2 * [round(
				distances[
					(distances['place1index'] == place1) &
					(distances['place2index'] == place2)
				]['duration'].values[0]
			) + buffer]  # artificially increase all transit times to simulate loading times

	return dist_matrix


def filler(amount: int, fill_with: Any = 0, random_int_up_to_fill: bool = False) -> np.array:
	"""
	:param amount: length of list to return
	:param fill_with: value to fill the list with, or in the case of randomization fill with a random integer in range of [0, fill_with)
	:param random_int_up_to_fill: choice to randomize an integer range
	:return: np array of shape (amount,)
	"""
	import random
	import numpy as np
	if random_int_up_to_fill:
		return np.array([random.randrange(fill_with) for _ in range(amount)])
	else:
		return np.array([fill_with for _ in range(amount)])


def multi_disc(amount: int, value_range: int, zero_as_none = False) -> MultiDiscrete:
	"""
	Shorthand for `MultiDiscrete(filler())` used by the observation space. This essentially creates a `MultiDiscrete` containing `amount` number of `Discrete` spaces with the range of `value_range`.
	:param amount: Number of `Discrete` objects in the return object
	:param value_range: The range of each `Discrete` object, indicating the possible range of values that a single Discrete element could be.
	:param zero_as_none: Whether to shift the range of each Discrete object by 1 so that 0 represents the empty value. This is used by environment variables that could have a `None` value, such as when a vehicle contains no package.
	:return: A `MultiDiscrete` object of shape (amount, value_range)
	"""
	from gymnasium.spaces import MultiDiscrete
	if zero_as_none:
		return MultiDiscrete(filler(amount, value_range+1))
	else:
		return MultiDiscrete(filler(amount, value_range))

