"""Unit tests for format detection executor."""
import pytest

from app.harness.executors.detect_format import detect_format


class TestDetectFormat:
    def test_wbpro_detected_from_metadata_markers(self):
        """WBPRO detected when 3+ metadata markers present."""
        text = (
            "CONTRACTOR (Payee)\n"
            "Kynoch Construction Ltd\n"
            "Claim No. 1\n"
            "Period From: 18/08/25\n"
            "Period To: 31/08/25\n"
            "Payment Due: 20/09/25\n"
        )
        result = detect_format(text)
        assert result["format"] == "wbpro"
        assert result["confidence"] >= 0.9

    def test_wbpro_detected_from_section_headers(self):
        """WBPRO detected when section headers present."""
        text = (
            "Claim No. 1\n"
            "Period From: 01/01/25\n"
            "CONTRACT WORKS\n"
            "VARIATION WORKS\n"
        )
        result = detect_format(text)
        assert result["format"] == "wbpro"
        assert "CONTRACT WORKS" in result["markers_found"]
        assert "VARIATION WORKS" in result["markers_found"]

    def test_wbpro_needs_minimum_markers(self):
        """Only 1 marker is not enough for WBPRO."""
        text = "Claim No. 5\nSome random text\n"
        result = detect_format(text)
        assert result["format"] == "generic"

    def test_generic_fallback(self):
        """Unknown format falls back to generic."""
        text = "Invoice #123\nTotal: $5,000.00\n"
        result = detect_format(text)
        assert result["format"] == "generic"
        assert result["confidence"] <= 0.5

    def test_markers_found_populated(self):
        """markers_found lists which markers were detected."""
        text = (
            "Claim No. 3\n"
            "Period From: 01/01/25\n"
            "Period To: 31/01/25\n"
            "Payment Due: 15/02/25\n"
        )
        result = detect_format(text)
        assert "Claim No." in result["markers_found"]
        assert "Period From:" in result["markers_found"]
