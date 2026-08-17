from ccrf.evidence import evidence_supported


def test_exact_quote_matches():
    corpus = "The proposal guaranty shall equal 10% of the total bid price."
    assert evidence_supported("proposal guaranty shall equal 10% of the total bid price", corpus)


def test_invented_quote_fails():
    corpus = "The proposal guaranty shall equal 10% of the total bid price."
    assert not evidence_supported("oral direction immediately changes time and price", corpus)
