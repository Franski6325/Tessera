# Tessera

TUI e CLI per **profilare l’hardware** di una macchina Linux open source, **scegliere ruoli combinabili**, **definire il livello di sicurezza** e **installare solo gli strumenti che vuoi** — con il gestore pacchetti della distro.

Tessera è originale. La navigazione è tastiera-first (j/k, tab, palette `ctrl+p`, passi `n`/`p`), con chrome a mosaico pensato per sessioni lunghe. Non è un fork e non contiene codice di altri prodotti.

Funziona su **EndeavourOS, Arch, Ubuntu, Debian, Kali, Fedora, openSUSE, Alpine, Void** e famiglie vicine. Dove un nodo `/sys` manca (VM, container, live USB, permessi DMI) il probe continua e annota il buco invece di crashare.

## Cosa fa

1. **Hardware** — CPU, RAM, GPU (PCI/DRM), dischi e LUKS, rete, batteria, DMI, USB, audio, termiche, virtualizzazione/container/WSL/live.
2. **Profilo energetico deterministico** — stesso snapshot ⇒ stessa raccomandazione: `performance`, `balanced`, `battery`, `quiet`, `server`. Puoi sovrascriverla.
3. **Ruoli combinabili** — `cyber` (lab autorizzato), `developer`, `ops`, `data`, `creative`, `daily`, `privacy`, `server`. Cyber + developer è una scelta di primo livello.
4. **Sicurezza a livelli**, tutti modificabili:
   - *rilassato* · *standard* · *rafforzato* · *fortezza* · *personalizzato*
   - firewall (ufw / firewalld / nft, senza flush delle tabelle docker/cni)
   - sysctl di hardening, AppArmor (non tocca SELinux enforcing)
   - politica password PAM, KeePassXC/pass (Tessera **non** vede i segreti)
   - SSH ristretto **solo se** hai già una chiave
   - USBGuard in fortezza, con policy generata dai device già collegati
   - **LUKS: verifica, non formatta**. Cifrare un root già in uso è un migrate manuale; Tessera lo spiega e si ferma.
5. **Catalogo strumenti** filtrato dai ruoli, con nomi per famiglia di distro, fallback AUR / BlackArch (opt-in) / Flathub / pipx.
6. **Gestori pacchetti** — usa quello nativo. Se un tool non c’è (tipico: AUR incompleto, niente BlackArch), *chiede* se aggiungere un extra. Dismettere yay/paru/nala rimuove **solo l’helper** (`pacman -R`, mai `-Rns`): i pacchetti già installati e i loro dati restano.

### Su yay, paru e «tutti i pacchetti cyber/developer»

yay e paru **non sono un repository**. Sono frontend di **pacman** + **AUR**.

- I repo ufficiali Arch (`core`/`extra`/`multilib`) coprono una parte dello stack developer, non un distro da pentest.
- Una workstation cyber su Arch di solito abilita **BlackArch** (scelta esplicita, strap ufficiale dal loro sito, con verifica HTTPS/GPG — Tessera non scarica strap da mirror a caso).
- Ciò che manca ancora può stare in AUR, su Flathub, o non esistere come pacchetto: Tessera marca la voce `NON installabile` invece di inventare un `curl | sh`.

## Legalità

Il ruolo **cyber** installa strumenti da repository ufficiali (nmap, wireshark, sqlmap, hashcat, framework di assessment, …) pensati per **laboratori e perimetri con autorizzazione scritta**. Usarli contro sistemi o reti senza permesso è illecito. Tessera non include exploit scritti da noi, non automatizza accessi, non elude protezioni di terzi.

## Installazione

Python 3.11+.

### EndeavourOS (e Arch)

EndeavourOS usa `pacman` (e spesso `yay`). Clona il repo, crea il venv, lancia la TUI.

```bash
# Origin CLI (Linux nativo)
curl -fsSL https://downloads.cursor.com/origin/install.sh | sh
origin auth login
origin repo clone francesco-tannoia/linux-config-optimizer
cd linux-config-optimizer
```

Se `origin` non viene trovato:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Poi Python e Tessera:

```bash
sudo pacman -S --needed python python-pip git
# opzionale, più veloce di pip:
# curl -LsSf https://astral.sh/uv/install.sh | sh
# source ~/.bashrc
# uv sync
# uv run tessera

python -m venv .venv
source .venv/bin/activate
pip install -e .
tessera
```

Repository: https://cursor.com/codebase/francesco-tannoia/linux-config-optimizer (privato; visibilità dalle impostazioni della pagina). Docs Origin: https://cursor.com/docs/origin/cli

### Altre distro

```bash
# dalla root del repo
uv sync --extra dev
# oppure
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Uso

```bash
tessera                 # TUI
tessera detect          # hardware in tabella
tessera detect --json
tessera recommend
tessera managers
tessera plan --roles cyber,developer --security hardened --export
tessera apply --roles cyber,developer --dry-run
sudo tessera apply --roles cyber,developer --live --yes   # dopo aver letto il piano
```

Tasti TUI: `n`/`p` passi, `j`/`k` selezione, `enter` conferma, `ctrl+p` comandi, `r` ri-scan, `?` aiuto, `q` esci.

I piani finiscono in `~/.local/share/tessera/plans/` (script bash revisionabile). I journal in `~/.local/state/tessera/journal/`.

## Sicurezza del apply

- Default **dry-run**.
- I passi `tessera-internal` sono idempotenti (file drop-in `90-tessera-*`, facili da cancellare).
- Il gestore nativo (`apt`, `pacman`, `dnf`, …) è **protetto**: Tessera rifiuta di disinstallarlo.
- Nessun `dist-upgrade` / `-Syu` distruttivo mascherato da «update».
- Su live USB e container i passi kernel/firewall vengono saltati o annotati.

## Test

```bash
uv run pytest
```

## Architettura

```
src/tessera/
  detect/     probe /sys /proc os-release (errori isolati)
  engine/     scoring deterministico
  catalog/    ruoli, pacchetti per distro, controlli di sicurezza
  pkg/        risoluzione gestore, query installed, retire helper
  apply/      planner + internal hardening + journal
  tui/        chrome a mosaico
  cli.py      typer
```

MIT. Vedi `LICENSE`.
