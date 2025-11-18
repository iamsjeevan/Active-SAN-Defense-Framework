import simpy
import random
import math
from ns.switch.switch import SimplePacketSwitch

class FailingSwitch(SimplePacketSwitch):
    """
    Custom switch that:
    - Tracks load using port buffer occupancy
    - Uses an AFTM-based exponential failure model (MTTF ↓ as load ↑)
    - Overrides .put() to avoid ns.py's built-in routing/demux system,
      and instead uses a simple port-based forwarding model.
    """

    def __init__(self,
                 env: simpy.Environment,
                 n_ports: int,
                 port_rate: float,
                 buffer_size: int,
                 switch_id: str,
                 base_mttf: float = 10000.0,
                 failure_alpha: float = 0.5):

        super().__init__(env, n_ports, port_rate, buffer_size, element_id=switch_id)

        self.env = env
        self.switch_id = switch_id
        self.is_failed = False
        self.current_load = 0.0
        self.base_mttf = base_mttf
        self.failure_alpha = failure_alpha

        # Calculate total buffer capacity from port queue limits
        caps = []
        for p in self.ports:
            if hasattr(p, "qlimit"):
                caps.append(p.qlimit)
        self.total_buffer_capacity = sum(caps) if caps else 1

        # Spawn a process that monitors load and triggers failure
        self.load_monitor_proc = env.process(self.monitor_load())

    def monitor_load(self):
        interval = 1.0  # 1 time unit per check
        while not self.is_failed:
            current_occupancy = 0
            for p in self.ports:
                if hasattr(p, "byte_size"):
                    current_occupancy += p.byte_size

            self.current_load = current_occupancy / self.total_buffer_capacity

            # AFTM failure logic: MTTF decreases exponentially with load
            if self.current_load > 0:
                current_mttf = self.base_mttf * math.exp(-self.failure_alpha * self.current_load)
                failure_rate = 1 / max(current_mttf, 1e-9)
            else:
                failure_rate = 1 / self.base_mttf

            if random.random() < (failure_rate * interval):
                self.fail_switch()
                return

            yield self.env.timeout(interval)

    def fail_switch(self):
        self.is_failed = True
        print(
            f"!!! SWITCH FAILURE !!! "
            f"Switch '{self.switch_id}' failed at time {self.env.now:.2f} "
            f"with load {self.current_load:.2%}"
        )
        # Cut off all outgoing connections when failed
        for port in self.ports:
            port.out = None

    # def put(self, packet):
    #     """
    #     Simple forwarding override:
    #     - If failed, drop packet
    #     - If active, forward to the first connected outbound port
    #     """
    #     if self.is_failed:
    #         return

    #     for port in self.ports:
    #         if getattr(port, "out", None) is not None:
    #             return port.put(packet)

    #     # No ports available → drop silently
    #     return
    def put(self, packet):
        """
        Simple forwarding override:
        - If failed: drop packet
        - If active: forward to the first connected outbound port
        - If none connected: drop packet safely
        """
        if self.is_failed:
            return  # drop silently

        for port in self.ports:
            out = getattr(port, "out", None)
            if out is not None:
                return port.put(packet)

        # No outbound ports → drop the packet (IMPORTANT!)
        return

