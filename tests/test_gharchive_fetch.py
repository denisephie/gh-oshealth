# testing for gharchive_fetch
import gzip

from oss_health.extract.gharchive_fetch import _decompress, _iter_lines

# for _iter_lines


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


# for _decompress


def test_decompress_single_chunk():
    original = b'{"a":1}\n{"b":2}\n'
    compressed = gzip.compress(original)
    assert b"".join(list(_decompress([compressed]))) == original
    # noteL b"".join() is to piece the yielded parts back together


def test_decompress_split_chunks():
    original = b'{"a":1}\n{"b":2}\n'
    compressed = gzip.compress(original)
    chunks = [compressed[:10], compressed[10:25], compressed[25:]]  # list
    assert (
        b"".join(list(_decompress(chunks))) == original
    )  # don't ([chunks]) -> wrapping in a double list


def test_decompress_chained_w_iter_lines():
    original = b'{"a":1}\n{"b":2}\n{"c":3}\n'
    compressed = gzip.compress(original)
    chunks = [compressed[:10], compressed[10:25], compressed[25:]]
    result = list(_iter_lines(_decompress(chunks)))
    assert result == [b'{"a":1}', b'{"b":2}', b'{"c":3}']
