#!/usr/bin/env python3
"""
JIRA-飞书单聊/群聊双发 Webhook 转发服务 (远端部署版)
监听端口: 18795, 绑定 0.0.0.0
原理: 接收 GET /webhook?key=KIKIGO-123&secret=xxx
      ➔ 查询 JIRA 完整详情 ➔ 获取经办人邮箱
      ➔ 双发飞书(群聊 + 私信@提醒)
"""
import http.server
import json
import urllib.parse
import threading
import time
import os
import sys
import traceback
import requests
from pathlib import Path

# ============================================================
#  配置区：从同目录 bridge.env 读取，或使用环境变量
# ============================================================
def load_env(env_file):
    """从 .env 文件加载键值对"""
    result = {}
    if not os.path.exists(env_file):
        return result
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                result[k.strip()] = v.strip()
    return result

# 加载配置
_env = load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge.env"))

PORT = int(_env.get("BRIDGE_PORT", os.environ.get("BRIDGE_PORT", "18795")))
WEBHOOK_SECRET = _env.get("WEBHOOK_SECRET", os.environ.get("WEBHOOK_SECRET", ""))
GROUP_CHAT_ID = _env.get("FEISHU_GROUP_CHAT_ID", os.environ.get("FEISHU_GROUP_CHAT_ID", ""))
GROUP_WEBHOOK_URL = _env.get("FEISHU_GROUP_WEBHOOK", os.environ.get("FEISHU_GROUP_WEBHOOK", ""))

JIRA_URL = _env.get("JIRA_URL", os.environ.get("JIRA_URL", ""))
JIRA_USERNAME = _env.get("JIRA_USERNAME", os.environ.get("JIRA_USERNAME", ""))
JIRA_PASSWORD = _env.get("JIRA_PASSWORD", os.environ.get("JIRA_PASSWORD", ""))

FEISHU_APP_ID = _env.get("FEISHU_APP_ID", os.environ.get("FEISHU_APP_ID", ""))
FEISHU_APP_SECRET = _env.get("FEISHU_APP_SECRET", os.environ.get("FEISHU_APP_SECRET", ""))


# ============================================================
#  JIRA 客户端 (精简内嵌版，无外部依赖)
# ============================================================
class JiraClient:
    def __init__(self):
        self.jira_url = JIRA_URL.rstrip("/")
        self.auth = (JIRA_USERNAME, JIRA_PASSWORD)
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}

    def get_bug(self, issue_key, expand=None):
        url = f"{self.jira_url}/rest/api/2/issue/{issue_key}?expand={expand}" if expand else f"{self.jira_url}/rest/api/2/issue/{issue_key}"
        resp = requests.get(url, auth=self.auth, headers=self.headers, verify=False, timeout=15)
        resp.raise_for_status()
        return resp.json()


