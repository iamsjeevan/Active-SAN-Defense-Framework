# Active-SAN-Defense-Framework

A discrete-event network simulation framework built in Python to model, test, and validate strategies for actively defending Storage Area Networks (SANs) from cascading failures. This is the official implementation for the paper: **"Actively Defending Storage Area Networks from Cascading Threats: A Dual Strategy of Traffic Compression and Dynamic Rerouting."**

## The Problem

High-volume workloads can cause data overloading on SAN switches, acting as a physical stressor that accelerates component failure. The failure of a single switch can trigger a chain reaction—a "cascading failure"—that forces traffic onto neighboring switches, causing them to fail in turn and leading to catastrophic, system-wide outages. This framework is designed to simulate this failure model and test advanced defensive countermeasures.

## The Solution: A Dual-Pronged Defense

This framework implements and evaluates two synergistic mechanisms that work together to enhance network resilience:

1.  **In-Line Traffic Compression:** Fundamentally reduces the initial data load across the entire network by simulating the effects of a high-performance entropy encoder (Asymmetric Numeral Systems).
2.  **Dynamic Load Redistribution:** Implements an intelligent, load-aware routing policy. The framework constantly monitors the load on each switch and dynamically reroutes traffic away from potential bottlenecks *before* they can become critical, effectively breaking the chain of cascading failures.

The primary goal is to provide a quantitative analysis of the improvements in key reliability metrics, such as **Mean Time To Failure (MTTF)**, when these active defenses are deployed.

---

## Technical Stack

*   **Core Simulation Engine:** [ns.py](https://github.com/wei-t/ns.py) (A SimPy-based Discrete-Event Network Simulator)
*   **Underlying Framework:** [SimPy](https://simpy.readthedocs.io/)
*   **Dynamic Routing & Topology:** [NetworkX](https://networkx.org/)
*   **Data Analysis & Visualization:** [Pandas](https://pandas.pydata.org/) & [Matplotlib](https://matplotlib.org/)
*   **Programming Language:** Python 3.10+

---


