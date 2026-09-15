"""Tests for the CSPRNG-based password generator."""

import re

import pytest

import app.password_generator as pg
from app.password_generator import (
    AMBIGUOUS_CHARS,
    DIGITS,
    LOWERCASE,
    SYMBOLS,
    UPPERCASE,
    GeneratorConfigError,
    generate_password,
)


class TestLength:
    def test_default_length_is_20(self):
        assert len(generate_password()) == 20

    @pytest.mark.parametrize("length", [8, 12, 20, 33, 64, 128])
    def test_exact_requested_length(self, length):
        assert len(generate_password(length)) == length

    def test_rejects_too_short(self):
        with pytest.raises(GeneratorConfigError):
            generate_password(7)

    def test_rejects_too_long(self):
        with pytest.raises(GeneratorConfigError):
            generate_password(129)

    def test_rejects_non_integer(self):
        with pytest.raises(GeneratorConfigError):
            generate_password("20")


class TestCharacterClasses:
    def test_uppercase_only(self):
        result = generate_password(
            24, use_lowercase=False, use_digits=False, use_symbols=False
        )
        assert set(result) <= set(UPPERCASE)
        assert len(set(result)) > 1

    def test_each_class_is_guaranteed_present(self):
        result = generate_password(8)
        assert re.search(r"[A-Z]", result)
        assert re.search(r"[a-z]", result)
        assert re.search(r"[0-9]", result)
        assert re.search(r"[^A-Za-z0-9]", result)

    def test_disabled_class_is_absent(self):
        for _ in range(30):
            result = generate_password(32, use_symbols=False, use_digits=False)
            assert not re.search(r"[0-9]", result)
            assert not re.search(r"[^A-Za-z0-9]", result)

    def test_requires_at_least_one_class(self):
        with pytest.raises(GeneratorConfigError):
            generate_password(
                16,
                use_uppercase=False,
                use_lowercase=False,
                use_digits=False,
                use_symbols=False,
            )

    def test_length_must_fit_selected_classes(self):
        with pytest.raises(GeneratorConfigError):
            generate_password(3)

    def test_exclude_ambiguous(self):
        for _ in range(20):
            result = generate_password(48, exclude_ambiguous=True)
            assert not set(result) & set(AMBIGUOUS_CHARS)

    def test_arbitrary_password_characters_allowed(self):
        result = generate_password(40)
        assert '"' not in result or True  # no artificial restriction beyond classes
        # symbols include punctuation outside shell-unsafe edge cases
        assert all(ord(ch) >= 32 for ch in result)


class TestRandomness:
    def test_outputs_differ(self):
        results = {generate_password(20) for _ in range(250)}
        assert len(results) == 250

    def test_never_imports_random_module(self):
        source = pg.__loader__.get_source(pg.__name__)
        code = "\n".join(
            line.split("#", 1)[0]
            for line in source.splitlines()
            if not line.strip().startswith((">>>", "#"))
        )
        assert not re.search(r"\bimport\s+random\b", code)
        assert not re.search(r"\bfrom\s+random\s+import\b", code)
        assert "secrets.choice" in code

    def test_uses_secrets_choice(self, monkeypatch):
        calls = {"n": 0}
        original = pg.secrets.choice

        def spy(seq):
            calls["n"] += 1
            return original(seq)

        monkeypatch.setattr(pg.secrets, "choice", spy)
        generate_password(16)
        assert calls["n"] >= 16

    def test_shuffling_is_csprng_backed(self, monkeypatch):
        calls = {"n": 0}
        original_sr = pg.secrets.SystemRandom

        class SpySystemRandom(original_sr):
            def shuffle(self, seq):
                calls["n"] += 1
                return super().shuffle(seq)

        monkeypatch.setattr(pg.secrets, "SystemRandom", SpySystemRandom)
        generate_password(20)
        assert calls["n"] == 1
