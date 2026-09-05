"""Block devices, rotation, mounts, LUKS/dm-crypt detection."""

from __future__ import annotations

import json
from pathlib import Path

from tessera.detect._io import list_dir, note, read_int, read_text, try_run, which
from tessera.models import ProbeNote, StorageDevice, StorageInfo


def detect_storage() -> StorageInfo:
    notes: list[ProbeNote] = []
    devices: list[StorageDevice] = []
    lsblk = _lsblk_json()
    if lsblk:
        devices.extend(_from_lsblk(lsblk))
    else:
        notes.append(note("storage.lsblk", "lsblk assente o non JSON: fallback su /sys/block.", "info"))
        devices.extend(_from_sysfs())

    root_encrypted = any(d.encrypted and "/" in d.mountpoints for d in devices)
    if not root_encrypted:
        root_encrypted = _root_on_crypt()
    if not devices:
        notes.append(note("storage.none", "Nessun disco enumerato.", "warning"))
    return StorageInfo(devices=tuple(devices), root_encrypted=root_encrypted, notes=tuple(notes))


def _lsblk_json() -> dict | None:
    if not which("lsblk"):
        return None
    raw = try_run(["lsblk", "-J", "-O", "-b"])
    if not raw:
        raw = try_run(["lsblk", "-J", "-b", "-o", "NAME,MODEL,SIZE,ROTA,TRAN,RM,MOUNTPOINT,FSTYPE,TYPE,SERIAL"])
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _walk_lsblk(node: dict, acc: list[StorageDevice], parent_crypt: bool = False) -> None:
    name = str(node.get("name") or "")
    typ = str(node.get("type") or "")
    fstype = node.get("fstype")
    mount = node.get("mountpoint") or node.get("mountpoints")
    mounts: tuple[str, ...] = ()
    if isinstance(mount, list):
        mounts = tuple(m for m in mount if m)
    elif isinstance(mount, str) and mount:
        mounts = (mount,)
    encrypted = parent_crypt or typ == "crypt" or (str(fstype or "").lower() in {"crypto_luks", "swap"} and "crypt" in typ)
    children = node.get("children") or []
    if typ in {"disk", "nvme", "rom"} or (typ == "crypt"):
        size = int(node.get("size") or 0)
        rota = node.get("rota")
        rotational = bool(rota) if rota is not None else False
        devices_name = name
        acc.append(
            StorageDevice(
                name=devices_name,
                model=str(node.get("model") or "").strip() or devices_name,
                size_bytes=size,
                rotational=rotational,
                transport=str(node.get("tran") or typ or ""),
                removable=bool(node.get("rm") or False),
                mountpoints=mounts,
                fstype=str(fstype) if fstype else None,
                encrypted=encrypted or any(_child_crypt(c) for c in children),
                serial=str(node.get("serial") or "") or None,
            )
        )
    for child in children:
        _walk_lsblk(child, acc, parent_crypt=encrypted or typ == "crypt")


def _child_crypt(node: dict) -> bool:
    if str(node.get("type") or "") == "crypt":
        return True
    return any(_child_crypt(c) for c in (node.get("children") or []))


def _from_lsblk(payload: dict) -> list[StorageDevice]:
    acc: list[StorageDevice] = []
    for node in payload.get("blockdevices") or []:
        _walk_lsblk(node, acc)
    # de-duplicate by name keeping the richer record
    uniq: dict[str, StorageDevice] = {}
    for dev in acc:
        prev = uniq.get(dev.name)
        if prev is None or (dev.encrypted and not prev.encrypted) or (dev.mountpoints and not prev.mountpoints):
            uniq[dev.name] = dev
    return list(uniq.values())


def _from_sysfs() -> list[StorageDevice]:
    out: list[StorageDevice] = []
    for block in list_dir("/sys/block"):
        name = block.name
        if name.startswith(("loop", "ram", "zram", "dm-")):
            continue
        size_sectors = read_int(block / "size") or 0
        size = size_sectors * 512
        rota = (read_text(block / "queue" / "rotational", default="1") or "1") == "1"
        model = read_text(block / "device" / "model", default=name) or name
        rem = (read_text(block / "removable", default="0") or "0") == "1"
        out.append(
            StorageDevice(
                name=name,
                model=model.strip(),
                size_bytes=size,
                rotational=rota,
                transport="",
                removable=rem,
                mountpoints=_mounts_for(name),
                fstype=None,
                encrypted=False,
            )
        )
    return out


def _mounts_for(name: str) -> tuple[str, ...]:
    raw = read_text("/proc/mounts", default="") or ""
    found: list[str] = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[0].endswith(name) or f"/{name}" in parts[0]:
            found.append(parts[1])
    return tuple(found)


def _root_on_crypt() -> bool:
    mounts = read_text("/proc/mounts", default="") or ""
    for line in mounts.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "/":
            src = parts[0]
            if "mapper" in src or "crypt" in src:
                return True
            # follow dm uuid
            uuid_path = Path("/sys/class/block") / Path(src).name / "dm" / "uuid"
            uuid = read_text(uuid_path, default="") or ""
            if uuid.upper().startswith("CRYPT"):
                return True
    crypttab = read_text("/etc/crypttab", default="")
    if crypttab and any(not line.startswith("#") and line.strip() for line in crypttab.splitlines()):
        return True
    return False
