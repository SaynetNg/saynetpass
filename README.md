# SAYNET.NG PASSWORD MANAGER

A fully ****offline**** desktop password manager built with Python and a

modern PySide6 (Qt) interface. The project is made for the community and can

be used on any platform that supports Python. Vault data is encrypted locally

using ****AES-256-GCM**** with a key derived from the master password using

****Argon2id****. The master password is never stored, hashed, logged, or exposed

by the application.

**---**

**## Features**

- First-launch screen for creating a new vault or opening an existing one

- Master-password setup with a password strength meter and a required

"cannot be recovered" acknowledgement

- Unlock checking using authenticated encryption instead of storing a password hash

- Brute-force protection during each application session, with increasing delays

up to 15 seconds and no permanent lockout

- Dashboard with sidebar (All Items / Favorites / Secure Notes / Categories),

search, and entry cards

- Add / edit / delete login entries and secure notes

- Password generator using Python's `secrets` module, with required character

classes and an option to leave out ambiguous characters

- Copy passwords or notes to the clipboard with automatic clearing (default 30s)

- Passwords can be temporarily revealed when needed

- Favorites and built-in or custom categories

- "Open website" only accepts validated `http(s)` URLs

- Auto-lock after a period of inactivity, with a manual Lock button

- Free to use and works across Windows, Linux, Raspberry Pi, macOS, and other

systems that support Python

- Dark / Light / System themes with live preview

- Settings for security, appearance, password generator defaults, and vault info

- Encrypted vault backup and restore using the encrypted SQLite vault file

(plaintext backup export is not available)

- Fully offline with no sync, telemetry, analytics, accounts, or network access

**## Requirements**

- Python 3.12+

- PySide6, `cryptography`, `argon2-cffi` (see `requirements.txt`)

**## Platform Support**

The application is written in Python and PySide6, so it does not require its

own platform-specific compiled code:

- ****Windows**** (10 / 11)

- ****Linux**** desktops (GNOME, KDE, etc.)

- ****Raspberry Pi**** (Raspberry Pi OS, 32- and 64-bit)

- ****macOS**** (Intel and Apple Silicon)

- Any other device/OS with a working Python 3.12+ and Qt build

The Dark / Light / System themes are available on all supported platforms.

****System**** follows the operating system's light/dark setting. Qt detects the

setting on Windows, macOS, and GNOME and uses a platform check on other systems.

**## About**

****saynet.ng Password Manager**** was developed by saynet.ng Innovations as a

simple password manager for people who want to keep their passwords on their

own device. It can be used on Windows, Linux, Raspberry Pi, macOS, and other

systems that support Python.

The application works completely offline. Your vault stays on the device and

there is no cloud service, account, or online sync involved.

**## Installation**

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

**## Running the Application**

```bash

python main.py

```

On the first launch, select ****Create New Vault****, choose a master password,

accept the no-recovery warning, and unlock the vault.

**## Testing**

```bash

pytest

```

The test suite covers the cryptography, database, authentication, password

generator, validation, and security checks

(`tests/test_security.py`).

**## Project Structure**

