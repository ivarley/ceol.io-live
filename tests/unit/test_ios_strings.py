"""Spec 057: every string in the iOS app's String Catalog has Irish.

The catalog (ios/Ceol/Ceol/Localizable.xcstrings) is synced from the app's build by
`make ios-strings`, which also applies the Irish in ios/Ceol/i18n-ga/*.json. This
fails when a catalog string with words in it has no Irish. (`make ios-test` checks the
other half: that every string the build extracts is in the catalog or a fragment.)
"""

import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location("ios_strings", os.path.join(ROOT, "scripts", "ios_strings.py"))
ios_strings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ios_strings)


def test_every_catalog_string_has_irish():
    missing = ios_strings.catalog_missing()
    assert not missing, f"no Irish in Localizable.xcstrings (make ios-strings after adding it to ios/Ceol/i18n-ga): {missing[:20]}"


def test_bare_specifiers_need_no_irish():
    assert not ios_strings.needs_irish("%@ · %@")
    assert not ios_strings.needs_irish("%1$lld / %2$lld")
    assert ios_strings.needs_irish("%lld tunes")
