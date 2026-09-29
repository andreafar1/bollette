from decimal import Decimal
from app.parser import PROVIDERS
def test_providers():
    assert PROVIDERS["enel"]=="Enel Energia"
    assert PROVIDERS["plenitude"]=="Eni Plenitude"
