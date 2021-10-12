def retry_call(f, exceptions=Exception, handler=None):
    while True:
        try:
            return f()
        except exceptions as e:
            if handler and handler(e):
                raise
