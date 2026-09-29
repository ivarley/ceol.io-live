"""
Fractional Indexing for CRDT-compatible list ordering.

Uses base-62 strings (0-9, A-Z, a-z) with lexicographic ordering to allow
insertions between any two positions without renumbering existing items.

Requires COLLATE "C" on the database column to ensure byte-order sorting,
which gives predictable order: 0-9 < A-Z < a-z.
"""

from typing import Optional

# Base-62 alphabet: digits, uppercase, lowercase (requires COLLATE "C" in PostgreSQL)
# Sorted by ASCII byte value: 0-9 (48-57), A-Z (65-90), a-z (97-122)
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = len(ALPHABET)  # 62
MIDPOINT = BASE // 2  # 31, which is 'V'
START_CHAR = "V"  # Start in the middle to leave room for insertions before


def _char_to_int(c: str) -> int:
    """Convert alphabet character to integer (0-61)."""
    return ALPHABET.index(c)


def _int_to_char(i: int) -> str:
    """Convert integer (0-61) to alphabet character."""
    return ALPHABET[i]


def generate_append_position(last_position: Optional[str]) -> str:
    """
    Generate a position for appending to the end of a list.

    Simply increments the last character, extending if needed.

    Examples:
        >>> generate_append_position(None)
        'V'
        >>> generate_append_position('V')
        'W'
        >>> generate_append_position('z')
        'zV'  (extends with the midpoint char, leaving room for inserts before)
    """
    if last_position is None or last_position == "":
        return START_CHAR

    # Try to increment the last character
    last_char = last_position[-1]
    last_val = _char_to_int(last_char)

    if last_val < BASE - 1:
        # Can increment last character
        return last_position[:-1] + _int_to_char(last_val + 1)
    else:
        # Last character is 'z', extend with midpoint (not '0')
        # Using midpoint leaves room for insertions before this position
        # e.g., 'z' -> 'zV' allows inserting 'z0'-'zU' before it
        return last_position + _int_to_char(MIDPOINT)


def generate_position_between(
    before: Optional[str],
    after: Optional[str]
) -> str:
    """
    Generate a position between two existing positions.

    Finds the exact midpoint. If positions are adjacent, extends with midpoint char.

    Examples:
        >>> generate_position_between(None, 'V')
        'A'  (midpoint between start and 'V')
        >>> generate_position_between('V', 'X')
        'W'
        >>> generate_position_between('V', 'W')
        'VV'  (no room, so extend with midpoint)
    """
    # Handle edge cases
    if before is None and after is None:
        return START_CHAR

    if before is None:
        # Inserting at the very start
        first_val = _char_to_int(after[0])
        if first_val > 0:
            # Use midpoint between 0 and first char
            mid = first_val // 2
            if mid > 0:
                return _int_to_char(mid)
            else:
                # first_val is 1, extend: '0' + midpoint
                return "0" + _int_to_char(MIDPOINT)
        else:
            # First char is '0', go deeper. A key of only '0's has nothing below it:
            # '00' < '0', so the old answer here ('0V') sorted AFTER the key it was
            # meant to precede.
            if len(after) == 1:
                raise ValueError("No position below a key of only 0s")
            else:
                return "0" + generate_position_between(None, after[1:])

    if after is None:
        # Inserting at the end - just append
        return generate_append_position(before)

    # Validate ordering
    if before >= after:
        raise ValueError(f"Invalid ordering: before='{before}' must be < after='{after}'")

    return _midpoint(before, after)


