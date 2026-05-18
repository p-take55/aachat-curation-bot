# aachat-curation-bot

aachat の Discover カタログ (`agents_catalog` / `skills_catalog`) に
agent / skill レポを積極的に登録する ops 用 agent。

kensaku63 / p-take55 名義の long-lived user JWT を host process が保持し、
LLM (curation agent) は **JWT を見ずに** tool 引数 (`github_repo` / `skill_path`)
だけで操作する (sidecar pattern)。

aachat 本体側の決定 / 設計:
- `kensaku63/aachat:docs/decisions/D-20260512-discovery-curation-agent-write-path.md`
- `kensaku63/aachat:docs/design/discovery-curation-write-path/`

## このリポは aachat-format agent

`aachat up` セッション起動時に `aachat/agents/aachat-curation-bot/` として
projection される想定 (本家 README.md 参照)。

```
.
├── identity.md             # agent の人格 / 方針
├── environment.yaml        # 依存パッケージ (Python: requests, python-dotenv)
├── knowledge/
│   ├── api-contract.md     # 叩く endpoint と不変条件
│   ├── token-setup.md      # JWT 取得・更新手順
│   └── curation-policy.md  # どんなレポを登録するかの基準
├── memory/                 # session 間引き継ぎ (登録済み / skipped 等)
├── .claude/skills/         # この agent 専用 skill (今後追加)
├── src/curation_bot/
│   ├── tools.py            # register_agent / register_skill 実装 (JWT は LLM 不可視)
│   └── cli.py              # 手動実行用 CLI
└── scripts/
    └── refresh-jwt.sh      # PAT → JWT 交換 (~80 日に 1 回実行)
```

## クイックスタート

```bash
# 1. 依存をインストール
uv sync   # or: pip install -e .

# 2. PAT を発行して .env に保存 (詳細: knowledge/token-setup.md)
cp .env.example .env
$EDITOR .env

# 3. JWT mint
./scripts/refresh-jwt.sh

# 4. 手動で 1 件登録してみる
uv run curation-bot register-agent obra/superpowers
uv run curation-bot register-skill obra/superpowers skills/brainstorming
```

## 使い方

### A. 手動 (1 件ずつ)

```bash
uv run curation-bot register-agent <owner>/<repo>
uv run curation-bot register-skill <owner>/<repo> <skill_path>
```

`skill_path` は relative。root に SKILL.md がある場合は `.` を使う。

### B. cron で定期的に

```cron
# 毎日 09:00 に JWT 期限チェック (期限 30 日以内なら更新)
0 9 * * * cd /path/to/aachat-curation-bot && ./scripts/refresh-jwt.sh >> ~/.aachat/refresh.log 2>&1
```

### C. LLM 駆動 (今後実装)

`src/curation_bot/agent.py` は未実装。Anthropic API / Claude Code / aachat
agent runtime のいずれかから `tools.register_agent` / `tools.register_skill`
を tool として expose し、X 検索 + GitHub 検索の結果から自律的に登録する。

LLM プロンプトに `knowledge/curation-policy.md` を読ませて判断基準を適用させる。

## 守るべき不変条件

1. **JWT は LLM コンテキストに出さない**。tool 引数 / 戻り値 / システムプロンプト / メモリのすべてで JWT 文字列を扱わない。`tools.py` は host process 側で JWT をロードし `Authorization` ヘッダにだけ詰める。
2. **GitHub PAT も同様**。`.env` に置く、`.gitignore` 済み。
3. **DELETE は agent からやらない**。catalog 行の取り消しは人間が SQL で対応する。
4. **agent JWT で叩かない**。aachat 本家が 403 で弾くが、tool 側でも user JWT 以外を見たら early-return すべき。

詳細は `identity.md` の「触ってはいけないもの」セクション。

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| `JWT not found at ...` | `./scripts/refresh-jwt.sh` を実行 |
| `401 Unauthorized` | JWT 期限切れ。`./scripts/refresh-jwt.sh` を実行 |
| `403 Only human users can submit to Discover` | host process が誤って agent JWT をロードしている。`.env` の `AACHAT_OPS_GITHUB_PAT` が human user の PAT であることを確認 |
| `400 Repository must contain CLAUDE.md or identity.md` | agent endpoint は CLAUDE.md / identity.md 必須。skill 単独レポなら `register-skill` を使う |
| `400 SKILL.md not found in repository` | `skill_path` を確認。`.` (root) / `skills/foo` 等 |
| `404 GitHub repository '...' was not found` | private repo or typo。public で再確認 |

## License

TBD
