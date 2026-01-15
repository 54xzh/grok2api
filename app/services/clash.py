"""Clash Meta 管理服务 - 订阅更新、节点管理"""

import asyncio
import base64
import os
import re
import signal
import subprocess
import sys
import httpx
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlsplit

from app.core.config import setting
from app.core.logger import logger


# 常量
CLASH_DIR = Path("/app/data/clash")
CLASH_CONFIG_PATH = CLASH_DIR / "config.yaml"
CLASH_API = "http://127.0.0.1:9090"


class ClashManager:
    """Clash Meta 管理器"""
    
    _instance = None
    _update_task = None
    _last_update = None
    _base64_charset_re = re.compile(r"^[A-Za-z0-9+/=_-]+$")
    
    @classmethod
    def get_instance(cls) -> "ClashManager":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = ClashManager()
        return cls._instance
    
    def __init__(self):
        self._proxies_cache: List[Dict] = []
        self._current_proxy: str = ""
        self._process: Optional[subprocess.Popen] = None
    
    async def is_running(self) -> bool:
        """检查 Clash 是否运行中"""
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(f"{CLASH_API}/version", headers=self._get_clash_api_headers())
                return resp.status_code == 200
        except:
            return False
    
    async def start(self) -> bool:
        """启动 Clash 进程"""
        if await self.is_running():
            logger.info("[Clash] 已在运行中")
            return True
        
        try:
            # 更新订阅配置
            await self.update_subscription()
            
            # 启动 Clash
            log_path = self._get_log_path()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as log_file:
                self._process = subprocess.Popen(
                    ["clash", "-d", str(CLASH_DIR)],
                    stdout=log_file,
                    stderr=subprocess.STDOUT
                )
            self._write_pid_file(self._process.pid)
            
            # 等待启动
            for _ in range(10):
                await asyncio.sleep(0.5)
                if await self.is_running():
                    logger.info("[Clash] 启动成功")
                    
                    # 选择节点
                    node = setting.grok_config.get("clash_proxy_node", "")
                    if node:
                        await self.select_proxy(node)
                    
                    return True
            
            logger.error("[Clash] 启动超时")
            return False
            
        except Exception as e:
            logger.error(f"[Clash] 启动失败: {e}")
            return False
    
    async def stop(self) -> bool:
        """停止 Clash 进程"""
        try:
            stopped = self._terminate_by_pid_file()
            if not stopped:
                stopped = self._terminate_by_process_handle()
            if not stopped:
                self._terminate_by_command()

            # 等待进程退出（避免 UI 状态不同步）
            for _ in range(10):
                await asyncio.sleep(0.3)
                if not await self.is_running():
                    break

            if not await self.is_running():
                self._clear_pid_file()
                logger.info("[Clash] 已停止")
                return True

            # 二次兜底：强制 kill（部分环境 SIGTERM 不生效）
            if self._force_kill_by_pid_file():
                for _ in range(10):
                    await asyncio.sleep(0.3)
                    if not await self.is_running():
                        break

            if not await self.is_running():
                self._clear_pid_file()
                logger.info("[Clash] 已停止")
                return True

            logger.warning("[Clash] 停止失败：进程仍在运行")
            return False
        except Exception as e:
            logger.error(f"[Clash] 停止失败: {e}")
            return False
    
    async def update_subscription(self) -> Dict[str, Any]:
        """更新订阅配置"""
        sub_url = setting.grok_config.get("clash_subscription_url", "")
        if not sub_url:
            return {"success": False, "error": "未配置订阅地址"}
        
        try:
            logger.info(f"[Clash] 正在更新订阅...")
            
            # 添加 User-Agent 头，有些订阅服务需要
            headers = {
                "User-Agent": "ClashMetaForAndroid/2.8.9.Meta",
                "Accept": "*/*"
            }
            
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(sub_url, headers=headers)
                resp.raise_for_status()
                content = (resp.text or "").strip()
            
            logger.debug(f"[Clash] 订阅内容长度: {len(content)}")
            
            config: Optional[Dict[str, Any]] = None
            uri_proxies: List[Dict[str, Any]] = []
            
            config = self._parse_clash_yaml(content)
            if config is not None:
                logger.info("[Clash] 检测到 Clash YAML 格式订阅")
            
            # 尝试 base64 解码（可能是 Clash YAML 或 URI 列表订阅）
            if config is None:
                decoded = self._try_base64_decode(content)
                if decoded:
                    config = self._parse_clash_yaml(decoded)
                    if config is not None:
                        logger.info("[Clash] 检测到 Base64 编码的 Clash YAML 订阅")
                    else:
                        uri_proxies = self._parse_subscription_uris(decoded)
                        if uri_proxies:
                            logger.info(f"[Clash] 检测到 Base64 编码的 URI 订阅，共 {len(uri_proxies)} 个可解析节点")

            # 非 base64 但可能是 URI 列表
            if config is None and not uri_proxies:
                uri_proxies = self._parse_subscription_uris(content)
            
            # 如果还是没有 proxies，可能是其他格式的订阅链接
            if config is None:
                # 尝试添加 clash 参数重新获取
                if "?" in sub_url:
                    clash_url = sub_url + "&flag=clash"
                else:
                    clash_url = sub_url + "?flag=clash"
                
                logger.info("[Clash] 尝试使用 flag=clash 参数获取...")
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    resp = await client.get(clash_url, headers=headers)
                    if resp.status_code == 200:
                        config = self._parse_clash_yaml(resp.text or "")
                        if config is None:
                            decoded = self._try_base64_decode(resp.text or "")
                            if decoded:
                                config = self._parse_clash_yaml(decoded)
            
            # 最终检查
            if config is None or not isinstance(config, dict):
                logger.error(f"[Clash] 无法解析订阅内容，前100字符: {content[:100]}")
                return {"success": False, "error": "订阅内容格式不正确，请确保是 Clash 格式订阅"}
            
            if "proxies" not in config or not isinstance(config.get("proxies"), list) or not config["proxies"]:
                logger.error(f"[Clash] 订阅中没有 proxies 字段，配置keys: {list(config.keys())}")
                return {"success": False, "error": "订阅中没有代理节点，请检查订阅是否为 Clash 格式"}

            # 合并 URI 订阅中解析到的节点（主要用于补齐 Clash 转换中丢失的协议，例如 hysteria2）
            if uri_proxies:
                existing_names = {
                    p.get("name") for p in config.get("proxies", [])
                    if isinstance(p, dict) and p.get("name")
                }
                for proxy in uri_proxies:
                    name = proxy.get("name")
                    if name in existing_names:
                        proxy["name"] = self._dedupe_name(name, existing_names)
                    config["proxies"].append(proxy)
                    existing_names.add(proxy.get("name"))

            # 添加/覆盖必要配置
            config["mixed-port"] = 7890
            config["allow-lan"] = False
            config["external-controller"] = "127.0.0.1:9090"
            config["mode"] = "global"  # 全局模式
            self._ensure_global_group(config)
            if not isinstance(config.get("rules"), list) or not config.get("rules"):
                config["rules"] = ["MATCH,GLOBAL"]
            
            # 保存配置（支持本地开发和 Docker 环境）
            config_path = self._get_config_path()
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
            
            self._last_update = datetime.now()
            self._proxies_cache = []  # 清除缓存
            
            # 如果 Clash 正在运行，重载配置
            if await self.is_running():
                await self._reload_config()
            
            logger.info(f"[Clash] 订阅更新成功，共 {len(config.get('proxies', []))} 个节点")
            return {"success": True, "proxy_count": len(config.get("proxies", []))}
            
        except httpx.HTTPError as e:
            logger.error(f"[Clash] 下载订阅失败: {e}")
            return {"success": False, "error": f"下载失败: {str(e)}"}
        except Exception as e:
            logger.error(f"[Clash] 更新订阅异常: {e}")
            return {"success": False, "error": str(e)}
    
    async def _reload_config(self) -> bool:
        """重载 Clash 配置"""
        try:
            config_path = self._get_config_path()
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.put(
                    f"{CLASH_API}/configs",
                    json={"path": str(config_path)},
                    headers=self._get_clash_api_headers()
                )
                return resp.status_code == 204
        except:
            return False
    
    async def get_proxies(self) -> List[Dict]:
        """获取所有代理节点"""
        proxies = []
        
        # 首先尝试直接从配置文件获取（最可靠的方式）
        config_path = self._get_config_path()
        logger.debug(f"[Clash] 尝试读取配置: {config_path}, 存在: {config_path.exists()}")
        
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                
                if config and isinstance(config, dict) and "proxies" in config:
                    raw_proxies = config.get("proxies", [])
                    if isinstance(raw_proxies, list):
                        for p in raw_proxies:
                            if isinstance(p, dict) and p.get("name"):
                                proxies.append({
                                    "name": p.get("name"),
                                    "type": p.get("type", "Unknown"),
                                    "now": ""
                                })
                        logger.info(f"[Clash] 从配置文件读取到 {len(proxies)} 个节点")
            except Exception as e:
                logger.error(f"[Clash] 读取配置文件失败: {e}")
        
        # 如果配置文件没有读到节点，返回缓存或空列表
        if proxies:
            self._proxies_cache = proxies
        
        return self._proxies_cache if self._proxies_cache else []
    
    def _get_config_path(self) -> Path:
        """获取配置文件路径，支持本地开发和 Docker 环境"""
        # Docker 环境
        if CLASH_CONFIG_PATH.parent.exists():
            return CLASH_CONFIG_PATH
        # 本地开发环境
        local_path = Path(__file__).parents[2] / "data" / "clash" / "config.yaml"
        return local_path

    def _get_pid_path(self) -> Path:
        """获取 PID 文件路径"""
        return self._get_config_path().parent / "clash.pid"

    def _get_log_path(self) -> Path:
        """获取日志文件路径"""
        docker_logs = Path("/app/logs")
        if docker_logs.exists():
            return docker_logs / "clash.log"
        return Path(__file__).parents[2] / "logs" / "clash.log"

    def _write_pid_file(self, pid: int) -> None:
        """写入 PID 文件（便于 stop 精准结束进程）"""
        try:
            pid_path = self._get_pid_path()
            pid_path.parent.mkdir(parents=True, exist_ok=True)
            pid_path.write_text(str(pid), encoding="utf-8")
        except Exception as e:
            logger.debug(f"[Clash] 写入PID文件失败: {e}")

    def _clear_pid_file(self) -> None:
        """清理 PID 文件"""
        try:
            pid_path = self._get_pid_path()
            if pid_path.exists():
                pid_path.unlink()
        except Exception:
            pass

    def _terminate_by_pid_file(self) -> bool:
        """优先通过 PID 文件结束进程"""
        pid_path = self._get_pid_path()
        if not pid_path.exists():
            return False

        pid = self._read_pid_file()
        if pid is None:
            return False

        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False)
                return True

            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            return False

    def _force_kill_by_pid_file(self) -> bool:
        """通过 PID 文件强制结束进程（SIGKILL）"""
        if sys.platform == "win32":
            return False

        pid = self._read_pid_file()
        if pid is None:
            return False

        try:
            os.kill(pid, signal.SIGKILL)
            return True
        except Exception:
            return False

    def _read_pid_file(self) -> Optional[int]:
        """读取 PID 文件"""
        pid_path = self._get_pid_path()
        if not pid_path.exists():
            return None

        try:
            return int(pid_path.read_text(encoding="utf-8").strip())
        except Exception:
            return None

    def _terminate_by_process_handle(self) -> bool:
        """如果本进程启动了 Clash，尝试通过句柄结束"""
        if not self._process:
            return False

        try:
            self._process.terminate()
            return True
        except Exception:
            return False

    def _terminate_by_command(self) -> None:
        """兜底：按命令名结束"""
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "clash.exe"], check=False)
            else:
                subprocess.run(["pkill", "-f", "clash"], check=False)
        except Exception:
            pass

    def _parse_clash_yaml(self, content: str) -> Optional[Dict[str, Any]]:
        """解析 Clash YAML（必须包含 proxies 列表）"""
        try:
            data = yaml.safe_load(content)
        except Exception:
            return None

        if isinstance(data, dict) and isinstance(data.get("proxies"), list):
            return data
        return None

    def _try_base64_decode(self, content: str) -> Optional[str]:
        """尝试对订阅内容进行 base64 解码"""
        cleaned = "".join((content or "").strip().split())
        if not cleaned:
            return None

        if not self._base64_charset_re.fullmatch(cleaned):
            return None

        padded = cleaned + ("=" * (-len(cleaned) % 4))
        for decoder in (base64.b64decode, base64.urlsafe_b64decode):
            try:
                decoded_bytes = decoder(padded)
                return decoded_bytes.decode("utf-8")
            except Exception:
                continue
        return None

    def _parse_subscription_uris(self, content: str) -> List[Dict[str, Any]]:
        """解析 URI 订阅（当前重点补齐 hysteria2）"""
        proxies: List[Dict[str, Any]] = []
        for raw_line in (content or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            proxy = None
            if line.startswith(("hysteria2://", "hy2://")):
                proxy = self._parse_hysteria2_uri(line)

            if proxy:
                proxies.append(proxy)
        return proxies

    def _parse_hysteria2_uri(self, uri: str) -> Optional[Dict[str, Any]]:
        """解析 hysteria2://... 链接为 Clash hysteria2 节点配置"""
        try:
            u = urlsplit(uri)
            if u.scheme not in {"hysteria2", "hy2"}:
                return None

            server = u.hostname
            port = u.port
            if not server or not port:
                return None

            q = parse_qs(u.query)

            password = ""
            if u.username and u.password:
                password = f"{unquote(u.username)}:{unquote(u.password)}"
            elif u.username:
                password = unquote(u.username)
            if not password:
                password = self._first_query_value(q, ["password", "auth", "passwd"])
            if not password:
                return None

            name = unquote(u.fragment) if u.fragment else f"hysteria2-{server}:{port}"

            proxy: Dict[str, Any] = {
                "name": name,
                "type": "hysteria2",
                "server": server,
                "port": port,
                "password": password,
            }

            ports = self._first_query_value(q, ["ports"])
            if ports:
                proxy["ports"] = ports

            up = self._first_query_value(q, ["up", "upmbps"])
            if up:
                proxy["up"] = self._format_rate(up)

            down = self._first_query_value(q, ["down", "downmbps"])
            if down:
                proxy["down"] = self._format_rate(down)

            obfs = self._first_query_value(q, ["obfs"])
            if obfs:
                proxy["obfs"] = obfs

            obfs_password = self._first_query_value(q, ["obfs-password", "obfs_password", "obfsPassword"])
            if obfs_password:
                proxy["obfs-password"] = obfs_password

            sni = self._first_query_value(q, ["sni", "peer"])
            if sni:
                proxy["sni"] = sni

            insecure = self._first_query_value(q, ["insecure", "allowInsecure", "allow_insecure"])
            if self._is_truthy(insecure):
                proxy["skip-cert-verify"] = True

            fingerprint = self._first_query_value(q, ["fingerprint"])
            if fingerprint:
                proxy["fingerprint"] = fingerprint

            alpn_list = self._parse_alpn(q.get("alpn", []))
            if alpn_list:
                proxy["alpn"] = alpn_list

            return proxy
        except Exception as e:
            logger.debug(f"[Clash] 解析 hysteria2 URI 失败: {e}")
            return None

    def _ensure_global_group(self, config: Dict[str, Any]) -> None:
        """确保存在可切换的 GLOBAL 选择组（避免切换节点 404）"""
        proxy_names = [
            p.get("name")
            for p in config.get("proxies", [])
            if isinstance(p, dict) and p.get("name")
        ]
        global_group = {"name": "GLOBAL", "type": "select", "proxies": proxy_names + ["DIRECT"]}

        groups = config.get("proxy-groups")
        if not isinstance(groups, list):
            config["proxy-groups"] = [global_group]
            return

        for g in groups:
            if isinstance(g, dict) and g.get("name") == "GLOBAL":
                g["type"] = "select"
                g["proxies"] = global_group["proxies"]
                return

        groups.insert(0, global_group)

    def _dedupe_name(self, name: str, existing: set) -> str:
        """生成不冲突的节点名"""
        base = name or "Unnamed"
        for i in range(2, 1000):
            candidate = f"{base}-{i}"
            if candidate not in existing:
                return candidate
        return f"{base}-{int(datetime.now().timestamp())}"

    def _first_query_value(self, q: Dict[str, List[str]], keys: List[str]) -> str:
        """从 query dict 中按优先级取第一个值"""
        for k in keys:
            v = q.get(k)
            if v and v[0] is not None:
                return str(v[0]).strip()
        return ""

    def _is_truthy(self, value: str) -> bool:
        """解析类似 1/true/yes 的布尔值"""
        if value is None:
            return False
        v = str(value).strip().lower()
        return v in {"1", "true", "yes", "y", "on"}

    def _format_rate(self, value: str) -> str:
        """将 up/down 速率标准化为带单位字符串"""
        v = str(value).strip()
        if not v:
            return ""
        if any(ch.isalpha() for ch in v):
            return v
        return f"{v} Mbps"

    def _parse_alpn(self, values: List[str]) -> List[str]:
        """解析 alpn 参数，支持逗号分隔或多值"""
        alpn: List[str] = []
        for raw in values or []:
            for part in str(raw).split(","):
                p = part.strip()
                if p:
                    alpn.append(p)
        return alpn
    
    async def select_proxy(self, name: str) -> Dict[str, Any]:
        """选择代理节点"""
        if not await self.is_running():
            return {"success": False, "error": "Clash 未运行"}
        
        try:
            headers = self._get_clash_api_headers()
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{CLASH_API}/proxies", headers=headers)

                selector_groups: List[str] = []
                last_error = ""

                if resp.status_code == 200:
                    data = resp.json() or {}
                    proxies = data.get("proxies", {}) or {}

                    # 1) 优先：包含目标节点的代理组
                    preferred: List[str] = []
                    fallback: List[str] = []
                    for group_name, info in proxies.items():
                        if not isinstance(info, dict):
                            continue
                        all_list = info.get("all")
                        if isinstance(all_list, list) and name in all_list:
                            if info.get("type") == "Selector":
                                preferred.append(group_name)
                            else:
                                fallback.append(group_name)
                    selector_groups.extend(preferred + fallback)

                    # 2) 兜底：尝试所有 Selector 组
                    for group_name, info in proxies.items():
                        if isinstance(info, dict) and info.get("type") == "Selector":
                            if group_name not in selector_groups:
                                selector_groups.append(group_name)

                # 3) 最后兜底：常见组名
                for group in ["GLOBAL", "Proxy", "节点选择", "🚀 节点选择", "✈️ 节点选择", "🔰 节点选择"]:
                    if group not in selector_groups:
                        selector_groups.append(group)

                from urllib.parse import quote

                for group in selector_groups:
                    try:
                        encoded_group = quote(group, safe="")
                        resp = await client.put(
                            f"{CLASH_API}/proxies/{encoded_group}",
                            json={"name": name},
                            headers=headers
                        )

                        if resp.status_code == 204:
                            self._current_proxy = name
                            logger.info(f"[Clash] 成功切换节点 (via {group}): {name}")
                            return {"success": True, "node": name}

                        if resp.status_code in {400, 404}:
                            last_error = f"切换失败({resp.status_code}): {group}"
                            continue

                        last_error = f"切换失败: {resp.status_code}"
                    except Exception as e:
                        last_error = str(e)
                        continue

                return {"success": False, "error": last_error or "未找到可用的代理组"}
                    
        except Exception as e:
            logger.error(f"[Clash] 切换节点失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_current_proxy(self) -> Optional[str]:
        """获取当前选中的节点"""
        if not await self.is_running():
            return self._current_proxy

        try:
            headers = self._get_clash_api_headers()
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{CLASH_API}/proxies", headers=headers)
                if resp.status_code != 200:
                    return self._current_proxy

                proxies = (resp.json() or {}).get("proxies", {}) or {}

                global_info = proxies.get("GLOBAL")
                if isinstance(global_info, dict) and global_info.get("now"):
                    self._current_proxy = global_info.get("now", "")
                    return self._current_proxy

                for _, info in proxies.items():
                    if isinstance(info, dict) and info.get("type") == "Selector" and info.get("now"):
                        self._current_proxy = info.get("now", "")
                        return self._current_proxy
        except Exception:
            pass

        return self._current_proxy

    def _get_clash_api_headers(self) -> Dict[str, str]:
        """读取配置中的 secret 并生成 Clash API 认证头"""
        try:
            config_path = self._get_config_path()
            if not config_path.exists():
                return {}

            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            if not isinstance(cfg, dict):
                return {}

            secret = cfg.get("secret")
            if isinstance(secret, str) and secret.strip():
                return {"Authorization": f"Bearer {secret.strip()}"}
        except Exception:
            return {}

        return {}
    
    async def get_status(self) -> Dict[str, Any]:
        """获取 Clash 状态"""
        running = await self.is_running()
        current = await self.get_current_proxy() if running else ""
        config_path = self._get_config_path()
        
        return {
            "running": running,
            "current_proxy": current,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "config_exists": config_path.exists()
        }
    
    async def start_auto_update(self):
        """启动自动更新任务"""
        if self._update_task and not self._update_task.done():
            return
        
        self._update_task = asyncio.create_task(self._auto_update_loop())
    
    async def _auto_update_loop(self):
        """自动更新循环"""
        while True:
            try:
                interval = setting.grok_config.get("clash_update_interval", 86400)
                await asyncio.sleep(interval)
                
                if setting.grok_config.get("clash_enabled", False):
                    logger.info("[Clash] 执行定时订阅更新...")
                    await self.update_subscription()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Clash] 自动更新异常: {e}")
                await asyncio.sleep(60)


# 全局实例
clash_manager = ClashManager.get_instance()
