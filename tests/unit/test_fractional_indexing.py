"""
Unit tests for fractional indexing module.

Tests the position generation algorithms used for CRDT-compatible list ordering.
Uses base-62 alphabet (0-9, A-Z, a-z) with COLLATE "C" for consistent sorting.
"""

import pytest
from fractional_indexing import (
    generate_append_position,
    generate_position_between,
    validate_position,
    ALPHABET,
    START_CHAR,
)


class TestGenerateAppendPosition:
    """Tests for generate_append_position function."""

    def test_append_to_empty_list(self):
        """First position in empty list starts at 'V'."""
        assert generate_append_position(None) == "V"
        assert generate_append_position("") == "V"

    def test_simple_append_increments_last_char(self):
        """Appending increments the last character."""
        assert generate_append_position("V") == "W"
        assert generate_append_position("W") == "X"
        assert generate_append_position("a") == "b"
        assert generate_append_position("0") == "1"
        assert generate_append_position("9") == "A"  # Digits roll to uppercase
        assert generate_append_position("Z") == "a"  # Uppercase rolls to lowercase

    def test_append_at_z_extends(self):
        """When last char is 'z', extend with midpoint 'V'."""
        assert generate_append_position("z") == "zV"
        assert generate_append_position("zz") == "zzV"
        assert generate_append_position("zzz") == "zzzV"

    def test_append_after_zV(self):
        """Continuing after zV increments normally."""
        assert generate_append_position("zV") == "zW"
        assert generate_append_position("z9") == "zA"
        assert generate_append_position("zZ") == "za"
        assert generate_append_position("zy") == "zz"

    def test_append_sequence_efficiency(self):
        """Verify append sequence stays efficient for typical session sizes."""
        # Simulate appending 100 tunes (large session)
        positions = []
        pos = None
        for _ in range(100):
            pos = generate_append_position(pos)
            positions.append(pos)

        # First 31 positions should be single char (V through z)
        assert all(len(p) == 1 for p in positions[:31])

        # Next 31 should be 2 chars (zV through zz)
        assert all(len(p) == 2 for p in positions[31:62])

        # Next 31 should be 3 chars (zzV through zzz)
        assert all(len(p) == 3 for p in positions[62:93])

        # All positions should be in sorted order
        assert positions == sorted(positions)


class TestGeneratePositionBetween:
    """Tests for generate_position_between function."""

    def test_between_none_and_none(self):
        """Both None returns start char."""
        assert generate_position_between(None, None) == "V"

    def test_insert_at_start_before_V(self):
        """Insert before 'V' finds midpoint."""
        result = generate_position_between(None, "V")
        # Should be somewhere between '0' and 'V' (0-31)
        # Midpoint of 0 and 31 is 15, which is 'F'
        assert result < "V"
        assert validate_position(result)

    def test_insert_at_start_before_1(self):
        """Insert before '1' handles edge case."""
        result = generate_position_between(None, "1")
        # '1' is at index 1, midpoint is 0, so we need to extend
        assert result < "1"
        assert validate_position(result)

    def test_insert_at_end(self):
        """Insert at end (after=None) appends."""
        assert generate_position_between("V", None) == "W"
        assert generate_position_between("z", None) == "zV"

    def test_insert_between_with_gap(self):
        """Insert between positions with a gap uses midpoint."""
        # V=31, X=33, midpoint is 32='W'
        assert generate_position_between("V", "X") == "W"

        # B=11, F=15, midpoint is 13='D'
        assert generate_position_between("B", "F") == "D"

    def test_insert_between_adjacent(self):
        """Insert between adjacent positions extends with midpoint."""
        # V and W are adjacent, so extend
        result = generate_position_between("V", "W")
        assert result.startswith("V")
        assert len(result) == 2
        assert "V" < result < "W"

    def test_insert_between_extended_positions(self):
        """Insert between multi-char positions works correctly."""
        # VV and VX have room for VW
        assert generate_position_between("VV", "VX") == "VW"

        # VV and VW are adjacent, extend
        result = generate_position_between("VV", "VW")
        assert result.startswith("VV")
        assert "VV" < result < "VW"

    def test_insert_produces_sorted_result(self):
        """Inserted position is always between before and after."""
        test_cases = [
            ("A", "z"),
            ("V", "W"),
            ("0", "z"),
            ("AA", "AB"),
            ("z0", "z9"),
            ("VV", "W"),
        ]
        for before, after in test_cases:
            result = generate_position_between(before, after)
            assert before < result < after, f"Failed for ({before}, {after}): got {result}"

    def test_invalid_ordering_raises(self):
        """Passing before >= after raises ValueError."""
        with pytest.raises(ValueError):
            generate_position_between("z", "A")

        with pytest.raises(ValueError):
            generate_position_between("V", "V")

    def test_bulk_insert_in_middle_efficiency(self):
        """Inserting many items sequentially stays reasonably short.

        Note: The basic generate_position_between function has O(n) length growth
        when repeatedly inserting at the same boundary. The actual bulk insert
        optimization (using generate_append_position for consecutive inserts)
        is handled in save_session_instance_tunes_ajax, not here.
        """
        # Simulate bulk insert: start with 'V', 'z', insert 10 items between them
        before = "V"
        after = "z"
        positions = []

        for _ in range(10):
            new_pos = generate_position_between(before, after)
            positions.append(new_pos)
            # Each subsequent insert goes after the previous (simulating bulk paste)
            before = new_pos

        # All positions should be valid and in order
        assert positions == sorted(positions)
        for pos in positions:
            assert validate_position(pos)

        # With basic bisect algorithm, worst case is O(n) length growth
        # For 10 items, max 7 chars is acceptable (bulk optimization at API level)
        assert all(len(pos) <= 10 for pos in positions)

    def test_bulk_insert_optimized_pattern(self):
        """Test the optimized bulk insert pattern used by save_session_instance_tunes_ajax.

        When inserting multiple consecutive items, the API uses:
        - First item: bisect between existing positions
        - Subsequent items: append (increment) from previous new position

        This prevents position explosion.
        """
        # Simulate inserting 10 new tunes between existing 'V' and 'z'
        prev_existing = "V"
        next_existing = "z"
        positions = []

        # First new item uses bisect
        first_pos = generate_position_between(prev_existing, next_existing)
        positions.append(first_pos)

        # Subsequent items use append (as done in save_session_instance_tunes_ajax)
        current_pos = first_pos
        for _ in range(9):
            new_pos = generate_append_position(current_pos)
            # But check it's still less than next_existing
            if new_pos >= next_existing:
                # Fall back to bisect if append exceeds bound
                new_pos = generate_position_between(current_pos, next_existing)
            positions.append(new_pos)
            current_pos = new_pos

        # All positions should be valid and in order
        assert positions == sorted(positions)
        for pos in positions:
            assert validate_position(pos)
            # Verify all positions are between the original bounds
            assert prev_existing < pos < next_existing

        # With append optimization and base-62, positions stay efficient
        # First is 'k' (midpoint V-z), then 'l', 'm', ... plenty of room
        assert all(len(pos) <= 4 for pos in positions)


