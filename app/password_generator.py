"""Cryptographically secure password generation.

Randomness comes exclusively from the `secrets` module (CSPRNG). The
`random` module is never used or even imported here. When character classes
are selected, the generator guarantees at least one character from each.
"""

from __future__ import annotations

import secrets
import string

UPPERCASE = string.ascii_uppercase
LOWERCASE = string.ascii_lowercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?/~"
AMBIGUOUS_CHARS = "Il1O0o|`'\":;,.{}"

MIN_LENGTH = 8
MAX_LENGTH = 128
DEFAULT_LENGTH = 20


class GeneratorConfigError(ValueError):
    pass


def _strip_ambiguous(alphabet: str, exclude_ambiguous: bool) -> str:
    if not exclude_ambiguous:
        return alphabet
    return "".join(ch for ch in alphabet if ch not in AMBIGUOUS_CHARS)


def generate_password(
    length: int = DEFAULT_LENGTH,
    *,
    use_uppercase: bool = True,
    use_lowercase: bool = True,
    use_digits: bool = True,
    use_symbols: bool = True,
    exclude_ambiguous: bool = False,
) -> str:
    if not isinstance(length, int) or length < MIN_LENGTH or length > MAX_LENGTH:
        raise GeneratorConfigError(
            f"Password length must be between {MIN_LENGTH} and {MAX_LENGTH}."
        )
    selected: list[tuple[str, str]] = []
    if use_uppercase:
        selected.append(("uppercase", _strip_ambiguous(UPPERCASE, exclude_ambiguous)))
    if use_lowercase:
        selected.append(("lowercase", _strip_ambiguous(LOWERCASE, exclude_ambiguous)))
    if use_digits:
        selected.append(("digit", _strip_ambiguous(DIGITS, exclude_ambiguous)))
    if use_symbols:
        selected.append(("symbol", _strip_ambiguous(SYMBOLS, exclude_ambiguous)))

    selected = [(label, alphabet) for label, alphabet in selected if alphabet]
    if not selected:
        raise GeneratorConfigError("Select at least one character type.")
    if length < len(selected):
        raise GeneratorConfigError(
            f"The length must be at least {len(selected)} to include every "
            "selected character type."
        )

    pool = "".join(alphabet for _, alphabet in selected)
    chars = [secrets.choice(alphabet) for _, alphabet in selected]
    chars += [secrets.choice(pool) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)
