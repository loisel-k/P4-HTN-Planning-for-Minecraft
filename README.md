# Heurisitic: add_heurisitic

This heurisitic (as described in the assignment) returns true when the program should prune a branch and false to allow planning to continue. This heurisitic does the following:

## Memoization (Failure Pruning)
Using `failed_memos = set()` this heurisitic memoizes pairs of the current task and a signature of the agent's state so that if the planner encounters the same task in the same state again, it is immediately pruned. It does this to prevent exponential blowup. 

## State Signature Compression 
Using `def state_signature(state)` this heurisitic makes sure only relevant numeric quantities (items, tools, and time) are used to identify states. This aids the memoization process. 

## Tool Recursion Guard 
This part of the heurisitic (marked by a comment in the code) makes it so that if the planner tries to produce a tool that is already in the current call stack, the branch is pruned. 

## Time Pruning for Goals
Marked by a comment in the code, this part of the heurisitic makes it so that plans that are too long (due to time limit) are instantly rejected. 

## Depth Safety Cutoff
This is the `if depth > 200` part of the code. This is a hard pruning of endlessly recursing plans (plans that just keep going and going). If a plan's depth is greater than 200 it gets pruned. 

# Method Ordering: define_ordering
I'm not sure if we had to include this in the README since the assignment just says to state the details of the heurisitic but just to be safe: define_ordering reorders applicable methods to try the most promising ones first. Each method is assigned a score based on tool waste (this is protected against in the heurisitic but just to be safe), missing required tools, time efficiency, and resource consumption penalty (recipes that need more total items are penalized). 