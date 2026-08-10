from backends import Segment, TranscriptionResult
from chunking import Chunk, merge_results, should_chunk


def test_should_chunk_threshold():
    assert should_chunk(19 * 60) is False
    assert should_chunk(20 * 60) is False  # exactly at threshold, not over
    assert should_chunk(21 * 60) is True


def test_merge_results_offsets_timestamps_and_renumbers():
    chunk_a = Chunk(path="/tmp/a.wav", start_offset=0.0)
    chunk_b = Chunk(path="/tmp/b.wav", start_offset=900.0)  # 15:00 in

    result_a = TranscriptionResult(
        segments=[Segment(start=0.0, end=2.0, text="first"), Segment(start=2.0, end=4.0, text="second")],
        language="en",
    )
    result_b = TranscriptionResult(
        segments=[Segment(start=0.0, end=1.5, text="third")],
        language="en",
    )

    merged = merge_results([(chunk_a, result_a), (chunk_b, result_b)])

    assert len(merged.segments) == 3
    assert merged.segments[0].start == 0.0 and merged.segments[0].end == 2.0
    assert merged.segments[1].start == 2.0 and merged.segments[1].end == 4.0
    # chunk_b's segment must be offset by chunk_b.start_offset (900s)
    assert merged.segments[2].start == 900.0
    assert merged.segments[2].end == 901.5
    assert merged.segments[2].text == "third"
    assert merged.language == "en"


def test_merge_results_uses_first_chunks_language():
    chunk_a = Chunk(path="/tmp/a.wav", start_offset=0.0)
    chunk_b = Chunk(path="/tmp/b.wav", start_offset=100.0)
    result_a = TranscriptionResult(segments=[], language="fr")
    result_b = TranscriptionResult(segments=[], language="en")

    merged = merge_results([(chunk_a, result_a), (chunk_b, result_b)])
    assert merged.language == "fr"


def test_merge_results_empty_list():
    merged = merge_results([])
    assert merged.segments == []
    assert merged.language is None
