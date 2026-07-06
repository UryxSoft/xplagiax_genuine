from app.infrastructure.parsers.scanned_pdf_detector import ScannedPdfDetector


def test_flags_low_density_text_as_scanned() -> None:
    detector = ScannedPdfDetector(min_chars_per_page=200)
    markdown = "short"  # 5 chars over many pages
    assert detector.is_scanned(markdown, page_count=10) is True


def test_does_not_flag_dense_text_as_scanned() -> None:
    detector = ScannedPdfDetector(min_chars_per_page=200)
    markdown = "x" * 5000
    assert detector.is_scanned(markdown, page_count=10) is False


def test_zero_pages_is_treated_as_scanned() -> None:
    detector = ScannedPdfDetector()
    assert detector.is_scanned("anything", page_count=0) is True
