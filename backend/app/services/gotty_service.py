import asyncio
import re
from dataclasses import dataclass
from typing import Optional

from app.config import settings
from app.core.exceptions import GottyStartupError
from app.utils.port_manager import PortManager
from app.utils.process_manager import ProcessManager


@dataclass
class GottySession:
    pid: int
    port: int
    token: str
    url: str


class GottyService:
    def __init__(self):
        self.port_manager = PortManager(
            settings.GOTTY_PRIMARY_PORT,
            settings.GOTTY_PORT_START,
            settings.GOTTY_PORT_END,
        )
        self.process_manager = ProcessManager()

    async def start_gotty(self, user_id: int) -> GottySession:
        port = await self.port_manager.allocate_port()
        try:
            cmd = self._build_command(port)
            process = await self.process_manager.start_process(cmd)
            token = await asyncio.wait_for(
                self._extract_random_token(process), timeout=15.0
            )
            url = self._build_gotty_url(port, token)
            return GottySession(pid=process.pid, port=port, token=token, url=url)
        except asyncio.TimeoutError:
            await self.port_manager.release_port(port)
            raise GottyStartupError("Gotty startup timed out")
        except Exception as e:
            await self.port_manager.release_port(port)
            raise GottyStartupError(str(e))

    async def stop_gotty(self, pid: int, port: Optional[int] = None):
        await self.process_manager.kill_process(pid)
        if port is not None:
            await self.port_manager.release_port(port)

    async def check_process_alive(self, pid: int) -> bool:
        return self.process_manager.is_alive(pid)

    def _build_command(self, port: int) -> list:
        cmd = [
            settings.GOTTY_PATH,
            "--address", "127.0.0.1",
            "--port", str(port),
            "--permit-write",
            "--reconnect",
            "--random-url",
            "--random-url-length", "16",
            "--ws-origin", ".*",
        ]
        if settings.GOTTY_CERT_PATH and settings.GOTTY_KEY_PATH:
            cmd += [
                "--tls",
                "--tls-crt", settings.GOTTY_CERT_PATH,
                "--tls-key", settings.GOTTY_KEY_PATH,
            ]
        cmd.append(settings.KIRO_CLI_PATH)
        return cmd

    async def _extract_random_token(self, process) -> str:
        pattern = re.compile(
            r"HTTP server is listening at: https?://[^/]+/([a-zA-Z0-9]+)/"
        )
        while True:
            line = await process.stdout.readline()
            if not line:
                raise GottyStartupError("Failed to extract random URL token from Gotty output")
            line_str = line.decode("utf-8", errors="replace").strip()
            match = pattern.search(line_str)
            if match:
                return match.group(1)

    def _build_gotty_url(self, port: int, token: str) -> str:
        host = settings.GOTTY_REMOTE_HOST or "localhost"
        scheme = "https" if (settings.GOTTY_CERT_PATH and settings.GOTTY_KEY_PATH) else "http"
        return f"{scheme}://{host}:{port}/{token}/"


gotty_service = GottyService()
