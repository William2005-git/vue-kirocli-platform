"""
IP 白名单服务

负责管理 IP 白名单配置，生成 Nginx geo 模块配置文件，并触发 Nginx 重载。
"""
import ipaddress
import logging
import subprocess
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.ip_whitelist import IPWhitelist
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

NGINX_WHITELIST_CONF = "/etc/nginx/conf.d/ip_whitelist.conf"


class IPWhitelistService:

    def get_whitelist(self, db: Session) -> dict:
        """返回启用状态和条目列表"""
        enabled_cfg = db.query(SystemConfig).filter_by(key="ip_whitelist_enabled").first()
        enabled = enabled_cfg.value == "true" if enabled_cfg else False

        entries = db.query(IPWhitelist).order_by(IPWhitelist.id).all()
        return {
            "enabled": enabled,
            "entries": [
                {"id": e.id, "cidr": e.cidr, "note": e.note or ""}
                for e in entries
            ],
        }

    def update_whitelist(
        self,
        db: Session,
        enabled: bool,
        entries: List[dict],
        requester_ip: Optional[str],
    ) -> None:
        """
        全量更新白名单：
        1. 若 enabled=True，校验 requester_ip 在新条目中（防自锁）
        2. 全量替换数据库条目
        3. 更新 system_config 中的启用开关
        4. 重新生成 Nginx 配置并 reload
        """
        if enabled and requester_ip:
            if not self._ip_in_entries(requester_ip, entries):
                raise ValueError(
                    f"当前 IP {requester_ip} 不在新白名单中，保存后将无法访问平台。"
                    f"请先将 {requester_ip} 加入白名单后再保存。"
                )

        # 全量替换数据库条目
        db.query(IPWhitelist).delete()
        for entry in entries:
            cidr = entry.get("cidr", "").strip()
            if cidr:
                db.add(IPWhitelist(
                    cidr=cidr,
                    note=entry.get("note", ""),
                ))

        # 更新启用开关
        cfg = db.query(SystemConfig).filter_by(key="ip_whitelist_enabled").first()
        if cfg:
            cfg.value = "true" if enabled else "false"
            cfg.updated_at = datetime.utcnow()
        else:
            db.add(SystemConfig(key="ip_whitelist_enabled", value="true" if enabled else "false"))

        db.commit()

        # 生成 Nginx 配置并 reload
        conf_content = self._generate_nginx_conf(enabled, entries)
        self._write_conf(conf_content)
        self._reload_nginx()

    def init_nginx_conf(self, db: Session) -> None:
        """应用启动时初始化 Nginx 配置文件（若不存在则生成默认配置）"""
        import os
        if not os.path.exists(NGINX_WHITELIST_CONF):
            data = self.get_whitelist(db)
            conf = self._generate_nginx_conf(data["enabled"], data["entries"])
            self._write_conf(conf)
            logger.info("Initialized Nginx IP whitelist config.")

    def _ip_in_entries(self, ip: str, entries: List[dict]) -> bool:
        """检查 IP 是否在 CIDR 条目列表中"""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        for entry in entries:
            cidr = entry.get("cidr", "").strip()
            if not cidr:
                continue
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                if addr in network:
                    return True
            except ValueError:
                continue
        return False

    def _generate_nginx_conf(self, enabled: bool, entries: List[dict]) -> str:
        """
        生成 Nginx geo 模块配置。
        禁用时 default=1（放行所有），启用时 default=0（仅白名单通过）。
        127.0.0.1 和 ::1 始终为 1。
        """
        default_val = "1" if not enabled else "0"
        lines = [
            "# 由 KiroCLI Platform 自动生成，请勿手动修改",
            f"# 更新时间: {datetime.utcnow().isoformat()}Z",
            "geo $ip_allowed {",
            f"    default   {default_val};",
            "    127.0.0.1 1;",
            "    ::1       1;",
        ]
        if enabled:
            for entry in entries:
                cidr = entry.get("cidr", "").strip()
                note = entry.get("note", "").strip()
                if cidr:
                    comment = f"  # {note}" if note else ""
                    lines.append(f"    {cidr} 1;{comment}")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _write_conf(self, content: str) -> None:
        try:
            with open(NGINX_WHITELIST_CONF, "w") as f:
                f.write(content)
        except PermissionError:
            logger.error(f"Permission denied writing {NGINX_WHITELIST_CONF}")
            raise

    def _reload_nginx(self) -> None:
        try:
            result = subprocess.run(
                ["/usr/bin/sudo", "/usr/sbin/nginx", "-s", "reload"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.error(f"nginx reload failed: {result.stderr}")
                raise RuntimeError(f"nginx reload failed: {result.stderr}")
            logger.info("Nginx reloaded successfully.")
        except subprocess.TimeoutExpired:
            logger.error("nginx reload timed out")
            raise RuntimeError("nginx reload timed out")
