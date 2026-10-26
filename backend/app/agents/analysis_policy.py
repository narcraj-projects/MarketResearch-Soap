"""Versioned offline strategy baseline. Proposals are tests, never claims of proven demand."""
from app.harness.analysis_types import OpportunityRule
import re

VERSION = "comparison-rules-1.0"
MEDICAL = re.compile(r"\b(?:cur(?:e[sd]?|ing)|treat(?:s|ed|ing)?|heal(?:s|ed|ing)?|prevent(?:s|ed|ing)?|acne|eczema|psoriasis|dermatitis|clinically\s+proven|medically\s+effective|certified\s+organic)\b", re.I)
RULES: dict[OpportunityRule, tuple[str, str, str, str, str]] = {
    "price_testing": ("Test a price proposition within the observed range", "Comparable per-100g observations differ within this sample; linked listing records are the premise, not market-wide demand.",
        "Could clarify whether customers value the proposed offer.", "Unit economics permit a test and sampled alternatives are relevant.", "Plan a small pricing/message test; validate costs and willingness to pay before changing prices."),
    "pack_clarity": ("Test clearer pack and weight information", "Retrieved listings differ in available pack/weight information; missing data concerns this evidence set only.",
        "Could make purchase quantities easier to understand.", "Clarity matters to target shoppers; missing information may exist elsewhere.", "Prototype an explicit total-weight and pack-count label and test comprehension."),
    "disclosure": ("Test more useful ingredient disclosure", "Sampled disclosed ingredient information differs or is unavailable in some retrieved listings.",
        "Could help shoppers compare disclosed ingredients without efficacy promises.", "Target shoppers value disclosure; published lists may be incomplete.", "Review actual formulation disclosure and test a clear ingredient-label prototype."),
    "positioning_test": ("Test a distinct positioning message", "At least two sampled competitors use different positioning language; these are source claims, not measured market positions.",
        "Could identify a message customers understand and prefer.", "The sampled language is relevant; no unobserved market gap is established.", "Draft alternative non-medical messages and plan a blinded comprehension test."),
    "feedback_test": ("Test the experience mentioned in public feedback", "Public feedback is available for at least two sampled competitors; individual source-reported comments are not representative demand.",
        "Could reveal which experience details deserve a limited test.", "The comments may be biased and target customers may disagree.", "Design a small experience test based on the cited comments without inventing testimonials.")}

FIELD_GROUPS = {
    "products": {"product", "product_type", "sku", "variant"}, "ingredients": {"ingredients"},
    "prices": {"price", "currency", "weight_g", "weight_basis", "pack_qty"},
    "positioning": {"positioning", "marketing_claim"}, "audience": {"audience"},
    "channels": {"channels"}, "packaging": {"packaging"}, "feedback": {"public_review"},
    "launches": {"reported_launch", "news", "published_date"}}
