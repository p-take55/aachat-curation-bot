# Token Setup — 一度だけやる手順

## 前提

- kensaku63 / p-take55 名義の GitHub アカウントにアクセスできること
- aachat の本番 API URL が分かっていること (env: `AACHAT_API_URL`)

## 1. GitHub PAT を発行

1. https://github.com/settings/tokens?type=beta を開く
2. `Generate new token`
3. 設定:
   - **Token name**: `aachat-curation-bot`
   - **Resource owner**: `kensaku63` (または `p-take55`)
   - **Expiration**: 1 年 (or No expiration、リスク許容に応じて)
   - **Repository access**: `Public Repositories (read-only)` で十分 (aachat は GitHub user の identity を verify するだけ)
   - **Permissions**: 何も追加しない (デフォルトの公開レポ read のみ)
4. `Generate token` → `github_pat_...` をコピー (二度と表示されない)

## 2. PAT を repo の `.env` に保存

```bash
cd /path/to/aachat-curation-bot
cp .env.example .env
$EDITOR .env
# AACHAT_OPS_GITHUB_PAT=github_pat_... を埋める
# AACHAT_API_URL=https://api.aachat.example を本番 URL に
```

`.env` は `.gitignore` 済み。誤って commit しないこと。

## 3. JWT を mint

```bash
./scripts/refresh-jwt.sh
# → "JWT saved to /Users/.../.aachat/curation-jwt (NNN bytes)"
```

これで 90 日有効な user JWT が `~/.aachat/curation-jwt` に保存される。

## 4. 動作確認

```bash
# 公開レポを 1 件登録してみる (origin='curated' になるはず)
uv run curation-bot register-agent obra/superpowers

# Discover で確認
curl "$AACHAT_API_URL/v1/agents/discover?limit=5&sort=recent" | jq
```

## JWT の更新 (~80 日に 1 回)

```bash
./scripts/refresh-jwt.sh
```

cron 化したい場合 (60 日に 1 回):

```cron
0 9 1 */2 * cd /path/to/aachat-curation-bot && ./scripts/refresh-jwt.sh >> ~/.aachat/refresh.log 2>&1
```

## 漏洩時の対応

- **JWT が漏れた**: aachat 側に revoke 機能は無いので、影響範囲は「PAT 経由で再 mint できる側」=「PAT 漏れに準ずる」。最低限 `rm ~/.aachat/curation-jwt` で curl の続行を止める。
- **PAT が漏れた**: GitHub の Settings → Personal access tokens から該当 PAT を即 revoke → 新規発行 → `.env` 更新 → `./scripts/refresh-jwt.sh`。

## 補足: なぜ user JWT を host process に置くのか

詳細は `kensaku63/aachat:docs/decisions/D-20260512-discovery-curation-agent-write-path.md`
の「認証経路の詳細 / aachat-platform agent からの ops 用 curation」を読むこと。要点:

- catalog 行は人間 user に紐づくべき (`submitted_by_user_id` の意味論)
- agent JWT で書ける経路は構造的に作らない (403)
- ただし「agent process が代理で書く」需要は満たしたい
- 解: agent **process** が人間の JWT を保持。**LLM** はそれを見ない (sidecar pattern)
- LLM 暴走時の被害は catalog write の範囲に閉じる