```

password_manager/

├── main.py                  # starts QApplication and WelcomeWindow

├── requirements.txt

├── README.md

├── conftest.py              # makes `pytest` rootdir importable

├── .gitignore               # excludes vault, settings, and logs

├── app/                     # Qt-free application logic

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

**## Security Architecture**

**### Encryption**

| Concern            | Choice                                              |

|--------------------|-----------------------------------------------------|

| Key derivation     | ****Argon2id****, 64 MiB, 3 passes, parallelism 1       |

| KDF salt           | 16 random bytes per vault (`secrets.token_bytes`)   |

| Cipher             | ****AES-256-GCM**** (authenticated encryption)          |

| Nonce              | Fresh ****12 random bytes per encryption operation****  |

| Blob layout        | `nonce ‖ ciphertext ‖ tag`                          |

| Wrong key / tamper | GCM authentication failure → never decrypts         |

Each entry's ****entire sensitive payload**** (title, username, password,

website, category, notes, favorite flag) is converted to JSON and encrypted

as a single unit. The following information is stored without encryption:

- the KDF salt and the verifier blob in `vault_metadata`

- each row's `id`, `kind`, and `created_at` / `updated_at` timestamps

**### Master Password**

The master password is ****never stored****. It is not hashed or encrypted in a

way that allows it to be recovered. Instead, Argon2id uses the master password

and vault salt to create a 32-byte key. The key is kept in memory while the

vault is unlocked.

****Unlock verification:**** the database contains a small **sentinel** value

encrypted with the derived key. During unlock, the password is used to create

a key and decrypt the sentinel. If authentication fails, the password is

rejected. There is no separate password hash stored in the database.

**### Vault Database**

SQLite is used for the vault database. Database queries use parameterized

statements (`?` placeholders), with transactions and rollback on errors.

SQLite errors are handled so that sensitive information is not exposed in logs.

**### Brute-Force Protection**

During a session, failed unlock attempts have increasing delays: attempts 1–2

have no delay, the 3rd waits 2s, the 4th 5s, the 5th 10s, and later attempts

are capped at 15s. The attempt count is kept in memory and is reset when the

application is restarted. This means a user is not permanently locked out of

their own vault. Argon2id also adds extra work to each password attempt.

**### Logging & Clipboard**

- `logging` uses a redaction filter to remove common secret-like values and

registered secrets from log messages.

- Copied passwords are automatically removed from the clipboard after the

configured timeout, unless another application has already replaced the

clipboard contents.

**### Backups**

File ▸ **Create Encrypted Backup** creates a copy of the encrypted SQLite vault.

**Restore Encrypted Backup** checks that the selected file is a valid vault

database before replacing the current one. The restored vault must then be

unlocked using its master password. Plaintext export is not available in this

version. (`vault.db` and backups are excluded in `.gitignore`.)

**## Threat Model**

**### Protects against**

- Someone copying the vault database without knowing the master password

- Secrets being accidentally stored as plaintext

- Reading saved passwords directly from the SQLite database

- Changes to encrypted records being accepted without authentication

- SQL injection through database input

- Passwords remaining in the clipboard indefinitely after being copied

- Leaving an unlocked vault unattended when auto-lock is enabled

- Passwords or other saved entries being written to log files

**### Does NOT fully protect against**

- Malware or keyloggers running while the vault is unlocked

- A compromised operating system that can access application memory

- Screen capture or someone looking at the screen

- Malware that monitors the clipboard

- Weak or easily guessed master passwords

- Losing the master password: ****there is no recovery, by design****

- Physical access to the computer combined with a guessable password

**## Limitations**

- ****Memory zeroing:**** Python does not guarantee that keys or decrypted data

are removed from memory immediately. Clearing references when locking is

best-effort.

- Some database information, including timestamps, entry `kind`, and row

counts, remains visible.

- No cloud sync or multi-device support.

- No password reuse or breach checking.

- The password strength meter is a guide and should not be treated as a

complete security assessment.

- Backups use the same master password as the original vault.

**## Development**

```bash

pip install -r requirements.txt

pytest            # run the test suite

python main.py    # run the application

```

**## Packaging a Windows Executable (PyInstaller)**

From the project root, with PyInstaller installed

(`pip install pyinstaller`):

```powershell

pyinstaller --noconfirm --clean --windowed --name PasswordManager `

```
--icon=app\_icon.ico main.py
```

```

Notes:

- PyInstaller includes support for PySide6; the required Qt plugins are

bundled during the build.

- Provide `app_icon.ico` if you want to use a custom application icon. The

application uses the `b.png` logo at runtime through

`ui/styles.create_app_icon()`. If `b.png` is not available, it falls back

to a simple shield/lock icon. Keep the image with the executable when needed.

- The `data/` folder is created next to the executable when the application

runs for the first time. Keep the executable in a location where you want

the vault data to be stored, or use the same location when restoring a backup.

- For a smaller build, `--onefile` can be used. It may take longer to start

and can sometimes trigger antivirus warnings because of how PyInstaller

packages applications.

- Rebuild and test the application after changing dependencies.
