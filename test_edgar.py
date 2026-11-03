import edgar as E

def main():
    h = "<html><body><p>Revenue was <b>$1,234</b> million&nbsp;in Q1.</p><table><tr><td>EPS</td><td>0.45</td></tr></table><script>x=1</script></body></html>"
    t = E.metne(h)
    assert "Revenue was $1,234 million in Q1." in t and "EPS | 0.45" in t and "x=1" not in t, t
    print("test_edgar: tamam")

main()
