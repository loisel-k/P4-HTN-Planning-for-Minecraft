import pyhop
import json

# -------------------------
# Core HTN tasks
# -------------------------

def check_enough(state, ID, item, num):
    if getattr(state, item)[ID] >= num:
        return []
    return False

def produce_enough(state, ID, item, num):
    return [('produce', ID, item), ('have_enough', ID, item, num)]

pyhop.declare_methods('have_enough', check_enough, produce_enough)

def produce(state, ID, item):
    return [('produce_{}'.format(item), ID)]

pyhop.declare_methods('produce', produce)

# -------------------------
# Method generation
# -------------------------

def make_method(name, rule):
    produces = rule.get('Produces', {})
    if not produces:
        return None

    prod_item = list(produces.keys())[0]
    normalized = name.replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '').replace(',', '')
    op_task_name = f"op_{normalized}"

    def method(state, ID):
        subtasks = []

        for tool, n in rule.get('Requires', {}).items():
            subtasks.append(('have_enough', ID, tool, n))

        for item, n in rule.get('Consumes', {}).items():
            subtasks.append(('have_enough', ID, item, n))

        subtasks.append((op_task_name, ID))
        return subtasks

    method.__name__ = f"produce_{prod_item}__via__{normalized}"
    method._rule = rule
    method._produces = prod_item
    return method

def declare_methods(data):
    prod_to_methods = {}

    for name, rule in data['Recipes'].items():
        m = make_method(name, rule)
        if not m:
            continue

        prod_item = list(rule['Produces'].keys())[0]
        qty = rule['Produces'][prod_item]
        time_cost = rule.get('Time', 0)
        tpu = time_cost / float(qty) if qty else time_cost

        prod_to_methods.setdefault(prod_item, []).append((m, tpu))

    for prod_item, methods in prod_to_methods.items():
        methods.sort(key=lambda x: x[1])
        pyhop.declare_methods(f'produce_{prod_item}', *[m for m, _ in methods])

# -------------------------
# Operators
# -------------------------

def make_operator(rule):
    def operator(state, ID):
        if state.time[ID] < rule.get('Time', 0):
            return False

        for item, n in rule.get('Requires', {}).items():
            if getattr(state, item)[ID] < n:
                return False

        for item, n in rule.get('Consumes', {}).items():
            if getattr(state, item)[ID] < n:
                return False

        for item, n in rule.get('Consumes', {}).items():
            getattr(state, item)[ID] -= n

        for item, n in rule.get('Produces', {}).items():
            getattr(state, item)[ID] += n

        state.time[ID] -= rule.get('Time', 0)
        return state
    return operator

def declare_operators(data):
    ops = []
    for name, rule in data['Recipes'].items():
        op = make_operator(rule)
        normalized = name.replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '').replace(',', '')
        op.__name__ = f"op_{normalized}"
        ops.append(op)
    pyhop.declare_operators(*ops)

# -------------------------
# Heuristic (SAFE)
# -------------------------

def add_heuristic(data, ID):
    min_time_per_unit = {}
    for rule in data['Recipes'].values():
        for item, qty in rule.get('Produces', {}).items():
            t = rule.get('Time', 0)
            tpu = t / float(qty) if qty else t
            min_time_per_unit[item] = min(min_time_per_unit.get(item, float('inf')), tpu)

    tools = set(data.get('Tools', []))
    
    failed_memos = set()
    
    def state_signature(state):
       # Compact, hashable snapshot
       sig = []
       for item in sorted(state.__dict__):
           if item in ('__name__', 'goals'):
               continue
           val = state.__dict__[item]
           if isinstance(val, dict) and ID in val:
               sig.append((item, val[ID]))
       return tuple(sig)


    def heuristic(state, curr_task, tasks, plan, depth, calling_stack):
        # ---- Memoization prune (FAILED subproblems only) ----
        sig = (curr_task, state_signature(state))
        if sig in failed_memos:
                return True

        if not isinstance(curr_task, (list, tuple)):
            return False

        tname = curr_task[0]

        # ---- Tool-only recursion guard ----
        if tname == 'produce' and len(curr_task) >= 3:
            item = curr_task[2]
            if item in tools and calling_stack:
                for prev in calling_stack:
                    if (
                        isinstance(prev, (list, tuple)) and
                        len(prev) >= 3 and
                        prev[0] == 'produce' and
                        prev[2] == item
                    ):
                        return True

        # ---- Time infeasibility prune (ONLY at goals) ----
        if tname == 'have_enough' and len(curr_task) == 4:
            _, _, item, num = curr_task
            cur = getattr(state, item)[ID]
            if cur >= num:
                return False
            if item in min_time_per_unit:
                needed = num - cur
                if needed * min_time_per_unit[item] > state.time[ID]:
                    return True

        # ---- Depth safety ----
        if depth > 200:
            return True

        # If this task fails deeper, remember it
        if depth > 0:
           failed_memos.add((curr_task, state_signature(state)))

        return False

    pyhop.add_check(heuristic)

# -------------------------
# Method ordering
# -------------------------

def define_ordering(data, ID):
    tools = set(data.get('Tools', []))

    ever_consumed = set()
    for rule in data['Recipes'].values():
        ever_consumed.update(rule.get('Consumes', {}).keys())

    def reorder_methods(state, curr_task, tasks, plan, depth, calling_stack, methods):
        scored = []

        for m in methods:
            rule = getattr(m, '_rule', None)
            if not rule:
                scored.append((9999, m))
                continue

            item = list(rule['Produces'].keys())[0]

            penalty = 0
            if item in tools and item not in ever_consumed and getattr(state, item)[ID] >= 1:
                penalty += 50000

            missing_tools = sum(
                1 for t, n in rule.get('Requires', {}).items()
                if getattr(state, t)[ID] < n
            )

            qty = rule['Produces'][item]
            time_cost = rule.get('Time', 0)
            tpu = time_cost / float(qty) if qty else time_cost

            consume_penalty = sum(rule.get('Consumes', {}).values())

            score = penalty + missing_tools * 1000 + tpu * 10 + consume_penalty
            scored.append((score, m))

        scored.sort(key=lambda x: x[0])
        return [m for _, m in scored]

    pyhop.define_ordering(reorder_methods)

# -------------------------
# Problem setup
# -------------------------

def set_up_state(data, ID):
    state = pyhop.State('state')
    state.time = {ID: data['Problem'].get('Time', 0)}

    for item in data['Items'] + data['Tools']:
        setattr(state, item, {ID: data['Problem']['Initial'].get(item, 0)})

    state.goals = data['Problem'].get('Goal', {})
    return state

def set_up_goals(data, ID):
    goals = []
    for item, num in data['Problem']['Goal'].items():
        if num > 0:
            goals.append(('have_enough', ID, item, num))
    return goals

# -------------------------
# Main
# -------------------------

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

    pyhop.pyhop(state, goals, verbose=1)
