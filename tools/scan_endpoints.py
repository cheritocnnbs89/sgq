import re, os, sys
BASE = sys.argv[1] if len(sys.argv) > 1 else "templates"
pat = re.compile(r"url_for\(\s*[\"']([a-zA-Z0-9_]+)[\"']")

found = {}
for root, _, files in os.walk(BASE):
    for f in files:
        if not f.lower().endswith((".html", ".htm", ".jinja2", ".j2")):
            continue
        p = os.path.join(root, f)
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                txt = fh.read()
            for m in pat.finditer(txt):
                ep = m.group(1)
                found.setdefault(ep, []).append(os.path.relpath(p, BASE))
        except Exception as e:
            print("No pude leer", p, e)

print("\nEndpoints referenciados en templates:")
for ep, files in sorted(found.items()):
    print(f" - {ep}: {len(files)} referencia(s) en {set(files)}")
