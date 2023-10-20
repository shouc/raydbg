import math
import random
import time

import ray

RESOURCE = 0.01

@ray.remote
def sampling_task(num_samples: int, task_id: int) -> int:
    num_inside = 0
    for i in range(num_samples):
        x, y = random.uniform(-1, 1), random.uniform(-1, 1)
        if math.hypot(x, y) <= 1:
            num_inside += 1
    global RESOURCE
    RESOURCE += 0.01
    return num_inside


# Change this to match your cluster scale.
NUM_SAMPLING_TASKS = 100
NUM_SAMPLES_PER_TASK = 10_000
TOTAL_NUM_SAMPLES = NUM_SAMPLING_TASKS * NUM_SAMPLES_PER_TASK

# Create and execute all sampling tasks in parallel.
val = [1 for x in range(1000000)]
results = [
    ray.get(sampling_task.remote(NUM_SAMPLES_PER_TASK, val))
    for i in range(NUM_SAMPLING_TASKS)
]

# Get all the sampling tasks results.
total_num_inside = sum(results)
pi = (total_num_inside * 4) / TOTAL_NUM_SAMPLES
print(f"Estimated value of π is: {pi}")
