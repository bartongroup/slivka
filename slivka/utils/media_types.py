import io
import json
import warnings

import yaml

try:
    import Bio.SeqIO
except ImportError:
    Bio = None


class ValidatorsDict(dict):
    def __missing__(self, key):
        warnings.warn(
            "There is no validator for %s. Files of this type will not be "
            "checked." % key, RuntimeWarning)
        return _check_any


def _check_any(_):
    return True


def check_plain_text(file):
    text_chars = (
            {0x7, 0x8, 0x9, 0xa, 0xc, 0xd, 0x1b} | set(range(0x20, 0x100)) - {
        0x7f}
    )
    chunk = file.read(16384)
    while chunk:
        if not set(chunk).issubset(text_chars):
            return False
        chunk = file.read(16384)
    return True


def check_json(file):
    wrapper = io.TextIOWrapper(file)
    try:
        json.load(wrapper)
    except ValueError:
        return False
    else:
        return True
    finally:
        wrapper.detach()


def check_yaml(file):
    wrapper = io.TextIOWrapper(file)
    try:
        yaml.safe_load_all(file)
    except ValueError:
        return False
    else:
        return True
    finally:
        wrapper.detach()


def biopython_check_factory(file_format):
    def validator(file):
        wrapper = io.TextIOWrapper(file, encoding='ascii')
        try:
            return sum(1 for _ in Bio.SeqIO.parse(wrapper, file_format)) > 0
        except (ValueError, IndexError):
            return False
        finally:
            # detach the wrapper so the underlying file won't be closed
            # on leaving the function scope
            wrapper.detach()

    return validator


global_validators = ValidatorsDict()
global_validators.update({
    'text/plain': check_plain_text,
    'application/json': check_json,
    'application/yaml': check_yaml,
    'application/x-yaml': check_yaml
})

if Bio is not None:
    bio_fmts = [
        ('fasta', 'fasta'), ('clustal', 'clustal'), ('genbank', 'genbank'),
        ('embl', 'embl'), ('stockholm', 'stockholm'), ('pfam', 'stockholm')
    ]
    validators = [
        (name, biopython_check_factory(fmt)) for name, fmt in bio_fmts
    ]
    global_validators.update(
        ('application/%s' % name, value) for name, value in validators
    )
    global_validators.update(
        ('application/x-%s' % name, value) for name, value in validators
    )
    global_validators.update(
        ('text/%s' % name, value) for name, value in validators
    )


def add_validator(media_type, validator):
    global_validators[media_type] = validator


def get_validator(media_type):
    return global_validators[media_type]


def has_validator(media_type):
    return media_type in global_validators


def validate(media_type, file):
    return global_validators[media_type](file)
