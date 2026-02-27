"""
设备指纹识别服务

管理用户设备记录，检测新设备登录。
"""
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.device import UserDevice

logger = logging.getLogger(__name__)

MAX_DEVICE_NAME_LEN = 50


class DeviceService:
    def process_login(
        self,
        db: Session,
        user_id: int,
        fingerprint_hash: Optional[str],
        client_ip: Optional[str],
        user_agent: Optional[str],
    ) -> bool:
        """
        处理登录时的设备指纹。
        返回 True 表示新设备，False 表示已知设备或无指纹。
        """
        if not fingerprint_hash:
            return False

        now = datetime.utcnow()
        device = db.query(UserDevice).filter_by(
            user_id=user_id, fingerprint_hash=fingerprint_hash
        ).first()

        if device:
            # 已知设备：更新最后登录信息
            device.last_seen_at = now
            device.last_seen_ip = client_ip
            device.login_count = (device.login_count or 0) + 1
            db.commit()
            return False
        else:
            # 新设备：插入记录
            device_name = self._infer_device_name(user_agent)
            db.add(UserDevice(
                user_id=user_id,
                fingerprint_hash=fingerprint_hash,
                device_name=device_name,
                first_seen_at=now,
                last_seen_at=now,
                last_seen_ip=client_ip,
                login_count=1,
            ))
            db.commit()
            return True

    def get_devices(
        self,
        db: Session,
        user_id: int,
        current_fingerprint: Optional[str] = None,
    ) -> List[dict]:
        """返回用户设备列表，标记当前设备"""
        devices = db.query(UserDevice).filter_by(user_id=user_id).order_by(
            UserDevice.last_seen_at.desc()
        ).all()
        result = []
        for d in devices:
            result.append({
                "id": d.id,
                "device_name": d.device_name,
                "fingerprint_preview": d.fingerprint_hash[:8] if d.fingerprint_hash else "",
                "fingerprint_hash": d.fingerprint_hash,
                "first_seen_at": d.first_seen_at.isoformat() if d.first_seen_at else None,
                "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
                "last_seen_ip": d.last_seen_ip,
                "login_count": d.login_count,
                "is_current": bool(current_fingerprint and d.fingerprint_hash == current_fingerprint),
            })
        return result

    def update_device_name(
        self,
        db: Session,
        user_id: int,
        device_id: int,
        name: str,
    ) -> UserDevice:
        """更新设备名称，校验归属和长度"""
        device = db.query(UserDevice).filter_by(id=device_id, user_id=user_id).first()
        if not device:
            raise ValueError("Device not found")
        name = name.strip()
        if len(name) > MAX_DEVICE_NAME_LEN:
            raise ValueError(f"Device name must be at most {MAX_DEVICE_NAME_LEN} characters")
        device.device_name = name
        db.commit()
        db.refresh(device)
        return device

    def delete_device(
        self,
        db: Session,
        user_id: int,
        device_id: int,
        current_fingerprint: Optional[str] = None,
    ) -> None:
        """删除设备，不允许删除当前设备"""
        device = db.query(UserDevice).filter_by(id=device_id, user_id=user_id).first()
        if not device:
            raise ValueError("Device not found")
        if current_fingerprint and device.fingerprint_hash == current_fingerprint:
            raise PermissionError("Cannot delete the current device")
        db.delete(device)
        db.commit()

    @staticmethod
    def _infer_device_name(user_agent: Optional[str]) -> str:
        """从 User-Agent 简单推断设备名称"""
        if not user_agent:
            return "Unknown Device"
        ua = user_agent.lower()
        if "iphone" in ua:
            return "iPhone"
        if "ipad" in ua:
            return "iPad"
        if "android" in ua:
            return "Android Device"
        if "macintosh" in ua or "mac os" in ua:
            return "Mac"
        if "windows" in ua:
            return "Windows PC"
        if "linux" in ua:
            return "Linux PC"
        return "Unknown Device"


device_service = DeviceService()
