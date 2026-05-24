from hello import greet


def test_greet_world():
    assert greet("World") == "Hello, World!"


def test_greet_custom():
    assert greet("Cursor") == "Hello, Cursor!"
