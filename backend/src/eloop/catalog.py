"""Device categories the platform understands.

Weights and scrap-value ranges are *indicative placeholders* meant to be replaced with real
recycler quotes. They exist so the user sees a sensible estimate before a collector confirms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Category:
    key: str
    label: str
    hazard: str  # "low" | "moderate" | "high"
    typical_weight_g: int
    value_inr: tuple[int, int]  # indicative scrap value per unit
    materials: tuple[str, ...]
    handling: str
    labels: tuple[str, ...]  # lowercase Amazon Rekognition label names that map to this category

    def public(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "hazard": self.hazard,
            "typical_weight_g": self.typical_weight_g,
            "value_inr_min": self.value_inr[0],
            "value_inr_max": self.value_inr[1],
            "materials": list(self.materials),
            "handling": self.handling,
        }


CATEGORIES: tuple[Category, ...] = (
    Category(
        "smartphone", "Smartphone", "moderate", 180, (80, 400),
        ("Lithium-ion battery", "Copper", "Gold", "Rare earths"),
        "Keep the battery in place. Do not open, crush or puncture the device.",
        ("mobile phone", "phone", "cell phone", "iphone", "smartphone"),
    ),
    Category(
        "laptop", "Laptop", "moderate", 2200, (300, 1500),
        ("Lithium-ion battery", "Aluminium", "Copper", "Gold"),
        "Power it off fully. Remove personal data before handing over.",
        ("laptop", "notebook computer"),
    ),
    Category(
        "tablet", "Tablet", "moderate", 480, (100, 500),
        ("Lithium-ion battery", "Glass", "Copper"),
        "Keep the screen intact if possible. Do not open the casing.",
        ("tablet computer", "ipad", "tablet"),
    ),
    Category(
        "tv_monitor", "TV or monitor", "moderate", 4500, (150, 800),
        ("Glass", "Plastics", "Copper", "Circuit boards"),
        "Carry upright with two hands. Do not stack other items on the screen.",
        ("monitor", "television", "tv", "lcd screen", "computer monitor", "display", "screen"),
    ),
    Category(
        "battery_pack", "Batteries and power banks", "high", 300, (30, 150),
        ("Lithium-ion cells", "Cobalt", "Nickel"),
        "Tape the terminals, keep away from heat and water, and never throw into household bins.",
        ("battery", "power bank", "batteries"),
    ),
    Category(
        "charger_cable", "Chargers and cables", "low", 120, (5, 40),
        ("Copper", "PVC"),
        "Bundle cables together. No special handling needed.",
        ("cable", "adapter", "charger", "power adapter", "plug", "usb", "electrical plug"),
    ),
    Category(
        "small_appliance", "Small appliance", "low", 1500, (20, 200),
        ("Steel", "Copper", "Plastics"),
        "Empty and clean the appliance. Wrap loose cords.",
        ("appliance", "toaster", "blender", "microwave", "kettle", "iron", "electric fan",
         "hair dryer", "mixer"),
    ),
    Category(
        "keyboard_mouse", "Keyboards and mice", "low", 450, (10, 60),
        ("Plastics", "Copper"),
        "No special handling needed.",
        ("keyboard", "computer keyboard", "mouse", "computer mouse"),
    ),
    Category(
        "circuit_board", "Loose circuit boards", "moderate", 250, (40, 250),
        ("Gold", "Silver", "Palladium", "Copper"),
        "Handle by the edges and keep dry. Boards may contain lead solder.",
        ("circuit board", "electronic chip", "motherboard", "printed circuit board"),
    ),
    Category(
        "router_modem", "Router or modem", "low", 350, (30, 150),
        ("Plastics", "Copper", "Circuit boards"),
        "Remove adapters and cables and bundle them separately.",
        ("router", "modem", "wireless router", "network router"),
    ),
    Category(
        "headphones", "Headphones and earbuds", "moderate", 200, (10, 80),
        ("Lithium cell (wireless models)", "Copper", "Plastics"),
        "Wireless models contain small batteries. Keep them dry.",
        ("headphones", "headset", "earphone", "earbuds", "earphones"),
    ),
)

BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}
LABEL_INDEX: dict[str, str] = {label: c.key for c in CATEGORIES for label in c.labels}
