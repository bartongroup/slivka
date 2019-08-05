from itertools import starmap

from markupsafe import Markup, escape


def html_attrs(attrs):
    attributes = []
    for key, value in attrs.items():
        if value is False or value is None:
            continue
        if value is True:
            attributes.append('{}="{}"'.format(key, escape(key)))
        else:
            attributes.append('{}="{}"'.format(key, escape(value)))
    return str.join(' ', attributes)


class BaseWidget:
    def __init__(self, name):
        self.name = name
        self.attrs = {}

    def __call__(self, **kwargs):
        return self.render(kwargs)

    def render(self, attrs):
        raise NotImplementedError

    def __setitem__(self, key, val):
        self.attrs[key] = val

    def __str__(self):
        return self()

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, str(self))

    def __html__(self):
        return str(self)


class InputWidget(BaseWidget):
    input_type = 'text'

    def __init__(self, name, value='', attrs=()):
        super().__init__(name)
        self.value = value
        self.attrs.update(attrs)

    def render(self, attrs=()):
        attributes = self.attrs.copy()
        attributes.update(attrs, name=self.name)
        attributes.setdefault('type', self.input_type)
        return Markup("<input %s>" % html_attrs(attributes))


class TextInputWidget(InputWidget):
    input_type = 'text'


class NumberInputWidget(InputWidget):
    input_type = 'number'


class HiddenInputWidget(InputWidget):
    input_type = 'hidden'


class CheckboxInputWidget(InputWidget):
    input_type = 'checkbox'


class FileInputWidget(InputWidget):
    input_type = 'file'


class SelectWidget(BaseWidget):
    def __init__(self, name, options=(), attrs=()):
        super().__init__(name)
        if isinstance(options, dict):
            options = list(options.items())
        self.options = options
        self.attrs.update(attrs)

    def render(self, attrs=()):
        attributes = self.attrs.copy()
        attributes.update(attrs, name=self.name)
        html = ["<select %s>" % html_attrs(attributes)]
        html.extend(starmap(self.html_option, self.options))
        html.append("</select>")
        return Markup(str.join('', html))

    @staticmethod
    def html_option(label, value, attrs=()):
        attrs = dict(attrs, value=value)
        return Markup(
            '<option {}>{}</option>'.format(html_attrs(attrs), escape(label))
        )


class ContentTypeFileWidget(BaseWidget):
    def __init__(self,
                 name,
                 types=(),
                 media_type_suffix='-media-type',
                 attrs=()):
        super().__init__(name)
        self.attrs.update(attrs)
        self.file_input = FileInputWidget(name, attrs)
        self.content_type_select = SelectWidget(
            name + media_type_suffix, types
        )

    def render(self, attrs=()):
        return (self.file_input.render(attrs) +
                self.content_type_select.render(attrs))
