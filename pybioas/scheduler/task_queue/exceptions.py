# noinspection PyShadowingBuiltins
class ConnectionError(OSError):
    """ Connection error. """
    def __init__(self, *args, **kwargs):
        pass


# noinspection PyShadowingBuiltins
class ConnectionAbortedError(ConnectionError):
    """ Connection aborted. """
    def __init__(self, *args, **kwargs):
        pass
