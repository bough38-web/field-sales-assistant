
import pytest
import pandas as pd
from src.utils import mask_name, normalize_address

def test_mask_name():
    assert mask_name("홍길동") == "홍*동"
    assert mask_name("이철") == "이*"
    assert mask_name("김") == "김"
    assert mask_name("") == ""
    assert mask_name(None) is None
    assert mask_name("남궁민수") == "남**수"

def test_normalize_address():
    assert normalize_address("서울특별시 강남구") == "서울시 강남구"
    assert normalize_address("강원특별자치도 춘천시") == "강원도 춘천시"
    assert normalize_address("  서울시  ") == "서울시"
    assert normalize_address("아파트(101동)") == "아파트"
