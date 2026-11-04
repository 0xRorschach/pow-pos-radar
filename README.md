# pow-pos-radar

A daily radar for **new proof-of-work, proof-of-stake and "useful work" chains on GitHub**. It finds fresh
node/miner repositories, throws out the noise cheaply and deterministically (forks, renamed copies, homework
projects, dApps, closed binaries, token "miners", ROI scams), ranks what is left, and hands a short list to a
deep-evaluation step that scores code, premine/distribution and network health with quoted evidence.

- `radar.py`: discovery + cheap filters + ledger + watchlist. Python 3 stdlib only, read-only against GitHub.
- `report.py`: renders one run as Markdown.
- `docs/evaluation-prompt.md`: the deep-evaluation protocol (gates G1–G8, 100-point rubric, JSON schema, card format)
  for a human or an LLM agent. Not automated here.

> **Not financial advice.** The radar describes code and public data. A high score is not a statement about the
> value of any token, and nothing here tells you to buy, mine or stake anything.

## Why

New chains appear on GitHub every day, and almost all of them are one of: a renamed Bitcoin/Monero/geth fork, a
blockchain-from-scratch tutorial, a smart-contract project that calls itself a "chain", a closed-source "miner", or
a scam. The few genuinely new networks are easiest to judge early, while the code is small and the launch is still
verifiable. The radar does the boring 95% of that filtering with ~60 API calls and leaves the reading to you.

## Pipeline (`radar.py`)

1. **Discovery.** 23 core GitHub search queries over a `created:>=` window (topics `proof-of-work`,
   `proof-of-stake`, `mining-pool`, `stratum`, `miner`, `mining`, `cosmos-sdk`, `substrate`, `depin`, `testnet`;
   keywords such as `"proof of work"`, `"mining pool"`, `hashrate`, `"full node"`, `pouw`; language-scoped
   `blockchain language:rust|go|c++`; multilingual synonyms such as mineração, minería, майнинг, 矿池, 挖矿),
   2 `fork:only` queries (forks are hidden by default; their parents reveal new upstreams), 4 momentum queries
   (older repos with ≥20 stars pushed this week), accounts known for porting miners/pools to new coins,
   bitcointalk Altcoin ANN board, rplant pool list, whattomine, Cosmos chain-registry (new `chain.json` →
   `codebase.git_repo`), miningpoolstats (only from a browser-saved file), and optionally one X search per day.
   Queries that only produced noise in testing were dropped: `L1`, "layer 1", `miner in:name`, `topic:validator`,
   `topic:consensus`, and any `in:readme`.
2. **Normalize + dedupe** by lower-case `owner/repo`; sources are merged; anything that already has a verdict in the
   ledger is skipped.
3. **Cheap keyword score** on name + description + topics: positive chain terms (capped at 3), −3 for education /
   captcha / raft / minecraft / data-mining style terms, −5 for scam terms (flasher, drainer, sniper, key finder,
   MEV bot…), +1 for systems languages, −1 for HTML/CSS/Solidity/notebooks, −1 for no description. Keep score ≥ 2.
   Measured on 80 hand-labelled repos: precision ≈ 0.63, recall ≈ 0.80.
4. **GraphQL enrichment** (8 repos per query, 1 point each) and hard filters: archived, empty, GitHub fork, skeleton
   (README < 200 B and ≤ 2 commits), dApp/contract repo without node files, closed binary (no source language but
   large releases), **old code re-uploaded** (first commit > 1 year older than the repo).
5. **Copy detection.** The root commit (found via the GraphQL history-cursor trick, no clone) is compared with known
   upstream roots: Bitcoin, Monero, go-ethereum (+bsc/core-geth), cosmos-sdk, polkadot-sdk, the Substrate solochain
   template, CometBFT, rusty-kaspa, Optimism. Also: `go.mod` module path, upstream file signatures with ≤ 20 commits
   (zip import), framework dependencies (cosmos-sdk/substrate/cometbft). GitHub's `isFork` misses all of these.
   **Derived coins are tagged, not rejected**; a fork with a real change can still be interesting.
6. **README check** (first 3 KB, survivors only): homework/tutorial wording without mainnet/testnet/genesis terms, and
   ROI wording ("guaranteed", "daily profit", "x% per day", cloud-mining contracts) are rejected.
