class ValidationError(ValueError):

    def __init__(self, code, reason):
        """
        :param code: short error code
        :param reason: description of the error
        """
        super().__init__(code, reason)

    @property
    def code(self):
        return self.args[0]

    @property
    def reason(self):
        return self.args[1]
