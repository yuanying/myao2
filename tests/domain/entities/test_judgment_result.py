"""Tests for JudgmentResult."""

import pytest

from myao2.domain.entities.judgment_result import JudgmentResult


class TestJudgmentResultCreation:
    """Tests for JudgmentResult creation."""

    def test_create_with_should_respond_true(self) -> None:
        """Test creation with should_respond=True."""
        result = JudgmentResult(
            should_respond=True,
            reason="User needs help",
        )

        assert result.should_respond is True
        assert result.reason == "User needs help"
        assert result.confidence == 1.0

    def test_create_with_should_respond_false(self) -> None:
        """Test creation with should_respond=False."""
        result = JudgmentResult(
            should_respond=False,
            reason="Active conversation",
        )

        assert result.should_respond is False
        assert result.reason == "Active conversation"
        assert result.confidence == 1.0

    def test_create_with_custom_confidence(self) -> None:
        """Test creation with custom confidence value."""
        result = JudgmentResult(
            should_respond=True,
            reason="Might be helpful",
            confidence=0.7,
        )

        assert result.should_respond is True
        assert result.reason == "Might be helpful"
        assert result.confidence == 0.7


class TestJudgmentResultImmutability:
    """Tests for JudgmentResult immutability."""

    def test_should_respond_is_immutable(self) -> None:
        """Test that should_respond cannot be modified."""
        result = JudgmentResult(
            should_respond=True,
            reason="Test",
        )

        with pytest.raises(AttributeError):
            result.should_respond = False  # type: ignore[misc]

    def test_reason_is_immutable(self) -> None:
        """Test that reason cannot be modified."""
        result = JudgmentResult(
            should_respond=True,
            reason="Test",
        )

        with pytest.raises(AttributeError):
            result.reason = "Modified"  # type: ignore[misc]

    def test_confidence_is_immutable(self) -> None:
        """Test that confidence cannot be modified."""
        result = JudgmentResult(
            should_respond=True,
            reason="Test",
        )

        with pytest.raises(AttributeError):
            result.confidence = 0.5  # type: ignore[misc]


class TestJudgmentResultDefaults:
    """Tests for JudgmentResult default values."""

    def test_default_confidence_is_one(self) -> None:
        """Test that default confidence is 1.0."""
        result = JudgmentResult(
            should_respond=True,
            reason="Test",
        )

        assert result.confidence == 1.0
