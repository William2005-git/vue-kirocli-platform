import asyncio
import socket

from app.core.exceptions import NoAvailablePortError


class PortManager:
    def __init__(self, primary_port: int, start_port: int, end_port: int):
        self.primary_port = primary_port
        self.start_port = start_port
        self.end_port = end_port
        self.allocated_ports: set = set()
        self._lock = asyncio.Lock()

    async def allocate_port(self) -> int:
        async with self._lock:
            if self.primary_port not in self.allocated_ports and self._is_port_available(
                self.primary_port
            ):
                self.allocated_ports.add(self.primary_port)
                return self.primary_port

            for port in range(self.start_port, self.end_port + 1):
                if port not in self.allocated_ports and self._is_port_available(port):
                    self.allocated_ports.add(port)
                    return port

            raise NoAvailablePortError()

    async def release_port(self, port: int):
        async with self._lock:
            self.allocated_ports.discard(port)

    def _is_port_available(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return True
            except OSError:
                return False