def _generate_before(after: str) -> str:
    """Generate a position before the given position, starting from minimum.

    This is used when we need to insert before a position where there's no
    explicit 'before' position (conceptually inserting at the start of a suffix).

    Examples:
        _generate_before('5') -> '2'  (midpoint of 0-5)
        _generate_before('1') -> '0V'  (can't go below 0, so extend)
        _generate_before('0V') -> '0A'  (midpoint of 0-V at second level)
        _generate_before('0') -> ValueError  (nothing sorts below '0': for a prefix
                                              'A', no key lies between 'A' and 'A0')
    """
    if not after:
        return _int_to_char(MIDPOINT)

    first_val = _char_to_int(after[0])

    if first_val > 1:
        # There's room for a midpoint
        return _int_to_char(first_val // 2)
    elif first_val == 1:
        # '1' at this level - midpoint is 0, so use '0' + recurse
        return ALPHABET[0] + _generate_before(after[1:] if len(after) > 1 else "")
    else:
        # '0' at this level - need to go deeper
        if len(after) > 1:
            return ALPHABET[0] + _generate_before(after[1:])
        else:
            # Just '0': nothing sorts below it. Extending ('0V') would sort AFTER it.
            raise ValueError("No position below a key of only 0s")


def _midpoint(before: str, after: str) -> str:
    """Find midpoint between two positions."""
    # Handle special case: before is a proper prefix of after
    # e.g., before='V' and after='VW' - we need to insert between them
    if after.startswith(before) and len(after) > len(before):
        # Get the suffix of after beyond before
        suffix = after[len(before):]
        # Recursively find midpoint between empty and suffix
        # This handles cases like before='A', after='A5' -> 'A2'
        # before='A', after='A0' has no answer and raises (see _generate_before)
        inner_mid = _generate_before(suffix)
        return before + inner_mid

    # Pad to same length for easier comparison
    max_len = max(len(before), len(after))
    b = before.ljust(max_len, ALPHABET[0])
    a = after.ljust(max_len, ALPHABET[0])

    # Find first differing position
    diff_idx = 0
    while diff_idx < max_len and b[diff_idx] == a[diff_idx]:
        diff_idx += 1

    if diff_idx == max_len:
        # Shouldn't happen if before < after
        raise ValueError(f"Positions are equal: {before} and {after}")

    before_val = _char_to_int(b[diff_idx])
    after_val = _char_to_int(a[diff_idx])

    # Check if there's room between them
    if after_val - before_val > 1:
        # There's a gap - use the midpoint
        # Use padded 'b' to handle case where before is shorter than diff_idx
        # e.g., before='a', after='a0i', diff_idx=2 → return 'a09' not 'a9'
        mid_val = (before_val + after_val) // 2
        return b[:diff_idx] + _int_to_char(mid_val)
    else:
        # Adjacent characters: no room at this index. Every key that fits shares
        # before's prefix through diff_idx and then sorts above before's own
        # suffix -- so bisect between that suffix and the top of the alphabet,
        # the mirror of _generate_before.
        #   before='ni', after='o'  → 'nr'  (midpoint of 'i'..top under 'n')
        #   before='a',  after='a1' → 'a0V' (padded prefix 'a0', empty suffix)
        # The old answer simply appended 'V' to `before`, which is correct but
        # wastes all the room in the suffix: inserting repeatedly in the same
        # gap grew the key by one character PER INSERT ('V','VV','VVV',...),
        # and the segmenter -- which logs every tune after the last one, before
        # the same follower -- hit the column's 32-character limit on the 32nd
        # tune of a session. This keeps growth to about one character per five.
        return b[:diff_idx + 1] + _generate_after(before[diff_idx + 1:])


def _generate_after(before: str) -> str:
    """Generate a position after `before` under the same prefix, bisecting
    toward the top of the alphabet (the mirror of _generate_before).

    Examples:
        _generate_after('')   -> 'V'   (nothing to clear: the midpoint)
        _generate_after('i')  -> 'r'   (midpoint of 'i'..top)
        _generate_after('y')  -> 'z'
        _generate_after('z')  -> 'zV'  (nothing above 'z' at this level: go deeper)
        _generate_after('zz') -> 'zzV'
    """
    if not before:
        return _int_to_char(MIDPOINT)

    first_val = _char_to_int(before[0])
    if first_val < BASE - 1:
        # (first_val + BASE) // 2 > first_val whenever first_val <= BASE - 2, and a
        # larger first character beats any suffix `before` may carry.
        return _int_to_char((first_val + BASE) // 2)
    # 'z' at this level: keep it and find room in the next.
    return ALPHABET[-1] + _generate_after(before[1:])


def validate_position(position: str) -> bool:
    """Check if a position string is valid.

    A trailing '0' is invalid: no key could ever be placed immediately before one
    ('A' < 'A0' with nothing between). Nothing here generates such a key."""
    if not position or not isinstance(position, str):
        return False
    if position.endswith("0"):
        return False
    return all(c in ALPHABET for c in position)
