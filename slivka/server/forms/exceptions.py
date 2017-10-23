class ValidationError(ValueError):
    """
    :param code: short error code
    :param reason: description of the error
    """

    def __init__(self, code, reason):
        super().__init__(code, reason)

    @property
    def code(self):
        """Error code."""
        return self.args[0]

    @property
    def reason(self):
        """Reason for validation error."""
        return self.args[1]
