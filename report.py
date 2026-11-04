#!/usr/bin/env python3
"""Build <RADAR_DATA_DIR>/reports/<date>.md from one radar run.

Inputs (all under <RADAR_DATA_DIR>/runs/<date>/): `sayac.json` (counter), `adaylar.json`, `elenenler.json`
(written by radar.py) and, optionally, files written by the deep-evaluation step: `cards.md`, `notes.md`, `limits.md`,
`rubric/*.json` (schema: docs/evaluation-prompt.md).

Usage: python3 report.py 2026-11-04
"""
import glob, json, os, sys

DATA = os.path.abspath(os.environ.get('RADAR_DATA_DIR') or os.path.join(os.getcwd(), 'radar-data'))
if len(sys.argv) < 2:
    sys.exit('usage: python3 report.py YYYY-MM-DD')
T = sys.argv[1]
G = os.path.join(DATA, 'runs', T)
ST = os.path.join(DATA, 'state')


def jl(p, default=None):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        if default is None:
            sys.exit(f'missing or unreadable: {p} (run radar.py first)')
        return default


def txt(p):
    return open(p, encoding='utf-8').read().strip() + '\n' if os.path.exists(p) else None


def rk(j, *keys, default=''):
    """read a rubric field by English key, falling back to the original Turkish key."""
    for k in keys:
        if k in j:
            return j[k]
    return default


s = jl(os.path.join(G, 'sayac.json'))
a = jl(os.path.join(G, 'adaylar.json'))
el = jl(os.path.join(G, 'elenenler.json'))
rub = [r for r in sorted(glob.glob(os.path.join(G, 'rubric', '*.json'))) if not os.path.basename(r).startswith('_')]
snap = jl(os.path.join(ST, 'izleme_snap', f'{T}.json'), {})
iz = jl(os.path.join(ST, 'izleme.json'), {'repolar': []})
o = s['ozet']
L = [f'# PoW/PoS Radar — {T}\n',
     f"> Generated {s['uretim'][:16]}Z · window: repos created in the last {s['pencere_gun']} days · status **{s['durum']}** · read-only; no candidate code was executed. Not financial advice.\n"]
n = txt(os.path.join(G, 'notes.md'))
if n:
    L.append(n)
L.append('## 1. Counter\n')
L.append(f"**{o['sorgu']} queries · {o['taranan_tekil']} unique candidates scanned · {o['tekrar_defterde']} already in the ledger · "
         f"{o['elenen']} rejected by cheap filters · {o['kota_disi']} below threshold / over the per-run cap · {o['kalan_derin']} sent to deep evaluation "
         f"({o.get('kuyruktan', 0)} from the queue) · watchlist {o['izleme']} (momentum {o['ivmelenen']})**\n")
L.append('| Step | Scanned | Returned | Rejected | Left | Note |\n|---|---:|---:|---:|---:|---|')
for st in s['adimlar']:
    note = st.get('not_') or ''
    if st.get('eleme'):
        note = ', '.join(f'{k} {v}' for k, v in st['eleme'].items())
    for k, en in (('tekil', 'unique'), ('github_repo', 'github_repos'), ('mainnet', 'mainnet'), ('havuza_giren_90g', 'added_≤90d'),
                  ('eslesen', 'matched'), ('secilen', 'selected'), ('kota_disi', 'over_cap'), ('ivmelenen', 'momentum'),
                  ('fork_parent_yeni', 'new_fork_parents'), ('turev', 'derived'), ('onceki_snapshot', 'prev_snapshot')):
        if k in st:
            note += f' · {en}={st[k]}'
    L.append(f"| {st['adim']} | {st.get('taranan', '')} | {st.get('donen', '')} | {st.get('elenen', '')} | {st.get('kalan', st.get('secilen', ''))} | {note.strip(' ·')} |")
c = s['cagri']
L.append(f"\nCalls: search {c['search']} · REST {c['rest']} · GraphQL {c['graphql']} ({c['graphql_puan']} points) · external HTTP {c['harici_http']} · X {c['x']}. "
         f"Errors: {len(s['hatalar'])} · warnings: {len(s['uyarilar'])}.\n")
if s['hatalar']:
    L.append('Errors: ' + '; '.join(f"{h['kaynak']}: {h['hata'][:80]}" for h in s['hatalar']) + '\n')
for u in s['uyarilar']:
    L.append(f'- ⚠️ {u}')

L.append('\n## 2. Candidates for deep evaluation\n')
cards = txt(os.path.join(G, 'cards.md'))
if cards:
    L.append(cards)
else:
    L.append('_No cards yet: run the deep-evaluation step (docs/evaluation-prompt.md) on `adaylar.json`, or read the list below._\n')
    L.append('| Priority | Repo | Lane | Tags | Why it ranked |\n|---:|---|---|---|---|')
    for x in a.get('adaylar', [])[:30]:
        g = x.get('gerekce') or []
        g = '; '.join(g[:3]) if isinstance(g, list) else str(g)[:120]
        L.append(f"| {x.get('oncelik')} | [{x['repo']}]({x.get('url')}) | {x.get('serit', '')} | {', '.join(x.get('etiketler') or [])[:60]} | {g[:120].replace('|', '/')} |")
