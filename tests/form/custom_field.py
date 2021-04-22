from slivka.server.forms import auto_schema
from slivka.server.forms.fields import BaseField


@auto_schema
class CustomField(BaseField):
    def __init__(self, name, alpha, bravo=None, **kwargs):
        super().__init__(name, **kwargs)
        self.alpha = alpha
        self.bravo = bravo
