# saynet.ng Password Manager

A secure, fully **offline** desktop password manager written in Python with a
modern PySide6 (Qt) interface. Built for the community and free to use across
any platform that supports Python. All vault data is encrypted locally with
**AES-256-GCM** using a key derived from your master password with
**Argon2id**. The master password is never stored, hashed, logged, or exposed
in any form.

---

## Features

- First-launch welcome flow: create a new vault or unlock an existing one
- Master-password setup with live strength meter and mandatory
  "cannot be recovered" acknowledgement
- Unlock verification via authenticated encryption (no password hash stored)
- Per-session brute-force backoff (increasing delays, capped at 15s, never a
  permanent lockout)
- Dashboard with sidebar (All Items / Favorites / Secure Notes / Categories),
  instant search, and entry cards
- Add / edit / delete login entries and encrypted secure notes
- Cryptographically secure password generator (`secrets` CSPRNG, guaranteed
  character classes, optional ambiguous-character exclusion)
- Copy password / note to clipboard with automatic timed clearing (default 30s)
- Temporary password reveal (eye button), never shown by default
- Favorites, built-in + custom categories
- "Open website" restricted to validated `http(s)` URLs
- Auto-lock on inactivity (configurable), manual 🔒 Lock button
- Built for the community — free to use, cross-platform (Windows, Linux,
  Raspberry Pi, macOS, and any device that supports Python)
- Live-preview Dark / Light / System themes (System follows the OS setting)
- Settings page (security, appearance, generator defaults, vault info)
- Encrypted vault backup export and restore (the backup file is the same
  encrypted SQLite vault — plaintext export is not offered)
- Fully offline: no sync, telemetry, analytics, accounts, or network use

## Requirements

- Python 3.12+
- PySide6, `cryptography`, `argon2-cffi` (see `requirements.txt`)

## Platform Support

Runs anywhere Python is supported — it is pure Python and PySide6, with no
platform-specific compiled code of its own:

- **Windows** (10 / 11)
- **Linux** desktops (GNOME, KDE, etc.)
- **Raspberry Pi** (Raspberry Pi OS, 32- and 64-bit)
- **macOS** (Intel and Apple Silicon)
- Any other device/OS with a working Python 3.12+ and Qt build

The Dark / Light / System themes work on every platform; **System** follows the
OS light/dark setting (Qt detects Windows, macOS, and GNOME automatically and
falls back to a platform probe elsewhere).

## About

**saynet.ng Password Manager** is developed for the community and can be used
freely across different platforms such as Linux, Raspberry Pi devices, and
Windows, on essentially any system that supports Python. It is fully offline —
your vault never leaves your machine.

## Installation

```bash
git clone <this project>
cd password_manager
python -m venv .venv
```

Activate the environment:

```powershell
.venv\Scripts\activate        # Windows (PowerShell)
```

