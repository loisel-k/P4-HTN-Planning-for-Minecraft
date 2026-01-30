import pyhop
import json

def check_enough(state, ID, item, num):
	if getattr(state,item)[ID] >= num: return []
	return False

def produce_enough(state, ID, item, num):
	return [('produce', ID, item), ('have_enough', ID, item, num)]

pyhop.declare_methods('have_enough', check_enough, produce_enough)

def produce(state, ID, item):
	return [('produce_{}'.format(item), ID)]

pyhop.declare_methods('produce', produce)

# Rule is a dictionary with keys: 'Time', 'Requires', 'Consumes', 'Produces'
def make_method(name, rule):
	# Each recipe should produce at least one item; use the first produced item as the product
	produces = rule.get('Produces', {})
	if not produces:
		return None
	# product name and quantity
	prod_item = list(produces.keys())[0]
	prod_qty = produces[prod_item]

	# normalize recipe name to match operator naming in declare_operators
	normalized = name.replace(' ', '_').replace('-', '_')
	normalized = normalized.replace('(', '').replace(')', '').replace(',', '')
	op_task_name = f"op_{normalized}"

	def method(state, ID):
		subtasks = []
		# First, ensure required tools (Requirements are not consumed)
		for tool, n in rule.get('Requires', {}).items():
			subtasks.append(('have_enough', ID, tool, n))
		# Ensure consumed inputs are available (produce them as needed)
		# Order input 
		for item, n in rule.get('Consumes', {}).items():
			subtasks.append(('have_enough', ID, item, n))
		# Perform operator to produce item!
		subtasks.append((op_task_name, ID))
		return subtasks

	# Name the method as assignment lays out
	method.__name__ = f"produce_{prod_item}__via__{normalized}"
	return method

def declare_methods(data):
	# some recipes are faster than others for the same product even though they might require extra tools
	# Build a mapping from produced item -> list of methods that produce it
	prod_to_methods = {}

	for name, rule in data['Recipes'].items():
		m = make_method(name, rule)
		if m is None:
			continue
		produces = rule.get('Produces', {})
		if not produces:
			continue
		prod_item = list(produces.keys())[0]
		prod_to_methods.setdefault(prod_item, [])
		prod_to_methods[prod_item].append((m, rule.get('Time', 0)))

	# Declare methods to pyhop, ordering by recipe time (fastest first)
	for prod_item, methods_and_times in prod_to_methods.items():
		methods_and_times.sort(key=lambda x: x[1])
		methods = [mt[0] for mt in methods_and_times]
		pyhop.declare_methods(f'produce_{prod_item}', *methods)

def make_operator(rule):
	def operator(state, ID):
		# Check time first
		if state.time[ID] < rule['Time']:
			return False

		# Check required tools (not consumed)
		requires = rule.get('Requires', {})
		for item, num in requires.items():
			if getattr(state, item)[ID] < num:
				return False

		# Check consumed inputs
		consumes = rule.get('Consumes', {})
		for item, num in consumes.items():
			if getattr(state, item)[ID] < num:
				return False

		# Apply effects: consume inputs
		for item, num in consumes.items():
			getattr(state, item)[ID] -= num

		# Apply effects: produce outputs
		for item, num in rule['Produces'].items():
			getattr(state, item)[ID] += num

		# Deduct time cost
		state.time[ID] -= rule['Time']
		return state
	return operator

def declare_operators(data):
	# your code here
	# hint: call make_operator, then declare the operator to pyhop using pyhop.declare_operators(o1, o2, ..., ok)
	ops = []
	for name, rule in data['Recipes'].items():
		op = make_operator(rule)
		normalized = name.replace(' ', '_').replace('-', '_')
		normalized = normalized.replace('(', '').replace(')', '').replace(',', '')
		op.__name__ = f"op_{normalized}"
		ops.append(op)
	pyhop.declare_operators(*ops)

def add_heuristic(data, ID):
	# prune search branch if heuristic() returns True
	# do not change parameters to heuristic(), but can add more heuristic functions with the same parameters: 
	# e.g. def heuristic2(...); pyhop.add_check(heuristic2)
	def heuristic(state, curr_task, tasks, plan, depth, calling_stack):
		# Prevent simple infinite recursion: if we're trying to produce an item
		# that's already on the calling stack as a produce request, prune.
		# curr_task may be like ('produce', ID, item) or ('have_enough', ID, item, num)
		try:
			tname = curr_task[0]
		except Exception:
			return False

		# find the target item if this is a produce/have_enough call
		target_item = None
		if tname == 'produce' and len(curr_task) >= 3:
			target_item = curr_task[2]
		elif tname == 'have_enough' and len(curr_task) >= 4:
			target_item = curr_task[2]

		if target_item is not None:
			# if another produce/have_enough for same item exists in the calling stack, prune
			for t in calling_stack:
				if not isinstance(t, (list, tuple)):
					continue
				if len(t) >= 3 and (t[0] == 'produce' or t[0] == 'have_enough') and t[2] == target_item:
					return True

		# Simple depth cap to avoid insane recursion (safeguard)
		if depth > 30:
			return True

		return False # if True, prune this branch

	pyhop.add_check(heuristic)

def define_ordering(data, ID):
	# if needed, use the function below to return a different ordering for the methods
	# note that this should always return the same methods, in a new order, and should not add/remove any new ones
	def reorder_methods(state, curr_task, tasks, plan, depth, calling_stack, methods):
		return methods
	
	pyhop.define_ordering(reorder_methods)

def set_up_state(data, ID):
	state = pyhop.State('state')
	setattr(state, 'time', {ID: data['Problem']['Time']})

	for item in data['Items']:
		setattr(state, item, {ID: 0})

	for item in data['Tools']:
		setattr(state, item, {ID: 0})

	for item, num in data['Problem']['Initial'].items():
		setattr(state, item, {ID: num})

	return state

def set_up_goals(data, ID):
	goals = []
	for item, num in data['Problem']['Goal'].items():
		goals.append(('have_enough', ID, item, num))

	return goals

if __name__ == '__main__':
	import sys
	rules_filename = 'crafting.json'
	if len(sys.argv) > 1:
		rules_filename = sys.argv[1]

	with open(rules_filename) as f:
		data = json.load(f)

	state = set_up_state(data, 'agent')
	goals = set_up_goals(data, 'agent')

	declare_operators(data)
	declare_methods(data)
	add_heuristic(data, 'agent')
	define_ordering(data, 'agent')

	#pyhop.print_operators()
	# pyhop.print_methods()

	# Hint: verbose output can take a long time even if the solution is correct; 
	# try verbose=1 if it is taking too long
	pyhop.pyhop(state, goals, verbose=3)
	# pyhop.pyhop(state, [('have_enough', 'agent', 'cart', 1),('have_enough', 'agent', 'rail', 20)], verbose=3)
