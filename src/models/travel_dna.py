"""
Derives the Travel DNA radar axes and "learned preferences" summary from a
user's actual stored profile — no synthetic/demo numbers. A brand-new
profile with nothing synced in yet has no real signal, so callers should
check has_learned_dna() before rendering the radar as if it means something.
"""
from src.models.user import UserProfile

DNA_AXES_BASELINE = 50
DNA_AXES = ("Adventure", "Culture", "Food", "Photography", "Relax", "Walking", "Nightlife")


def has_learned_dna(profile: UserProfile) -> bool:
    return bool(profile.travel_preferences or profile.food_preferences or profile.travel_dna_notes)


def compute_dna_axes(profile: UserProfile) -> dict:
    """Maps the profile's travel/food preference tags onto the 7 radar axes.
    Starts every axis at a neutral baseline and adds weight for each stated
    preference that bears on it — deterministic and explainable, unlike a
    black-box score."""
    axes = {axis: DNA_AXES_BASELINE for axis in DNA_AXES}
    tags = set(profile.travel_preferences)

    if "adventure" in tags:
        axes["Adventure"] += 30
    if "nature_wildlife" in tags:
        axes["Adventure"] += 15
        axes["Walking"] += 15
    if "culture_heritage" in tags:
        axes["Culture"] += 30
    if "photography" in tags:
        axes["Photography"] += 35
    if "relaxation" in tags:
        axes["Relax"] += 30
    if "wellness_spa" in tags:
        axes["Relax"] += 20
    if "luxury" in tags:
        axes["Relax"] += 10
    if "nightlife" in tags:
        axes["Nightlife"] += 35
    if profile.food_preferences:
        axes["Food"] += 25

    return {axis: min(100, score) for axis, score in axes.items()}


def learned_preference_rows(profile: UserProfile) -> list:
    """(label, value) rows for the 'Learned preferences' panel — only for
    fields that actually have data, so an incomplete profile shows fewer
    rows rather than blank ones."""
    rows = []
    if profile.food_preferences:
        rows.append(("food preferences", ", ".join(p.replace("_", " ").title() for p in profile.food_preferences)))
    if profile.travel_preferences:
        rows.append(("travel style", ", ".join(p.replace("_", " ").title() for p in profile.travel_preferences)))
    if profile.inflight_preferences:
        rows.append(("in-flight", ", ".join(p.replace("_", " ").title() for p in profile.inflight_preferences)))

    hotel = profile.hotel_preferences
    hotel_bits = []
    if hotel.budget_tier:
        hotel_bits.append(f"{hotel.budget_tier} tier")
    if hotel.bed_type and hotel.bed_type != "No preference":
        hotel_bits.append(hotel.bed_type.lower())
    if hotel.view and hotel.view != "No preference":
        hotel_bits.append(hotel.view.lower())
    amenities = [a for a, flag in (("pool", hotel.pool), ("gym", hotel.gym), ("spa", hotel.spa)) if flag]
    if amenities:
        hotel_bits.append(" + ".join(amenities))
    if hotel_bits:
        rows.append(("hotel style", ", ".join(hotel_bits)))

    return rows
