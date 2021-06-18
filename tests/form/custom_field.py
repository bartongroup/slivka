from slivka.server.forms.fields import BaseField


class CustomField(BaseField):
    def __init__(self, id, alpha, bravo=None, **kwargs):
        super().__init__(id, **kwargs)
        self.alpha = alpha
        self.bravo = bravo
