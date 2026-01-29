import pyhop

'''begin operators'''

def op_punch_for_wood(state, ID):
	if state.time[ID] >= 4:
		state.wood[ID] += 1
		state.time[ID] -= 4
		return state
	return False

# Cheatsheet comments here to refer to while coding:
def op_craft_wooden_axe_at_bench(state, ID):
	# state: a pyhop.State object. Attributes like state.time, state.plank, etc. are dictionaries mapping agent IDs to counts.
	#ID: a string identifying the agent performing the action

	# Precondtions: check the agent has at least 1 time unit available, a bench, at least 3 planks, and at least 2 sticks
	if state.time[ID] >= 1 and state.bench[ID] >= 1 and state.plank[ID] >= 3 and state.stick[ID] >=2:
		# Effect: increement the count of wooden aces for this agent
		state.wooden_axe[ID] += 1
		# Consume the required materials
		state.plank[ID] -= 3
		state.stick[ID] -= 2
		# Spend the time cost of crafting 
		state.time[ID] -= 1
		# Return the modified state to indicate the operator succeeded
		return state
	# Preconditions not met, operator fails - pyhop will try other methods
	return False

# Overview: operator to craft plank -> need 1 unit of time and 1 wood for 4 planks
def op_craft_plank(state, ID): 
	if state.time[ID] >= 1 and state.wood[ID] >= 1:
		state.plank[ID] += 4
		state.wood[ID] -= 1
		state.time[ID] -= 1
		return state
	return False

def op_craft_stick(state, ID):
	if state.time[ID] >= 1 and state.plank[ID] >= 2:
		state.stick[ID] += 4
		state.plank[ID] -= 2
		state.time[ID] -= 1
		return state
	return False

def op_craft_bench(state, ID):
	if state.time[ID] >= 1 and state.plank[ID] >= 4:
		state.bench[ID] += 1
		state.plank[ID] -= 4
		state.time[ID] -= 1
		return state
	return False

def op_wooden_axe_for_wood(state, ID):
	if state.time[ID] >= 2 and state.wooden_axe[ID] >= 1:
		state.wood[ID] += 1
		state.time[ID] -= 2
		return state
	return False

# Add in new operators 
pyhop.declare_operators(op_punch_for_wood, op_craft_wooden_axe_at_bench, op_craft_plank, op_craft_stick, op_craft_bench, op_wooden_axe_for_wood)

'''end operators'''

def check_enough(state, ID, item, num):
	if getattr(state,item)[ID] >= num: return []
	return False

def produce_enough(state, ID, item, num):
	return [('produce', ID, item), ('have_enough', ID, item, num)]

def produce(state, ID, item):
	if item == 'wood': 
		return [('produce_wood', ID)]
	elif item == 'wooden_axe':
		# if the agent already has an axe, no need to craft another (since I was having issues here)
		if state.wooden_axe[ID] >= 1:
			return []
		# built-in limit: only one wooden axe can be made
		if state.made_wooden_axe[ID] is True:
			return False
		state.made_wooden_axe[ID] = True
		return [('produce_wooden_axe', ID)]
	elif item == 'plank':
		return [('produce_plank', ID)]
	elif item == 'stick':
		return [('produce_stick', ID)]
	elif item == 'bench':
		return [('produce_bench', ID)]
	else:
		return False

# Method for having enough wood -> running into issues with have_enough for wood, so writing a custom method here
def have_enough_wood(state, ID, item, num):
	if item != 'wood':
		return False
	# already enough
	if state.wood[ID] >= num:
		return []
	# if we already have an axe, use it to produce wood
	if state.wooden_axe[ID] >= 1:
		return [('produce', ID, 'wood'), ('have_enough', ID, 'wood', num)]
	# compute how many punches we can still do
	punches_possible = state.time[ID] // 4
	remaining = num - state.wood[ID]
	# if punching alone can reach the goal, do it
	if punches_possible >= remaining:
		return [('produce', ID, 'wood'), ('have_enough', ID, 'wood', num)]
	# otherwise, try to produce an axe first (may require some punching to get materials)
	return [('produce', ID, 'wooden_axe'), ('have_enough', ID, 'wood', num)]

pyhop.declare_methods('have_enough', have_enough_wood, check_enough, produce_enough)
pyhop.declare_methods('produce', produce)

'''begin recipe methods'''

def punch_for_wood(state, ID):
	return [('op_punch_for_wood', ID)]

def craft_wooden_axe_at_bench(state, ID):
	return [('have_enough', ID, 'bench', 1), ('have_enough', ID, 'stick', 2), ('have_enough', ID, 'plank', 3), ('op_craft_wooden_axe_at_bench', ID)]

# Add recipes for added operators
def wooden_axe_for_wood(state, ID):
	return [('have_enough', ID, 'wooden_axe', 1), ('op_wooden_axe_for_wood', ID)]

def craft_plank(state, ID):
	return [('have_enough', ID, 'wood', 1), ('op_craft_plank', ID)]

def craft_stick(state, ID):
	return [('have_enough', ID, 'plank', 2), ('op_craft_stick', ID)]

def craft_bench(state, ID):
	return [('have_enough', ID, 'plank', 4), ('op_craft_bench', ID)]

# Recipe method for producing wood
def produce_wood_method(state, ID):
	# prefer using an existing axe, otherwise punch for wood
	if state.wooden_axe[ID] >= 1:
		return [('have_enough', ID, 'wooden_axe', 1), ('op_wooden_axe_for_wood', ID)]
	else:
		return [('op_punch_for_wood', ID)]

pyhop.declare_methods('produce_wood', produce_wood_method)
pyhop.declare_methods('produce_wooden_axe', craft_wooden_axe_at_bench)
pyhop.declare_methods('produce_plank', craft_plank)
pyhop.declare_methods('produce_stick', craft_stick)
pyhop.declare_methods('produce_bench', craft_bench)

'''end recipe methods'''

# declare state
state = pyhop.State('state')
state.wood = {'agent': 0}
state.time = {'agent': 46}
state.wooden_axe = {'agent': 0}
state.made_wooden_axe = {'agent': False}
# Initialize new resources to zero
state.plank = {'agent': 0}
state.stick = {'agent': 0}
state.bench = {'agent': 0} 

# pyhop.print_operators()
# pyhop.print_methods()

pyhop.pyhop(state, [('have_enough', 'agent', 'wood', 1)], verbose=1)
pyhop.pyhop(state, [('have_enough', 'agent', 'wood', 12)], verbose=1)