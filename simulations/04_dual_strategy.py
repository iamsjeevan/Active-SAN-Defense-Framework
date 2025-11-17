# simulations/04_dual_strategy.py

import simpy
from ns.packet.dist_packet_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.link.wire import Wire
from ns.demux.fib_demux import FIBDemux

from san_components.compression_wrapper import CompressionWrapper
from san_components.failing_switch import FailingSwitch
from san_components.routing_controller import RoutingController

def build_network(env):
    # Packet generator
    pg = DistPacketGenerator(
        env,
        id="PG",
        flow_id=0,
        arrival_dist=lambda: 0.001,  # 1000 pps
        size_dist=lambda: 1500
    )

    # Compression module
    comp = CompressionWrapper(env, compression_ratio=0.6)

    # Switches
    sw1 = FailingSwitch(env, id="SW1", ports=2, failure_threshold=0.85)
    sw2 = FailingSwitch(env, id="SW2", ports=2, failure_threshold=0.85)
    sw3 = FailingSwitch(env, id="SW3", ports=2, failure_threshold=0.85)

    # FIB demuxers for dynamic routing
    fib1 = FIBDemux(env)
    fib2 = FIBDemux(env)
    fib3 = FIBDemux(env)

    # Sink
    sink = PacketSink(env)

    # Connect pipeline
    pg.out = comp
    comp.out = fib1

    # fib for SW1 routes to SW2 + SW3
    fib1.downstream = {0: sw2, 1: sw3}
    fib1.fib = {0: 0}  # default: forward to SW2

    # SW2 and SW3 both go to sink
    sw2.out_ports[0] = sink
    sw3.out_ports[0] = sink

    # Controller
    controller = RoutingController(
        env,
        switches={"SW1": sw1, "SW2": sw2, "SW3": sw3},
        fib_demuxes={"SW1": fib1},
        interval=0.5
    )

    return pg, comp, [sw1, sw2, sw3], sink


if __name__ == "__main__":
    env = simpy.Environment()
    pg, comp, switches, sink = build_network(env)

    print("Running simulation...")
    env.run(until=10)

    print("\nPackets received:", sink.count)
    print("Packets processed by compressor:", comp.packets_processed)
    print("Bytes saved:", comp.bytes_saved)
