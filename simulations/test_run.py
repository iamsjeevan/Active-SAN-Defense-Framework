import simpy

# ns.py imports
from ns.packet.dist_packet_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.demux.fib_demux import FIBDemux
from ns.link.wire import Wire

# your components
from san_components.compression_wrapper import CompressionWrapper
from san_components.failing_switch import FailingSwitch
from san_components.routing_controller import RoutingController

def main():
    env = simpy.Environment()

    print("🧪 Starting test simulation...")

    # 1. Packet generator (1000 packets/sec, size=1500B)
    pg = DistPacketGenerator(
        env,
        id="PG",
        flow_id=1,
        arrival_dist=lambda: 0.001,   # 1000 pps
        size_dist=lambda: 1500
    )

    # 2. Compression module (40% reduction)
    comp = CompressionWrapper(env, compression_ratio=0.6)

    # 3. Switches (2 ports each)
    sw1 = FailingSwitch(env, id="SW1", ports=2, failure_threshold=0.8)
    sw2 = FailingSwitch(env, id="SW2", ports=1, failure_threshold=0.95)

    # 4. FIB demux (used for routing)
    fib1 = FIBDemux(env)
    fib1.downstream = {0: sw1}    # Send everything to sw1
    fib1.fib = {1: 0}             # Flow 1 -> port 0 (sw1)

    # 5. Connect SW1 -> SW2 -> Sink
    sw1.out_ports[0] = sw2
    sink = PacketSink(env)
    sw2.out_ports[0] = sink

    # 6. Connect generator pipeline
    pg.out = comp
    comp.out = fib1

    # 7. Routing controller (not doing dynamic routing yet, just starting)
    controller = RoutingController(
        env,
        switches={"SW1": sw1, "SW2": sw2},
        fib_demuxes={"SW1": fib1},
        interval=1.0
    )

    # 8. Run
    env.run(until=3)

    print("\n✅ TEST FINISHED")
    print("Packets received at sink:", sink.count)
    print("Packets processed by compressor:", comp.packets_processed)
    print("Bytes saved:", comp.bytes_saved)
    print("SW1 failed:", sw1.failed)
    print("SW2 failed:", sw2.failed)

if __name__ == "__main__":
    main()
