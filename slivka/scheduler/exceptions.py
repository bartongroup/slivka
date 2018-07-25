class QueueError(RuntimeError):
    """
    Superclass of all queue related error statuses
    """


class JobNotFoundError(QueueError):
    """
    Job with the given id not found.
    """


class QueueBrokenError(QueueError):
    """
    Error raised when the queue is broken and all other requests for resource
    will fail.
    """


class ServerError(QueueBrokenError):
    """
    Internal server error
    """


class QueueTemporarilyUnavailableError(QueueError):
    """
    Exception raised when the queue is temporarily not available but resource
    will be accessible in the future
    """