```bash
source .venv/bin/activate     # Linux / macOS
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Application

```bash
python main.py
```

On the first launch, choose **Create New Vault**, set a master password,
acknowledge the no-recovery warning, and unlock the vault.

## Testing

```bash
pytest
```

The suite includes cryptographic, database, authentication, generator,
validation, and dedicated security-regression tests
(`tests/test_security.py`).

## Project Structure

```
password_manager/
├── main.py                  # thin startup: QApplication + WelcomeWindow
├── requirements.txt
├── README.md
├── conftest.py              # makes `pytest` rootdir importable
├── .gitignore               # excludes vault, settings, and logs
├── app/                     # Qt-free, fully testable core
│   ├── config.py            # paths, constants, persisted settings
│   ├── crypto.py            # Argon2id KDF + AES-256-GCM helpers
│   ├── database.py          # parameterized SQLite access
│   ├── auth.py              # vault create/unlock + backoff
│   ├── models.py            # Entry + unlocked Vault session
│   ├── password_generator.py# `secrets`-based generator
│   ├── clipboard.py         # timed clipboard clearing
│   ├── validators.py        # input validation / URL sanitizing
│   └── utils.py             # timestamps, redacted logging, strength
├── ui/                      # PySide6 interface
│   ├── welcome_window.py    ├── setup_window.py
│   ├── unlock_window.py     ├── main_window.py
│   ├── add_entry_dialog.py  ├── edit_entry_dialog.py
│   ├── password_generator_dialog.py
│   ├── password_strength_widget.py
│   ├── settings_window.py   └── styles.py
├── tests/
│   ├── test_crypto.py       ├── test_auth.py
│   ├── test_database.py     ├── test_password_generator.py
│   ├── test_validators.py   └── test_security.py
└── data/                    # created/vault lives here (gitignored)
```

## Security Architecture

### Encryption

| Concern            | Choice                                              |
|--------------------|-----------------------------------------------------|
| Key derivation     | **Argon2id**, 64 MiB, 3 passes, parallelism 1       |
| KDF salt           | 16 random bytes per vault (`secrets.token_bytes`)   |
| Cipher             | **AES-256-GCM** (authenticated encryption)          |
| Nonce              | Fresh **12 random bytes per encryption operation**  |
| Blob layout        | `nonce ‖ ciphertext ‖ tag`                          |
| Wrong key / tamper | GCM authentication failure → never decrypts         |

Each entry's **entire sensitive payload** (title, username, password,
website, category, notes, favorite flag) is serialized to JSON and encrypted
as one unit. Only these are stored in the clear:

- the KDF salt and the verifier blob in `vault_metadata`
- each row's `id`, `kind`, and `created_at` / `updated_at` timestamps

### Master Password

The master password is **never stored** — not hashed, not encrypted with any
recoverable scheme. It is combined with the vault salt via Argon2id to derive
a 32-byte key held only in process memory while the vault is unlocked.

**Unlock verification:** the database stores a *sentinel* value encrypted with
the derived key. To unlock, the candidate password's key must decrypt that
sentinel and pass GCM authentication. A wrong password simply fails to
authenticate — there is no separate password hash to attack or leak.

### Vault Database

SQLite with **parameterized queries only** (`?` placeholders), transactions,
rollback on failure, and user-safe error translation. Raw SQLite exceptions
are logged as non-sensitive information only.

### Brute-Force Protection

Within an application session: attempts 1–2 have no delay; the 3rd waits 2s,
4th 5s, 5th 10s, then a capped 15s. State is memory-only — a legitimate user
who restarts the application is never permanently locked out (deliberate
design choice to avoid self-inflicted denial, per the product requirements;
it trades persistence for usability since the strong Argon2id KDF already
makes offline guessing expensive).

### Logging & Clipboard

- `logging` passes through a redaction filter that drops common secret-shaped
  assignments and any registered secret value (the master password registers
  itself during vault operations).
- Copied passwords are automatically cleared from the clipboard after a
  configurable timeout, unless the user copied something else first.

### Backups

File ▸ *Create Encrypted Backup* writes a copy of the encrypted SQLite vault;
*Restore Encrypted Backup* validates that the file is a genuine vault
database before replacing the current one, then requires unlock with the
backup's master password. Plaintext export is intentionally **not
implemented** in this version. (`vault.db` and backups are excluded in
`.gitignore`.)

## Threat Model

### Protects against

- Someone stealing or copying the vault database file without the master
  password (offline decryption infeasible against a strong master password due
  to Argon2id work factor + AES-256-GCM)
- Accidental plaintext storage of secrets (only encrypted blobs are written)
- Casual database inspection (no field is readable in cleartext)
- Tampering with stored records (authentication tag rejection)
- Database-level SQL injection (fully parameterized statements)
- Clipboard exposure of secrets after copying (timed clearing)
- Reuse of an unlocked machine inattention (auto-lock + manual lock)
- Log files leaking master passwords / entries (redaction)

### Does NOT fully protect against

- Malware or keyloggers running on the computer while the vault is unlocked
- A compromised operating system (privileged memory reading can extract the
  in-session key)
- Screen capture / shoulder surfing
- Clipboard-monitoring malware
- Weak master passwords (defence in depth helps, but entropy is your job)
- Loss of the master password: **there is no recovery, by design**
- Physical access combined with guessable passwords

## Limitations

- **Memory zeroing:** Python gives no guarantee that decrypted data or keys
  leave RAM promptly; locking and clearing references is best-effort only.
- Plaintext timestamps, entry `kind`, and row counts remain visible in the
  encrypted database (metadata-level information).
- No cloud sync / multi-device support by design.
- No password reuse / breach checking (offline-first; out of scope).
- The strength meter is an honest heuristic — advisory, not exhaustive.
- Backups share the original master password's key.

## Development

```bash
pip install -r requirements.txt
pytest            # run the test suite
python main.py    # run the application
```

## Packaging a Windows Executable (PyInstaller)

From the project root, with PyInstaller installed
(`pip install pyinstaller`):

```powershell
pyinstaller --noconfirm --clean --windowed --name PasswordManager `
    --icon=app_icon.ico main.py
```

Notes:

- PyInstaller ships hooks for PySide6; `QApplication` plugins are bundled
  automatically.
- Provide `app_icon.ico` for a custom icon; the app uses the `b.png` logo at
  runtime via `ui/styles.create_app_icon()` (falls back to a drawn shield/lock
  if `b.png` is missing — keep it alongside the executable when packaging).
- The `data/` folder is created next to the executable at first run — keep the
  `.exe` in a folder you treat as your vault location (or set the same path
  when restoring a backup).
- For smaller output, `--onefile` can be added, but expect slower startup and
  more antivirus false positives (PyInstaller bootstrappers are commonly
  flagged; whitelist your own build).
- Rebuild + retest after every dependency change.

## License

MIT — see `LICENSE` (or add your own license file as preferred).
