from tessera.detect._io import note
from tessera.detect.cpu import detect_cpu
from tessera.detect.memory import detect_memory
from tessera.detect.gpu import detect_gpu
from tessera.detect.storage import detect_storage
from tessera.detect.network import detect_network
from tessera.detect.battery import detect_battery
from tessera.detect.distro import detect_distro
from tessera.detect.platform import (
    classify_chassis,
    detect_audio,
    detect_dmi,
    detect_thermals,
    detect_usb,
    detect_virt,
)
from tessera.detect.managers import detect_managers
from tessera.exceptions import ProbeError, UnsupportedPlatformError
from tessera.models import (
    BatteryInfo,
    CpuInfo,
    DistroFamily,
    DistroInfo,
    DmiInfo,
    GpuInfo,
    HardwareSnapshot,
    MemoryInfo,
    NetworkInfo,
    ProbeNote,
    StorageInfo,
    VirtInfo,
)

import os
import sys
from datetime import datetime, timezone


def _empty_cpu() -> CpuInfo:
    return CpuInfo("sconosciuto", "unknown", 1, 1, 1, None, (), "unknown", ())


def _empty_mem() -> MemoryInfo:
    return MemoryInfo(0, 0, 0)


def _empty_gpu() -> GpuInfo:
    return GpuInfo(())


def _empty_storage() -> StorageInfo:
    return StorageInfo((), False)


def _empty_net() -> NetworkInfo:
    return NetworkInfo((), "localhost")


def _empty_bat() -> BatteryInfo:
    return BatteryInfo(False, None, None, None, None, None)


def _empty_dmi() -> DmiInfo:
    return DmiInfo(None, None, None, None, None, None, None, None, None)


def _empty_virt() -> VirtInfo:
    return VirtInfo(False, False, None, None, False, False)


def _empty_distro() -> DistroInfo:
    return DistroInfo("unknown", (), "unknown", "", DistroFamily.UNKNOWN, "unknown", "", None)


def _catch(fn, notes: list[ProbeNote], fallback):
    try:
        return fn()
    except ProbeError as exc:
        notes.append(note(exc.code, str(exc), "error", exc.hint))
        return fallback()
    except Exception as exc:  # noqa: BLE001
        notes.append(note("probe.unexpected", f"{getattr(fn, '__name__', fn)}: {exc}", "error"))
        return fallback()


def collect_snapshot() -> HardwareSnapshot:
    if sys.platform != "linux" and os.environ.get("TESSERA_ALLOW_NONLINUX") != "1":
        raise UnsupportedPlatformError(
            f"Tessera è per Linux open source (trovato {sys.platform}).",
            code="platform.os",
            hint="Imposta TESSERA_ALLOW_NONLINUX=1 solo per test su dati mock.",
        )

    notes: list[ProbeNote] = []
    distro = _catch(detect_distro, notes, _empty_distro)
    cpu = _catch(detect_cpu, notes, _empty_cpu)
    memory = _catch(detect_memory, notes, _empty_mem)
    gpu = _catch(detect_gpu, notes, _empty_gpu)
    storage = _catch(detect_storage, notes, _empty_storage)
    network = _catch(detect_network, notes, _empty_net)
    battery = _catch(detect_battery, notes, _empty_bat)
    dmi = _catch(detect_dmi, notes, _empty_dmi)
    usb = _catch(detect_usb, notes, lambda: tuple())
    audio = _catch(detect_audio, notes, lambda: tuple())
    thermals = _catch(detect_thermals, notes, lambda: tuple())
    virt = _catch(detect_virt, notes, _empty_virt)
    managers = _catch(lambda: detect_managers(distro.family), notes, lambda: tuple())

    chassis = classify_chassis(dmi, virt, battery.present)
    for part in (cpu, memory, gpu, storage, network, battery, virt, distro):
        notes.extend(getattr(part, "notes", ()))

    hot = [z for z in thermals if z.celsius is not None and z.celsius >= 85]
    if hot:
        notes.append(note("thermal.hot", f"Zone calde: {', '.join(z.name for z in hot)}. Meglio quiet/battery.", "warning"))

    return HardwareSnapshot(
        hostname=network.hostname,
        chassis=chassis,
        distro=distro,
        cpu=cpu,
        memory=memory,
        gpu=gpu,
        storage=storage,
        network=network,
        battery=battery,
        dmi=dmi,
        usb=usb,
        audio=audio,
        thermals=thermals,
        virt=virt,
        managers=managers,
        notes=tuple(notes),
        collected_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


__all__ = ["collect_snapshot"]
