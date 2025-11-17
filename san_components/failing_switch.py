# this is CG code Main code from GAIStd
# san_components/failing_switch.py

from ns.switch.simple_switch import SimplePacketSwitch

class FailingSwitch(SimplePacketSwitch):
    """
    Extends ns.py SimplePacketSwitch to simulate overload-based failure.
    """
    def __init__(self, env, id, ports, failure_threshold=0.85):
        super().__init__(env, id, ports)
        self.failure_threshold = failure_threshold
        self.failed = False

    @property
    def current_load(self):
        # average port occupancy ratio
        loads = [
            len(port.buffer) / port.max_size
            for port in self.out_ports.values()
            if port.max_size > 0
        ]
        return max(loads) if loads else 0.0

    def put(self, packet):
        if self.failed:
            # drop immediately
            return

        # overload → fail
        if self.current_load >= self.failure_threshold:
            print(f"[{self.env.now}] Switch {self.id} FAILED (load={self.current_load:.2f})")
            self.failed = True
            return

        # otherwise normal behavior
        return super().put(packet)
