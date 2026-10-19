"""
xhs_collector.py — 小红书筛选式采集器（工程化版）

第一性原理
==========
反爬是一个二分类器，把"机器流"和"人类流"分开。它能依赖的证据：
  1) 时间签名 — 动作间隔是否像人（对数正态 + 偶发长停 + 阶段疲劳）
  2) 空间签名 — 是否有 scroll/hover 这样的"目光移动"前置
  3) 行为签名 — 是否"读完"再操作；是否一直走直线
  4) 容量签名 — 单会话动作总量是否在人类注意力区间内
本脚本对前 4 项做工程化对冲；指纹层（UA/Canvas/Cookie）交给 opencli browser。

模块切分
========
  Cadence       节奏调度器（log-normal 思考时间 / 长尾停顿 / 阶段休眠）
  Volume        会话容量预算（达上限自动落盘退出，避免过度暴露）
  CLIRunner     opencli 调用包装（URL 转义 / JSON 解析 / 超时重试）
  BrowserSession 浏览器原语包装 + 人化前置（scrollIntoView / mouseover / click）
  FilterPanel   筛选面板交互（多选择器 + 激活校验 + 失败重试）
  NoteListExtractor 列表抽取（多选择器族 + 结构形态兜底）
  Checkpoint    断点状态机（任务级 pending/in_progress/done/failed，逐条落盘）
  Collector     总编排（参数化：keyword / sort / range / top / comments）

CLI 用法
========
  python xhs_collector.py --keyword "AI玩具" --sort liked --range week --top 10
  python xhs_collector.py --resume                # 从上次 checkpoint 续抓
  python xhs_collector.py --keyword X --dry-run   # 只打印动作时间线，不发请求
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

# ─── 常量 ──────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
OPENCLI = r"E:\nodejs\node-v22.22.0-win-x64\opencli.cmd"

SORT_LABELS = {"liked": "最多点赞", "latest": "最新", "comprehensive": "综合"}
RANGE_LABELS = {
    "day": "一天内", "week": "一周内", "half-month": "半月内",
    "month": "一月内", "half-year": "半年内", "unlimited": "不限",
}
RANGE_LABEL_OPTIONS = {
    "day": ["一天内"],
    "week": ["一周内"],
    "half-month": ["半月内", "一周内", "半年内"],
    "month": ["一月内", "一个月内", "近一月", "一周内", "半年内"],
    "half-year": ["半年内"],
    "unlimited": ["不限"],
}

def fs_path(path: Path) -> str:
    s = str(path)
    if os.name != "nt" or s.startswith("\\\\?\\"):
        return s
    if s.startswith("\\\\"):
        return "\\\\?\\UNC\\" + s.lstrip("\\")
    return "\\\\?\\" + s

# (mu, sigma, floor_s, ceil_s) for log-normal think time
# 三档节奏：
#   normal   人化最强；适合长周期单会话或 stealth profile
#   compact  压缩思考时间；切片调度下用（外层片间冷却已是反爬主屏障）
#   swift    极简；几乎只留页面渲染所需的最小停顿，仅用于受控本机测试
CADENCE_PRESETS: dict[str, dict[str, tuple[float, float, float, float]]] = {
    "normal": {
        "scan":        (1.4, 0.55, 3.0, 12.0),
        "read":        (2.6, 0.60, 6.0, 28.0),
        "click":       (0.5, 0.40, 1.0, 4.5),
        "hover":       (-1.5, 0.35, 0.15, 0.6),
        "post_click":  (1.0, 0.40, 1.5, 5.0),
        "phase_break": (3.5, 0.30, 25.0, 90.0),
        "macro_break": (5.0, 0.25, 120.0, 360.0),
    },
    "compact": {
        "scan":        (0.6, 0.45, 1.0, 4.0),
        "read":        (1.2, 0.50, 2.0, 7.0),
        "click":       (-0.2, 0.35, 0.4, 1.8),
        "hover":       (-1.8, 0.30, 0.10, 0.4),
        "post_click":  (0.0, 0.35, 0.6, 2.0),
        "phase_break": (1.0, 0.25, 2.0, 6.0),
        "macro_break": (1.5, 0.25, 4.0, 9.0),
    },
    "swift": {
        "scan":        (0.0, 0.30, 0.4, 1.5),
        "read":        (0.5, 0.35, 0.8, 3.0),
        "click":       (-0.5, 0.30, 0.2, 1.0),
        "hover":       (-2.0, 0.25, 0.05, 0.25),
        "post_click":  (-0.5, 0.30, 0.3, 1.2),
        "phase_break": (0.5, 0.25, 1.0, 3.0),
        "macro_break": (0.5, 0.25, 1.0, 3.0),
    },
}
LONG_TAIL_PROB = 0.06       # 6% 概率叠加 15-45s 的"走神"
LONG_TAIL_RANGE = (15.0, 45.0)
MACRO_BREAK_EVERY = (12, 18)  # 每隔 12-18 个动作来一次大休息

# ─── 日志 ──────────────────────────────────────────────────────────────────

class Log:
    def __init__(self, log_path: Path):
        self.path = log_path
        self.fh = open(log_path, "a", encoding="utf-8")
        self.fh.write(f"\n{'='*72}\n[start] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.fh.flush()

    def __call__(self, msg: str = "", level: str = "info"):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        self.fh.write(line + "\n")
        self.fh.flush()

    def section(self, title: str):
        bar = "█" * 56
        self("")
        self(bar)
        self(f"█  {title}")
        self(bar)

    def close(self):
        try:
            self.fh.write(f"[end] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.fh.close()
        except Exception:
            pass

# ─── 节奏调度器 ────────────────────────────────────────────────────────────

class Cadence:
    """
    用对数正态分布产生人类思考时间。理由：
      实证研究里，鼠标点击的 inter-arrival time 接近 log-normal —
      众数偏小（大多动作是连贯的）但有长尾（偶尔走神）。

    三档 mode：
      normal  完整人化（含 long_tail 走神 + 宏休息），适合单会话长周期
      compact 切片场景下用：外层片间冷却已是反爬主屏障，单片内部不需要假装"长时间在线"
      swift   仅本机受控测试，几乎只留页面响应必需的停顿
    """

    def __init__(self, log: Log, dry_run: bool = False, mode: str = "normal"):
        self.log = log
        self.dry_run = dry_run
        self.mode = mode if mode in CADENCE_PRESETS else "normal"
        self.profiles = CADENCE_PRESETS[self.mode]
        self.actions = 0
        self._next_macro_at = random.randint(*MACRO_BREAK_EVERY) if self.mode == "normal" else 10**9

    def _draw(self, profile: str) -> float:
        mu, sigma, floor, ceil = self.profiles[profile]
        delay = floor + random.lognormvariate(mu, sigma)
        delay = max(floor, min(delay, ceil))
        # 仅 normal 模式叠加走神长尾，compact/swift 不需要
        if (self.mode == "normal"
                and profile in ("scan", "read", "click", "post_click")
                and random.random() < LONG_TAIL_PROB):
            delay += random.uniform(*LONG_TAIL_RANGE)
        return delay

    def sleep(self, profile: str = "scan", note: str = ""):
        d = self._draw(profile)
        tag = f"[{self.mode}/{profile}{':'+note if note else ''}] {d:.2f}s"
        if self.dry_run:
            self.log(f"  ⏱  (dry) {tag}")
            return
        self.log(f"  ⏱  {tag}")
        time.sleep(d)

    def tick(self):
        """每完成一个动作调用一次。可能触发宏休息（仅 normal 模式）。"""
        self.actions += 1
        if self.mode != "normal":
            return
        if self.actions >= self._next_macro_at:
            self.macro_break()
            self._next_macro_at = self.actions + random.randint(*MACRO_BREAK_EVERY)

    def macro_break(self):
        d = self._draw("macro_break")
        self.log(f"  ☕ 宏休息（疲劳模拟）{d:.0f}s ...")
        if not self.dry_run:
            time.sleep(d)

    def phase_break(self, name: str):
        d = self._draw("phase_break")
        self.log(f"\n  ━━━ 阶段切换：{name} （{d:.0f}s）━━━")
        if not self.dry_run:
            time.sleep(d)

# ─── 容量预算 ──────────────────────────────────────────────────────────────

class Volume:
    """
    硬性限制单会话总动作数。一旦逼近上限，落盘退出，
    让用户/调度器在冷却期后恢复（断点续抓）。
    """

    def __init__(self, log: Log, hard_cap: int):
        self.log = log
        self.hard_cap = hard_cap
        self.spent = 0

    def consume(self, n: int = 1):
        self.spent += n

    def remaining(self) -> int:
        return max(0, self.hard_cap - self.spent)

    def exhausted(self) -> bool:
        return self.spent >= self.hard_cap

# ─── opencli 调用 ──────────────────────────────────────────────────────────

class CLIRunner:
    def __init__(self, log: Log, dry_run: bool = False):
        self.log = log
        self.dry_run = dry_run

    @staticmethod
    def _quote(arg: str) -> str:
        if any(c in arg for c in '&?"|<>^()'):
            return '"' + arg.replace('"', '\\"') + '"'
        if " " in arg:
            return '"' + arg + '"'
        return arg

    def run(self, argv: list[str], desc: str = "", timeout: int = 90,
            retries: int = 1, retry_wait: tuple[float, float] = (15.0, 35.0)) -> str | None:
        cmd_str = " ".join(self._quote(a) for a in argv)
        self.log(f"  📡 {desc} :: {cmd_str[:140]}")
        if self.dry_run:
            return "<dry-run>"
        last_err = ""
        for attempt in range(1, retries + 2):
            try:
                r = subprocess.run(
                    cmd_str, capture_output=True, text=True,
                    timeout=timeout, encoding="utf-8", errors="replace", shell=True,
                )
                if r.returncode == 0:
                    return r.stdout
                last_err = f"exit={r.returncode}; stderr={(r.stderr or '')[:300]}"
                self.log(f"  ⚠️ {last_err}")
            except subprocess.TimeoutExpired:
                last_err = f"timeout after {timeout}s"
                self.log(f"  ⏰ {last_err}")
            except Exception as e:
                last_err = repr(e)
                self.log(f"  💥 {last_err}")
            if attempt <= retries:
                wait = random.uniform(*retry_wait)
                self.log(f"  ↻ 重试 #{attempt}（{wait:.1f}s 后）")
                time.sleep(wait)
        self.log(f"  ❌ 放弃：{desc} — {last_err}")
        return None

    def run_json(self, argv: list[str], desc: str = "", timeout: int = 90,
                 retries: int = 1) -> Any:
        out = self.run(argv, desc, timeout, retries)
        if not out or out == "<dry-run>":
            return None
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            self.log(f"  ⚠️ JSON 解析失败，原始前 200 字: {out[:200]!r}")
            return None

# ─── 浏览器原语 ────────────────────────────────────────────────────────────

class BrowserSession:
    def __init__(self, cli: CLIRunner, cadence: Cadence, log: Log, session: str):
        self.cli = cli
        self.cadence = cadence
        self.log = log
        self.session = session

    def _argv(self, *parts: str) -> list[str]:
        return [OPENCLI, "browser", self.session, *parts]

    def open(self, url: str, desc: str = "open") -> bool:
        out = self.cli.run(self._argv("open", url), desc, timeout=60, retries=1)
        self.cadence.tick()
        return out is not None

    def eval_js(self, js: str, desc: str = "eval", timeout: int = 30) -> str | None:
        """
        通过 base64 注入彻底绕开 Windows cmd 的多层引号转义。
        包装为：eval(decodeURIComponent(escape(atob('<base64>'))))
        - atob 解出原始字节
        - escape→decodeURIComponent 再把 UTF-8 字节还原为字符串（兼容中文/emoji）
        - 整个 wrapper 仅包含 [A-Za-z0-9+/=] + 几个 ASCII 标点，cmd 不会动它
        """
        b64 = base64.b64encode(js.encode("utf-8")).decode("ascii")
        wrapper = f"eval(decodeURIComponent(escape(atob('{b64}'))))"
        out = self.cli.run(self._argv("eval", wrapper), desc, timeout=timeout, retries=1)
        self.cadence.tick()
        return out

    def eval_json(self, js: str, desc: str = "eval-json", timeout: int = 30) -> Any:
        # JS 末尾自带 JSON.stringify(...) 的，opencli 会把字符串原样回传
        raw = self.eval_js(js, desc, timeout)
        if not raw:
            return None
        raw = raw.strip()
        # opencli eval 输出可能带 quote/escape；尝试两次解析
        try:
            return json.loads(raw)
        except Exception:
            pass
        try:
            unwrapped = json.loads(raw)
            if isinstance(unwrapped, str):
                return json.loads(unwrapped)
            return unwrapped
        except Exception:
            return raw

    def scroll(self, direction: str = "down", desc: str = "scroll"):
        self.cli.run(self._argv("scroll", direction), desc, timeout=20, retries=0)
        self.cadence.tick()

    def click_css_nth(self, selector: str, nth: int, desc: str = "click") -> dict:
        out = self.cli.run_json(self._argv("click", selector, "--nth", str(nth)),
                                desc, timeout=30, retries=0)
        self.cadence.tick()
        return out if isinstance(out, dict) else {"clicked": False}

    def screenshot(self, path: str, desc: str = "shot") -> bool:
        out = self.cli.run(self._argv("screenshot", path), desc, timeout=30)
        return out is not None

    def unbind(self):
        self.cli.run(self._argv("unbind"), "unbind", timeout=20, retries=0)

    # ── 高层：人化点击（先 scroll 入视野 → mouseover → click） ─────────────
    def humanized_click_by_text(self, label: str, scope_selector: str = "body",
                                 desc: str = "") -> dict:
        """
        在 scope_selector 范围内查找 textContent.trim() === label 的元素并点击。
        返回 {clicked: bool, label, target: tag.class}.
        """
        js = (
            "(function(){"
            f"var scope=document.querySelector({json.dumps(scope_selector)})||document;"
            "var els=Array.from(scope.querySelectorAll('span,div,button,a,li'));"
            f"var target=null;var label={json.dumps(label)};"
            "for(var i=0;i<els.length;i++){"
            "  var t=(els[i].textContent||'').trim();"
            "  if(t===label){target=els[i];break;}"
            "}"
            "if(!target){return JSON.stringify({clicked:false,label:label,reason:'not-found'});}"
            "var clickEl=target.closest('[class*=\"tag\"],[class*=\"chip\"],[class*=\"filter\"],[role=\"tab\"],button')||target.parentElement||target;"
            "try{clickEl.scrollIntoView({block:'center'});}catch(e){}"
            "try{clickEl.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));}catch(e){}"
            "try{clickEl.click();}catch(e){return JSON.stringify({clicked:false,label:label,reason:'click-throw:'+e.message});}"
            "return JSON.stringify({clicked:true,label:label,target:clickEl.tagName+'.'+(clickEl.className||'').toString().slice(0,40)});"
            "})()"
        )
        self.cadence.sleep("hover", note=label)
        out = self.eval_json(js, desc=desc or f"click[{label}]")
        self.cadence.sleep("post_click", note=label)
        if isinstance(out, dict):
            return out
        if isinstance(out, str):
            try: return json.loads(out)
            except Exception: return {"clicked": False, "label": label, "raw": out}
        return {"clicked": False, "label": label}

# ─── 筛选面板 ──────────────────────────────────────────────────────────────

class FilterPanel:
    """
    调度筛选面板的展开 → 选项点击 → 激活校验。
    多选择器策略：CSS class、aria 角色、文本兜底。
    """

    PANEL_SELECTORS = [".filter", "[class*=filter]", "[role=button][aria-label*=筛选]"]

    def __init__(self, browser: BrowserSession, cadence: Cadence, log: Log):
        self.browser = browser
        self.cadence = cadence
        self.log = log

    def open_panel(self) -> bool:
        for sel in self.PANEL_SELECTORS:
            js = (
                f"(function(){{var e=document.querySelector({json.dumps(sel)});"
                "if(!e)return JSON.stringify({ok:false,sel:" + json.dumps(sel) + "});"
                "try{e.scrollIntoView({block:'center'});}catch(_){}"
                "try{e.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));}catch(_){}"
                "try{e.click();}catch(err){return JSON.stringify({ok:false,err:err.message});}"
                "return JSON.stringify({ok:true,sel:" + json.dumps(sel) + "});"
                "})()"
            )
            self.cadence.sleep("hover", note="panel")
            out = self.browser.eval_json(js, desc=f"panel[{sel}]")
            ok = isinstance(out, dict) and out.get("ok")
            if ok:
                self.log(f"  🪄 筛选面板已展开（selector={sel}）")
                self.cadence.sleep("post_click", note="panel-open")
                return True
        self.log("  ❌ 所有筛选面板选择器都未命中")
        return False

    def pick(self, label: str, max_retries: int = 2) -> bool:
        """
        点击筛选项。小红书的筛选项 DOM 形如：
            <div class="tag-container">
              <div class="tags">
                <span>最多点赞</span>      ← 文本在这里
              </div>                       ← click 这里才会切激活
              <div class="tags">…</div>
              ...
            </div>
        点击 SPAN 自己 / 上溯 [class*=tag] 都不会触发激活态切换；
        必须点 SPAN 的直接父级 DIV.tags（PoC 验证有效）。
        """
        for attempt in range(1, max_retries + 2):
            self.cadence.sleep("hover", note=label)
            js = (
                "(function(){"
                f"var lab={json.dumps(label)};"
                "var tags=Array.from(document.querySelectorAll('.tags'));"
                "var matches=tags.map(function(e,i){var r=e.getBoundingClientRect();return {i:i,el:e,rect:r,text:(e.textContent||'').trim()};})"
                ".filter(function(x){return x.text===lab&&x.rect.width&&x.rect.height&&x.rect.bottom>=0&&x.rect.right>=0&&x.rect.top<=innerHeight&&x.rect.left<=innerWidth;});"
                "if(!matches.length){return JSON.stringify({found:false,reason:'tag-not-found'});}"
                "var m=matches[0];"
                "try{m.el.scrollIntoView({block:'center'});}catch(_){}"
                "return JSON.stringify({found:true,index:m.i,target:m.el.tagName+'.'+(m.el.className||'')});"
                "})()"
            )
            res = self.browser.eval_json(js, desc=f"pick[{label}]") or {}
            if isinstance(res, str):
                try: res = json.loads(res)
                except Exception: res = {"clicked": False}
            self.cadence.sleep("post_click", note=label)
            if res.get("found"):
                click_res = self.browser.click_css_nth(".tags", int(res.get("index")), desc=f"click-tag[{label}]")
                if click_res.get("clicked"):
                    self.log(f"  ✓ 选中 「{label}」 (target={res.get('target')}, nth={res.get('index')})")
                    return True
                res["reason"] = f"real-click-failed:{click_res}"
            if res.get("clicked"):
                self.log(f"  ✓ 选中 「{label}」 (target={res.get('target')})")
                return True
            self.log(f"  · 第 {attempt} 次未命中 「{label}」 ({res.get('reason')})")
            if attempt <= max_retries:
                self.open_panel()  # 重新展开面板再试
        self.log(f"  ❌ 多次尝试仍无法选中 「{label}」")
        return False

    def verify_active(self, expected_labels: list[str]) -> dict:
        """
        校验 expected_labels 是否在激活态。
        小红书：激活的筛选项 DOM 形如 <div class="tags active"><span>最多点赞</span></div>。
        其余兜底用于 DOM 演化。
        """
        js = (
            "(function(){"
            "function texts(sel){return Array.from(document.querySelectorAll(sel)).map(function(e){return (e.textContent||'').trim();}).filter(Boolean);}"
            "var a=texts('.tags.active span,.tags.active');"
            "var b=texts('[class*=selected],[class*=active]');"
            "var c=texts('[aria-pressed=\"true\"],[aria-selected=\"true\"]');"
            "return JSON.stringify({a:a,b:b,c:c});"
            "})()"
        )
        out = self.browser.eval_json(js, desc="verify-filters") or {}
        seen = set()
        for k in ("a", "b", "c"):
            for s in out.get(k, []) if isinstance(out, dict) else []:
                seen.add(s)
        hits = {lbl: (lbl in seen) for lbl in expected_labels}
        self.log(f"  🔍 激活校验: {hits}")
        return hits

# ─── 笔记列表抽取 ──────────────────────────────────────────────────────────

class NoteListExtractor:
    """
    多策略抽取搜索结果列表。优先使用 PoC 验证过的 section.note-item，
    若返回不足 N 条，回退到结构形态匹配（基于 a[href*='/explore/' 或 search_result]）。
    """

    @staticmethod
    def _build_js(strategy: str, want: int) -> str:
        # opencli xiaohongshu note 要求带 xsec_token 的签名 URL；
        # 只有 search_result 形态的 a 含 token，/explore/ 不含。
        # 全部策略统一：先找 search_result，找不到再回退。
        url_picker = (
            "(function(card){"
            "var a=card.querySelector('a[href*=\"search_result\"][href*=\"xsec_token\"]')"
            "||card.querySelector('a[href*=\"search_result\"]')"
            "||card.querySelector('a[href*=\"xsec_token\"]')"
            "||card.querySelector('a[href*=\"explore\"]');"
            "return a?a.href:'';"
            "})"
        )
        if strategy == "primary":
            sel = "section.note-item"
            mapper = (
                "{rank:i+1,"
                "title:(s.querySelector('.title span')||s.querySelector('.note-text')||{}).textContent||'',"
                "author:(s.querySelector('.author-wrapper .name, .name')||{}).textContent||'',"
                "likes:(s.querySelector('.like-wrapper .count, .count')||{}).textContent||'0',"
                "url:(" + url_picker + ")(s)}"
            )
        elif strategy == "secondary":
            sel = "div[class*='note-item'], li[class*='note-item']"
            mapper = (
                "{rank:i+1,"
                "title:(s.querySelector('[class*=title]')||{}).textContent||'',"
                "author:(s.querySelector('[class*=name],[class*=author]')||{}).textContent||'',"
                "likes:(s.querySelector('[class*=count],[class*=like]')||{}).textContent||'0',"
                "url:(" + url_picker + ")(s)}"
            )
        else:  # structural fallback — 仅扫含 token 的 search_result 锚点
            return (
                "JSON.stringify((function(){"
                "var anchors=Array.from(document.querySelectorAll('a[href*=\"search_result\"][href*=\"xsec_token\"]'));"
                "if(anchors.length===0){anchors=Array.from(document.querySelectorAll('a[href*=\"search_result\"]'));}"
                "var seen=new Set();var out=[];"
                "anchors.forEach(function(a){"
                "  if(seen.has(a.href))return; seen.add(a.href);"
                "  var card=a.closest('section,article,div,li')||a;"
                "  var t=(card.querySelector('[class*=title], [class*=note-text], [class*=desc]')||{}).textContent||a.title||'';"
                "  var n=(card.querySelector('[class*=name], [class*=author]')||{}).textContent||'';"
                "  var l=(card.querySelector('[class*=count], [class*=like]')||{}).textContent||'0';"
                "  if(t.trim())out.push({rank:out.length+1,title:t.trim(),author:n.trim(),likes:l.trim(),url:a.href});"
                "}); return out.slice(0," + str(want * 2) + ");"
                "})())"
            )
        return (
            "JSON.stringify(Array.from(document.querySelectorAll(" + json.dumps(sel) + ")).slice(0," + str(want * 2) + ")"
            ".map(function(s,i){return " + mapper + ";})"
            ".filter(function(n){return n.url && n.title;}))"
        )

    def extract(self, browser: BrowserSession, log: Log, want: int) -> list[dict]:
        for strat in ("primary", "secondary", "structural"):
            js = self._build_js(strat, want)
            out = browser.eval_json(js, desc=f"extract[{strat}]")
            notes = out if isinstance(out, list) else []
            # opencli xiaohongshu note 强制要求 xsec_token；丢掉没 token 的
            with_tok = [n for n in notes if "xsec_token" in (n.get("url") or "")]
            log(f"  · 策略「{strat}」抽到 {len(notes)} 条（带 token: {len(with_tok)}）")
            notes = with_tok
            min_notes = max(1, min(want, max(3, want // 2)))
            if len(notes) >= min_notes:
                # 去重 + 截断
                uniq = []
                seen = set()
                for n in notes:
                    u = n.get("url", "")
                    if not u or u in seen:
                        continue
                    seen.add(u)
                    uniq.append(n)
                    if len(uniq) >= want:
                        break
                # rank 重新编号
                for i, n in enumerate(uniq, 1):
                    n["rank"] = i
                return uniq
        return []

# ─── 断点状态机 ────────────────────────────────────────────────────────────

@dataclass
class TaskStatus:
    status: str = "pending"   # pending | in_progress | done | failed
    attempts: int = 0
    error: str | None = None
    data: Any = None

@dataclass
class CollectorState:
    version: int = 1
    params: dict = field(default_factory=dict)
    started_at: str = ""
    last_update: str = ""
    phase: str = "init"        # init | list | details | comments | done
    list_status: str = "pending"
    notes: list[dict] = field(default_factory=list)
    details: dict[str, TaskStatus] = field(default_factory=dict)  # key=url
    comments: dict[str, TaskStatus] = field(default_factory=dict)
    stats: dict = field(default_factory=lambda: {"requests": 0, "actions": 0})

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "params": self.params,
            "started_at": self.started_at,
            "last_update": self.last_update,
            "phase": self.phase,
            "list_status": self.list_status,
            "notes": self.notes,
            "details": {k: asdict(v) for k, v in self.details.items()},
            "comments": {k: asdict(v) for k, v in self.comments.items()},
            "stats": self.stats,
        }

    @staticmethod
    def from_dict(d: dict) -> "CollectorState":
        s = CollectorState(
            version=d.get("version", 1),
            params=d.get("params", {}),
            started_at=d.get("started_at", ""),
            last_update=d.get("last_update", ""),
            phase=d.get("phase", "init"),
            list_status=d.get("list_status", "pending"),
            notes=d.get("notes", []),
            stats=d.get("stats", {"requests": 0, "actions": 0}),
        )
        s.details = {k: TaskStatus(**v) for k, v in (d.get("details") or {}).items()}
        s.comments = {k: TaskStatus(**v) for k, v in (d.get("comments") or {}).items()}
        return s

class Checkpoint:
    def __init__(self, state_path: Path, output_path: Path, log: Log):
        self.state_path = state_path
        self.output_path = output_path
        self.log = log
        self.state: CollectorState = CollectorState()

    def load_or_init(self, params: dict) -> bool:
        state_fs = Path(fs_path(self.state_path))
        if state_fs.exists():
            try:
                d = json.loads(state_fs.read_text(encoding="utf-8"))
                self.state = CollectorState.from_dict(d)
                self.log(f"  📁 已加载 checkpoint: phase={self.state.phase}, "
                         f"notes={len(self.state.notes)}, "
                         f"detail_done={sum(1 for t in self.state.details.values() if t.status=='done')}, "
                         f"comment_done={sum(1 for t in self.state.comments.values() if t.status=='done')}")
                return True
            except Exception as e:
                self.log(f"  ⚠️ checkpoint 损坏，新建：{e}")
        self.state.params = params
        self.state.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
        return False

    def save(self):
        self.state.last_update = time.strftime("%Y-%m-%d %H:%M:%S")
        payload = json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2)
        tmp = self.state_path.with_name(f"{self.state_path.name}.{os.getpid()}.tmp")
        for attempt in range(6):
            try:
                Path(fs_path(tmp)).write_text(payload, encoding="utf-8")
                os.replace(fs_path(tmp), fs_path(self.state_path))
                return
            except PermissionError:
                time.sleep(0.25 * (attempt + 1))
        Path(fs_path(self.state_path)).write_text(payload, encoding="utf-8")
        try:
            Path(fs_path(tmp)).unlink(missing_ok=True)
        except Exception:
            pass

    def emit_output(self):
        """从 state 派生面向下游的 JSON。"""
        items = []
        for n in self.state.notes:
            url = n.get("url", "")
            d = self.state.details.get(url)
            c = self.state.comments.get(url)
            items.append({
                "rank": n.get("rank"),
                "title": n.get("title"),
                "author": n.get("author"),
                "likes_search": n.get("likes"),
                "url": url,
                "detail": d.data if d and d.status == "done" else None,
                "comments": c.data if c and c.status == "done" else [],
            })
        out = {
            "probe_time": self.state.started_at,
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "params": self.state.params,
            "stats": self.state.stats,
            "weekly_top": items,
        }
        Path(fs_path(self.output_path)).write_text(
            json.dumps(out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

# ─── 编排器 ────────────────────────────────────────────────────────────────

@dataclass
class CollectorParams:
    keyword: str
    sort: str = "liked"
    range: str = "week"
    top: int = 10
    comments_per_note: int = 10
    with_replies: bool = False
    session: str = "xhs"
    max_actions: int = 60
    output_dir: Path | None = None
    output: Path | None = None
    state: Path | None = None
    dry_run: bool = False
    resume: bool = False
    cadence: str = "normal"        # normal | compact | swift
    # 切片控制：单次会话只跑指定阶段 / 指定 note 子集
    phase: str = "all"            # all | list | details | comments
    note_indices: list[int] | None = None  # 1-based rank 子集，None=全部

class Collector:
    def __init__(self, params: CollectorParams):
        self.p = params
        self._setup_paths()
        self.log = Log(self._log_path)
        self.cadence = Cadence(self.log, dry_run=self.p.dry_run, mode=self.p.cadence)
        self.volume = Volume(self.log, hard_cap=self.p.max_actions)
        self.cli = CLIRunner(self.log, dry_run=self.p.dry_run)
        self.browser = BrowserSession(self.cli, self.cadence, self.log, self.p.session)
        self.filter_panel = FilterPanel(self.browser, self.cadence, self.log)
        self.list_extractor = NoteListExtractor()
        self.cp = Checkpoint(self._state_path, self._output_path, self.log)

    def _setup_paths(self):
        slug = re.sub(r"[^\w一-鿿]+", "_", self.p.keyword).strip("_") or "kw"
        base = f"xhs_{slug}_{self.p.sort}_{self.p.range}"
        output_dir = (self.p.output_dir or Path.cwd()).resolve()
        self._output_path = (self.p.output or (output_dir / f"{base}.json")).resolve()
        self._state_path = (self.p.state or self._output_path.with_suffix(".state.json")).resolve()
        self._log_path = self._output_path.with_suffix(".log")
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    # ── phase 1：列表 ─────────────────────────────────────────────────────
    def _phase_list(self):
        self.log.section("阶段 1/3：搜索 + 筛选 + 抽取列表")
        if self.cp.state.list_status == "done" and self.cp.state.notes:
            self.log(f"  ↪ 列表已存在（{len(self.cp.state.notes)} 条），跳过")
            return True
        self.cp.state.phase = "list"
        self.cp.state.list_status = "in_progress"
        self.cp.save()

        url = f"https://www.xiaohongshu.com/search_result?keyword={quote(self.p.keyword)}"
        if not self.browser.open(url, desc=f"open search[{self.p.keyword}]"):
            self.cp.state.list_status = "failed"
            self.cp.save()
            return False
        self.cadence.sleep("read", note="page-settle")

        # 关闭可能的"我知道了"弹窗
        self.browser.eval_js(
            "Array.from(document.querySelectorAll('button')).forEach(function(b){if((b.textContent||'').includes('我知道了'))b.click();});'ok'",
            desc="dismiss-popup",
        )
        self.cadence.sleep("click", note="popup")

        sort_label = SORT_LABELS.get(self.p.sort)
        range_label = RANGE_LABELS.get(self.p.range)
        range_label_options = RANGE_LABEL_OPTIONS.get(self.p.range, [range_label] if range_label else [])
        if not sort_label or not range_label:
            self.log(f"  ❌ 不支持的 sort={self.p.sort} 或 range={self.p.range}")
            self.cp.state.list_status = "failed"
            self.cp.save()
            return False

        if not self.filter_panel.open_panel():
            self.cp.state.list_status = "failed"
            self.cp.save()
            return False

        ok_sort = self.filter_panel.pick(sort_label)
        ok_range_label = None
        for candidate in range_label_options:
            if self.filter_panel.pick(candidate):
                ok_range_label = candidate
                if candidate != range_label:
                    self.log(f"  ↪ 时间范围「{range_label}」不可用，改用当前 UI 可选项「{candidate}」")
                break
        ok_range = ok_range_label is not None
        if not (ok_sort and ok_range):
            self.cp.state.list_status = "failed"
            self.cp.save()
            return False

        self.cadence.sleep("scan", note="results-load")
        active = self.filter_panel.verify_active([sort_label, ok_range_label])
        if not all(active.values()):
            # 重试一次：再点一遍未激活的标签
            missing = [lbl for lbl, ok in active.items() if not ok]
            self.log(f"  ↻ 筛选未激活：{missing}，重点一次")
            for lbl in missing:
                self.filter_panel.pick(lbl, max_retries=1)
            self.cadence.sleep("scan", note="results-reload")
            active = self.filter_panel.verify_active([sort_label, ok_range_label])
            if not all(active.values()):
                self.log(f"  ❌ 重试后仍未激活：{active} — 中止 list 阶段，避免污染下游")
                self.cp.state.list_status = "failed"
                self.cp.save()
                return False
        self.log(f"  ✓ 筛选确认激活：{sort_label} + {ok_range_label}")

        # 滚一下让懒加载触发
        self.browser.scroll("down", desc="scroll-load-more")
        self.cadence.sleep("scan", note="post-scroll")

        notes = self.list_extractor.extract(self.browser, self.log, want=self.p.top)
        min_notes = max(1, min(self.p.top, 3))
        if len(notes) < min_notes:
            self.log(f"  ❌ 仅抽到 {len(notes)} 条，停止")
            self.cp.state.list_status = "failed"
            self.cp.save()
            return False

        self.cp.state.notes = notes
        self.cp.state.list_status = "done"
        # 初始化 details/comments 任务表
        for n in notes:
            url = n.get("url", "")
            if url and url not in self.cp.state.details:
                self.cp.state.details[url] = TaskStatus()
            if url and url not in self.cp.state.comments:
                self.cp.state.comments[url] = TaskStatus()
        self.cp.save()

        self.log(f"\n  🏆 Top {len(notes)}：")
        for n in notes:
            self.log(f"    {n['rank']}. 👍{str(n.get('likes','')):>5} | {(n.get('title','') or '')[:42]}")
        return True

    def _selected_notes(self) -> list[dict]:
        """根据 --note-indices 过滤要处理的笔记（1-based rank）。"""
        notes = self.cp.state.notes
        if not self.p.note_indices:
            return notes
        idx_set = set(self.p.note_indices)
        return [n for n in notes if n.get("rank") in idx_set]

    # ── phase 2：详情 ─────────────────────────────────────────────────────
    def _phase_details(self):
        self.log.section("阶段 2/3：拉取笔记正文 + 互动数据")
        self.cp.state.phase = "details"
        self.cp.save()

        targets = self._selected_notes()
        if self.p.note_indices:
            self.log(f"  ✂ 切片：仅处理 rank {sorted(self.p.note_indices)}（{len(targets)} 条）")

        for n in targets:
            if self.volume.exhausted():
                self.log("  ⛔ 触达容量上限，落盘退出（可 --resume 续抓）")
                return False
            url = n.get("url", "")
            task = self.cp.state.details.get(url)
            if not task or task.status == "done":
                continue
            self.cadence.sleep("scan", note=f"detail-{n['rank']}")
            task.status = "in_progress"
            task.attempts += 1
            self.cp.save()

            argv = [OPENCLI, "xiaohongshu", "note", url, "-f", "json",
                    "--site-session", "persistent", "--keep-tab", "true"]
            data = self.cli.run_json(argv, desc=f"note[{n['rank']}] {n.get('title','')[:25]}",
                                     timeout=90, retries=1)
            self.volume.consume(1)
            self.cadence.tick()

            if data and isinstance(data, list):
                if data and isinstance(data[0], dict) and ("field" in data[0] or "value" in data[0]):
                    d = {row.get("field", ""): row.get("value", "") for row in data}
                elif data and isinstance(data[0], dict):
                    d = dict(data[0])
                    d["visible_comment_rows"] = [
                        {"rank": row.get("rank"), "comment_text": row.get("comment_text", ""), "comment_time": row.get("comment_time", "")}
                        for row in data if row.get("comment_text")
                    ]
                else:
                    d = {}
                task.status = "done"
                task.data = d
                body = d.get("content") or d.get("note_content") or d.get("body") or ""
                self.log(f"    ✅ 正文 {len(body)} 字 | "
                         f"👍{d.get('likes','?')} ⭐{d.get('collects','?')} 💬{d.get('comments','?')}")
            elif data and isinstance(data, dict):
                task.status = "done"
                task.data = data
            else:
                task.status = "failed"
                task.error = "no-data-or-bad-shape"
                self.log("    ⚠️ 详情拉取失败")
            self.cp.save()
        return True

    # ── phase 3：评论 ─────────────────────────────────────────────────────
    def _phase_comments(self):
        self.log.section("阶段 3/3：拉取热门评论")
        self.cp.state.phase = "comments"
        self.cp.save()

        targets = self._selected_notes()
        if self.p.note_indices:
            self.log(f"  ✂ 切片：仅处理 rank {sorted(self.p.note_indices)}（{len(targets)} 条）")

        for n in targets:
            if self.volume.exhausted():
                self.log("  ⛔ 触达容量上限，落盘退出")
                return False
            url = n.get("url", "")
            task = self.cp.state.comments.get(url)
            if not task or task.status == "done":
                continue
            self.cadence.sleep("scan", note=f"comment-{n['rank']}")
            task.status = "in_progress"
            task.attempts += 1
            self.cp.save()

            argv = [OPENCLI, "xiaohongshu", "comments", url,
                    "--limit", str(self.p.comments_per_note),
                    "-f", "json",
                    "--site-session", "persistent", "--keep-tab", "true"]
            if self.p.with_replies:
                argv.extend(["--with-replies", "true"])
            data = self.cli.run_json(argv, desc=f"comments[{n['rank']}] {n.get('title','')[:25]}",
                                     timeout=90, retries=1)
            self.volume.consume(1)
            self.cadence.tick()

            if data and isinstance(data, list):
                task.status = "done"
                task.data = data
                if data:
                    top = max(data, key=lambda c: int(str(c.get("likes", 0)).replace(",", "") or 0)) \
                          if all(isinstance(c, dict) for c in data) else data[0]
                    self.log(f"    ✅ {len(data)} 条 | 🔥 {top.get('author','?')}: "
                             f"{(top.get('text','') or '')[:50]} (👍{top.get('likes',0)})")
            else:
                task.status = "failed"
                task.error = "no-data"
                self.log("    ⚠️ 评论拉取失败")
            self.cp.save()
        return True

    # ── 主流程 ────────────────────────────────────────────────────────────
    def run(self) -> int:
        params_dict = {k: getattr(self.p, k) for k in
                       ("keyword", "sort", "range", "top", "comments_per_note",
                        "with_replies", "session", "max_actions", "phase", "note_indices")}
        self.cp.load_or_init(params_dict)
        # phase / note_indices 是切片指令，不覆盖已有任务表，因此每次都重写
        self.cp.state.params = params_dict
        self.log(f"  🎯 关键词={self.p.keyword} | sort={self.p.sort} | range={self.p.range} | "
                 f"top={self.p.top} | comments={self.p.comments_per_note} | "
                 f"phase={self.p.phase} | indices={self.p.note_indices} | dry={self.p.dry_run}")
        self.log(f"  📂 输出: {self._output_path}")
        self.log(f"  📂 状态: {self._state_path}")

        # ── 切片调度 ──────────────────────────────────────────────────
        run_list = self.p.phase in ("all", "list")
        run_details = self.p.phase in ("all", "details")
        run_comments = self.p.phase in ("all", "comments")

        # details/comments 阶段需要 list 已完成
        if (run_details or run_comments) and self.cp.state.list_status != "done":
            if run_list:
                ok_list = self._phase_list()
                self.cp.emit_output()
                if not ok_list:
                    self.log.close()
                    return 1
            else:
                self.log("  ❌ 切片要求跳过 list，但状态文件中 list_status != done — 先跑 --phase list")
                self.log.close()
                return 2
        elif run_list:
            ok_list = self._phase_list()
            self.cp.emit_output()
            if not ok_list:
                self.log.close()
                return 1

        if run_details:
            self.cadence.phase_break("详情阶段")
            self._phase_details()
            self.cp.emit_output()

        if run_comments:
            self.cadence.phase_break("评论阶段")
            self._phase_comments()
            self.cp.emit_output()

        if not self.p.dry_run:
            self.browser.unbind()

        # 统计
        self.cp.state.phase = "done"
        self.cp.state.stats["actions"] = self.cadence.actions
        self.cp.state.stats["requests"] = self.volume.spent
        self.cp.save()
        self.cp.emit_output()

        d_done = sum(1 for t in self.cp.state.details.values() if t.status == "done")
        c_done = sum(1 for t in self.cp.state.comments.values() if t.status == "done")
        n = len(self.cp.state.notes)
        self.log("")
        self.log("█" * 56)
        self.log(f"█  完成 | 动作 {self.cadence.actions} 次 | 详情 {d_done}/{n} | 评论 {c_done}/{n}")
        self.log(f"█  输出 → {self._output_path}")
        self.log("█" * 56)
        self.log.close()
        return 0

# ─── CLI ──────────────────────────────────────────────────────────────────

def parse_args() -> CollectorParams:
    ap = argparse.ArgumentParser(description="小红书筛选式采集器（人化版）")
    ap.add_argument("--keyword", "-k", help="搜索关键词")
    ap.add_argument("--sort", choices=list(SORT_LABELS.keys()), default="liked",
                    help="排序：liked(最多点赞)/latest(最新)/comprehensive(综合)")
    ap.add_argument("--range", dest="time_range",
                    choices=list(RANGE_LABELS.keys()), default="week",
                    help="时间范围：day/week/half-month/month/half-year/unlimited")
    ap.add_argument("--top", type=int, default=10, help="抓取的笔记数量")
    ap.add_argument("--comments-per-note", type=int, default=10, help="每条笔记的评论数")
    ap.add_argument("--with-replies", action="store_true", help="包含楼中楼")
    ap.add_argument("--session", default="xhs", help="opencli 浏览器 session 名")
    ap.add_argument("--max-actions", type=int, default=60,
                    help="单次会话动作硬上限（达上限自动落盘退出）")
    ap.add_argument("--output-dir", type=Path, help="默认输出目录（默认当前工作目录）")
    ap.add_argument("--output", type=Path, help="输出 JSON 路径（默认 <output-dir>/xhs_<kw>_<sort>_<range>.json）")
    ap.add_argument("--state", type=Path, help="状态文件路径（默认与 output 同目录）")
    ap.add_argument("--resume", action="store_true", help="从 checkpoint 续抓")
    ap.add_argument("--dry-run", action="store_true", help="不发请求，只打印计划")
    ap.add_argument("--cadence", choices=("normal", "compact", "swift"), default="normal",
                    help="节奏模式：normal=完整人化；compact=切片调度配套；swift=本机受控测试")
    # ── 切片入口 ───────────────────────────────────────────────────────
    ap.add_argument("--phase", choices=("all", "list", "details", "comments"),
                    default="all",
                    help="只跑某一阶段（用于跨会话切片调度）")
    ap.add_argument("--note-indices", default="",
                    help="仅处理指定 rank 的笔记，逗号分隔，如 '1,2,3' 或 '1-3,7'")
    args = ap.parse_args()

    if not args.keyword:
        ap.error("--keyword 必填")

    indices: list[int] | None = None
    if args.note_indices:
        indices = []
        for chunk in args.note_indices.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "-" in chunk:
                a, b = chunk.split("-", 1)
                indices.extend(range(int(a), int(b) + 1))
            else:
                indices.append(int(chunk))
        indices = sorted(set(indices))

    return CollectorParams(
        keyword=args.keyword,
        sort=args.sort,
        range=args.time_range,
        top=args.top,
        comments_per_note=args.comments_per_note,
        with_replies=args.with_replies,
        session=args.session,
        max_actions=args.max_actions,
        output_dir=args.output_dir,
        output=args.output,
        state=args.state,
        dry_run=args.dry_run,
        resume=args.resume,
        cadence=args.cadence,
        phase=args.phase,
        note_indices=indices,
    )

def main() -> int:
    try:
        params = parse_args()
        return Collector(params).run()
    except KeyboardInterrupt:
        print("\n[中断] 用户取消（state 已保存，可 --resume）")
        return 130

if __name__ == "__main__":
    sys.exit(main())
