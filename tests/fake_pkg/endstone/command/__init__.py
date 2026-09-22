class CommandSenderWrapper:
    def __init__(self, wrapped, on_message=None, on_error=None):
        self.wrapped = wrapped
        self.on_message = on_message
        self.on_error = on_error
