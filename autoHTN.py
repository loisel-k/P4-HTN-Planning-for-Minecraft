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
    produces = rule.get('Produces', {})
    if not produces:
        return None
    prod_item = list(produces.keys())[0]

    normalized = name.replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '').replace(',', '')
    op_task_name = f"op_{normalized}"

    def method(state, ID):
        subtasks = []
        # Ensure required tools (not consumed)
        for tool, n in rule.get('Requires', {}).items():
            subtasks.append(('have_enough', ID, tool, n))
        # Ensure consumed inputs are available
        for item, n in rule.get('Consumes', {}).items():
            subtasks.append(('have_enough', ID, item, n))
        # Perform operator
        subtasks.append((op_task_name, ID))
        return subtasks

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
        # Cheap pre-check: time must be enough
        if state.time[ID] < rule.get('Time', 0):
            return False

        # Check required tools (not consumed)
        for item, num in rule.get('Requires', {}).items():
            if getattr(state, item)[ID] < num:
                return False

        # Check consumed inputs
        for item, num in rule.get('Consumes', {}).items():
            if getattr(state, item)[ID] < num:
                return False

        # Apply effects: consume inputs
        for item, num in rule.get('Consumes', {}).items():
            getattr(state, item)[ID] -= num

        # Apply effects: produce outputs
        for item, num in rule.get('Produces', {}).items():
            getattr(state, item)[ID] += num

        # Deduct time cost
        state.time[ID] -= rule.get('Time', 0)
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
    # Min time per unit for reachability pruning
    min_time_per_unit = {}
    for _, rule in data.get('Recipes', {}).items():
        for item, qty in rule.get('Produces', {}).items():
            t = rule.get('Time', 0)
            tpu = t / float(qty) if qty else t
            min_time_per_unit[item] = min(min_time_per_unit.get(item, float('inf')), tpu)

    tools = set(data.get('Tools', []))

    # Precompute which tools are ever required
    tool_required_by = {t: set() for t in tools}
    for name, rule in data.get('Recipes', {}).items():
        for t in rule.get('Requires', {}):
            tool_required_by[t].add(name)

    def heuristic(state, curr_task, tasks, plan, depth, calling_stack):
        if not isinstance(curr_task, (list, tuple)):
            return False

        tname = curr_task[0]

        # ---- HARD RULE: never remake a tool we already have ----
        if tname == 'produce' and len(curr_task) >= 3:
            item = curr_task[2]
            if item in tools and getattr(state, item)[ID] >= 1:
                return True

        # ---- Prevent tool recursion chains ----
        if calling_stack and tname == 'produce' and len(curr_task) >= 3:
            item = curr_task[2]
            for prev in calling_stack:
                if isinstance(prev, (list, tuple)) and prev[0] == 'produce' and prev[2] == item:
                    return True

        # ---- Time infeasibility pruning ----
        if tname == 'have_enough' and len(curr_task) == 4:
            _, _, item, num = curr_task
            cur = getattr(state, item)[ID]
            if cur >= num:
                return False
            if item in min_time_per_unit:
                needed = num - cur
                if needed * min_time_per_unit[item] > state.time[ID]:
                    return True

        # ---- Tool usefulness pruning ----
        if tname == 'produce' and len(curr_task) >= 3:
            item = curr_task[2]

            if item in tools:
				# Allow producing a tool if:
				# 1) it is a goal, or
				# 2) it is required by a remaining task
                is_goal = item in getattr(state, 'goals', {})
                required_later = any(
					isinstance(t, (list, tuple)) and item in str(t)
					for t in tasks
				)

                if not is_goal and not required_later:
                    return True



        # Depth safety net
        if depth > 200:
            return True

        return False

    pyhop.add_check(heuristic)

def define_ordering(data, ID):
    tools = set(data.get('Tools', []))

    def reorder_methods(state, curr_task, tasks, plan, depth, calling_stack, methods):
        scored = []

        for m in methods:
            rule = getattr(m, '_rule', None)
            if not rule:
                scored.append((9999, m))
                continue

            produces = rule.get('Produces', {})
            if not produces:
                scored.append((9999, m))
                continue

            item = list(produces.keys())[0]

            # ---- Never remake tools ----
            if item in tools and getattr(state, item)[ID] >= 1:
                continue

            # ---- Goal tool detection (FIXED) ----
            is_goal_tool = (
                item in tools and
                item in getattr(state, 'goals', {})
            )

            goal_bonus = -500 if is_goal_tool else 0

            # ---- Missing required tools ----
            missing_tools = sum(
                1 for t, n in rule.get('Requires', {}).items()
                if getattr(state, t)[ID] < n
            )

            # ---- Time per unit ----
            qty = produces[item]
            time_cost = rule.get('Time', 0)
            tpu = time_cost / float(qty) if qty else time_cost

            # ---- Consumption penalty ----
            consume_penalty = sum(rule.get('Consumes', {}).values())

            score = (
                missing_tools * 1000 +
                tpu * 10 +
                consume_penalty +
                goal_bonus
            )

            scored.append((score, m))

        scored.sort(key=lambda x: x[0])
        return [m for _, m in scored]

    pyhop.define_ordering(reorder_methods)


def set_up_state(data, ID):
    state = pyhop.State('state')
    # Efficient initialization
    setattr(state, 'time', {ID: data['Problem'].get('Time', 0)})

    for item in data['Items'] + data['Tools']:
        setattr(state, item, {ID: data['Problem']['Initial'].get(item, 0)})

    # Attach goals for methods to check
    setattr(state, 'goals', data['Problem'].get('Goal', {}))

    return state

def set_up_goals(data, ID):
    goals = []
    for item, num in data['Problem']['Goal'].items():
        if num > 0:  # Only create goals that are actually needed
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
	pyhop.pyhop(state, goals, verbose=1)
	# pyhop.pyhop(state, [('have_enough', 'agent', 'cart', 1),('have_enough', 'agent', 'rail', 20)], verbose=3)
