import pytest
from science_diagnostic_agent.models import FactorCode, FACTOR_TO_CATEGORY
from science_diagnostic_agent.factor_rules import FACTOR_PUBLIC_LABELS
from science_diagnostic_agent.result_catalog import CATEGORY_DESCRIPTIONS, _PREVIEW_EVIDENCE

def test_factor_code_mapping_integrity():
    """Ensure every FactorCode has a category mapping and a public label"""
    for code in FactorCode:
        assert code in FACTOR_TO_CATEGORY, f"Missing category mapping for {code}"
        assert code in FACTOR_PUBLIC_LABELS, f"Missing public label for {code}"

def test_taste_invariants_no_forbidden_words():
    """Ensure no forbidden words (e.g. 粗心, 笨, 态度不端正) exist in public text generation strings"""
    forbidden_words = ["粗心", "笨", "态度不端正", "不认真", "不努力"]

    # Check category descriptions
    for cat, desc in CATEGORY_DESCRIPTIONS.items():
        for word in forbidden_words:
            assert word not in desc, f"Forbidden word '{word}' found in CATEGORY_DESCRIPTIONS for {cat}"

    # Check preview evidence
    for key, ev_list in _PREVIEW_EVIDENCE.items():
        for ev in ev_list:
            for word in forbidden_words:
                assert word not in ev, f"Forbidden word '{word}' found in _PREVIEW_EVIDENCE for {key}: '{ev}'"

    # We could also check prompts.py, but prompts.py contains the word '粗心' explicitly
    # to tell the LLM *not* to use it ("粗心永远不是结论"). So we only check user-facing strings here.
