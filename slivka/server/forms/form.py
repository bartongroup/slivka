import collections
from collections import OrderedDict
from tempfile import mkstemp

from frozendict import frozendict
from werkzeug.datastructures import MultiDict

import slivka
from slivka.db.documents import UploadedFile, JobRequest
from slivka.utils import Singleton
from .fields import *


class DeclarativeFormMetaclass(type):
    @classmethod
    def __prepare__(mcs, name, bases):
        return OrderedDict()

    def __new__(mcs, name, bases, attrs):
        fields = OrderedDict()
        for key, field in list(attrs.items()):
            if isinstance(field, BaseField):
                fields[field.name] = field
                attrs.pop(key)
        attrs['fields'] = fields
        return super().__new__(mcs, name, bases, attrs)


class BaseForm(metaclass=DeclarativeFormMetaclass):
    service = ''

    def __init__(self, data=None, files=None):
        self.is_bound = not (data is None and files is None)
        self.data = MultiDict() if data is None else data
        self.files = MultiDict() if files is None else files
        self._errors = None
        self._cleaned_data = frozendict()

    @property
    def errors(self) -> collections.Mapping:
        if self._errors is None:
            self.full_clean()
        return self._errors

    @property
    def cleaned_data(self) -> collections.Mapping:
        return self._cleaned_data

    def is_valid(self):
        return self.is_bound and not self.errors

    def full_clean(self):
        errors = {}
        if not self.is_bound:
            return
        cleaned_data = {}
        for name, field in self.fields.items():
            value = field.value_from_request_data(self.data, self.files)
            try:
                value = field.validate(value)
                cleaned_data[name] = value
                if value is not None and isinstance(field, FileField):
                    assert isinstance(value, FileWrapper)
                    # If no validator has checked for the type we need
                    # to check here whether it's allowed on the server.
                    media_type = value.get_detected_media_type()
                    if not media_type:
                        raise ValidationError(
                            'File content does not match %s '
                            'or this media type is not allowed' % value.media_type,
                            'invalid'
                        )
            except ValidationError as err:
                errors[field.name] = err
        self._errors = frozendict(errors)
        self._cleaned_data = frozendict(cleaned_data)

    def __iter__(self):
        return iter(self.fields.values())

    def __getitem__(self, item):
        return self.fields[item]

    def save(self, database):
        if not self.is_valid():
            raise RuntimeError(self.errors, 'invalid_form')
        inputs = []
        uploaded_files = []
        for name, field in self.fields.items():
            value = self.cleaned_data[name]
            if value is not None and isinstance(field, FileField):
                assert isinstance(value, FileWrapper)
                # make sure that the type was detected by full_clean
                assert value.get_detected_media_type()
                if value.uuid is None:
                    (fd, path) = mkstemp(dir=slivka.settings.UPLOADS_DIR)
                    with open(fd, 'wb') as fp:
                        value.save_as(fp, path=path)
                    uploaded_files.append(UploadedFile(
                        title=value.title,
                        path=path,
                        media_type=value.get_detected_media_type()
                    ))
            param = field.to_cmd_parameter(value)
            inputs.append((name, param))
        request = JobRequest(service=self.service, inputs=inputs)
        request.insert(database)
        for file in uploaded_files:
            file.insert(database)
        return request


class FormLoader(metaclass=Singleton):
    def __init__(self):
        self._forms = {
            service: self._build_form_class(service, conf.form)
            for service, conf in slivka.settings.service_configurations.items()
        }

    def get_form_class(self, service):
        return self[service]

    def __getitem__(self, item):
        return self._forms[item]

    def _build_form_class(self, service, json_data):
        attrs = OrderedDict((name, self._build_field(name, data))
                            for name, data in json_data.items())
        attrs['service'] = service
        cls = DeclarativeFormMetaclass(
            service.capitalize() + 'Form',
            (BaseForm,),
            attrs
        )
        return cls

    @staticmethod
    def _build_field(name, field_meta):
        value_meta = field_meta['value']
        field_type = value_meta['type']
        common_kwargs = {
            'name': name,
            'label': field_meta['label'],
            'description': field_meta.get('description'),
            'default': value_meta.get('default'),
            'required': value_meta.get('required', True)
        }
        if field_type == 'int':
            return IntegerField(
                **common_kwargs,
                min=value_meta.get('min'),
                max=value_meta.get('max')
            )
        elif field_type == 'float' or field_type == 'decimal':
            return DecimalField(
                **common_kwargs,
                min=value_meta.get('min'),
                max=value_meta.get('max'),
                min_exclusive=value_meta.get('min-exclusive', False),
                max_exclusive=value_meta.get('max-exclusive', False)
            )
        elif field_type == 'text':
            return TextField(
                **common_kwargs,
                min_length=value_meta.get('min-length'),
                max_length=value_meta.get('max-length')
            )
        elif field_type == 'boolean' or field_type == 'flag':
            return FlagField(
                **common_kwargs
            )
        elif field_type == 'choice':
            return ChoiceField(
                **common_kwargs,
                choices=value_meta.get('choices')
            )
        elif field_type == 'file':
            return FileField(
                **common_kwargs,
                extensions=value_meta.get('extensions', ()),
                media_type=value_meta.get('media-type')
            )
        else:
            raise RuntimeError('Invalid field type "%r"' % field_type)
