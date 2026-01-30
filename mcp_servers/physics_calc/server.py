import math

def calculate_vut(ca, ce, u, te):
    """Variability-Utilization-Time Equation."""
    v = (ca**2 + ce**2) / 2
    utilization_factor = u / (1 - u)
    tq = v * utilization_factor * te
    return {"expected_queue_time": tq}

def calculate_littles_law(wip, th):
    """CT = WIP / TH."""
    return {"cycle_time": wip / th}

if __name__ == "__main__":
    # Internal Test
    print(f"Kernel Test: {calculate_littles_law(15, 100)}")
