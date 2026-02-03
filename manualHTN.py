import pyhop

'''begin operators'''

def op_punch_for_wood(state, ID):
    if state.time[ID] >= 4:
        state.wood[ID] += 1
        state.time[ID] -= 4
        return state
    return False

def op_craft_wooden_axe_at_bench(state, ID):
    if state.time[ID] >= 1 and state.bench[ID] >= 1 and state.plank[ID] >= 3 and state.stick[ID] >= 2:
        state.wooden_axe[ID] += 1
        state.plank[ID] -= 3
        state.stick[ID] -= 2
        state.time[ID] -= 1
        return state
    return False

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

pyhop.declare_operators(
    op_punch_for_wood,
    op_craft_wooden_axe_at_bench,
    op_craft_plank,
    op_craft_stick,
    op_craft_bench,
    op_wooden_axe_for_wood
)

'''end operators'''

def check_enough(state, ID, item, num):
    if getattr(state, item)[ID] >= num:
        return []
    return False

def produce_enough(state, ID, item, num):
    current = getattr(state, item)[ID]

    if current >= num:
        return []

    if item == 'wood':
        # If we have an axe, produce wood using it
        if state.wooden_axe[ID] >= 1:
            return [('op_wooden_axe_for_wood', ID), ('have_enough', ID, 'wood', num)]
        # Otherwise, punch for wood
        punches_possible = state.time[ID] // 4
        remaining = num - current
        if punches_possible >= remaining:
            return [('op_punch_for_wood', ID), ('have_enough', ID, 'wood', num)]
        # Not enough punches: produce an axe first
        if not state.made_wooden_axe[ID]:
            state.made_wooden_axe[ID] = True
            return [('produce', ID, 'wooden_axe'), ('have_enough', ID, 'wood', num)]
        else:
            # Can't make more axes and not enough time to punch -> fail
            return False

    if item == 'wooden_axe':
        if getattr(state, item)[ID] >= 1 or state.made_wooden_axe[ID]:
            return []
        state.made_wooden_axe[ID] = True
        return [('produce', ID, 'wooden_axe'), ('have_enough', ID, 'wooden_axe', num)]

    # Generic case for other resources
    return [('produce', ID, item), ('have_enough', ID, item, num)]


def produce(state, ID, item):
    if item == 'wood':
        return [('produce_wood', ID)]
    elif item == 'wooden_axe':
        return [('produce_wooden_axe', ID)]
    elif item == 'plank':
        return [('produce_plank', ID)]
    elif item == 'stick':
        return [('produce_stick', ID)]
    elif item == 'bench':
        return [('produce_bench', ID)]
    return False

pyhop.declare_methods('have_enough', check_enough, produce_enough)
pyhop.declare_methods('produce', produce)

'''begin recipe methods'''

def craft_wooden_axe_at_bench(state, ID):
    return [
        ('have_enough', ID, 'bench', 1),
        ('have_enough', ID, 'stick', 2),
        ('have_enough', ID, 'plank', 3),
        ('op_craft_wooden_axe_at_bench', ID)
    ]

def craft_plank(state, ID):
    return [('have_enough', ID, 'wood', 1), ('op_craft_plank', ID)]

def craft_stick(state, ID):
    return [('have_enough', ID, 'plank', 2), ('op_craft_stick', ID)]

def craft_bench(state, ID):
    return [('have_enough', ID, 'plank', 4), ('op_craft_bench', ID)]

def produce_wood_method(state, ID):
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

# ----------------- Declare initial state -----------------

state = pyhop.State('state')
state.wood = {'agent': 0}
state.time = {'agent': 46}
state.wooden_axe = {'agent': 0}
state.made_wooden_axe = {'agent': False}
state.plank = {'agent': 0}
state.stick = {'agent': 0}
state.bench = {'agent': 0}

# ----------------- Run examples -----------------

pyhop.pyhop(state, [('have_enough', 'agent', 'wood', 1)], verbose=1)
pyhop.pyhop(state, [('have_enough', 'agent', 'wood', 12)], verbose=1)
