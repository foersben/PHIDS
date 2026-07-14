import sys
import time
import asyncio
from phids.io.scenario import load_scenario_from_json
from phids.engine.loop import SimulationLoop

async def run_benchmark(scenario_path, num_ticks=1000):
    config = load_scenario_from_json(scenario_path)
    # run headless without recording replays for raw engine performance
    loop = SimulationLoop(config, disable_replay=True)

    # disable pause
    loop.running = True

    t0 = time.perf_counter()
    for _ in range(num_ticks):
        result = await loop.step()
        if result.terminated:
            break
    t1 = time.perf_counter()
    return t1 - t0

if __name__ == "__main__":
    import sys
    scenario = sys.argv[1]
    ticks = int(sys.argv[2])
    print(asyncio.run(run_benchmark(scenario, ticks)))
