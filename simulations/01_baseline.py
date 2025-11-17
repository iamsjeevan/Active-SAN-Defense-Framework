import simpy
import functools
import random
from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from san_components.failing_switch import FailingSwitch

def run_simulation(sim_time=1000):
    print("Creating environment...")
    env = simpy.Environment()

    # Create a switch
    switch = FailingSwitch(
        env=env,
        n_ports=2,
        port_rate=1e9,
        buffer_size=2 * 1024 * 1024,
        switch_id="S1",
        base_mttf=500,
        failure_alpha=5,
    )

    # A single packet sink
    sink = PacketSink(env, rec_flow_ids=False)

    # Traffic source
    adist = functools.partial(random.expovariate, 2000)
    sdist = lambda: 1500
    packet_gen = DistPacketGenerator(env, "src", adist, sdist)

    # Wire generator → switch → sink
    packet_gen.out = switch
    switch.ports[0].out = sink  # switch forwards out first port

    print("--- Starting Simple SAN Simulation ---")
    env.run(until=sim_time)
    print("--- Finished ---")

    if switch.is_failed:
        print("Switch failed as expected.")
    else:
        print("Switch did not fail under this load.")

if __name__ == "__main__":
    run_simulation()
