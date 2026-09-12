from docpilot.text_splitter import RecursiveTextSplitter


def test_splitter_respects_size_and_overlap() -> None:
    splitter = RecursiveTextSplitter(chunk_size=30, chunk_overlap=5)
    chunks = splitter.split_text("第一段内容。" * 20)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 30 for chunk in chunks)


def test_splitter_rejects_invalid_overlap() -> None:
    try:
        RecursiveTextSplitter(chunk_size=10, chunk_overlap=10)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("expected ValueError")
