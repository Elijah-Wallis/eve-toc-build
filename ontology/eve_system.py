"""
EVE MEDSPA SYSTEM ONTOLOGY
==========================
This module defines the "Eve" business model as a Thermodynamic System (Factory).
It maps generic MedSpa terms to Theory of Constraints (TOC) and Factory Physics objects.

GOVERNING PRINCIPLE:
Treat the MedSpa as a high-end factory.
- Raw Material: Untreated Leads (WIP).
- The Machine: The Aesthetician's Chair / Consultation Room.
- The Constraint: Chair Time availability (NOT marketing volume).
- Finished Good: A satisfied, recurring patient (Throughput).
- Waste (Entropy): Unconverted leads, cancellations, no-shows.

THE SILENT KILLER:
Conversion Velocity (Speech to Action). If 'Time to Consult' increases, 
Variance (V) spikes, and Throughput (T) crashes.
"""

from dataclasses import dataclass
from typing import List, Optional
from .logic import FactoryPhysics

@dataclass
class Lead:
    """
    Represents 'Raw Material' or 'Work In Progress' (WIP).
    
    Nuance:
    A lead is NOT a sale. It is a liability (Inventory Cost) until converted.
    High volume of leads with low conversion velocity = High Operating Expense (OE).
    """
    id: str
    source: str
    entry_time: float
    status: str  # 'New', 'Contacted', 'Consult_Scheduled', 'Converted', 'Dead'

@dataclass
class TreatmentResource:
    """
    Represents the 'Machine' or 'Work Center'.
    
    The Bottleneck Analysis:
    In Eve, the constraint is likely the Aesthetician's available hours.
    If Utilization (U) > 90%, Queue Time (Wait) approaches infinity (VUT Equation).
    """
    name: str  # e.g., "Injector_Station_1"
    capacity_hours_per_week: float
    current_load_hours: float
    
    @property
    def utilization(self) -> float:
        return self.current_load_hours / self.capacity_hours_per_week

class EvePlantPhysics:
    """
    The Physics Engine specific to Eve MedSpa.
    """
    
    @staticmethod
    def calculate_patient_throughput(active_leads: int, conversion_rate: float, cycle_time_days: float) -> float:
        """
        Calculates T (Throughput).
        T = WIP / CT (Little's Law).
        
        To increase T, you must either:
        1. Reduce Cycle Time (Speed to Lead).
        2. Optimize WIP (Don't flood the funnel if the chair is full).
        """
        return FactoryPhysics.littles_law(wip=active_leads, cycle_time=cycle_time_days)

    @staticmethod
    def analyze_bottleneck_impact(cancellation_rate: float, chair_utilization: float, avg_appt_time: float):
        """
        Applies the VUT Equation to the MedSpa.
        
        - Variability (V): Represented by 'cancellation_rate'. High variability kills flow.
        - Utilization (U): 'chair_utilization'.
        - Time (T): 'avg_appt_time'.
        
        Returns: Expected Wait Time for a new patient.
        """
        # Mapping Variability to a sigma-like factor for the VUT equation
        # High cancellations = High Variability (Ca/Ce)
        variability_factor = 1.0 + cancellation_rate 
        
        return FactoryPhysics.vut_equation(
            ca=variability_factor, 
            ce=1.0, # Assumed process consistency
            u=chair_utilization, 
            te=avg_appt_time
        )