# ============================================================
#  飞书通知器
# ============================================================
class FeishuNotifier:
    def __init__(self):
        self._token = None
        self._token_expires_at = 0
        self._email_map = {}  # email/enterprise_email -> open_id
        self._sent_cache = {} # (key, target, type) -> timestamp
        self._cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_map.json")
        self.load_cache()

    def load_cache(self):
        """从本地 JSON 文件加载映射缓存"""
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    self._email_map = json.load(f)
                print(f"[Feishu] ✅ 已从本地持久化文件加载 {len(self._email_map)} 个邮箱映射缓存。")
            except Exception as e:
                print(f"[Feishu] 加载本地缓存文件失败: {e}")

    def save_cache(self):
        """将映射缓存持久化保存到本地 JSON 文件"""
        try:
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._email_map, f, ensure_ascii=False, indent=2)
            print(f"[Feishu] ✅ 已将最新的 {len(self._email_map)} 个邮箱映射持久化写入本地文件。")
        except Exception as e:
            print(f"[Feishu] 写入本地缓存文件失败: {e}")

    def get_tenant_access_token(self):
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                self._token = data.get("tenant_access_token")
                self._token_expires_at = time.time() + data.get("expire", 7200)
                return self._token
            else:
                print(f"[Feishu] Token 获取失败: {data.get('msg')}")
        except Exception as e:
            print(f"[Feishu] Token 请求异常: {e}")
        return None

    def _fetch_all(self, base_url, headers):
        """通用分页拉取 Feishu 接口数据"""
        results = []
        page_token = ""
        has_more = True
        
        while has_more:
            # 拼接分页参数
            sep = "&" if "?" in base_url else "?"
            url = f"{base_url}{sep}page_size=50"
            if page_token:
                url += f"&page_token={page_token}"
                
            try:
                resp = requests.get(url, headers=headers, timeout=10).json()
                if resp.get("code") == 0:
                    data = resp.get("data", {})
                    results.extend(data.get("items", []))
                    has_more = data.get("has_more", False)
                    page_token = data.get("page_token", "")
                else:
                    print(f"[Feishu] 分页拉取失败: Code={resp.get('code')} Msg={resp.get('msg')}")
                    break
            except Exception as e:
                print(f"[Feishu] 分页拉取异常: {e}")
                break
                
        return results

    def refresh_email_map(self):
        """拉取可见部门及根目录下的所有用户，支持分页，构建 email -> open_id 映射 并写入缓存文件"""
        token = self.get_tenant_access_token()
        if not token:
            return
        
        headers = {"Authorization": f"Bearer {token}"}
        new_map = {}

        try:
            # 1. 先获取可见范围的部门列表
            scope_url = "https://open.feishu.cn/open-apis/contact/v3/scopes"
            scope_resp = requests.get(scope_url, headers=headers, timeout=10).json()
            
            dept_ids = []
            if scope_resp.get("code") == 0:
                dept_ids = scope_resp.get("data", {}).get("department_ids", [])
            else:
                print(f"[Feishu] 获取可见范围失败: {scope_resp.get('msg')}")

            # 2. 如果可见范围里有部门，遍历分页获取每个部门下的用户
            if dept_ids:
                print(f"[Feishu] 发现可见部门 {len(dept_ids)} 个，准备分页拉取部门成员...")
                for d_id in dept_ids:
                    url = f"https://open.feishu.cn/open-apis/contact/v3/users/find_by_department?department_id={d_id}"
                    items = self._fetch_all(url, headers)
                    for item in items:
                        open_id = item.get("open_id")
                        if open_id:
                            email = item.get("email")
                            ent_email = item.get("enterprise_email")
                            if email:
                                new_map[email.lower()] = open_id
                            if ent_email:
                                new_map[ent_email.lower()] = open_id
            
            # 3. 兜底分页拉取根目录用户
            fallback_url = "https://open.feishu.cn/open-apis/contact/v3/users"
            items = self._fetch_all(fallback_url, headers)
            for item in items:
                open_id = item.get("open_id")
                if open_id:
                    email = item.get("email")
                    ent_email = item.get("enterprise_email")
                    if email:
                        new_map[email.lower()] = open_id
                    if ent_email:
                        new_map[ent_email.lower()] = open_id

            self._email_map = new_map
            print(f"[Feishu] 成功刷新通讯录映射，共拉取到 {len(new_map)} 个邮箱关联。")
            self.save_cache()

        except Exception as e:
            print(f"[Feishu] 刷新通讯录映射发生异常: {e}")

    def get_openid_by_email(self, email):
        """通过邮箱查询 open_id (支持企业与普通邮箱，自带读穿透机制)"""
        if not email:
            return None
        
        email_lower = email.strip().lower()
        if email_lower in self._email_map:
            return self._email_map[email_lower]
        
        # 本地缓存未命中，代表可能是新员工或改了绑定，主动穿透刷新一次
        print(f"[Feishu] 🔑 邮箱 {email} 未命中本地缓存，触发实时拉取刷新...")
        self.refresh_email_map()
        return self._email_map.get(email_lower)

    def send_card(self, receive_id, receive_id_type, card_json):
        token = self.get_tenant_access_token()
        if not token:
            print("[Feishu] Token 为空，放弃发送。")
            return False

        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {
            "receive_id": receive_id,
            "msg_type": "interactive",
            "content": json.dumps(card_json, ensure_ascii=False)
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                print(f"[Feishu] ✅ 卡片已发送 → {receive_id_type}={receive_id}")
                return True
            else:
                print(f"[Feishu] ❌ 发送失败 → {receive_id_type}={receive_id} | Code={data.get('code')} Msg={data.get('msg')}")
        except Exception as e:
            print(f"[Feishu] ❌ 请求异常: {e}")
        return False

    def send_group_webhook(self, webhook_url, card_json):
        """通过群机器人 Webhook 直接推送卡片（无需鉴权）"""
        payload = {"msg_type": "interactive", "card": card_json}
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            data = resp.json()
            if data.get("code") == 0 or data.get("StatusCode") == 0:
                print(f"[Feishu] ✅ 群 Webhook 卡片发送成功")
                return True
            else:
                print(f"[Feishu] ❌ 群 Webhook 发送失败: {data}")
        except Exception as e:
            print(f"[Feishu] ❌ 群 Webhook 请求异常: {e}")
        return False

    def is_duplicate(self, issue_key, target, channel_type):
        """10秒防重复判定与发送频率锁"""
        if not target:
            return False
        now = time.time()
        cache_key = (issue_key, target, channel_type)
        last_sent = self._sent_cache.get(cache_key, 0)
        
        if now - last_sent < 10:
            return True
            
        self._sent_cache[cache_key] = now
        self._cleanup_sent_cache(now)
        return False

    def _cleanup_sent_cache(self, now):
        """定期清理 60 秒以上的过期发送历史记录"""
        self._sent_cache = {k: v for k, v in self._sent_cache.items() if now - v < 60}


# ============================================================
#  卡片构建
# ============================================================
def build_feishu_card(issue_key, summary, reporter, priority, assignee_name, assignee_openid, assignee_email, jira_url):
    issue_url = f"{jira_url}/browse/{issue_key}"

    # 优先使用 open_id @提到经办人（最稳定），其次使用邮箱，最后退回到名字文本
    if assignee_openid:
        assignee_display = f"<at id={assignee_openid}></at>"
    elif assignee_email:
        assignee_display = f"<at id={assignee_email}></at>"
    else:
        assignee_display = assignee_name

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🚨 JIRA 新增/变更 Bug 提醒"},
            "template": "red"
        },
        "elements": [
            {
                "tag": "markdown",
                "content": (
                    f"**问题标题**：{summary}\n"
                    f"**缺陷 Key**：[{issue_key}]({issue_url})\n"
                    f"**经办人**：{assignee_display}\n"
                    f"**创建人**：{reporter}\n"
                    f"**优先级**：{priority}"
                )
            },
            {
                "tag": "action",
                "elements": [{
                    "tag": "button",
                    "text": {"content": "🚀 点击前往 JIRA 查看", "tag": "plain_text"},
                    "url": issue_url,
                    "type": "primary"
                }]
            }
        ]
    }