if rub:
    L.append('\n### Rubric summary\n\n| Project | Class | Conservative | Score | Coverage | Reason |\n|---|---|---:|---:|---:|---|')
    for r in rub:
        j = jl(r)
        cov = rk(j, 'coverage', 'kapsam', default=0) or 0
        L.append(f"| {rk(j, 'project', 'proje')} | {rk(j, 'class', 'sinif')} | {rk(j, 'conservative_score', 'konservatif_skor')} | "
                 f"{rk(j, 'score', 'skor')} | {round(cov * 100)}% | {rk(j, 'class_reason', 'sinif_gerekce')} |")

L.append('\n## 3. Watchlist (snapshot)\n')
L.append('| Repo | Why | ★ | Forks | Releases (latest) | Commits 7d / 30d | Last push |\n|---|---|---:|---:|---|---|---|')
for x in iz['repolar']:
    sn = snap.get(x['repo'], {})
    L.append(f"| {x['repo']} | {x.get('neden', '')[:70]} | {sn.get('stars', '')} | {sn.get('forks', '')} | {sn.get('releases', '')} ({sn.get('latest_release') or '—'}) | "
             f"{sn.get('commits_7g', '')} / {sn.get('commits_30g', '—')} | {(sn.get('pushed') or '')[:10]} |")
if a.get('izleme_ivme'):
    L.append('\nMomentum signals: ' + '; '.join(f"{x['repo']}: {', '.join(x['isaret'])}" for x in a['izleme_ivme']))
L.append('\n(Star deltas need a previous snapshot; the first day shows none.)\n')

L.append('## 4. Below threshold / over the cap (top 25; not deep-evaluated)\n')
L.append('| Priority | Repo | Lane | Tags | Description |\n|---:|---|---|---|---|')
for x in a.get('kota_disi', [])[:25]:
    L.append(f"| {x['oncelik']} | {x['repo']} | {x['serit']} | {', '.join(x['etiketler'])[:60]} | {(x['aciklama'] or '')[:90].replace('|', '/')} |")

L.append('\n## 5. Rejected by cheap filters (with reason)\n')
by = {}
for x in el:
    by.setdefault(x['neden'].split(' ')[0], []).append(x)
for k, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
    L.append(f'**{k}** — {len(xs)}')
    show = xs if k != 'score<2' else xs[:12]
    for x in show:
        L.append(f"- {x['repo']} — {x['neden'][:110]}" + (f" · _{x['aciklama'][:70]}_" if x['aciklama'] else ''))
    if k == 'score<2' and len(xs) > 12:
        L.append(f'- … +{len(xs) - 12} (full list: `runs/{T}/elenenler.json`)')
    L.append('')

L.append('## 6. External sources\n')
d = a.get('dis_kaynaklar', {})
b = d.get('bitcointalk', {})
L.append('**bitcointalk Altcoin ANN (page 1, PoW/PoS filtered):**')
for k in b.get('konular', []):
    L.append(f"- {'🟢' if k['pencerede'] else '⚪'} {k['ilk_ileti'] or '?'} · [{k['baslik'][:90]}](https://bitcointalk.org/index.php?topic={k['topic']}.0) · GitHub: {', '.join(k['github']) or 'none'}")
cr = d.get('chain_registry', [])
L.append('\n**Cosmos chain-registry (new chain.json in window):** ' + ('; '.join(
    f"{x.get('pretty_name')} ({'testnet' if x['testnet'] else 'mainnet'}, {x['tarih']}, repo {x.get('git_repo') or 'none'})" for x in cr) or 'none'))
for nm in ('rplant', 'whattomine'):
    x = d.get(nm, {})
    L.append(f"\n**{nm}:** {x.get('toplam')} coins; " + ('first run → baseline saved (new = 0).' if x.get('taban_cizgisi') else
             f"new: {', '.join(str(y.get('sembol') or y.get('ad')) for y in x.get('yeni', [])) or 'none'}"))
m = d.get('miningpoolstats', {})
if m.get('liste'):
    L.append('\n**miningpoolstats new coins** (saved from a browser): ' + '; '.join(
        f"{c['coin'].split('|')[1]} ({c['coin'].split('|')[0]}, {c['algo']}, ~{c['yas_gun']:.0f} d, {c['havuz']} pools)" for c in m['liste']))
else:
    L.append(f"\n**miningpoolstats:** {m.get('atlandi', 'none')}")
xx = d.get('x', {})
if xx:
    L.append(f"\n**X (twitterapi.io, 1 call):** {xx.get('tweet', xx.get('atlandi'))} tweets; GitHub links: {', '.join(xx.get('github', [])) or 'none'}")

lim = txt(os.path.join(G, 'limits.md'))
L.append('\n## 7. Known limits\n')
L.append(lim or '- Cheap filters are keyword/metadata based (measured precision ≈0.63, recall ≈0.80 on 80 labelled repos); a project that never says "proof of work", "validator", "mining" etc. in name/description/topics can be missed.\n'
         '- The created-in-window lane misses older repos that only recently became active; the momentum queries cover part of this.\n'
         '- Copy detection only knows the upstream root commits listed in radar.py; zip imports are caught heuristically.\n')
if rub:
    L.append('## Appendix A — Rubric JSON files\n')
    for r in rub:
        j = jl(r)
        L.append(f"### {rk(j, 'project', 'proje')} — `{os.path.relpath(r, DATA)}`\n\n```json\n{json.dumps(j, ensure_ascii=False, indent=1)}\n```\n")
os.makedirs(os.path.join(DATA, 'reports'), exist_ok=True)
out = os.path.join(DATA, 'reports', f'{T}.md')
body = '\n'.join(L)
open(out, 'w', encoding='utf-8').write(body)
print(out, len(body))
