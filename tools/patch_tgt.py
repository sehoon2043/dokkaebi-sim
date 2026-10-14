# 도술마다 광역(대상 수)/단일 표시 + 스타일별 탭(boss_*, hunt_*) 줄 묶기
import sys, json
p, tgt_path = sys.argv[1], sys.argv[2]
h = open(p, encoding="utf-8").read()
T = json.load(open(tgt_path, encoding="utf-8"))
def rep(a, b):
    global h
    assert h.count(a) == 1, a[:60]
    h = h.replace(a, b)
rep('function named(attrs, n, text){ const e = el("span", attrs, text); e.prepend(icon(n)); return e; }',
    'const TGT = ' + json.dumps(T, ensure_ascii=False) + ';\n'
    'function named(attrs, n, text){ const e = el("span", attrs, text); e.prepend(icon(n)); const t = TGT[n];'
    ' if (t) e.appendChild(el("span", {class: "tgt" + (t > 1 ? " aoe" : "")}, t > 1 ? "광역 " + t : "단일")); return e; }')
rep(".tab-sub{font-weight:400;font-size:.8em;opacity:.85}",
    ".tab-sub{font-weight:400;font-size:.8em;opacity:.85}\n.tgt{display:inline-block;font-size:.66rem;line-height:1.5;padding:0 5px;margin-left:4px;border-radius:999px;border:1px solid var(--line);color:var(--muted);white-space:nowrap;vertical-align:1px;font-weight:500}"
    ".tgt.aoe{border-color:var(--accent);color:var(--accent)}")
rep('    const g = GRP[t.id] || "기타";',
    '    const g = GRP[t.id] || (t.id.startsWith("boss_") ? "보스" : t.id.startsWith("hunt_") ? "필드 사냥" : t.id.startsWith("comm_") ? "커뮤니티 덱" : "기타");')
open(p, "w", encoding="utf-8").write(h); print("patched", len(T))
