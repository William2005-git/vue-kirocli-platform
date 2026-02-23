import asyncio
import os
import pwd
from typing import Dict, Optional

import psutil


class ProcessManager:
    def __init__(self):
        self.processes: Dict[int, asyncio.subprocess.Process] = {}

    async def start_process(
        self, cmd: list
    ) -> asyncio.subprocess.Process:
        # 确保子进程继承正确的 HOME/USER 环境变量
        # systemd 服务环境可能缺少这些，导致 kiro-cli 找不到认证 token
        env = os.environ.copy()
        if "HOME" not in env or not env["HOME"]:
            try:
                env["HOME"] = pwd.getpwuid(os.getuid()).pw_dir
            except Exception:
                env["HOME"] = f"/home/{env.get('USER', 'ubuntu')}"
        if "USER" not in env or not env["USER"]:
            try:
                env["USER"] = pwd.getpwuid(os.getuid()).pw_name
            except Exception:
                env["USER"] = "ubuntu"
        # 确保 PATH 包含常用目录
        if "/usr/local/bin" not in env.get("PATH", ""):
            env["PATH"] = "/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        self.processes[process.pid] = process
        return process

    async def kill_process(self, pid: int):
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
        except psutil.NoSuchProcess:
            pass
        finally:
            self.processes.pop(pid, None)

    def is_alive(self, pid: int) -> bool:
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False

    def get_process(self, pid: int) -> Optional[asyncio.subprocess.Process]:
        return self.processes.get(pid)
