"""Clash Meta 管理服务 - 订阅更新、节点管理"""

import asyncio
import os
import subprocess
import httpx
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

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
    
    @classmethod
    def get_instance(cls) -> "ClashManager":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = ClashManager()
        return cls._instance
    
    def __init__(self):
        self._proxies_cache: List[Dict] = []
        self._current_proxy: str = ""
    
    async def is_running(self) -> bool:
        """检查 Clash 是否运行中"""
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(f"{CLASH_API}/version")
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
            subprocess.Popen(
                ["clash", "-d", str(CLASH_DIR)],
                stdout=open("/app/logs/clash.log", "a"),
                stderr=subprocess.STDOUT
            )
            
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
            subprocess.run(["pkill", "-f", "clash"], check=False)
            logger.info("[Clash] 已停止")
            return True
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
                content = resp.text
            
            logger.debug(f"[Clash] 订阅内容长度: {len(content)}")
            
            config = None
            
            # 尝试直接解析为 YAML
            try:
                config = yaml.safe_load(content)
                if isinstance(config, dict) and "proxies" in config:
                    logger.info("[Clash] 检测到 Clash YAML 格式订阅")
            except:
                config = None
            
            # 如果不是 YAML，尝试 base64 解码
            if config is None or not isinstance(config, dict) or "proxies" not in config:
                try:
                    import base64
                    # 尝试 base64 解码
                    decoded = base64.b64decode(content).decode('utf-8')
                    config = yaml.safe_load(decoded)
                    if isinstance(config, dict) and "proxies" in config:
                        logger.info("[Clash] 检测到 Base64 编码的 Clash 订阅")
                except:
                    pass
            
            # 如果还是没有 proxies，可能是其他格式的订阅链接
            if config is None or not isinstance(config, dict):
                # 尝试添加 clash 参数重新获取
                if "?" in sub_url:
                    clash_url = sub_url + "&flag=clash"
                else:
                    clash_url = sub_url + "?flag=clash"
                
                logger.info("[Clash] 尝试使用 flag=clash 参数获取...")
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    resp = await client.get(clash_url, headers=headers)
                    if resp.status_code == 200:
                        try:
                            config = yaml.safe_load(resp.text)
                        except:
                            pass
            
            # 最终检查
            if config is None or not isinstance(config, dict):
                logger.error(f"[Clash] 无法解析订阅内容，前100字符: {content[:100]}")
                return {"success": False, "error": "订阅内容格式不正确，请确保是 Clash 格式订阅"}
            
            if "proxies" not in config or not config["proxies"]:
                logger.error(f"[Clash] 订阅中没有 proxies 字段，配置keys: {list(config.keys())}")
                return {"success": False, "error": "订阅中没有代理节点，请检查订阅是否为 Clash 格式"}
            
            # 添加/覆盖必要配置
            config["mixed-port"] = 7890
            config["allow-lan"] = False
            config["external-controller"] = "127.0.0.1:9090"
            config["mode"] = "global"  # 全局模式
            
            # 保存配置（支持本地开发和 Docker 环境）
            config_path = self._get_config_path()
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, allow_unicode=True)
            
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
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.put(
                    f"{CLASH_API}/configs",
                    json={"path": str(CLASH_CONFIG_PATH)}
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
    
    async def select_proxy(self, name: str) -> Dict[str, Any]:
        """选择代理节点"""
        if not await self.is_running():
            return {"success": False, "error": "Clash 未运行"}
        
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                # 尝试多个常见的代理组名称
                selector_groups = ["GLOBAL", "Proxy", "🚀 节点选择", "✈️ 节点选择", "节点选择", "🔰 节点选择"]
                
                # 首先获取所有代理组
                resp = await client.get(f"{CLASH_API}/proxies")
                if resp.status_code == 200:
                    data = resp.json()
                    proxies = data.get("proxies", {})
                    # 查找 Selector 类型的代理组
                    for proxy_name, info in proxies.items():
                        if info.get("type") == "Selector":
                            selector_groups.insert(0, proxy_name)
                
                # 尝试切换
                last_error = ""
                for group in selector_groups:
                    try:
                        # URL 编码代理组名称（处理 emoji 等特殊字符）
                        from urllib.parse import quote
                        encoded_group = quote(group, safe='')
                        resp = await client.put(
                            f"{CLASH_API}/proxies/{encoded_group}",
                            json={"name": name}
                        )
                        
                        if resp.status_code == 204:
                            self._current_proxy = name
                            logger.info(f"[Clash] 成功切换节点 (via {group}): {name}")
                            return {"success": True, "node": name}
                        elif resp.status_code == 400:
                            # 400 表示这个节点不在这个组中，尝试下一个组
                            last_error = f"节点 {name} 不在代理组 {group} 中"
                            continue
                        else:
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
        if await self.is_running():
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(f"{CLASH_API}/proxies/GLOBAL")
                    if resp.status_code == 200:
                        data = resp.json()
                        self._current_proxy = data.get("now", "")
                        return self._current_proxy
            except:
                pass
        return self._current_proxy
    
    async def get_status(self) -> Dict[str, Any]:
        """获取 Clash 状态"""
        running = await self.is_running()
        current = await self.get_current_proxy() if running else ""
        
        return {
            "running": running,
            "current_proxy": current,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "config_exists": CLASH_CONFIG_PATH.exists()
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
