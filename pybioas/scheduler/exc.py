class ServerError(Exception):
    """ Internal server error """


class NotFoundError(RuntimeError):
    """
    Job with the given id not found.
    """


class SubmissionError(RuntimeError):
    """
    Job cannot be submitted by the Executor due to an external queue error.
    """


class JobRetrievalError(RuntimeError):
    """
    Job cannot be fetched from the queue due to an external queue error
    """