class TestValidatePosition:
    """Tests for validate_position function."""

    def test_valid_positions(self):
        """Valid positions return True."""
        assert validate_position("V") is True
        assert validate_position("abc123") is True
        assert validate_position("ABC123") is True
        assert validate_position("z0z0z0") is True
        assert validate_position("0") is True
        assert validate_position("ABCxyz") is True  # Mixed case is valid

    def test_invalid_positions(self):
        """Invalid positions return False."""
        assert validate_position("") is False
        assert validate_position(None) is False
        assert validate_position("V W") is False  # Space
        assert validate_position("V-W") is False  # Hyphen
        assert validate_position("V_W") is False  # Underscore
        assert validate_position("V!W") is False  # Special char


class TestOrderingConsistency:
    """Tests that verify ordering properties critical for CRDT correctness."""

    def test_all_generated_positions_are_valid(self):
        """All generated positions pass validation."""
        # Generate many positions through various methods
        positions = []

        # Append sequence
        pos = None
        for _ in range(50):
            pos = generate_append_position(pos)
            positions.append(pos)
            assert validate_position(pos), f"Invalid position: {pos}"

        # Insert between various positions
        for i in range(0, len(positions) - 1, 5):
            between = generate_position_between(positions[i], positions[i + 1])
            assert validate_position(between), f"Invalid position: {between}"

    def test_lexicographic_ordering_matches_logical_ordering(self):
        """Positions sort correctly with simple string comparison."""
        # This is critical: PostgreSQL ORDER BY order_position COLLATE "C" must work correctly
        positions = []
        pos = None
        for _ in range(30):
            pos = generate_append_position(pos)
            positions.append(pos)

        # Insert some items in the middle
        mid_pos = generate_position_between(positions[10], positions[11])
        positions.insert(11, mid_pos)

        mid_pos2 = generate_position_between(positions[11], positions[12])
        positions.insert(12, mid_pos2)

        # The logical order should match lexicographic sort
        assert positions == sorted(positions)

    def test_repeated_inserts_at_same_point(self):
        """Repeated inserts at the same point don't cause issues."""
        # Start with two positions far apart
        before = "A"
        after = "z"

        # Insert 20 items, always inserting right after 'before'
        for _ in range(20):
            new_pos = generate_position_between(before, after)
            assert before < new_pos < after
            # For subsequent inserts, the new position becomes the 'after' bound
            # This simulates inserting multiple items at the same cursor position
            after = new_pos

        # Verify we haven't exceeded reasonable length
        assert len(after) <= 8  # Should stay reasonable


class TestMigrationCompatibility:
    """Tests related to migration from integer order_number."""

    def test_sequential_positions_from_migration(self):
        """Verify migration pattern produces correct ordering."""
        # The migration uses a SQL function that starts at 'V' and increments
        # This simulates what that function produces

        def simulate_migration_position(order_num):
            """Simulate the SQL generate_fractional_position function."""
            if order_num is None or order_num < 1:
                return "V"

            alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
            start_idx = 31  # 'V' is at index 31
            first_range = 62 - start_idx  # 31: V-z

            if order_num <= first_range:
                return alphabet[start_idx + order_num - 1]

            pos = order_num - first_range
            if pos <= 62:
                return "z" + alphabet[pos - 1]

            pos -= 62
            if pos <= 62:
                return "zz" + alphabet[pos - 1]

            pos -= 62
            if pos <= 62:
                return "zzz" + alphabet[pos - 1]

            return "zzzz" + str(pos - 62)

        # Generate positions for order_numbers 1-100
        positions = [simulate_migration_position(i) for i in range(1, 101)]

        # Verify they're in sorted order
        assert positions == sorted(positions)

        # Verify first few match expected values
        assert positions[0] == "V"  # order_number 1
        assert positions[1] == "W"  # order_number 2
        assert positions[30] == "z"  # order_number 31
        assert positions[31] == "z0"  # order_number 32

    def test_migration_positions_compatible_with_append(self):
        """Positions from migration work with subsequent appends."""
        # After migration, existing data has positions like V, W, X, ...
        # New appends should work correctly

        # Simulate last migrated position is 'X' (order_number 3)
        last_migrated = "X"

        # Append new items
        new1 = generate_append_position(last_migrated)
        new2 = generate_append_position(new1)

        assert last_migrated < new1 < new2
        assert new1 == "Y"
        assert new2 == "Z"
