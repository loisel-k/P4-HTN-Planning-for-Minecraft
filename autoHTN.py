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
		for item, n in rule.get('Consumes', {}).items():
			subtasks.append(('have_enough', ID, item, n))
		# Perform operator to produce item!
		subtasks.append((op_task_name, ID))
		return subtasks

	# Name the method as assignment lays out
	method.__name__ = f"produce_{prod_item}__via__{normalized}"
	method._rule = rule
	method._produces = prod_item
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
		time_cost = rule.get('Time', 0)
		qty = produces[prod_item]
		time_per_unit = time_cost / float(qty) if qty else time_cost
		prod_to_methods[prod_item].append((m, time_per_unit))

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
	min_time_per_unit = {}
	base_producible = set()
	for _, rule in data.get('Recipes', {}).items():
		produces = rule.get('Produces', {})
		if not produces:
			continue
		item = list(produces.keys())[0]
		qty = produces[item]
		time_cost = rule.get('Time', 0)
		time_per_unit = time_cost / float(qty) if qty else time_cost
		if item not in min_time_per_unit or time_per_unit < min_time_per_unit[item]:
			min_time_per_unit[item] = time_per_unit
		if not rule.get('Requires') and not rule.get('Consumes'):
			base_producible.add(item)
	tools_set = set(data.get('Tools', []))

	def heuristic(state, curr_task, tasks, plan, depth, calling_stack):
		if not isinstance(curr_task, (list, tuple)) or not curr_task:
			return False
		tname = curr_task[0]

		# Cycle check: prune direct self-recursion for non-base items
		if tname == 'produce' and len(curr_task) >= 3:
			item = curr_task[2]
			if calling_stack:
				last = calling_stack[-1]
				if isinstance(last, (list, tuple)) and len(last) >= 3 and last[0] == 'produce' and last[2] == item:
					if item not in base_producible:
						return True
			# Avoid making extra tools when one already exists
			if item in tools_set and getattr(state, item)[ID] >= 1:
				return True

		# Time feasibility check for have_enough
		if tname == 'have_enough' and len(curr_task) >= 4:
			item = curr_task[2]
			num = curr_task[3]
			current = getattr(state, item)[ID]
			if current >= num:
				return False
			if state.time[ID] <= 0:
				return True
			time_per_unit = min_time_per_unit.get(item)
			if time_per_unit is not None:
				needed = num - current
				if needed * time_per_unit > state.time[ID]:
					return True

		# Simple depth cap to avoid extreme recursion
		if depth > 120:
			return True

		return False # if True, prune this branch

	pyhop.add_check(heuristic)

def define_ordering(data, ID):
	# if needed, use the function below to return a different ordering for the methods
	# note that this should always return the same methods, in a new order, and should not add/remove any new ones
	def reorder_methods(state, curr_task, tasks, plan, depth, calling_stack, methods):
		target_item = None
		if isinstance(curr_task, (list, tuple)) and curr_task:
			if isinstance(curr_task[0], str) and curr_task[0].startswith('produce_'):
				target_item = curr_task[0][len('produce_'):]
		scored = []
		fallback = []
		for m in methods:
			rule = getattr(m, '_rule', None)
			if rule is None:
				fallback.append(m)
				continue
			produces = rule.get('Produces', {})
			if not produces:
				fallback.append(m)
				continue
			item = list(produces.keys())[0]
			qty = produces[item]
			time_cost = rule.get('Time', 0)
			time_per_unit = time_cost / float(qty) if qty else time_cost
			unmet_tools = 0
			tool_priority = 0
			for tool, n in rule.get('Requires', {}).items():
				if getattr(state, tool)[ID] < n:
					unmet_tools += 1
					if target_item in {'cobble', 'coal', 'ore'}:
						if tool == 'wooden_pickaxe':
							tool_priority = max(tool_priority, 0)
						elif tool == 'stone_pickaxe':
							tool_priority = max(tool_priority, 1)
						elif tool == 'iron_pickaxe':
							tool_priority = max(tool_priority, 2)
						else:
							tool_priority = max(tool_priority, 3)
			if target_item in {'cobble', 'coal', 'ore'}:
				scored.append((unmet_tools, tool_priority, time_per_unit, m))
			else:
				scored.append((unmet_tools, time_per_unit, m))
		# If any method can run immediately (no missing tools), prefer only those for resource gathering
		if target_item in {'wood', 'cobble', 'coal', 'ore'} and scored:
			if any((s[0] == 0) for s in scored):
				scored = [s for s in scored if s[0] == 0]
		if target_item in {'cobble', 'coal', 'ore'}:
			scored.sort(key=lambda x: (x[0], x[1], x[2]))
			return [s[3] for s in scored] + fallback
		scored.sort(key=lambda x: (x[0], x[1]))
		return [s[2] for s in scored] + fallback
	
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
