def example_selector(inputs):
    """
    Selector function reads the values that are about to be used to
    start the command line program and returns one of the service
    ids defined in the service configuration file.
    It is useful if you want to redirect the job to different
    execution engines or queues based on their size or complexity.

    :param inputs: parameter id to cmd parameter(s) mapping
    :type inputs: dict[str, str | list[str]]
    :return: selected runner id
    """
    return "local-queue"
