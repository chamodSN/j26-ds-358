import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cross_encoder import query_to_text, product_to_text


def test_removes_price_limits_keeps_specs():
    assert query_to_text("gaming phone good battery under 60000") == "gaming phone good battery"
    assert query_to_text("8GB laptop under Rs 150,000") == "8GB laptop"
    assert query_to_text("earbuds less than $50") == "earbuds"
    assert query_to_text("phone 5000mah battery") == "phone 5000mah battery"      # spec, not price
    assert query_to_text("27 inch monitor 144hz") == "27 inch monitor 144hz"


def test_removes_price_words_platform_delivery():
    assert query_to_text("cheap wireless mouse") == "wireless mouse"
    assert query_to_text("redmi 12c on daraz free shipping") == "redmi 12c"
    assert query_to_text("amazon basics hdmi cable") == "amazon basics hdmi cable"  # brand kept


def test_price_span_from_m1_and_category_from_m3():
    q = query_to_text("gaming phone under LKR 60k", price_span="under LKR 60k", use_rules=False,
                      category="Mobile Phones > Smartphones")
    assert q == "[Mobile Phones > Smartphones] gaming phone"


def test_never_empty():
    assert query_to_text("cheap") == "cheap"


def test_key_value_format():
    p = {"title": "Pixel 8", "brand": "Google", "color": None}
    assert product_to_text(p, "key_value") == "Pixel 8 | brand: Google"


def test_numbers_with_units_are_specs_not_prices():
    assert query_to_text("tv under 50 inch") == "tv under 50 inch"
    assert query_to_text("ssd up to 2tb") == "ssd up to 2tb"
    assert query_to_text("laptop under 500") == "laptop"
    assert query_to_text("4k tv under $400") == "4k tv"


def test_found_in_esci_check():
    assert query_to_text("iphone chargers 5 pack") == "iphone chargers 5 pack"            # "rs 5" is not rupees
    assert query_to_text("headphones with microphone with free shipping") == "headphones with microphone"
    assert query_to_text("glorious model o-") == "glorious model o-"                       # unchanged query stays as typed
    assert query_to_text("rs 5000 earbuds") == "earbuds"

def test_found_in_s9c_noise_check():
    # "built in" / "plug in" / "add on" are part of the product, not left-over words
    assert query_to_text("laptop with camera and microphone built in under 60000") == "laptop with camera and microphone built in"
    assert query_to_text("add on camera lens on daraz") == "add on camera lens"
    # currency glued to the number (and the common LRK typo)
    assert query_to_text("phone under 30000LKR") == "phone"
    assert query_to_text("phone under 30000LRK") == "phone"
    # platform without "on/from": removed for marketplaces, kept for brands (amazon)
    assert query_to_text("daraz samsung phone") == "samsung phone"
    assert query_to_text("amazon fire tv stick") == "amazon fire tv stick"