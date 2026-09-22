class Button:
    def __init__(self, text="", icon=None, on_click=None):
        self.text, self.icon, self.on_click = text, icon, on_click


class TextInput:
    def __init__(self, label="", placeholder="", default_value=None):
        self.label = label


class ActionForm:
    def __init__(self, title="", content="", buttons=None, on_submit=None, on_close=None):
        self.title, self.content, self.buttons = title, content, buttons or []


class ModalForm:
    def __init__(self, title="", controls=None, submit_button=None, icon=None, on_submit=None):
        self.title, self.controls, self.on_submit = title, controls or [], on_submit
