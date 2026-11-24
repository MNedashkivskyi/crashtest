"""Every shipped cheat must pass its vuln/hardened fixture triplet.

This is the false-positive guard from the spec: release is blocked if any cheat
fails. Runs in plain pytest, no Harbor, no network.
"""

import pytest

from crashtest.registry import all_cheats
from crashtest.selftest import check_cheat

_CHEATS = all_cheats()


@pytest.mark.parametrize("cheat", _CHEATS, ids=[c.id for c in _CHEATS])
def test_cheat_fixture_triplet(cheat):
    results = check_cheat(cheat)
    failures = [r for r in results if not r.ok]
    assert not failures, "; ".join(f"{r.point}: {r.detail}" for r in failures)


def test_catalog_is_nonempty():
    assert _CHEATS, "no cheats discovered"
