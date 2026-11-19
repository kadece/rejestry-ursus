#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
rejestry-ursus - daemon uzupelniajacy rejestry o nowe dane z biezacego roku.
=============================================================================

5. oraz 20. kazdego miesiaca o 06:00 uruchamia Vibe headless z promptem
z pliku PROMPT-daemon.txt (katalog tego skryptu). Vibe pobiera wykazy
z ursus.um.warszawa.pl (build.py --all), przebudowuje data/*.json oraz
site/index.html i publikuje zmiany na GitHubie (kadece/rejestry-ursus).

Uzycie:
  python ursus_daemon.py            # daemon (do uruchamiania z Harmonogramu zadan)
  python ursus_daemon.py status     # pokaz stan
  python ursus_daemon.py run-now    # wymus pelny przebieg teraz (z publikacja)
  python ursus_daemon.py test       # przebieg testowy (dry-run, BEZ publikacji)
  python ursus_daemon.py next 2026-12-05T06:00   # zmien termin kolejnego przebiegu
"""

import json
import os
import sys
import time
import datetime as dt
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
VIBE_EXE = r"C:\Users\Krzysztof\.local\bin\vibe.exe"
PYTHON_EXE = r"C:\Users\Krzysztof\AppData\Local\Programs\Python\Python312\python.exe"
PROMPT_PATH = os.path.join(BASE, "PROMPT-daemon.txt")

STATE_PATH = os.path.join(BASE, "daemon-state.json")
LOG_PATH = os.path.join(BASE, "daemon.log")
RUNS_DIR = os.path.join(BASE, "runs-daemon")
LOCK_PATH = os.path.join(BASE, ".ursus-daemon.lock")

RUN_DAYS = (5, 20)               # 5. i 20. kazdego miesiaca
RUN_HOUR = 6                     # o tej godzinie
CHECK_INTERVAL_S = 300           # co ile sekund daemon sprawdza termin
RETRY_AFTER_FAILURE_S = 6 * 3600 # co ile ponawiac nieudany przebieg
MAX_ATTEMPTS = 10                # po tylu porazkach czeka na reczne "run-now"
RUN_TIMEOUT_S = 5400             # 90 min na pelny przebieg (build ~4 min + publikacja)


def log(msg: str) -> None:
    line = f"{dt.datetime.now().isoformat(timespec='seconds')}  {msg}"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def next_run_after(now: dt.datetime) -> dt.datetime:
    """Najblizszy termin z dni RUN_DAYS o godzinie RUN_HOUR, strictly po `now`."""
    for month_offset in range(0, 3):
        year = now.year + (now.month - 1 + month_offset) // 12
        month = (now.month - 1 + month_offset) % 12 + 1
        for day in RUN_DAYS:
            cand = dt.datetime(year, month, day, RUN_HOUR, 0, 0)
            if cand > now:
                return cand
    raise RuntimeError("nie umiem policzyc kolejnego terminu")


def default_state() -> dict:
    return {
        "next_run_at": next_run_after(dt.datetime.now()).isoformat(timespec="seconds"),
        "last_run_at": None,
        "attempts": 0,
        "last_result": None,
        "schedule": {"days": list(RUN_DAYS), "hour": RUN_HOUR},
    }


def load_state() -> dict:
    default = default_state()
    if not os.path.exists(STATE_PATH):
        save_state(default)
        return default
    with open(STATE_PATH, "r", encoding="utf-8-sig") as f:
        st = json.load(f)
    for k, v in default.items():
        st.setdefault(k, v)
    return st


def save_state(st: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2, ensure_ascii=False)


def parse_when(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


def build_prompt(today: dt.date, dry_run: bool) -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8-sig") as f:
        user_task = f.read()
    header = (
        "KONTEKST AUTOMATU (vibe headless, bez interakcji z uzytkownikiem):\n"
        f"- Dzis jest {today.isoformat()}.\n"
        f"- Katalog projektu: {BASE} - pracuj w nim.\n"
        "- To automatyczny przebieg daemona ursus_daemon.py\n"
        f"  (harmonogram: {RUN_DAYS[0]}. i {RUN_DAYS[1]}. kazdego miesiaca o {RUN_HOUR:02d}:00).\n"
        "- Wykonaj zadanie ponizej.\n"
    )
    if dry_run:
        header += (
            "- TRYB TESTOWY (dry-run): wykonaj build i kontrole jakosci, przygotuj raport,\n"
            "  ale NIE publikuj nic na GitHuba (pomin krok publikacji).\n"
        )
    header += (
        '- Na samym koncu odpowiedzi dodaj dokladnie linie "RESULT: OK"\n'
        '  lub "RESULT: FAIL - <krotki powod>".\n'
        "\n--- ZADANIE (plik: PROMPT-daemon.txt) ---\n"
    )
    return header + user_task


def run_vibe(prompt: str, log_name: str, timeout_s: int) -> tuple[bool, str]:
    """Uruchamia vibe -p headless; zwraca (sukces, sciezka do logu przebiegu)."""
    os.makedirs(RUNS_DIR, exist_ok=True)
    out_path = os.path.join(RUNS_DIR, f"{log_name}-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.log")
    cmd = [VIBE_EXE, "-p", prompt, "--auto-approve", "--trust",
           "--workdir", BASE, "--max-turns", "60", "--output", "text"]
    log(f"Uruchamiam Vibe headless: {log_name} (log przebiegu: {out_path})")
    try:
        with open(out_path, "w", encoding="utf-8") as out:
            proc = subprocess.run(cmd, cwd=BASE, stdout=out, stderr=subprocess.STDOUT,
                                  timeout=timeout_s)
    except subprocess.TimeoutExpired:
        log(f"PRZEKROCZONY CZAS ({timeout_s}s): {log_name}")
        return False, out_path
    if proc.returncode != 0:
        log(f"Vibe zakonczyl sie kodem {proc.returncode}: {log_name}")
        return False, out_path
    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
        tail = f.read()[-2000:]
    if "RESULT: OK" in tail:
        return True, out_path
    log(f"Brak sygnalu RESULT: OK w odpowiedzi agenta: {log_name}")
    return False, out_path


def run_update(force: bool = False, dry_run: bool = False) -> bool:
    st = load_state()
    now = dt.datetime.now()
    if not force and now < parse_when(st["next_run_at"]):
        print("Termin jeszcze nie nadszedl. Uzyj 'run-now', zeby wymusic.")
        return False
    label = f"{now.date().isoformat()} {'(test)' if dry_run else ''}".strip()
    prompt = build_prompt(now.date(), dry_run)
    ok, out_path = run_vibe(prompt, "ursus-" + label.replace(" ", "-"), RUN_TIMEOUT_S)
    st = load_state()
    st["last_result"] = f"ursus {label}: {'OK' if ok else 'FAIL'} ({out_path})"
    if ok:
        st["last_run_at"] = now.isoformat(timespec="seconds")
        st["attempts"] = 0
        st["next_run_at"] = next_run_after(now).isoformat(timespec="seconds")
        log(f"Przebieg zakonczony sukcesem. Kolejny przebieg: {st['next_run_at']}")
    else:
        st["attempts"] += 1
        if st["attempts"] >= MAX_ATTEMPTS:
            st["next_run_at"] = "9999-12-31T23:59:59"
            log(f"Przebieg nie udal sie x{st['attempts']}. Wstrzymano do recznego 'run-now'.")
        else:
            st["next_run_at"] = (now + dt.timedelta(seconds=RETRY_AFTER_FAILURE_S)).isoformat(timespec="seconds")
            log(f"Przebieg nie udal sie (proba {st['attempts']}/{MAX_ATTEMPTS}). "
                f"Ponowna proba: {st['next_run_at']}")
    save_state(st)
    return ok


def acquire_lock() -> bool:
    if os.path.exists(LOCK_PATH):
        try:
            age = time.time() - os.path.getmtime(LOCK_PATH)
        except OSError:
            age = 999999
        if age < 86400:
            print("Daemon juz dziala (plik .ursus-daemon.lock).")
            return False
        log("Znaleziono przeterminowany lock - przejmuje.")
    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    return True


def release_lock() -> None:
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


def daemon_loop() -> None:
    if not acquire_lock():
        sys.exit(0)
    os.makedirs(RUNS_DIR, exist_ok=True)
    log(f"Daemon rejestry-ursus startuje (przebiegi: {RUN_DAYS[0]}. i {RUN_DAYS[1]}. miesiaca o {RUN_HOUR:02d}:00).")
    try:
        while True:
            try:
                st = load_state()
                now = dt.datetime.now()
                if now >= parse_when(st["next_run_at"]):
                    log("Termin przebiegu nadszedl - startuje uzupelnianie rejestrow.")
                    run_update(force=True)
            except Exception as e:
                log(f"BLAD petli daemon: {e!r}")
            time.sleep(CHECK_INTERVAL_S)
    finally:
        release_lock()
        log("Daemon zatrzymany.")


def cmd_status() -> None:
    st = load_state()
    print(json.dumps(st, indent=2, ensure_ascii=False))


def main() -> None:
    os.makedirs(RUNS_DIR, exist_ok=True)
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if arg in ("status",):
        cmd_status()
    elif arg in ("run-now",):
        run_update(force=True, dry_run=False)
    elif arg in ("test", "dry-run"):
        run_update(force=True, dry_run=True)
    elif arg in ("next",):
        st = load_state()
        st["next_run_at"] = sys.argv[2]
        save_state(st)
        print(f"Ustawiono kolejny przebieg na: {sys.argv[2]}")
    elif arg in ("", "daemon", "run"):
        daemon_loop()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
