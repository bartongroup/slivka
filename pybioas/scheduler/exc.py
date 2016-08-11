# noinspection PyShadowingBuiltins
class ConnectionError(OSError):
    """ Connection error. """


# noinspection PyShadowingBuiltins
class ConnectionResetError(ConnectionError):
    """ Connection reset. """


class ServerError(Exception):
    """ Internal server error """


class SubmissionError(RuntimeError):
    """
    Job cannot be submitted by the Executor due to an external queue error.
    """


class JobRetrievalError(RuntimeError):
    """
    Job cannot be fetched from the queue due to an external queue error
    """
