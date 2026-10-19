"""
S40_Jira通用连接器 — 全局共享 JIRA REST API 客户端
迁移自: @@TESTING_ROOT:win@@\.agent\skills\A6_Bug分析\jira_utils.py (406行, 生产验证)
改动: (1) 凭证从 config/jira_credentials.env 读取 (2) 添加 CLI 入口
"""
import requests
import json
import os
import sys
import argparse
from pathlib import Path

def load_jira_config():
    """从 jira_credentials.env 加载配置"""
    config = {}
    current_dir = Path(__file__).parent.resolve()
    env_file = current_dir.parent / "config" / "jira_credentials.env"

    if not env_file.exists():
        print(f"错误: 找不到 JIRA 凭证文件 {env_file}")
        sys.exit(1)

    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    return config

class JiraClient:
    def __init__(self, jira_url=None, username=None, password=None):
        """初始化Jira工具类（自动从 env 文件加载凭证）"""
        if not jira_url or not username or not password:
            cfg = load_jira_config()
            jira_url = jira_url or cfg.get("JIRA_URL", "")
            username = username or cfg.get("JIRA_USERNAME", "")
            password = password or cfg.get("JIRA_PASSWORD", "")

        self.jira_url = jira_url
        self.auth = (username, password)
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # 字段ID缓存
        self.field_cache = {
            'components': {},
            'versions': {},
            'sprints': {},
            'issue_type': None,
            'priority': None
        }
        self._priorities = None
        self._issue_types = {}
        self._components = {}
        self._versions = {}
        self._sprints = {}
        import threading
        self._lock = threading.Lock()

    def _get(self, path):
        """发送GET请求"""
        url = f"{self.jira_url}/rest/api/2/{path}"
        if "/rest/agile/1.0/" in path:
            url = f"{self.jira_url}{path}" if path.startswith("/rest") else f"{self.jira_url}/rest/agile/1.0/{path}"

        response = requests.get(url, auth=self.auth, headers=self.headers, verify=False)
        response.raise_for_status()
        return response.json()

    def create_bug(self, project_key, summary, description, priority="High", component=None, fix_version=None, affects_version=None, sprint=None, issue_links=None, assignee=None, security_level=None, labels=None):
        """创建Jira Bug"""
        try:
            issue_type_id = self.get_issue_type_id(project_key, "故障")
            priority_id = self.get_priority_id(priority)

            component_ids = []
            if component:
                for comp_name in component.split(","):
                    comp_name = comp_name.strip()
                    if comp_name:
                        comp_id = self.get_component_id(project_key, comp_name)
                        if comp_id: component_ids.append({"id": comp_id})

            fix_version_ids = []
            if fix_version:
                for v_name in fix_version.split(","):
                    v_name = v_name.strip()
                    if v_name:
                        v_id = self.get_version_id(project_key, v_name)
                        if v_id: fix_version_ids.append({"id": v_id})

            affects_version_ids = []
            if affects_version:
                for v_name in affects_version.split(","):
                    v_name = v_name.strip()
                    if v_name:
                        v_id = self.get_version_id(project_key, v_name)
                        if v_id: affects_version_ids.append({"id": v_id})

            sprint_id = None
            if sprint:
                try:
                    sprint_id = self.get_sprint_id(sprint)
                    if sprint_id:
                        sprint_id = int(sprint_id)
                except Exception as e:
                    print(f"  ⚠️ 提示: Jira 中未找到 Sprint '{sprint}'，本次建单将不绑定 Sprint")
                    sprint_id = None
        except Exception as e:
            raise Exception(f"转化字段ID失败: {str(e)}")

        url = f"{self.jira_url}/rest/api/2/issue/"
        data = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description.replace('\n', '\r\n'),
                "issuetype": {"id": issue_type_id},
                "priority": {"id": priority_id}
            }
        }

        if component_ids:
            data["fields"]["components"] = component_ids
        if fix_version_ids:
            data["fields"]["fixVersions"] = fix_version_ids
        if affects_version_ids:
            data["fields"]["versions"] = affects_version_ids
        if sprint_id:
            data["fields"]["customfield_10108"] = sprint_id
        if assignee:
            data["fields"]["assignee"] = {"name": assignee}
        if security_level:
            data["fields"]["security"] = {"id": str(security_level)}
        if labels:
            data["fields"]["labels"] = labels if isinstance(labels, list) else [labels]
        else:
            data["fields"]["labels"] = ["agent-created"]

        try:
            response = requests.post(url, auth=self.auth, headers=self.headers, json=data, verify=False)
            if response.status_code != 201:
                print(f"调试: API响应状态码: {response.status_code}")
                print(f"调试: API响应内容: {response.text}")
            response.raise_for_status()
            result = response.json()
            return {
                "key": result.get("key"),
                "id": result.get("id"),
                "self": result.get("self")
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"创建Bug失败: {str(e)}"
            if hasattr(e, 'response') and e.response:
                error_msg += f" - 状态码: {e.response.status_code}"
                try:
                    error_msg += f" - 响应内容: {e.response.text}"
                except:
                    pass
            raise Exception(error_msg)

    def delete_issue(self, issue_key):
        """物理删除 Jira 中的指定工单"""
        url = f"{self.jira_url}/rest/api/2/issue/{issue_key}"
        try:
            response = requests.delete(url, auth=self.auth, headers=self.headers, verify=False)
            response.raise_for_status()
            print(f"🗑️ 已成功从 Jira 删除工单: {issue_key}")
            return True
        except Exception as e:
            print(f"❌ 删除 Jira 工单 {issue_key} 失败: {str(e)}")
            return False

    def get_bug(self, bug_key, expand=None):
        """获取Bug详情"""
        url = f"issue/{bug_key}?expand={expand}" if expand else f"issue/{bug_key}"
        try:
            return self._get(url)
        except requests.exceptions.RequestException as e:
            raise Exception(f"获取Bug详情失败: {str(e)}")

    def get_all_summaries(self, project_key):
        """批量获取系统中所有已经存在的Bug，返回 {标题: Key} 字典"""
        print(f"🔍 正在从 Jira 获取项目 {project_key} 的现有数据...")
        jql = f'project = "{project_key}" AND issuetype = "故障"'

        summary_to_key = {}
        start_at = 0
        max_results = 100

        while True:
            resp = self._get(f"search?jql={requests.utils.quote(jql)}&startAt={start_at}&maxResults={max_results}&fields=summary")
            issues = resp.get("issues", [])
            if not issues:
                break

            for issue in issues:
                summary = issue.get("fields", {}).get("summary")
                if summary:
                    summary_to_key[summary.strip()] = issue["key"]

            total = resp.get("total", 0)
            start_at += max_results
            if start_at >= total:
                break

        print(f"✅ 已加载 {len(summary_to_key)} 条现有数据")
        return summary_to_key

    def is_issue_exists(self, project_key, summary):
        """检查是否存在相同摘要的Bug，如果存在返回 Key，否则 None"""
        jql = f'project = "{project_key}" AND summary ~ "\\"{summary}\\""'
        try:
            resp = self._get(f"search?jql={requests.utils.quote(jql)}&maxResults=1&fields=key")
            issues = resp.get("issues", [])
            if issues:
                return issues[0]["key"]
            return None
        except:
            return None

    def prewarm(self, project_keys):
        """预热缓存，顺序获取元数据并打印一次"""
        print(f"🚀 正在加载项目 {project_keys} 的 Jira 元数据...")

        self.get_priority_id("High")
        print(f"  - 已加载优先级 ID")

        for pk in project_keys:
            self.get_issue_type_id(pk, "故障")
            self.get_component_id(pk, "")
            self.get_version_id(pk, "")
            print(f"  - 已加载项目 {pk} 的类型、组件和版本 ID")

        self._preload_all_sprints()

    def _preload_all_sprints(self):
        """提前扫描所有看板并加载所有 Sprint"""
        with self._lock:
            if getattr(self, '_sprints_preloaded', False):
                return
            try:
                boards = self._get("/rest/agile/1.0/board").get("values", [])
                for board in boards:
                    if board.get("type") == "scrum":
                        path = f"/rest/agile/1.0/board/{board['id']}/sprint"
                        try:
                            sprints_data = self._get(path).get("values", [])
                            for s in sprints_data:
                                self._sprints[s["name"]] = str(s["id"])
                        except:
                            continue
                self._sprints_preloaded = True
                print(f"  - 已成功同步 {len(self._sprints)} 个 Sprint 信息")
            except Exception as e:
                print(f"⚠️ 预加载 Sprint 失败: {e}")

    def get_priority_id(self, priority_name):
        """根据优先级名称获取ID"""
        with self._lock:
            if not self._priorities:
                try:
                    self._priorities = {p["name"]: p["id"] for p in self._get("priority")}
                except:
                    self._priorities = {}
        return self._priorities.get(priority_name, "2")

    def get_issue_type_id(self, project_key, type_name):
        """根据问题类型名称获取ID"""
        with self._lock:
            if project_key not in self._issue_types:
                try:
                    project_info = self._get(f"project/{project_key}")
                    self._issue_types[project_key] = {it["name"]: it["id"] for it in project_info.get("issueTypes", [])}
                except:
                    self._issue_types[project_key] = {}
        it_id = self._issue_types[project_key].get(type_name)
        if not it_id and type_name == "故障":
            return next((v for k,v in self._issue_types[project_key].items() if "故障" in k or "Bug" in k), "10103")
        return it_id

    def get_component_id(self, project_key, component_name):
        """根据组件名称获取ID"""
        with self._lock:
            if project_key not in self._components:
                try:
                    self._components[project_key] = {c["name"]: c["id"] for c in self._get(f"project/{project_key}/components")}
                except:
                    self._components[project_key] = {}
        if not component_name: return None
        return self._components[project_key].get(component_name)

    def get_version_id(self, project_key, version_name):
        """根据版本名称获取ID"""
        with self._lock:
            if project_key not in self._versions:
                try:
                    self._versions[project_key] = {v["name"]: v["id"] for v in self._get(f"project/{project_key}/versions")}
                except:
                    self._versions[project_key] = {}
        if not version_name: return None
        return self._versions[project_key].get(version_name)

    def get_sprint_id(self, sprint_name):
        """根据Sprint名称查询Sprint ID"""
        with self._lock:
            if sprint_name in self._sprints:
                return self._sprints[sprint_name]

            try:
                boards = self._get("/rest/agile/1.0/board").get("values", [])
                for board in boards:
                    if board.get("type") != "scrum":
                        continue
                    path = f"/rest/agile/1.0/board/{board['id']}/sprint"
                    try:
                        sprints = self._get(path).get("values", [])
                        for sprint in sprints:
                            self._sprints[sprint["name"]] = str(sprint["id"])
                    except:
                        continue

                if sprint_name in self._sprints:
                    return self._sprints[sprint_name]

                raise Exception(f"未找到名称为 '{sprint_name}' 的Sprint")
            except requests.exceptions.RequestException as e:
                raise Exception(f"查询Sprint失败: {str(e)}")

    def add_issue_link(self, source_key, target_key, link_type="Relates"):
        """添加问题链接"""
        url = f"{self.jira_url}/rest/api/2/issueLink"
        data = {
            "type": {"name": link_type},
            "inwardIssue": {"key": target_key},
            "outwardIssue": {"key": source_key}
        }
        try:
            response = requests.post(url, auth=self.auth, headers=self.headers, json=data, verify=False)
            response.raise_for_status()
            if response.status_code in [201, 204]:
                return {"status": "success"}
            try:
                return response.json()
            except ValueError:
                return {"status": "success", "msg": "Link created but no JSON response"}
        except requests.exceptions.RequestException as e:
            error_msg = f"添加问题链接失败: {str(e)}"
            if hasattr(e, 'response') and e.response:
                error_msg += f" - 状态码: {e.response.status_code}"
                try:
                    error_msg += f" - 响应内容: {e.response.text}"
                except:
                    pass
            raise Exception(error_msg)

    def get_feishu_group_name(self, project_key):
        """获取项目对应的飞书群名称"""
        try:
            import yaml
            current_dir = Path(__file__).parent.resolve()
            cfg_path = current_dir.parent / "config" / "feishu_bot_webhooks.yaml"
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    webhooks_cfg = yaml.safe_load(f)
                project_cfg = webhooks_cfg.get("webhooks", {}).get(project_key.upper())
                if project_cfg:
                    return project_cfg.get("project_name", project_key)
        except:
            pass
        return project_key

    def send_feishu_notification(self, project_key, issue_key, summary, assignee="未指派", priority="High", component="", detail_info=None):
        """发送项目专属飞书群机器人通知卡片"""
        try:
            import yaml
            current_dir = Path(__file__).parent.resolve()
            cfg_path = current_dir.parent / "config" / "feishu_bot_webhooks.yaml"
            if not cfg_path.exists():
                print(f"⚠️ 找不到飞书 Webhook 配置文件: {cfg_path}")
                return False

            with open(cfg_path, "r", encoding="utf-8") as f:
                webhooks_cfg = yaml.safe_load(f)

            project_cfg = webhooks_cfg.get("webhooks", {}).get(project_key.upper())
            if not project_cfg or not project_cfg.get("webhook_url"):
                print(f"⚠️ 未为项目 '{project_key}' 配置飞书群 Webhook")
                return False

            webhook_url = project_cfg["webhook_url"]
            jira_link = f"{self.jira_url}/browse/{issue_key}"

            reverse_assignee_map = {
                "zhouxishun": "锡舜", "xishun": "锡舜", "longtao": "龙涛", "xiayi": "夏亿", "wuqinghua": "吴清华", "zhangxuetan": "章学坛",
                "wuhao": "吴昊", "shanyuxin": "雨欣", "wangyanjie": "王彦杰", "liuzujun": "刘祖军",
                "wangchenyu": "晨宇", "chengfangyuan": "成方圆", "zhaojieying": "赵洁颖", "liyaqi": "雅琪",
                "wangyuliong": "王玉龙", "yangbing": "杨兵"
            }
            priority_cn_map = {
                "High": "高 (P0)", "Medium": "中 (P1)", "Low": "低 (P2)", "Lowest": "建议 (P3)",
                "P0": "高 (P0)", "P1": "中 (P1)", "P2": "低 (P2)", "P3": "建议 (P3)", "P4": "建议 (P4)"
            }
            raw_assignee = str(assignee).strip()
            assignee_cn = reverse_assignee_map.get(raw_assignee.lower(), raw_assignee)
            raw_priority = str(priority).strip()
            priority_cn = priority_cn_map.get(raw_priority, raw_priority)

            elements = [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**[{issue_key}]({jira_link})** {summary}\n**经办人**: {assignee_cn} | **优先级**: {priority_cn} | **组件**: {component or '未分类'}"
                    }
                }
            ]

            if detail_info and isinstance(detail_info, dict):
                prob = detail_info.get("problem", "")
                if prob:
                    elements.append({"tag": "hr"})
                    elements.append({
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"> {prob}"
                        }
                    })

            card_payload = {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"🐛 项目 {project_key} 新建缺陷通知"
                        },
                        "template": "red"
                    },
                    "elements": elements
                }
            }

            resp = requests.post(webhook_url, json=card_payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"⚠️ 飞书群通知发送异常: {str(e)}")
            return False

    def send_batch_feishu_notification(self, project_key, issue_list):
        """发送项目专属飞书群机器人【批量聚合】通知卡片 (防刷屏)"""
        if not issue_list:
            return True

        if len(issue_list) == 1:
            iss = issue_list[0]
            return self.send_feishu_notification(
                project_key=project_key,
                issue_key=iss.get("key"),
                summary=iss.get("summary"),
                assignee=iss.get("assignee", "未指派"),
                priority=iss.get("priority", "Medium"),
                component=iss.get("component", ""),
                detail_info={"problem": iss.get("problem", "")}
            )

        try:
            import yaml
            current_dir = Path(__file__).parent.resolve()
            cfg_path = current_dir.parent / "config" / "feishu_bot_webhooks.yaml"
            if not cfg_path.exists():
                print(f"⚠️ 找不到飞书 Webhook 配置文件: {cfg_path}")
                return False

            with open(cfg_path, "r", encoding="utf-8") as f:
                webhooks_cfg = yaml.safe_load(f)

            project_cfg = webhooks_cfg.get("webhooks", {}).get(project_key.upper())
            if not project_cfg or not project_cfg.get("webhook_url"):
                print(f"⚠️ 未为项目 '{project_key}' 配置飞书群 Webhook")
                return False

            webhook_url = project_cfg["webhook_url"]
            project_name = project_cfg.get("project_name", project_key)

            print(f"📢 【防错发安全锁】确认目标飞书接收群: 项目 Key [{project_key.upper()}] ➔ 飞书群 [{project_name}]")

            # 经办人与优先级中文反向映射表
            reverse_assignee_map = {
                "zhouxishun": "锡舜", "xishun": "锡舜", "longtao": "龙涛", "xiayi": "夏亿", "wuqinghua": "吴清华", "zhangxuetan": "章学坛",
                "wuhao": "吴昊", "shanyuxin": "雨欣", "wangyanjie": "王彦杰", "liuzujun": "刘祖军",
                "wangchenyu": "晨宇", "chengfangyuan": "成方圆", "zhaojieying": "赵洁颖", "liyaqi": "雅琪",
                "wangyuliong": "王玉龙", "yangbing": "杨兵"
            }
            priority_cn_map = {
                "High": "高 (P0)", "Medium": "中 (P1)", "Low": "低 (P2)", "Lowest": "建议 (P3)",
                "P0": "高 (P0)", "P1": "中 (P1)", "P2": "低 (P2)", "P3": "建议 (P3)", "P4": "建议 (P4)"
            }

            elements = []
            for iss in issue_list:
                key = iss.get("key")
                summary = iss.get("summary")
                raw_assignee = str(iss.get("assignee", "未指派")).strip()
                assignee_cn = reverse_assignee_map.get(raw_assignee.lower(), raw_assignee)
                
                raw_priority = str(iss.get("priority", "Medium")).strip()
                priority_cn = priority_cn_map.get(raw_priority, raw_priority)
                
                comp = iss.get("component", "未分类")
                problem = iss.get("problem", "")

                jira_link = f"{self.jira_url}/browse/{key}"
                content = f"**[{key}]({jira_link})** {summary}\n**经办人**: {assignee_cn} | **优先级**: {priority_cn} | **组件**: {comp}"
                if problem:
                    content += f"\n> {problem}"

                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content
                    }
                })
                elements.append({"tag": "hr"})

            if elements and elements[-1].get("tag") == "hr":
                elements.pop()

            card_payload = {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"🐛 {project_name} 新建缺陷通知 (共 {len(issue_list)} 项)"
                        },
                        "template": "red"
                    },
                    "elements": elements
                }
            }

            resp = requests.post(webhook_url, json=card_payload, timeout=10)
            if resp.status_code == 200:
                print(f"✅ 批量飞书群通知卡片已送达! (共 {len(issue_list)} 项 Bug)")
                return True
            else:
                print(f"⚠️ 批量飞书群通知发送失败: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            print(f"⚠️ 批量飞书群通知发送异常: {str(e)}")
            return False

    def get_automation_rules(self, project_key="KIKIGO"):
        """获取 Jira Automation 自动化规则列表"""
        project_id = "GLOBAL"
        if project_key and project_key != "GLOBAL":
            proj_data = self._get(f"project/{project_key}")
            project_id = proj_data.get("id", "GLOBAL")
        
        url = f"{self.jira_url}/rest/cb-automation/latest/project/{project_id}/rule"
        res = requests.get(url, auth=self.auth, headers=self.headers, verify=False)
        res.raise_for_status()
        return res.json()

    def create_feishu_automation_rule(self, rule_name, webhook_url, jql=None, project_key="KIKIGO"):
        """通过 Jira Automation REST API 创建针对飞书群的 Webhook 通知规则"""
        import time
        if not jql:
            jql = f'issuetype IN ("故障", "bug") AND project = {project_key} AND (labels IS EMPTY OR labels != agent-created)'
        
        payload = {
            "clientKey": "com.codebarrel.tenant.global",
            "name": rule_name,
            "state": "ENABLED",
            "canOtherRuleTrigger": False,
            "notifyOnError": "FIRSTERROR",
            "trigger": {
                "id": "1",
                "component": "TRIGGER",
                "schemaVersion": 1,
                "type": "jira.issue.event.trigger:created",
                "value": {
                    "synchronous": False,
                    "eventKey": "jira:issue_created",
                    "issueEvent": "issue_created"
                },
                "children": [],
                "conditions": []
            },
            "components": [
                {
                    "id": "2",
                    "component": "CONDITION",
                    "schemaVersion": 1,
                    "type": "jira.jql.condition",
                    "value": jql,
                    "children": [],
                    "conditions": []
                },
                {
                    "id": "3",
                    "component": "ACTION",
                    "schemaVersion": 2,
                    "type": "jira.issue.outgoing.webhook",
                    "value": {
                        "url": webhook_url,
                        "headers": [
                            {
                                "id": f"_header_{int(time.time()*1000)}",
                                "name": "飞书机器人",
                                "value": {"keyOrValue": "", "secret": False}
                            }
                        ],
                        "sendIssue": False,
                        "contentType": "custom",
                        "customBody": "{\n  \"msg_type\": \"interactive\",\n  \"card\": {\n    \"config\": {\n      \"wide_screen_mode\": true\n    },\n    \"header\": {\n      \"title\": {\n        \"tag\": \"plain_text\",\n        \"content\": \"🚨 JIRA 新增 Bug 提醒\"\n      },\n      \"template\": \"red\"\n    },\n    \"elements\": [\n      {\n        \"tag\": \"markdown\",\n        \"content\": \"**问题标题**：{{issue.summary}}\\n**缺陷 Key**：[{{issue.key}}]({{issue.url}})\\n**经办人**：{{#issue.assignee}}{{issue.assignee.displayName}}{{/}}{{^issue.assignee}}*未分配*{{/}}\\n**创建人**：{{issue.reporter.displayName}}\\n**优先级**：{{issue.priority.name}}\"\n      },\n      {\n        \"tag\": \"action\",\n        \"elements\": [\n          {\n            \"tag\": \"button\",\n            \"text\": {\n              \"content\": \"🚀 点击前往 JIRA 查看\",\n              \"tag\": \"plain_text\"\n            },\n            \"url\": \"{{#issue.url}}{{issue.url}}{{/}}{{^issue.url}}https://jira.patch-x.cn/browse/{{issue.key}}{{/}}\",\n            \"type\": \"primary\"\n          }\n        ]\n      }\n    ]\n  }\n}\n",
                        "method": "POST",
                        "responseEnabled": False,
                        "usedSecretsKeys": []
                    },
                    "children": [],
                    "conditions": []
                }
            ],
            "projects": [],
            "labels": [],
            "tags": []
        }

        url = f"{self.jira_url}/rest/cb-automation/latest/project/GLOBAL/rule"
        res = requests.post(url, auth=self.auth, headers=self.headers, json=payload, verify=False)
        res.raise_for_status()
        return res.json()


# ========== 兼容别名 ==========
# 保持与旧代码 `from jira_utils import JiraUtils` 的兼容
JiraUtils = JiraClient


# ========== CLI 入口 ==========
def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    parser = argparse.ArgumentParser(description="S40 Jira 通用连接器 CLI")
    parser.add_argument("--action", required=True,
                        choices=["test_auth", "get_metadata", "create_bug", "search", "list_automation_rules", "create_automation_rule"],
                        help="执行动作")
    parser.add_argument("--project", default="KIKIGO", help="JIRA 项目 Key")
    parser.add_argument("--summary", default="", help="Bug 标题")
    parser.add_argument("--description", default="", help="Bug 描述")
    parser.add_argument("--component", default="", help="组件名称")
    parser.add_argument("--assignee", default="", help="经办人用户名")
    parser.add_argument("--priority", default="High", help="优先级")
    parser.add_argument("--jql", default="", help="JQL 查询语句")
    parser.add_argument("--rule_name", default="", help="自动化规则名称")
    parser.add_argument("--webhook_url", default="", help="飞书机器人 Webhook URL")
    args = parser.parse_args()

    client = JiraClient()

    if args.action == "test_auth":
        url = f"{client.jira_url}/rest/api/2/myself"
        resp = requests.get(url, auth=client.auth, headers=client.headers, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ 鉴权成功！用户: {data.get('displayName')} ({data.get('name')})")
        else:
            print(f"❌ 鉴权失败: {resp.status_code}")

    elif args.action == "get_metadata":
        client.prewarm([args.project])
        comps = client._components.get(args.project, {})
        vers = client._versions.get(args.project, {})
        print(f"\n📦 项目 {args.project} 元数据:")
        print(f"  组件 ({len(comps)}): {', '.join(comps.keys())}")
        print(f"  版本 ({len(vers)}): {', '.join(vers.keys())}")
        print(f"  Sprint ({len(client._sprints)}): {', '.join(client._sprints.keys())}")

    elif args.action == "create_bug":
        if not args.summary:
            print("❌ --summary 必填"); return
        result = client.create_bug(
            project_key=args.project,
            summary=args.summary,
            description=args.description,
            component=args.component or None,
            assignee=args.assignee or None,
            priority=args.priority
        )
        print(f"✅ Bug 已创建: {result['key']}")
        print(f"   链接: {client.jira_url}/browse/{result['key']}")

    elif args.action == "search":
        jql = args.jql or f'project = "{args.project}" AND issuetype = "故障" AND status = "开放"'
        resp = client._get(f"search?jql={requests.utils.quote(jql)}&maxResults=20&fields=summary,status,assignee,priority")
        issues = resp.get("issues", [])
        print(f"🔍 共找到 {resp.get('total', 0)} 条结果（显示前 {len(issues)} 条）:\n")
        for iss in issues:
            f = iss.get("fields", {})
            assignee = f.get("assignee", {})
            assignee_name = assignee.get("displayName", "未指派") if assignee else "未指派"
            print(f"  [{iss['key']}] {f.get('summary', '')} | {f.get('status', {}).get('name', '')} | {assignee_name}")

    elif args.action == "list_automation_rules":
        rules = client.get_automation_rules(args.project)
        print(f"⚙️ 项目 {args.project} 自动化规则 (共 {len(rules)} 条):")
        for r in rules:
            print(f"  - [{r.get('id')}] {r.get('name')} (状态: {r.get('state')})")
            for comp in r.get('components', []):
                if comp.get('type') == 'jira.issue.outgoing.webhook':
                    print(f"    Webhook URL: {comp.get('value', {}).get('url')}")

    elif args.action == "create_automation_rule":
        if not args.rule_name or not args.webhook_url:
            print("❌ --rule_name 和 --webhook_url 均为必填项"); return
        res = client.create_feishu_automation_rule(
            rule_name=args.rule_name,
            webhook_url=args.webhook_url,
            jql=args.jql or None,
            project_key=args.project
        )
        print(f"✅ 自动化规则已创建! ID: {res.get('id')}, 名称: {res.get('name')}")

if __name__ == "__main__":
    main()
