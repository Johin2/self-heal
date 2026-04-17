import pytest

from mymod import extract_price


@pytest.mark.heal(target="mymod.extract_price")
def test_rupees():
    assert extract_price("₹1,299") == 1299.0


@pytest.mark.heal(target="mymod.extract_price")
def test_dollars():
    assert extract_price("$12.99") == 12.99


@pytest.mark.heal(target="mymod.extract_price")
def test_euros():
    assert extract_price("€5,49") == 5.49
