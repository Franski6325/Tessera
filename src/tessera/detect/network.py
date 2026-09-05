"""Network interfaces from sysfs + /proc/net."""

from __future__ import annotations

import socket
from pathlib import Path

from tessera.detect._io import list_dir, note, read_int, read_text
from tessera.models import NetIface, NetworkInfo, ProbeNote


def detect_network() -> NetworkInfo:
    notes: list[ProbeNote] = []
    hostname = read_text("/proc/sys/kernel/hostname", default=None) or socket.gethostname()
    ifaces: list[NetIface] = []
    for path in list_dir("/sys/class/net"):
        name = path.name
        if name == "lo":
            continue
        mac = read_text(path / "address", default=None)
        oper = (read_text(path / "operstate", default="down") or "down").lower()
        wireless = (path / "wireless").exists() or (path / "phy80211").exists()
        speed = read_int(path / "speed")
        ipv4, ipv6 = _addrs(name)
        ifaces.append(
            NetIface(
                name=name,
                mac=mac if mac and mac != "00:00:00:00:00:00" else None,
                ipv4=ipv4,
                ipv6=ipv6,
                wireless=wireless,
                up=oper == "up",
                speed_mbps=speed if speed and speed > 0 else None,
            )
        )
    if not ifaces:
        notes.append(note("net.none", "Nessuna interfaccia oltre lo.", "warning"))
    return NetworkInfo(interfaces=tuple(ifaces), hostname=hostname, notes=tuple(notes))


def _addrs(iface: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    v4: list[str] = []
    v6: list[str] = []
    fib = Path("/proc/net/fib_trie")
    # Prefer ip -o if present is avoided to keep zero deps; parse /proc/net/if_inet6 and `ip` optional.
    inet6 = read_text("/proc/net/if_inet6", default="") or ""
    for line in inet6.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[5] == iface:
            hexaddr = parts[0]
            v6.append(_expand_v6(hexaddr))
    # IPv4: /proc/net/fib_trie is painful; use getaddr-like via sysfs only when `ip` missing.
    from tessera.detect._io import try_run, which

    if which("ip"):
        raw = try_run(["ip", "-o", "addr", "show", "dev", iface])
        if raw:
            for line in raw.splitlines():
                if "inet " in line:
                    try:
                        v4.append(line.split("inet ")[1].split()[0])
                    except IndexError:
                        continue
                if "inet6 " in line:
                    try:
                        addr = line.split("inet6 ")[1].split()[0]
                        if addr not in v6:
                            v6.append(addr)
                    except IndexError:
                        continue
    del fib
    return tuple(v4), tuple(v6)


def _expand_v6(hexaddr: str) -> str:
    hexaddr = hexaddr.zfill(32)
    chunks = [hexaddr[i : i + 4] for i in range(0, 32, 4)]
    return ":".join(chunks)
