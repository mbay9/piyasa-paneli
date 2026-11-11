import edgar as E

def main():
    h = "<html><body><p>Revenue was <b>$1,234</b> million&nbsp;in Q1.</p><table><tr><td>EPS</td><td>0.45</td></tr></table><script>x=1</script></body></html>"
    t = E.metne(h)
    assert "Revenue was $1,234 million in Q1." in t and "EPS | 0.45" in t and "x=1" not in t, t
    print("test_edgar: tamam")

main()

def t_temizle():
    import tempfile, os, datetime as dt
    d = tempfile.mkdtemp()
    for s, f in (("AAA", "2026-01-05_x.txt"), ("AAA", "2026-10-30_y.txt"), ("BBB", "2026-02-01_z_10-Q_nakit.txt"), ("BBB", "not.txt")):
        os.makedirs(os.path.join(d, s), exist_ok=True); open(os.path.join(d, s, f), "w").write("x")
    assert E.temizle(d, dt.date(2026, 11, 10)) == 2
    assert sorted(os.listdir(os.path.join(d, "AAA"))) == ["2026-10-30_y.txt"] and os.listdir(os.path.join(d, "BBB")) == ["not.txt"]

t_temizle(); print("test_edgar temizle: tamam")
