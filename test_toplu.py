import tablo_toplu as T

def t_bul():
    assert T.bul("Revenue | $ | 6,055 | | 4,742", 6055e6) == "6,055"
    assert T.bul("revenue of $584,899 thousand", 584899000.0) == "584,899"
    assert T.bul("Revenue was 392.4 million", 392.4e6) == "392.4"
    assert T.bul("total 16,055 only", 6055e6) is None  # başka sayının parçası sayılmaz
    assert T.bul("revenue of $6.06 billion", 6055e6) == "6.06 billion"

def t_ceyrek():
    ce = {"2026-06-30": {}, "2026-09-30": {}, "2025-09-30": {}}
    assert T.ceyrek_anahtari(ce, "2026-10-21") == "2026-09-30"
    assert T.ceyrek_anahtari(ce, "2027-02-01") is None  # 110 günden eski çeyrek kullanılmaz
    assert T.gecen_yil(ce, "2026-09-30") == "2025-09-30"

t_bul(); t_ceyrek(); print("test_toplu: tamam")