7. **Cross-source match** by name tokens against rplant / whattomine / miningpoolstats lists, bitcointalk titles,
   X posts and miner-porter repos (miner/pool repos themselves are excluded from matching).
8. **Priority score** (deterministic): keyword score + lane bonus (useful-work 3 > PoW 2 > PoS 1, −1 for miner/pool
   repos) + **3 per extra independent source** + README chain terms + release + commits in 30d + CI + tests +
   systems language; penalties: derived codebase −1, **≥ 30 stars on a repo < 14 days old −2** (stars on brand-new
   repos are a scam signal, not quality), repo > 90 days old −2; missing LICENSE is flagged.
   Everything at **priority ≥ 4** goes to deep evaluation. `RADAR_MAX_DEEP` (default 20) only caps one run; the
   overflow is queued in the ledger and picked up next run, never silently dropped.
9. **Watchlist** snapshot (GitHub GraphQL + Gitea API): stars, forks, releases, commits 7d/30d. Momentum signals:
   ≥ 10 new stars, ≥ 20 commits in 7 days, new release.
10. **Counter**: scanned / returned / rejected / left per step, plus API call counts. If discovery returns 0 or more
    than half of the core queries fail, status is `ALARM` and the exit code is 2 (no silent empty days).

Typical budget for a 2-day window: ~29 searches, ~100 REST calls, ~30 GraphQL points, ~15 external HTTP requests,
a few minutes.

## Deep evaluation (optional, `docs/evaluation-prompt.md`)

- **Gates G1–G8** (any FAIL = reject): open-source node, open reference miner/validator, no paid node licence/NFT,
  no ROI promise, no centralized app "mining", no hidden copy, no hidden/denied premine, no seed-phrase requests.
- **100-point rubric**: Code 30 (originality, quality, bus factor, miner openness/dev fee, hardware fairness, audits),
  Product 20 (liveness, explorer/docs, independent pools, verifiable launch, delivery), Useful work 15 (only if
  claimed: is the work real, is there paying demand, is the reward tied to it), Economics 25 (premine, emission,
  reward source, dev fee, airdrop-farming trap), Team 10.
- Every score needs a verbatim quote from a file@commit or URL; the project's own claims cap a criterion at 2/4;
  unknowns are counted as 1 point in the **conservative score** used for ranking.
- Classes: `EARLY-CANDIDATE`, `WATCH`, `INSUFFICIENT-DATA`, `REJECT`. Record them with `radar.py record`.

### Pitfalls this method is built around
- A shallow clone's `--max-parents=0` commit is the shallow boundary, not the real root. Check the upstream root
  with `GET /repos/<o>/<r>/commits/<sha>` instead.
- Docs often describe code that was removed; verify reward split and consensus in current code and in the newest
  release branch.
- A prior mainnet that was wiped and relaunched ("clean slate") is invisible in a recent clone; read the project's
  forum history.
- "Bulletproofs" marketing on top of Borromean range proofs, a "Fuzzing" badge on a failing nightly, an "independent
  review" written by an AI: check the linked call, the last workflow runs and the reviewer line.
- Liveness ≠ decentralization: sample block producers across days and map them to genesis addresses.
- "No premine" + a disclosed founder share: do the arithmetic (pre-launch blocks × reward).
- Wallet/installer binaries under a look-alike org are a user-safety warning, not just a reject.

## Install

```bash
git clone https://github.com/grogureis/pow-pos-radar
cd pow-pos-radar
export GITHUB_TOKEN=...            # read-only token (fine-grained, public repos, no write scopes)
export RADAR_DATA_DIR=~/radar-data # where state/ and runs/ are kept (default ./radar-data)
```
Python 3.9+, no packages. Never commit the token; keep it in the environment or in a file pointed to by
`RADAR_ENV_FILE` (`KEY=VALUE` lines, git-ignored).

## Run

```bash
python3 radar.py --days 7          # first run: wider window; creates the ledger and copies izleme.example.json
python3 radar.py                   # daily run (2-day window)
python3 radar.py --x               # + one twitterapi.io search (needs TWITTERAPI_IO_KEY; max one call per day)
python3 report.py 2026-11-04       # Markdown report for that run date

# after evaluating a candidate (by hand or with docs/evaluation-prompt.md):
python3 radar.py record someorg/somechain WATCH "original Go PoW, testnet only, single developer" --score 55
python3 radar.py record someorg/otherchain REJECT "renamed Monero fork, hidden 20% premine" --score 22
python3 radar.py record someorg/nearmiss REJECT "conservative 46, early testnet" --score 46 --watch
```

