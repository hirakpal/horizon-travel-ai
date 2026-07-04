# tests/test_travel_dna.py
from src.models.user import HotelPreferences, UserProfile
from src.models.travel_dna import compute_dna_axes, has_learned_dna, learned_preference_rows


def test_has_learned_dna_false_for_empty_profile():
    assert has_learned_dna(UserProfile()) is False


def test_has_learned_dna_true_when_any_signal_present():
    assert has_learned_dna(UserProfile(food_preferences=["vegetarian"])) is True
    assert has_learned_dna(UserProfile(travel_preferences=["adventure"])) is True
    assert has_learned_dna(UserProfile(travel_dna_notes=["Loves museums"])) is True


def test_compute_dna_axes_all_baseline_for_empty_profile():
    axes = compute_dna_axes(UserProfile())
    assert all(score == 50 for score in axes.values())
    assert set(axes.keys()) == {"Adventure", "Culture", "Food", "Photography", "Relax", "Walking", "Nightlife"}


def test_compute_dna_axes_boosts_relevant_axes():
    profile = UserProfile(travel_preferences=["adventure", "photography", "nightlife"],
                           food_preferences=["vegetarian"])
    axes = compute_dna_axes(profile)
    assert axes["Adventure"] == 80
    assert axes["Photography"] == 85
    assert axes["Nightlife"] == 85
    assert axes["Food"] == 75
    assert axes["Culture"] == 50  # untouched


def test_compute_dna_axes_nature_wildlife_boosts_two_axes():
    profile = UserProfile(travel_preferences=["nature_wildlife"])
    axes = compute_dna_axes(profile)
    assert axes["Adventure"] == 65
    assert axes["Walking"] == 65


def test_compute_dna_axes_caps_at_100():
    profile = UserProfile(travel_preferences=["adventure", "nature_wildlife"])
    axes = compute_dna_axes(profile)
    assert axes["Adventure"] == 95  # 50 + 30 + 15, still under 100
    profile2 = UserProfile(travel_preferences=["photography"])
    # stack an already-high value to confirm capping logic itself works
    axes2 = compute_dna_axes(profile2)
    assert axes2["Photography"] == 85
    assert max(compute_dna_axes(UserProfile(travel_preferences=[
        "adventure", "nature_wildlife", "photography", "relaxation", "wellness_spa", "luxury", "nightlife"
    ])).values()) <= 100


def test_learned_preference_rows_only_includes_populated_fields():
    rows = learned_preference_rows(UserProfile())
    assert rows == []

    profile = UserProfile(food_preferences=["vegetarian", "vegan"])
    rows = learned_preference_rows(profile)
    assert rows == [("food preferences", "Vegetarian, Vegan")]


def test_learned_preference_rows_hotel_style_combines_fields():
    profile = UserProfile(hotel_preferences=HotelPreferences(
        budget_tier="high", bed_type="King", view="Sea view", pool=True, spa=True))
    rows = learned_preference_rows(profile)
    hotel_row = dict(rows)["hotel style"]
    assert "high tier" in hotel_row
    assert "king" in hotel_row
    assert "sea view" in hotel_row
    assert "pool + spa" in hotel_row


def test_learned_preference_rows_skips_no_preference_hotel_fields():
    profile = UserProfile(hotel_preferences=HotelPreferences(budget_tier="medium"))
    rows = learned_preference_rows(profile)
    assert dict(rows)["hotel style"] == "medium tier"
