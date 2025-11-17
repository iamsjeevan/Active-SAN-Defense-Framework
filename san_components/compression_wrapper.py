# san_components/compression_wrapper.py

class CompressionWrapper:
    """
    A network component that sits in front of a switch to simulate the effect
    of in-line traffic compression. It reduces packet size at the cost of a small delay.

    Parameters
    ----------
    env : simpy.Environment
        The simulation environment.
    compression_ratio : float
        The factor by which to reduce the packet size.
        E.g., 0.6 means the output packet is 60% of the original size (a 40% reduction).
    delay_ms : float
        The CPU processing delay for compression, in milliseconds.
    """
    def __init__(self, env, compression_ratio: float = 0.6, delay_ms: float = 0.01):
        self.env = env
        self.compression_ratio = compression_ratio
        self.delay = delay_ms / 1000.0  # Convert ms to seconds for SimPy
        self.out = None  # This will be connected to the next network element (e.g., a switch)
        self.packets_processed = 0
        self.bytes_saved = 0

    def put(self, packet):
        """
        The main packet processing method. This is called by the upstream component.
        """
        # Simulate the CPU processing delay for compressing the packet
        if self.delay > 0:
            yield self.env.timeout(self.delay)

        # The core logic: shrink the packet and track savings
        original_size = packet.size
        packet.size *= self.compression_ratio
        self.bytes_saved += original_size - packet.size
        self.packets_processed += 1

        # Forward the now-smaller packet to the connected output component
        self.out.put(packet)