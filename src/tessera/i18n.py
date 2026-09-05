"""Tiny in-process translations. Default follows LANG, with Italian first-class copy."""

from __future__ import annotations

import os
from typing import Mapping

IT: dict[str, str] = {
    "app.title": "Tessera",
    "app.tagline": "Profila l'hardware. Scegli ruoli. Rafforza il sistema.",
    "app.legal": (
        "Tessera configura SOLO questa macchina, con strumenti dei repository ufficiali "
        "o AUR/Flathub scelti da te. Uso cyber: esclusivamente su sistemi e reti per cui "
        "hai autorizzazione scritta. Nessun exploit, nessun accesso non autorizzato."
    ),
    "nav.welcome": "Benvenuto",
    "nav.hardware": "Hardware",
    "nav.power": "Profilo",
    "nav.roles": "Ruoli",
    "nav.security": "Sicurezza",
    "nav.packages": "Strumenti",
    "nav.managers": "Gestori",
    "nav.review": "Revisione",
    "nav.apply": "Applica",
    "welcome.continue": "Inizia la scansione",
    "welcome.quit": "Esci",
    "footer.help": "j/k o ↑↓  sposta   ⏎  conferma   tab  pannelli   ctrl+p  comandi   ?  aiuto   q  esci",
    "hw.scanning": "Lettura di /sys, /proc e os-release…",
    "hw.done": "Scansione completata",
    "power.performance": "Prestazioni",
    "power.balanced": "Bilanciato",
    "power.battery": "Batteria",
    "power.quiet": "Silenzioso / termico",
    "power.server": "Server / headless",
    "role.cyber": "Cyber (lab autorizzato, pentest, blue/red team)",
    "role.developer": "Sviluppo software",
    "role.ops": "Ops / SRE / infrastruttura",
    "role.data": "Dati / scienza",
    "role.creative": "Creativo / media",
    "role.daily": "Uso quotidiano",
    "role.privacy": "Privacy quotidiana",
    "role.server": "Server",
    "sec.relaxed": "Rilassato",
    "sec.standard": "Standard",
    "sec.hardened": "Rafforzato",
    "sec.fortress": "Fortezza",
    "sec.custom": "Personalizzato",
    "palette.title": "Comandi",
    "apply.dry": "Simulazione (nessuna modifica)",
    "apply.live": "Esecuzione reale (richiede conferma)",
}

EN: dict[str, str] = {
    "app.title": "Tessera",
    "app.tagline": "Profile the hardware. Pick roles. Harden the system.",
    "app.legal": (
        "Tessera configures THIS machine only, using official repositories or AUR/Flathub "
        "packages you select. Cyber tooling is for systems and networks you are written-authorized "
        "to test. No exploits, no unauthorized access."
    ),
    "nav.welcome": "Welcome",
    "nav.hardware": "Hardware",
    "nav.power": "Profile",
    "nav.roles": "Roles",
    "nav.security": "Security",
    "nav.packages": "Tools",
    "nav.managers": "Managers",
    "nav.review": "Review",
    "nav.apply": "Apply",
    "welcome.continue": "Start scan",
    "welcome.quit": "Quit",
    "footer.help": "j/k or ↑↓  move   ⏎  confirm   tab  panes   ctrl+p  commands   ?  help   q  quit",
    "hw.scanning": "Reading /sys, /proc and os-release…",
    "hw.done": "Scan complete",
    "power.performance": "Performance",
    "power.balanced": "Balanced",
    "power.battery": "Battery",
    "power.quiet": "Quiet / thermal",
    "power.server": "Server / headless",
    "role.cyber": "Cyber (authorized lab, pentest, blue/red team)",
    "role.developer": "Software development",
    "role.ops": "Ops / SRE / infrastructure",
    "role.data": "Data / science",
    "role.creative": "Creative / media",
    "role.daily": "Daily driver",
    "role.privacy": "Everyday privacy",
    "role.server": "Server",
    "sec.relaxed": "Relaxed",
    "sec.standard": "Standard",
    "sec.hardened": "Hardened",
    "sec.fortress": "Fortress",
    "sec.custom": "Custom",
    "palette.title": "Commands",
    "apply.dry": "Dry run (no changes)",
    "apply.live": "Live apply (confirmation required)",
}

_TABLES: dict[str, Mapping[str, str]] = {"it": IT, "en": EN}


def detect_lang(override: str | None = None) -> str:
    if override in _TABLES:
        return override
    lang = os.environ.get("TESSERA_LANG") or os.environ.get("LANG") or "it"
    lang = lang.lower()
    if lang.startswith("it"):
        return "it"
    return "en"


class I18n:
    def __init__(self, lang: str | None = None) -> None:
        self.lang = detect_lang(lang)

    def t(self, key: str, **kwargs: object) -> str:
        table = _TABLES.get(self.lang, EN)
        raw = table.get(key) or EN.get(key) or key
        if kwargs:
            try:
                return raw.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return raw
        return raw
