# useful.py
"""I'm a useful module."""

some_variable = "foobar"
new_variable = 'I am new!'

def boo() -> None:
    return 42



def test():
    assert boo() == 42

print('I am outside.')

if __name__ == "__main__":
    print("Running tests...")
    test()
    print("OK")
