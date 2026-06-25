<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **tg_autorpg** (1676 symbols, 4726 relationships, 143 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/tg_autorpg/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/tg_autorpg/context` | Codebase overview, check index freshness |
| `gitnexus://repo/tg_autorpg/clusters` | All functional areas |
| `gitnexus://repo/tg_autorpg/processes` | All execution flows |
| `gitnexus://repo/tg_autorpg/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

## Session: i18n Audit

### Goal
Migrate all hardcoded RU strings to bilingual (RU/EN) — completed across all 19+ files.

### Done
- Commands: removed `/loot`, `/top`, `/maps` from menu; removed `/pull` handler; removed `btn_top`/`btn_maps`; added gold shop button to profile
- Info: replaced changelog/rules/FAQ with clean onboarding; updated `info_about`/`info_commands` i18n keys
- i18n infra: `ctime(sec, lang="ru")` signature (RU→w/d/h/m/s, EN→нед/дн/ч/мин/сек); `ISkill.execute(self, ..., lang="ru")` with bilingual results; 4 missing keys added; corrupt key fixed
- ctime `lang` passed: user.py, game/{monsters,events,bosses,challenge}.py, plugins/monsters.py, loops.py, admin.py
- Fully i18n-ized: user.py, quests.py, maps.py, admin.py (keyboards only), monsters.py, passive_skills.py, vip_shop.py, shop.py, stars_shop.py, event_handlers.py, skills/base.py, game/quests.py
- Passive effects (player + boss): 17 effects `on_trigger` now bilingual via `target.lang`
- game/monsters.py: "урона" replaced with `dmg_label` in EN rounds
- core/exceptions.py: BotException/PlayerNotFound/DatabaseError now bilingual
- `_combined.py:40`: fixed reversed lang condition
- Items: `core/loot.py` — added `name_en`/`flair_en` to all 120+ entries; `generate_item_data(lang)` stores both languages; `item_string(item, lang)` displays EN names for EN users

### Session 2: Boss Passive Bug Fixes
**CRIT**: BossCritEffect (2x) — added `damage_bonus=1.0` to `on_trigger` return. Previously missing multiplier made crits hit like normal hits.
**CRIT**: BossVampirismEffect — extracted `res.healing` and applied to `boss_hp`. Healing was never applied.
**HIGH**: BossPoisonAuraEffect — changed from `extra` to `poison_damage`, extracted and applied to `player_hp`. Poison was never applied.
**HIGH**: Legendary HP bar overflow — clamped bar blocks with `min(6, max(0, ...))`.
**HIGH**: Per-boss cooldown — added `set_boss_cooldown` calls on auto+choice alert and win paths. Without this, boss reappeared every tick until defeated.
**HIGH**: Cooldown cache not cleared — added `cls._cooldown_cache.pop(boss_id, None)` in `clear_boss_passives`. Without this, cleared passives stuck until server restart.
**HIGH**: send_message crash — wrapped both `send_message` calls in `send_boss_encounter_alert` with try/except. Prevents silent crashes when player blocks the bot.
**HIGH**: Passive trigger filter — added `effect.trigger not in (ON_DAMAGE_DEALT, ON_HP_BELOW): continue` in `on_dealt` handler. Previously all passives fired on damage, including ON_KILL passives.
**MED**: Boss MP not reset on loss — added `boss.mp = boss.max_mp` in loss path. Boss kept depleted MP from fight.
**MED**: Boss stats not persisted — added `await boss.update()` after stat init in `resolve_battle`, added `max_hp/max_mp/defense` to win/loss save columns.
**MED**: Distance check in callback — added `_boss_distance` check against `BOSS_RADIUS_CHOICE` before allowing fight. Player could click "Fight" from anywhere.
**MED**: Dead code removed — removed unreachable `boss.defeated and boss.respawn_available > now` block in `should_show_boss_to_player` (`get_boss_at` filters `defeated=False`).
**MED**: Boss passives lang — added `lang` to all 5 `PassiveContext` constructors in registry.py. Player boss passives always showed RU.
**MED**: Paid respawn timer — removed timer check from `respawn_boss` (paid gold overrides cooldown).
**LOW**: CrushingBlowEffect — renamed from "Stunning Blow" (no stun), removed `stun=True` flag, added `condition_en = "Upgraded"`.
**LOW**: Bugs 16-25 (low priority) — verified nonexistent in current codebase.

### Session 3: Deep Boss System Audit (10 real fixes)
**CRIT**: Reference sharing — `player.weapon = weapon` (boss weapon dict) shared with player; player weapon mutations (upgrade/downgrade in loss path) corrupted boss equipment in-memory. Fixed: `copy.deepcopy(weapon)`.
**CRIT**: Tick healing lost on restart — `trigger_on_tick` modified `player.hp` but never called `await player.update()`. Fixed: added save.
**CRIT**: Passive cooldowns lost on restart — `ep.cooldown_until`/`ep.last_triggered_at` modified in-memory, never saved. Fixed: added `await ep.update()` in all trigger paths.
**CRIT**: Division by zero in HP bars — `int(p_hp / p_max * 6)` crashed if `max_hp == 0`. Fixed: `max(p_max, 1)`.
**CRIT**: Additive passive stacking — Crit (x2) + Crushing (x0.5) = `1+1.0+(-0.5)=1.5x` instead of `x1.0`. Fixed: `bonus_mult = (1+bonus_mult)*(1+res.damage_bonus)-1` (multiplicative).
**HIGH**: Difficulty persistence — "medium" boss randomly became another difficulty permanently after first fight. Fixed: removed `boss.difficulty = now_difficulty` mutation + removed `difficulty` from save columns.
**HIGH**: None guards — `boss.level`, `equipment` unchecked (4 sites). Fixed: `x or 0`, `if not equipment: return`.
**HIGH**: Damage clamp — `int(dmg * (1 - passive_reduction))` could go negative if `reduction > 1.0` (heals boss). Fixed: `max(0, ...)`.
**HIGH**: Bare except — `except:` caught `KeyboardInterrupt`/`SystemExit`. Fixed: `except Exception:`.
**HIGH**: Dead code — removed `get_equipment_total_level` (bosses.py), `trigger_boss_on_dealt`/`trigger_boss_on_taken` (boss_passives.py).

### Remaining (LOW priority)
- ~65 unused i18n keys in `i18n.py` (dead code)
- `name_ru/name_en` + `description_ru/description_en` data fields (already use `get_name(lang)`)
- admin command handlers (~50 hardcoded RU strings — admin-only, admins are RU-speaking)
- Alert popups in a few places where `lang` isn't available before player lookup
- game/bosses.py:854-857 item quality names "Затупившийся"/"Бывалый" stored in DB

### Patterns
- `if lang == "en" else` for inline strings (primary)
- `t(lang, key)` for existing i18n dict keys
- `ctime(seconds, lang)` — default "ru" for backward compat
- `target.lang` for passive effects (fallback to RU when target is None)
- `PassiveContext` always initialized with `lang` — even for non-boss passives
- Boss passive `on_trigger` must populate ALL PassiveResult fields that the handler checks
- `try/except` around `bot.send_message` to prevent crash when player blocks bot
- `effect.trigger` filter in passive handler loops to prevent wrong-trigger passives from firing

## Session 4: Monitor Dashboard (aesthetic + new metrics)

### Goal
Local monitor at `localhost:8082` showing bot health, container health, players, time-tracking metrics.

### Done
- Created `monitor/` dir + `server.py` (aiohttp), `static/index.html` (aesthetic dashboard), `requirements.txt`, `Dockerfile`
- `docker-compose.yml` monitor service: port 8082, network `autorpg_net`, env `API_URL=http://vpn:8081`
- `src/health.py` auto-mounts `api_handler.setup_api_routes(app)` from health server (port 8081)
- `src/api_handler.py` endpoints: `/api/stats`, `/api/players`, `/api/players/{uid}`, `/api/bot`
  - `stats`: counts, sums, db_size, idle_now, total_online/idle/offline_seconds_all, current_idle/online_seconds, avg_account_age_seconds
  - `player`: full record + time fields + active skills + passives + recent quests
  - `bot`: alive, db_connected, tick_count, last_tick_ago, last_idle_tick_ago, uptime_seconds
- Migration `019_player_time_tracking.py`: 5 BigInteger columns on `users` — `total_online_seconds`, `total_idle_seconds`, `total_offline_seconds`, `last_online_at`, `last_idle_at`
- `Player` model: 5 new BigInteger fields (default=0)
- `loops.py` online→offline: accumulate `total_online_seconds += now - last_online_at`, set `last_online_at=0`, `last_idle_at=now`
- `loops.py` idle tick: increment `total_idle_seconds += cfg.INTERVAL` per tick
- `handlers/user.py` cmd_start: set `last_online_at=now`, accumulate `total_idle_seconds += now - last_idle_at` on return, `last_idle_at=0`
- monitor `server.py`: composes `/api/status` from bot + Docker socket, proxies other endpoints; filters containers by `com.docker.compose.project == COMPOSE_PROJECT_NAME`
- monitor service: Docker socket mount (`/var/run/docker.sock:/var/run/docker.sock:ro`) + `COMPOSE_PROJECT_NAME=tg_autorpg` env
- Monitor `index.html`: aesthetic dark theme, status bar (bot + containers), 14 stat cards (incl. time totals), player list with search, detail panel (time bar, equipment, quests, passives, skills, clan, prestige, timestamps)

### Deploy steps (not yet executed)
1. `docker compose build autorpg monitor`
2. `docker compose run --rm autorpg alembic upgrade head` (if entrypoint doesn't auto-migrate)
3. `docker compose up -d`
4. Verify: `curl localhost:8081/api/bot` · `curl localhost:8082/api/status` · `curl localhost:8082/api/players/{uid}` · open `http://localhost:8082`

### Critical Context
- autorpg runs in `network_mode: "service:vpn"` — health/API exposed on `vpn` container :8081
- monitor uses `autorpg_net` to reach `http://vpn:8081`; `cfg.API_URL` not used (separate env)
- `cfg.INTERVAL` is the game tick (5s) — used for idle accumulation
- `_BOT_START_TIME` set at module import in `api_handler.py` for uptime
- `health.py` exports `_bot_instance`, `_db_connected`, `_tick_count`, `_last_tick_time`, `_last_idle_tick_time` as module globals
- DB name: `autorpg`; `SELECT pg_database_size('autorpg')` for size
- ORM: ormar; `Player.objects.filter(name__icontains=...)` for search
- Docker socket HTTP: `GET /containers/json?filters=...` over Unix socket
- `loops.py` still loads `Player.objects.all()` to compute sums — full table scan, acceptable for now
- `monitor/requirements.txt` only has `aiohttp` — no new deps

### Bottlenecks / Risk
- `loops.py` sum query: full Player table scan in memory. Future: `SELECT SUM(...)` direct DB.
- `idle_now` in stats: 2× Player.objects.all() (online filter + idle_since>0 filter). Could combine.
- Monitor `/api/status` calls Docker API synchronously per request — fast but blocks.
- `Player.objects.all()` for 8-hour sum window: same scan, but cached within request handler scope.

## Session 5: Docker HTTP fix + Healthcheck

### Bug fixes
- **CRIT** `monitor/server.py:57-125` `_http_get_unix()`: Docker API returns response with neither Content-Length nor Transfer-Encoding (close-delimited). Old code returned early after seeing headers, parsing truncated body. New helper handles all 3 modes: Content-Length, chunked, close-delimited.
- **HIGH** `docker/entrypoint.sh`: was unconditionally running `python3 bot.py "$@"` even when override CMD was `alembic`/`bash`/etc. Would fail with port-bind error when running `docker compose run --rm autorpg alembic upgrade head`. Fixed: detect override commands and exec them directly.
- **HIGH** `Dockerfile` + `docker-compose.yml` healthcheck: was port 8080 (wrong, health server uses 8081) AND broken one-liner (`aiohttp.ClientSession()` called before `asyncio.run()` → "no running event loop"). Replaced with `docker/healthcheck.py` script.

### Session 6: Online time tracking fix
- **CRIT** `src/loops.py`: `total_online_seconds` was only updated on online→offline transition (asymmetric with idle which uses per-tick accumulation). Player online for 21 min showed 0s. Fixed: added per-tick `bulk_update` on `total_online_seconds` for all online players (5s per tick, mirrors idle pattern).
- **CRIT** `src/handlers/user.py:194`: removed double-count of idle time on /start. Per-tick idle loop already accumulates; the +max(0, now - last_idle_at) was adding the same range a second time.
- **MED** `src/loops.py:138-147`: removed redundant `total_online_seconds += max(0, now - last_online_at)` from online→offline transition (per-tick loop now handles it). Cleaned update columns accordingly.

### Deploy
```bash
docker compose build monitor autorpg
docker compose up -d
```

### Critical Context
- Dockerfile HEALTHCHECK CMD doesn't support multi-line python (parser fails on `async`). Use script file.
- `docker compose` healthcheck overrides Dockerfile HEALTHCHECK when both defined.
- `entrypoint.sh` must special-case `python3`/`alembic`/`bash`/`sh` to not prepend `python3 bot.py`.
- Docker socket on monitor is read-only; HTTP API only — no Docker SDK needed in monitor.
- `get_running_loop()` errors when called outside an asyncio context — aiohttp.ClientSession() in `-c` script must be inside the run() callable.
- `total_online_seconds` and `total_idle_seconds` now use symmetric per-tick accumulation via `bulk_update` (1 query per tick regardless of player count).

## Session 7: Fix totalquests counter

### Goal
`Player.totalquests` was always 0 on monitor dashboard because never incremented.

### Done
- `src/game/quests.py:363`: added `player.totalquests += 1` and `totalquests` to `update(_columns=[...])`
- `src/handlers/quests.py:471-473`: added missing `await quest.update()` on completion (data loss bug — completion status never persisted for non-location-locked quests) + `player.totalquests += 1`
- Backfill: direct SQL `UPDATE users SET totalquests = (SELECT COUNT(*) FROM player_quests WHERE player_uid = users.uid AND status = 'completed')` — 1 player backfilled (優木ひなか: 1 quest)
- Rebuilt autorpg, verified dashboard shows `total_quests: 1`

### Relevant Files
- `src/game/quests.py:361-363`: complete_quest() — totalquests increment
- `src/handlers/quests.py:468-488`: update_quest_progress() — totalquests increment + persist fix
- `src/api_handler.py:35`: total_quests sum (now works since field has real values)

### Risk
- LOW. Only adds increment logic, no schema changes.
