from fastapi import HTTPException
import pytest

from app.api.dependencies import _require_api_key
from app.config import settings


def test_timing_safe_api_key_mismatch_various_prefixes():
    settings.API_KEY = "secretAPIkey123"
    correct = settings.API_KEY

    mismatches = []
    # Create mismatches that share increasing prefix lengths with the correct key
    for i in range(len(correct)):
        # pick a different character than the one at position i
        diff_char = "!" if correct[i] != "!" else "?"
        mismatches.append(correct[:i] + diff_char + "-suffix")

    # Also test a longer key with correct prefix
    mismatches.append(correct + "-extra")

    for key in mismatches:
        with pytest.raises(HTTPException) as exc:
            _require_api_key(key)
        assert exc.value.status_code == 401
