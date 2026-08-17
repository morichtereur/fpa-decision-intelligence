from src import config as C


def test_paths_are_under_root():
    assert C.RAW == C.DATA / "raw"
    assert C.FACTS == C.DATA / "facts"


def test_scope_is_fixed_to_one_company():
    assert C.COMPANY == "adidas AG"
    assert C.CHANNELS == ["Wholesale", "Direct-to-Consumer"]
    assert C.CATEGORIES == ["Footwear", "Apparel", "Accessories and Gear"]
    assert C.FISCAL_YEARS == [2023, 2024, 2025]
