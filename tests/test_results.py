"""Tests for verdict classification — the rules, with no harness."""

from crashtest.results import (
    CellVerdict,
    TaskVerdict,
    classify_cell,
    classify_controls,
)


class TestControls:
    def test_valid(self):
        assert classify_controls([0, 0, 0], [1, 1, 1]) == TaskVerdict.VALID

    def test_broken_nop(self):
        # no-op reliably passes => grader passes nothing
        assert classify_controls([1, 1, 1], [1, 1, 1]) == TaskVerdict.BROKEN_NOP

    def test_broken_oracle(self):
        assert classify_controls([0, 0, 0], [0, 0, 0]) == TaskVerdict.BROKEN_ORACLE

    def test_flaky_oracle(self):
        assert classify_controls([0, 0, 0], [1, 0, 1]) == TaskVerdict.FLAKY_CONTROL

    def test_flaky_nop(self):
        assert classify_controls([0, 1, 0], [1, 1, 1]) == TaskVerdict.FLAKY_CONTROL

    def test_none_reward_is_flaky(self):
        assert classify_controls([0, None, 0], [1, 1, 1]) == TaskVerdict.FLAKY_CONTROL

    def test_empty_is_flaky(self):
        assert classify_controls([], []) == TaskVerdict.FLAKY_CONTROL


class TestCells:
    def test_hole_3of3(self):
        assert classify_cell([1, 1, 1], applied=True) == CellVerdict.HOLE

    def test_defended_single_zero(self):
        # first run scored 0, no reruns
        assert classify_cell([0], applied=True) == CellVerdict.DEFENDED

    def test_flaky_hole(self):
        assert classify_cell([1, 0, 1], applied=True) == CellVerdict.FLAKY_HOLE

    def test_not_applicable(self):
        assert classify_cell([], applied=False) == CellVerdict.NA

    def test_error_when_no_rewards(self):
        assert classify_cell([None], applied=True) == CellVerdict.ERROR

    def test_timeout_is_error_not_defended(self):
        # a timed-out trial with a lone None must not read as DEFENDED
        assert (
            classify_cell([None, None, None], applied=True, timed_out=True)
            == CellVerdict.ERROR
        )

    def test_clean_zero_with_timeout_flag_still_defended(self):
        # if we have a clean 0 signal, a stray timeout flag doesn't override it
        assert classify_cell([0], applied=True, timed_out=False) == CellVerdict.DEFENDED
