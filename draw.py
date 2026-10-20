"""The random selection. No database and no UI in here, so it is easy to test."""
import secrets

_rng = secrets.SystemRandom()   # cryptographically secure randomness


def pick_winners(eligible_ids: list, k: int) -> list:
    """Pick k DIFFERENT ids, each equally likely (uniform, without replacement)."""
    if len(eligible_ids) < k:
        raise ValueError(f"Need at least {k} eligible employees, found {len(eligible_ids)}.")
    return _rng.sample(list(eligible_ids), k)
