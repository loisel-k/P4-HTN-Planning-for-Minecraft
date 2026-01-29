## Plan for Requirement 2 — Operators
1. Implement `make_operator(rule)`:
   - Input: a recipe rule (dict) from `crafting.json`.
   - Behavior: return an operator function `op_<name>` that:
     - Checks time and required tool counts (`Requires`) and consumed inputs (`Consumes`),
     - Updates state by subtracting consumed items and increasing produced items, and
     - Deducts rule `Time` from `state.time[ID]`.
   - Return `False` if preconditions fail.
   - Name operators: `op_<recipe_name_normalized>` (e.g., `op_craft_wooden_axe_at_bench`).
2. Implement `declare_operators(data)` to create operator functions for all `Recipes` and call `pyhop.declare_operators(...)`.
3. Test: run `autoHTN.py` with `crafting.json` and check `pyhop.print_operators()`; then try small goals (like craft a plank) to validate preconditions and effects.  
Essentially want this function to do the first half of the manualHTN - make valid operators. 

## Plan for Requirement 3 — Methods
1. Implement `make_method(name, rule)`:
   - Return a function `produce_<item>` that decomposes the recipe into subtasks:
     - Ensure required `Requires` items are available (`('have_enough', ID, tool, qty)`),
     - Ensure consumed inputs are produced in a workable order (`('have_enough', ID, input, qty)`), and
     - Finally apply the operator `('op_<recipe>', ID)`.
2. Implement `declare_methods(data)` to generate methods for each recipe grouped by produced item. Order methods by expected usefulness (see next bullet).
3. Ordering subtasks: for recipes that both *require* tools and *consume* inputs, order preconditions so that easily producible prerequisites happen first (e.g., produce wood first to make planks, then craft sticks, then bench, etc.).
4. Name methods: `produce_<item>` so they are compatible with `pyhop`'s `produce` method used in `ASSIGNMENT.md` and `autoHTN.py`.
5. Test: call `pyhop.print_methods()` and run `pyhop.pyhop` with single goals (e.g., have_enough cart 1) and inspect plan structure.  
Similar to Req 2, want this function do the recipe part of manualHTN - make valid methods that call the operators.  

## Plan for Requirement 4 — JSON → HTN problem initializer 
1. Review and use `set_up_state(data, ID)` and `set_up_goals(data, ID)` (already present):
   - Confirm they set `time`, initialize `Items` and `Tools`, and set initial counts from `Problem.Initial`.
   - Confirm goals are returned as `('have_enough', ID, item, qty)` pairs.
2. Add small robustness checks:
   - Ensure initial missing keys get zero (currently implemented), and assert all `Items` and `Tools` exist as attributes on state -> learnt this from manualHTN -> need to initialize.
3. Test: run the `__main__` path of `autoHTN.py` for a few sample problems.
Essentially initializes problem (sets it up to create a plank, given no resource in beginning like Case 2). 

## Plan for Requirement 5 — Test cases & heuristics 
1. Implement heuristics in `add_heuristic(data, ID)` to **prune** unproductive/cyclic branches:
   - Cycle detection: if `('produce', ID, X)` is currently in `calling_stack` (or repeated in it), prune; this prevents infinite regress when recipes require themselves.
   - Time feasibility check: estimate maximum possible production given `state.time[ID]` (e.g., bound wood production by floor(time / min_time_per_unit)), prune branches that can’t possibly reach goal.
   - Tool-creation guard: if a method attempts to produce a tool that itself requires the same target (e.g., wooden_axe → wood → wooden_axe), prune unless we have a base path (like punching) to bootstrap.
2. Implement `define_ordering(data, ID)` or use `reorder_methods` to prefer methods that:
   - Have lower time-per-output (higher throughput), and
   - Require fewer unavailable tools (favor methods that can run immediately), and
   - Use punching as fallback only when punching alone can reach the goal or to bootstrap resource needs.
Side Note: I think I prefer implementation of heurisitics and ordering methods for a task (define_ordering).  
3. Test each required case:
   - Case 1: Given {'plank': 1} → goal {'plank': 1} (time <= 0)
   - Case 2: {} → {'plank': 1} (time <= 300)
   - Case 3: {'plank':3,'stick':2} → {'wooden_pickaxe':1} (time <= 10)
   - Case 4: {} → {'iron_pickaxe':1} (time <= 100)
   - Case 5: {} → {'cart':1,'rail':10} (time <= 175)
   - Case 6: {} → {'cart':1,'rail':20} (time <= 250)
4. Performance tests: measure runtime and iterate heuristics to ensure each case runs in < 30s.
Basically this requirement just has you test that it works with the test cases after refining with the simplfying tasks listed out in the assignment so you don't get stuck in an infinite loop.  