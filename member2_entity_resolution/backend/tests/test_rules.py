from app.entity_resolution.rules import ACCEPT, REJECT, UNDECIDED, verdict


def test_same_model_different_format():
    assert verdict("Sony Turntable - PSLX350H", "Sony PS-LX350H Belt Drive Turntable")[0] == ACCEPT


def test_different_model_numbers():
    assert verdict("Linksys 8-port switch EZXS88W", "Linksys 16-port switch EZXS16W")[0] == REJECT


def test_capacity_conflict():
    assert verdict(
        "Kingston 2GB DDR memory kit",
        "Kingston 4GB DDR memory kit"
    ) == (UNDECIDED, "capacity_conflict")


def test_no_evidence():
    assert verdict("Sony turntable", "Sony record player")[0] == UNDECIDED

def test_variant_suffix_is_undecided():
    assert verdict("Sony DSCW150 camera", "Sony DSC-W150N camera")[0] == UNDECIDED


def test_one_digit_differs_is_rejected():
    assert verdict("Sony DSCW150 camera", "Sony DSCW170 camera")[0] == REJECT

def test_aperture_is_not_a_model():
    assert verdict("Canon EF-S 55-250mm f/4-5.6 IS Lens - 2044B002",
                   "Canon EF 70-300mm f/4-5.6 IS USM Lens - 0345B002")[0] == REJECT


def test_shared_family_token_is_not_enough():
    assert verdict("495916-B21 HP E5506 ML350 G6 CPU Kit",
                   "601248-B21 HP E5507 ML350 G6 CPU Kit")[0] != ACCEPT


def test_dot_separator_normalised():
    assert verdict("TomTom Mount - 9N00101", "TOMTOM Mount Kit - 9N00.101")[0] == ACCEPT


def test_long_digit_code_compared():
    assert verdict("Weber Grill E-310 - 3741001", "Weber Grill E-310 3841001")[0] == REJECT