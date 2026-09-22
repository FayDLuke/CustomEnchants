class Plugin:
    def __init__(self):
        self._config = {}
        self.logger = _Logger()

    def save_default_config(self):
        pass

    def reload_config(self):
        return self._config

    @property
    def data_folder(self):
        return "."


class _Logger:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
