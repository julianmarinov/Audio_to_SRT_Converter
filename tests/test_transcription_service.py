from transcription_service import _is_oom_error, _sanitize_filename


def test_is_oom_error_by_message():
    assert _is_oom_error(RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB"))
    assert _is_oom_error(RuntimeError("MPS backend out of memory (MPS allocated: ...)"))
    assert not _is_oom_error(ValueError("unrelated error"))


def test_is_oom_error_by_class_name():
    class OutOfMemoryError(Exception):
        pass

    assert _is_oom_error(OutOfMemoryError("generic"))


def test_sanitize_filename_replaces_illegal_chars():
    assert _sanitize_filename('a/b:c*d?"e') == "a_b_c_d__e"


def test_sanitize_filename_empty_falls_back():
    assert _sanitize_filename("   ") == "youtube_audio"
