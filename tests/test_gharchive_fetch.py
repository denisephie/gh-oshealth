# testing for gharchive_fetch

from oss_health.extract.gharchive_fetch import _iter_lines


def test_line_split_across_two_chunks():
    chunk = [b'{"a":1}\n{"b"', b":2}\n"]
    expected = [b'{"a":1}', b'{"b":2}']
    assert list(_iter_lines(chunk)) == expected


def test_chunk_ending_on_newline():
    chunk = [b'{"a":1}\n', b'{"b":2}\n']
    expected = [b'{"a":1}', b'{"b":2}']
    assert list(_iter_lines(chunk)) == expected


def test_no_trailing_newline():
    chunk = [b'{"a":1}\n{"b":2}']
    expected = [b'{"a":1}', b'{"b":2}']
    assert list(_iter_lines(chunk)) == expected


def test_chunk_with_no_newline():
    chunk = [b'{"a"', b":1", b"}\n"]
    expected = [b'{"a":1}']
    assert list(_iter_lines(chunk)) == expected


def test_several_lines_in_one_chunk():
    chunk = [b'{"a":1}\n{"b":2}\n{"c":3}\n']
    expected = [b'{"a":1}', b'{"b":2}', b'{"c":3}']
    assert list(_iter_lines(chunk)) == expected


def test_empty_input():
    chunk = []
    expected = []
    assert list(_iter_lines(chunk)) == expected
