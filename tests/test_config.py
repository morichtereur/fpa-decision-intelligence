from src import config as C


def test_paths_are_under_root():
    assert C.RAW == C.DATA / "raw"
    assert C.FACTS == C.DATA / "facts"


def test_the_application_is_no_longer_scoped_to_one_company():
    """This test used to assert the opposite — that the scope was fixed to
    adidas. That was true of the product it described, and is deliberately
    untrue of this one: client configurability is the point. adidas remains
    the default so that every existing entry point keeps its behaviour."""
    from src import clientpack

    assert clientpack.DEFAULT_CLIENT == "adidas"
    assert set(clientpack.available_clients()) >= {"adidas", "manufacturing_demo"}


def test_adidas_constants_still_describe_the_default_client():
    """C.COMPANY and friends now describe the *default* client's extraction
    scope — src/extract.py still reads adidas PDFs against them."""
    assert C.COMPANY == "adidas AG"
    assert C.CHANNELS == ["Wholesale", "Direct-to-Consumer"]
    assert C.CATEGORIES == ["Footwear", "Apparel", "Accessories and Gear"]
    assert C.FISCAL_YEARS == [2023, 2024, 2025]
