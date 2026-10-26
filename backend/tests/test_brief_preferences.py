import pytest
from pydantic import ValidationError

from app.api_schemas import BriefCreate, BriefPreferences


def test_brief_preferences_preserve_ui_inputs_and_decimal_strings():
    brief = BriefCreate(category="DEMO soap", geography="DEMO India", customer="DEMO buyer", objective="DEMO decision",
        preferences=BriefPreferences(price_segment="Mid-premium", own_price="125.50", own_weight_g="100"))
    assert brief.model_dump(mode="json")["preferences"] == {
        "price_segment": "Mid-premium", "own_price": "125.50", "own_weight_g": "100", "currency": "INR"}


@pytest.mark.parametrize("payload", [{"own_price": "-1"}, {"own_weight_g": "0"}, {"own_price": "NaN"}, {"own_weight_g": "Infinity"}, {"price_segment": "invented"}, {"currency": "USD"}])
def test_brief_preferences_reject_invalid_values(payload):
    with pytest.raises(ValidationError):
        BriefPreferences(**payload)