Other settings: `RADAR_UTC_OFFSET` (hours, run-date label), `RADAR_MAX_DEEP`, `RADAR_PORTERS`
(comma-separated GitHub accounts). Daily cron example:

```cron
30 6 * * *  cd /path/to/pow-pos-radar && GITHUB_TOKEN=... RADAR_DATA_DIR=/path/to/radar-data python3 radar.py && python3 report.py $(date -u +\%F)
```

## Files written

```
$RADAR_DATA_DIR/state/defter.json           ledger: every candidate seen, sources, verdict, reason, T+7/30/90 dates, queue
$RADAR_DATA_DIR/state/izleme.json           watchlist (seeded from izleme.example.json)
$RADAR_DATA_DIR/state/izleme_snap/<date>.json   daily watchlist snapshot (momentum = diff with the previous one)
$RADAR_DATA_DIR/state/dis_kaynak/*.json     rplant / whattomine / miningpoolstats baselines (diff = new coins)
$RADAR_DATA_DIR/state/x_log.json            one-X-call-per-day lock and cache
$RADAR_DATA_DIR/runs/<date>/adaylar.json    candidates for deep evaluation (+ below-threshold, momentum, external sources)
$RADAR_DATA_DIR/runs/<date>/elenenler.json  rejected candidates with reasons
$RADAR_DATA_DIR/runs/<date>/sayac.json      counter: per-step numbers, API calls, errors, status OK/WARN/ALARM
$RADAR_DATA_DIR/reports/<date>.md           report.py output
```
Optional inputs written by the evaluation step: `runs/<date>/cards.md`, `notes.md`, `limits.md`,
`rubric/<owner>__<repo>.json`. Internal JSON keys are Turkish (`adaylar` candidates, `elenenler` rejected,
`defter` ledger, `izleme` watchlist, `oncelik` priority, `serit` lane, `etiketler` tags, `gerekce` reason);
the printed output and reports are English.

## Output example (synthetic)

```
radar 2026-11-04 window created>=2026-11-02 (2 days)
[step] {"adim": "1-core-search", "taranan": 23, "donen": 141, "tekil": 128, "hata": 0, ...}
[step] {"adim": "6-ledger+keyword-score", "taranan": 150, "elenen": 97, "kalan": 53, "eleme": {"score<2": 95, "scam-word": 2}}
[step] {"adim": "7-enrich+copy-check", "taranan": 53, "elenen": 31, "kalan": 22, "eleme": {"github-fork": 9, "empty-repo": 7, "skeleton": 6, ...}}
[step] {"adim": "9-priority+cap", "taranan": 21, "secilen": 4, "kota_disi": 17, ...}

COUNTER 2026-11-04: queries 29 · scanned 150 · already in ledger 12 · rejected 126 · below threshold/cap 17 · deep 4 · watchlist 3 (momentum 0) · status OK
  CANDIDATE 9 example-labs/examplecoin pow ['framework:cosmos-sdk']
  CANDIDATE 6 someone/new-randomx-chain pow ['derivative:monero-project/monero (+wownero)', 'file-signature:cryptonote']
```

## Safety

- The radar never runs, builds or clones candidate code. The evaluation protocol only allows a read-only shallow
  clone with hooks, submodules and LFS disabled, and forbids running anything from it.
- The GitHub token is used for GET and GraphQL queries only: no stars, issues, PRs or forks.
- README and other repo text is treated as data; instructions inside it are ignored and noted as a red flag.
- Secrets are never written to state files or reports.

## Limits

- Keyword/metadata filters miss projects that never use chain vocabulary in their name, description or topics.
- The created-in-window lane misses months-old repos that only just became active; the momentum queries cover
  part of that gap.
- Copy detection knows only the listed upstream roots; zip imports are caught heuristically.
- Priority weights are hand-set and uncalibrated (an old revival coin can outrank a new multi-source one).
- Fine-grained tokens cannot read stargazer lists, so star velocity comes from daily snapshot diffs.
- miningpoolstats blocks scripted access; it is only used when a browser-saved file is present.
- The deep evaluation is a protocol, not code: its quality depends on the reviewer/model and on quote checking.

## License

MIT. See [LICENSE](LICENSE). Not financial advice.
