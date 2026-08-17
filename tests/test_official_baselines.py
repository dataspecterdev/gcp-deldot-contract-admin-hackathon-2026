from ccrf.review import load_official_baselines, official_excerpt_block
from ccrf.statute import retrieve_statute_excerpt


def test_team_confirmed_baselines_load():
    data = load_official_baselines()
    for rid in ("CC-07", "CC-09", "CC-10", "CC-11", "CC-12", "CC-13", "CC-14"):
        assert rid in data, rid
        assert data[rid].get("excerpt")
    assert "50 percent" in data["CC-14"]["excerpt"]
    assert "7 calendar days" in data["CC-12"]["excerpt"]
    assert "oral promise" in data["CC-11"]["excerpt"]
    assert "General Description" in data["CC-10"]["excerpt"]
    assert "30 days" in data["CC-07"]["excerpt"]
    assert "three years" in data["CC-13"]["excerpt"]
    block = official_excerpt_block("CC-07")
    assert "6967" in block or "business license" in block.lower()


def test_title29_retrieved_only_for_overlap_ccs():
    bid = retrieve_statute_excerpt("CC-02")
    assert "10%" in bid
    assert "6960" not in bid  # prevailing wage stays out
    assert len(bid) < 2500
    bonds = retrieve_statute_excerpt("CC-04")
    assert "100%" in bonds
    licenses = retrieve_statute_excerpt("CC-07")
    assert "30 days" in licenses
    assert retrieve_statute_excerpt("CC-14") == ""  # keep DelDOT 108.1, not building 50%
    assert retrieve_statute_excerpt("CC-09") == ""
