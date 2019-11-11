import io
import json
from warnings import warn

import slivka.utils

try:
    import Bio.SeqIO
except ImportError:
    Bio = None


def biopython_validator_factory(file_format):
    def validator(file):
        wrapper = io.TextIOWrapper(file, encoding='ascii')
        try:
            return sum(1 for _ in Bio.SeqIO.parse(wrapper, file_format)) > 0
        except (ValueError, IndexError):
            return False
        finally:
            # detach the wrapper or it will close the underlying stream
            # when leaving the function's scope
            wrapper.detach()
    return validator


def plain_text_validator(file):
    text_chars = (
        {0x7, 0x8, 0x9, 0xa, 0xc, 0xd, 0x1b} | set(range(0x20, 0x100)) - {0x7f}
    )
    chunk = file.read(16384)
    while chunk:
        if not set(chunk).issubset(text_chars):
            return False
        chunk = file.read(16384)
    return True


def json_validator(file):
    wrapper = io.TextIOWrapper(file)
    try:
        json.load(wrapper)
    except ValueError:
        return False
    else:
        return True
    finally:
        wrapper.detach()


def reject_validator(_):
    return False


def pass_validator(_):
    return True


_built_in_validators = {
    'text/plain': plain_text_validator,
    'application/json': json_validator
}

if Bio is not None:
    bio_formats = {
        'fasta': biopython_validator_factory('fasta'),
        'clustal': biopython_validator_factory('clustal'),
        'genbank': biopython_validator_factory('genbank'),
        'embl': biopython_validator_factory('embl'),
        'pfam': biopython_validator_factory('stockholm')
    }
    _built_in_validators.update({
        "application/%s" % n: v for n, v in bio_formats.items()
    })
    _built_in_validators.update({
        "application/x-%s" % n: v for n, v in bio_formats.items()
    })


class ValidatorDict(dict):
    def init_from_settings(self):
        for media_type in slivka.settings.ACCEPTED_MEDIA_TYPES:
            self.add(media_type)

    def __missing__(self, key):
        return reject_validator

    def __setitem__(self, key, validator):
        if validator is None:
            if key not in _built_in_validators:
                msg = (
                    "Media type %s has no built-in validator available. "
                    "Every file declaring this media type will be accepted." %
                    key
                )
                warn(msg, RuntimeWarning)
            validator = _built_in_validators.get(key, pass_validator)
        dict.__setitem__(self, key, validator)

    def add(self, media_type, validator=None):
        self[media_type] = validator


_validators = None


def validate_file_content(file, media_type):
    global _validators
    if _validators is None:
        _validators = ValidatorDict()
        _validators.init_from_settings()
    return _validators[media_type](file)
