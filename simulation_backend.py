import simpy
import numpy as np
import random

# --- CONFIGURATION & PAPER CONSTANTS ---
# Baseline Failure Rates (from Table 1 of the PDF)
LAMBDA_0 = {
    'Server': 1.04e-7,
    'Storage': 4.75e-11,
    'SwA1': 4.75e-11,
    'SwA2': 4.75e-11,
    'SwB1': 4.75e-11,
    'SwB2': 4.75e-11
}

class ANSCompressor:
    """
    NOVELTY #1: Traffic Compression using Asymmetric Numeral Systems.
    In a real system, this runs at the bit level. 
    For simulation, we model the statistical reduction ratio.
    """
    def __init__(self, min_ratio=1.2, max_ratio=2.8):
        self.min_ratio = min_ratio
        self.max_ratio = max_ratio

    def compress(self, data_size_mb):
        # Calculate random compression ratio based on entropy
        ratio = random.uniform(self.min_ratio, self.max_ratio)
        compressed_size = data_size_mb / ratio
        return compressed_size, ratio

class ReliabilityMath:
    """
    Implements the AFTM (Accelerated Failure Time Model) from the Paper.
    """
    @staticmethod
    def calculate_failure_rate(component_name, load_L, alpha=1.0):
        """
        Equation (2): h(t; L) = lambda_0 * e^(alpha * L)
        """
        lambda_0 = LAMBDA_0.get(component_name, 1.0e-5)
        # Calculate accelerated failure rate
        accelerated_lambda = lambda_0 * np.exp(alpha * load_L)
        return accelerated_lambda

    @staticmethod
    def calculate_reliability(accelerated_lambda, time_t):
        """
        Equation (3/5): R(t) = e^(-lambda * t)
        """
        return np.exp(-accelerated_lambda * time_t)

class SANSimulation:
    def __init__(self):
        self.env = simpy.Environment()
        self.compressor = ANSCompressor()
        self.results = []

    def traffic_generator(self, switch_name, duration_hours):
        """
        Simulates traffic flowing into a switch over time.
        """
        t = 0
        while t < duration_hours:
            # 1. Generate Raw Load (Random between 50MB and 500MB)
            raw_load = random.uniform(50, 500)
            
            # 2. Apply Novelty #1 (ANS Compression)
            comp_load, ratio = self.compressor.compress(raw_load)
            
            # 3. Calculate Paper Metrics (Reliability drops as load increases)
            # We assume alpha=0.01 for sensitivity
            fail_rate = ReliabilityMath.calculate_failure_rate(switch_name, comp_load, alpha=0.01)
            reliability = ReliabilityMath.calculate_reliability(fail_rate, t)

            # 4. Log Data
            self.results.append({
                'time': t,
                'switch': switch_name,
                'raw_load': raw_load,
                'compressed_load': comp_load,
                'compression_ratio': ratio,
                'reliability': reliability
            })
            
            # Advance time by 1 hour
            t += 1
            yield self.env.timeout(1)

    def run_simulation(self, duration=24):
        # Create a process for SwA1
        self.env.process(self.traffic_generator('SwA1', duration))
        self.env.run(until=duration)
        return self.results

# --- TEST BLOCK (Runs only if you execute this file directly) ---
if __name__ == "__main__":
    print("--- Starting Backend Simulation Test ---")
    sim = SANSimulation()
    data = sim.run_simulation(duration=10) # Run for 10 hours
    
    print(f"{'Time':<5} | {'Raw (MB)':<10} | {'Comp (MB)':<10} | {'Rel (R(t))':<10}")
    print("-" * 45)
    for row in data:
        print(f"{row['time']:<5} | {row['raw_load']:<10.2f} | {row['compressed_load']:<10.2f} | {row['reliability']:.6f}")
    print("--- Backend Test Complete ---")