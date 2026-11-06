#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模型切换矩阵探针。

读当前 CODEX_HOME 的 config.toml + model_catalog.json，把目录里的模型逐个真打一遍，
用来回答"切到某个模型会不会挂"。只读密钥，不打印原文。

用法：
    python probe-model-matrix.py                  # 全量（目录内全部模型）
    python probe-model-matrix.py --models grok-4.7,xai/grok-4.7
    python probe-model-matrix.py --effort high    # 统一思考档，默认各模型最高档
    python probe-model-matrix.py --stream         # 用 SSE 流式（更接近真实客户端）
    python probe-model-matrix.py --home <CODEX_HOME>

退出码：0 = 全部通过；1 = 有失败。
"""
import argparse
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HOME_CANDIDATES = [
    os.environ.get("CODEX_HOME"),
    os.path.expanduser(r"~\.codex"),
    r"D:\github\codex-profilewithdeepseek-data\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex",
    r"D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex",
]
EFFORT_ORDER = ("max", "ultra", "high", "xhigh", "medium", "low", "minimal")
ALIAS_HINTS = ("openai/", "anthropic/", "xai/", "google/", "qwen/", "deepseek/", "glm/",
               "moonshotai/", "bytedance/", "minimax/", "typesafe/")
# 裸名 → 上游前缀（按家族对应，不要跨家族瞎试）
FAMILY_PREFIX = (("gpt-", "openai/"), ("claude-", "anthropic/"), ("grok-", "xai/"),
                 ("gemini-", "google/"), ("qwen", "qwen/"), ("deepseek", "deepseek/"),
                 ("glm-", "glm/"), ("kimi", "moonshotai/"), ("doubao", "bytedance/"),
                 ("minimax", "minimax/"))


def find_home(explicit):
    """按优先级找 CODEX_HOME；只有同时具备 config.toml 与 model_provider 的才算。"""
    skipped = []
    for h in ([explicit] if explicit else []) + HOME_CANDIDATES:
        cfg = os.path.join(h, "config.toml") if h else None
        if not cfg or not os.path.isfile(cfg):
            continue
        txt = io.open(cfg, encoding="utf-8").read()
        if re.search(r'^\s*model_provider\s*=', txt, re.M):
            return h
        skipped.append(h)
    for h in skipped:
        print("跳过 %s：config.toml 没有 model_provider（多半是原生 Codex 的 home）" % h)
    sys.exit("找不到带 model_provider 的 CODEX_HOME，用 --home 指定")


def load_route(home):
    """从 config.toml 取当前 model_provider 的 base_url 与 bearer。"""
    txt = io.open(os.path.join(home, "config.toml"), encoding="utf-8").read()
    m = re.search(r'^\s*model_provider\s*=\s*"([^"]+)"', txt, re.M)
    prov = m.group(1) if m else None
    if not prov:
        sys.exit("config.toml 里没有 model_provider")
    block = re.search(r"\[model_providers\.%s\](.*?)(?=\n\[|\Z)" % re.escape(prov), txt, re.S)
    if not block:
        sys.exit("找不到 [model_providers.%s] 段" % prov)
    body = block.group(1)
    base = re.search(r'base_url\s*=\s*"([^"]+)"', body)
    key = re.search(r'experimental_bearer_token\s*=\s*"([^"]+)"', body)
    if not base or not key:
        sys.exit("provider %s 缺 base_url 或 experimental_bearer_token" % prov)
    return prov, base.group(1).rstrip("/"), key.group(1)


def load_models(home):
    p = os.path.join(home, "model_catalog.json")
    if not os.path.isfile(p):
        sys.exit("缺 model_catalog.json")
    cat = json.load(io.open(p, encoding="utf-8"))
    return cat["models"] if isinstance(cat, dict) else cat


def pick_effort(model, forced):
    if forced:
        return forced
    lv = model.get("supported_reasoning_levels") or []
    names = [x.get("effort") if isinstance(x, dict) else x for x in lv]
    for want in EFFORT_ORDER:
        if want in names:
            return want
    return None


def call(url, key, model, effort, stream, budget=None):
    body = {"model": model, "input": "回答两个字：ok", "store": False}
    if stream:
        body["stream"] = True
    if effort:
        body["reasoning"] = {"effort": effort, "summary": "auto"}
    if budget:
        body["max_output_tokens"] = budget
    req = urllib.request.Request(url, data=json.dumps(body).encode())
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("User-Agent", "codex-cli/probe")
    if stream:
        req.add_header("Accept", "text/event-stream")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            if stream:
                got = False
                for raw in r:
                    if b"output_text.delta" in raw:
                        got = True
                        break
                return ("ok" if got else "ok(无文本)"), ""
            d = json.loads(r.read())
            if d.get("status") not in (None, "completed"):
                return "status=" + str(d.get("status")), json.dumps(
                    d.get("incomplete_details"), ensure_ascii=False)
            return "ok", ""
    except urllib.error.HTTPError as e:
        return "HTTP %s" % e.code, e.read()[:200].decode("utf-8", "replace").replace("\n", " ")
    except Exception as e:
        return "ERR", repr(e)[:120]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home")
    ap.add_argument("--models", help="逗号分隔，默认全部目录模型")
    ap.add_argument("--effort", help="统一思考档；默认取各模型支持的最高档")
    ap.add_argument("--budget", type=int, help="显式 max_output_tokens；默认不传（让适配器注入）")
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    home = find_home(args.home)
    prov, base, key = load_route(home)
    url = base + "/responses"
    models = load_models(home)
    if args.models:
        want = [x.strip() for x in args.models.split(",") if x.strip()]
        by_slug = {m["slug"]: m for m in models}
        models = [by_slug.get(s, {"slug": s}) for s in want]

    print("CODEX_HOME : %s" % home)
    print("provider   : %s  ->  %s" % (prov, url))
    print("密钥        : %s*** (len=%d)" % (key[:4], len(key)))
    print("模式        : %s  effort=%s" % ("stream" if args.stream else "json",
                                          args.effort or "各模型最高档"))
    print("-" * 96)

    def job(m):
        eff = pick_effort(m, args.effort)
        st, msg = call(url, key, m["slug"], eff, args.stream, args.budget)
        return m["slug"], eff or "-", st, msg

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for slug, eff, st, msg in ex.map(job, models):
            rows.append((slug, eff, st, msg))
            print("  %-34s effort=%-8s %-14s %s" % (slug, eff, st, msg[:90]))

    bad = [r for r in rows if not r[2].startswith("ok")]
    print("-" * 96)
    print("汇总：%d 个模型，通过 %d，异常 %d" % (len(rows), len(rows) - len(bad), len(bad)))

    if bad:
        print("\n失败项与可能原因：")
        for slug, eff, st, msg in bad:
            hint = ""
            if "model_not_found" in msg or "model_unavailable" in msg:
                if not any(slug.startswith(p) for p in ALIAS_HINTS):
                    pre = next((p for f, p in FAMILY_PREFIX if slug.startswith(f)), None)
                    hint = ("裸名无路由 → 试 %s%s" % (pre, slug)) if pre else \
                        "该 slug 不在上游，先在网关 /v1/models 查真实 id"
                else:
                    hint = "上游没有这个模型，加前缀也救不回来"
            elif "not supported by this model" in msg:
                hint = "参数不被该模型接受 → 降思考档（max→high），或确认没走直连 48760"
            elif st == "HTTP 403":
                hint = "鉴权失败 → 查 provider 的 bearer 是否为 48760 认可的 64 位真钥匙"
            elif "timeout" in msg.lower():
                hint = "上游超时 → 重试或换同等模型"
            print("  %-34s %-14s %s" % (slug, st, hint))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
