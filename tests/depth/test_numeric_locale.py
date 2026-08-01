"""Qt's locale must not reach the native libraries we hand numbers to.

QApplication calls setlocale(LC_ALL, "") on construction, adopting the user's
locale. Under a comma-decimal locale (fr_FR, de_DE, ...) the Orbbec SDK parses
its own frame-processor config with locale-dependent C float parsing, so "1.0"
truncates to 1 and the range 0.0..1.0 collapses to [0, 0]:

    Filter@FrameProcessor: config item DisparityTransform#2 value 1 out of range [0, 0]

The camera then never opens, and the node renders transparent black.
"""

import locale

import pytest

from numeric_locale import restoreCNumericLocale

COMMA_DECIMAL_LOCALES = ("fr_FR.UTF-8", "de_DE.UTF-8", "fr_FR", "de_DE")


@pytest.fixture(autouse=True)
def preserve_numeric_locale():
    """Locale is process-global: leave it exactly as it was found."""
    original = locale.setlocale(locale.LC_NUMERIC)
    yield
    locale.setlocale(locale.LC_NUMERIC, original)


def use_a_comma_decimal_locale():
    for candidate in COMMA_DECIMAL_LOCALES:
        try:
            locale.setlocale(locale.LC_NUMERIC, candidate)
        except locale.Error:
            continue
        if locale.localeconv()["decimal_point"] == ",":
            return candidate
    pytest.skip("no comma-decimal locale is installed on this machine")


def test_restores_a_dot_decimal_point_for_native_libraries():
    use_a_comma_decimal_locale()
    assert locale.localeconv()["decimal_point"] == ","

    restoreCNumericLocale()

    # The invariant that matters is the separator the C library hands to
    # anything parsing numbers, not the locale's name.
    assert locale.localeconv()["decimal_point"] == "."


def test_leaves_the_rest_of_the_locale_alone():
    name = use_a_comma_decimal_locale()
    original_collate = locale.setlocale(locale.LC_COLLATE)

    restoreCNumericLocale()

    # Only LC_NUMERIC is at fault. Resetting LC_ALL would also revert sorting
    # and date formatting, which the user legitimately set.
    assert locale.setlocale(locale.LC_COLLATE) == original_collate
    assert name is not None


def test_is_safe_to_call_when_the_locale_is_already_c():
    locale.setlocale(locale.LC_NUMERIC, "C")

    restoreCNumericLocale()

    assert locale.localeconv()["decimal_point"] == "."
