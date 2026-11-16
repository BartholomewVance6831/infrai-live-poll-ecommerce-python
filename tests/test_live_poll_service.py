from src.live_poll_service import decide_checkout


def test_checkout_waits_for_a_clear_live_poll_result():
    result = decide_checkout("order-1042", {"morning": 4, "evening": 2})

    assert result.winner == "morning"
    assert result.votes == 4
    assert result.checkout_allowed is True


def test_checkout_stays_closed_until_three_votes_agree():
    assert decide_checkout("order-1042", {"morning": 2, "evening": 1}).checkout_allowed is False
