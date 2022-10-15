from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Any, Optional


@dataclass
class DisplayData:
    electric_cost: float = 0.0
    forecast: List[Any] = field(default_factory=lambda: [])
    day_lowhigh: List[float] = field(default_factory=lambda: [float("nan"), float("nan")])
    day_lowhigh_date: Optional[datetime] = None
    daily_energy: float = 0.0
    soil_moisture: float = float("nan")