# ============================================================
#  HTTP Handler
# ============================================================
class BridgeHandler(http.server.BaseHTTPRequestHandler):

    def check_should_notify(self, issue_data, webhook_event=None):
        """判断是否需要发送经办人私信：仅限新建或本次变更修改了经办人"""
        fields = issue_data.get("fields", {})
        created_str = fields.get("created", "")
        updated_str = fields.get("updated", "")

        if webhook_event == "jira:issue_created":
            return True, "Jira 新建单子事件"

        from datetime import datetime
        try:
            if created_str and updated_str:
                c_dt = datetime.strptime(created_str[:19], "%Y-%m-%dT%H:%M:%S")
                u_dt = datetime.strptime(updated_str[:19], "%Y-%m-%dT%H:%M:%S")
                if abs((u_dt - c_dt).total_seconds()) <= 5:
                    return True, "全新创建单子"
        except Exception:
            pass

        changelog = issue_data.get("changelog", {})
        histories = changelog.get("histories", [])
        if histories:
            latest_history = histories[-1]
            items = latest_history.get("items", [])
            for item in items:
                if item.get("field") == "assignee":
                    from_user = item.get("fromString", "未指派")
                    to_user = item.get("toString", "未指派")
                    return True, f"经办人变更: [{from_user}] -> [{to_user}]"

        return False, "非新建且本次未修改经办人（仅改状态/其它字段）"

    jira_client = JiraClient()
    notifier = FeishuNotifier()

    def log_message(self, format, *args):
        """覆盖默认日志格式，加上时间戳"""
        sys.stderr.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}\n")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        params = urllib.parse.parse_qs(parsed.query)

        # Secret 校验（防止恶意触发）
        if WEBHOOK_SECRET:
            secret = params.get("secret", [""])[0]
            if secret != WEBHOOK_SECRET:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden: invalid secret")
                print(f"[Bridge] ⛔ 收到非法请求，secret 不匹配！来源: {self.client_address[0]}")
                return

        keys = params.get("key", [])
        if not keys:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing 'key' parameter")
            return

        issue_key = keys[0]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "queued", "key": issue_key}).encode())

        threading.Thread(target=self.process_webhook, args=(issue_key,), daemon=True).start()

    def process_webhook(self, issue_key, webhook_event=None):
        print(f"\n[Bridge] ========== 处理 {issue_key} (事件: {webhook_event}) ==========")
        try:
            issue = self.jira_client.get_bug(issue_key, expand="changelog")
            should_notify, reason = self.check_should_notify(issue, webhook_event)
            if not should_notify:
                print(f"[Bridge] 🛑 屏蔽私信通知 [{reason}] (Key: {issue_key})，不打扰经办人。")
                return

            fields = issue.get("fields", {})

            summary = fields.get("summary", "无标题")
            # 优先从 creator (创建人) 获取，其次从 reporter (报告人) 获取，并支持 displayName 和 name 兜底
            user_obj = fields.get("creator") or fields.get("reporter") or {}
            reporter = user_obj.get("displayName") or user_obj.get("name") or "匿名"
            priority = (fields.get("priority") or {}).get("name", "Medium")

            assignee = fields.get("assignee")
            assignee_name = "未指派"
            assignee_email = None
            if assignee:
                assignee_name = assignee.get("displayName", "未指派")
                assignee_email = assignee.get("emailAddress")

            # 1. 查找经办人的 open_id
            assignee_openid = None
            if assignee_email:
                print(f"[Bridge] 正在解析经办人邮箱: {assignee_email}")
                assignee_openid = self.notifier.get_openid_by_email(assignee_email)

            # 2. 构建卡片 (若有 open_id 则使用其进行安全@提及)
            card = build_feishu_card(
                issue_key, summary, reporter, priority,
                assignee_name, assignee_openid, assignee_email, self.jira_client.jira_url
            )

            # 3. 发送私信给对应的经办人（解析邮箱为 open_id 发送）；进行10秒去重
            if assignee_email:
                private_target = assignee_openid or assignee_email
                if not self.notifier.is_duplicate(issue_key, private_target, "private"):
                    if assignee_openid:
                        print(f"[Bridge] 邮箱成功解析为 open_id: {assignee_openid}，正在发送私信给经办人...")
                        self.notifier.send_card(assignee_openid, "open_id", card)
                    else:
                        print(f"[Bridge] ⚠️ 无法将邮箱 {assignee_email} 解析为飞书 open_id，尝试直接用邮箱发送...")
                        self.notifier.send_card(assignee_email, "email", card)
                else:
                    print(f"[Bridge] ⚠️ 检测到 {issue_key} 短时间内重复向经办人 {private_target} 发送私信，已拦截。")
            else:
                print("[Bridge] 该 Bug 暂无经办人，跳过私信。")

        except Exception:
            print(f"[Bridge] 处理 {issue_key} 异常:")
            traceback.print_exc()

    def do_POST(self):
        """兼容 POST 方式的 JIRA Webhook"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        # 从 POST body 中提取 issue key
        issue_key = None
        if "issue" in data:
            issue_key = data["issue"].get("key")
        elif "key" in data:
            issue_key = data["key"]

        if not issue_key:
            # 也尝试从 URL 参数中提取
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            keys = params.get("key", [])
            issue_key = keys[0] if keys else None

        if not issue_key:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Cannot extract issue key")
            return

        # Secret 校验
        if WEBHOOK_SECRET:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            secret = params.get("secret", [""])[0]
            if secret != WEBHOOK_SECRET:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden")
                return

        # 提取 webhookEvent
        webhook_event = data.get("webhookEvent")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "queued", "key": issue_key}).encode())

        threading.Thread(target=self.process_webhook, args=(issue_key, webhook_event), daemon=True).start()


# ============================================================
#  启动入口
# ============================================================
def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # 启动前配置自检
    missing = []
    if not JIRA_URL: missing.append("JIRA_URL")
    if not JIRA_USERNAME: missing.append("JIRA_USERNAME")
    if not JIRA_PASSWORD: missing.append("JIRA_PASSWORD")
    if not FEISHU_APP_ID: missing.append("FEISHU_APP_ID")
    if not FEISHU_APP_SECRET: missing.append("FEISHU_APP_SECRET")

    if missing:
        print(f"❌ 缺少必要配置项: {', '.join(missing)}")
        print("请在同目录的 bridge.env 文件中配置，或通过环境变量传入。")
        sys.exit(1)

    if not GROUP_CHAT_ID:
        print("⚠️ 未配置 FEISHU_GROUP_CHAT_ID，将跳过群聊发送。")

    if WEBHOOK_SECRET:
        print(f"🔒 Webhook Secret 已启用（长度: {len(WEBHOOK_SECRET)} 字符）")
    else:
        print("⚠️ 未配置 WEBHOOK_SECRET，任何人都可以触发此 Webhook！建议配置。")

    server = http.server.HTTPServer(("0.0.0.0", PORT), BridgeHandler)
    print(f"🚀 JIRA-飞书消息双发网关启动成功！")
    print(f"   监听地址: http://0.0.0.0:{PORT}")
    print(f"   Webhook URL: http://<公网IP>:{PORT}/webhook?key=KIKIGO-123")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭...")
        server.server_close()

if __name__ == "__main__":
    main()
