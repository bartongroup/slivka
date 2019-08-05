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
    _built_in_validators.update({
        'application/fasta': biopython_validator_factory('fasta'),
        'application/clustal': biopython_validator_factory('clustal'),
        'application/genbank': biopython_validator_factory('genbank'),
        'application/embl': biopython_validator_factory('embl')
    })

for media_type, path in getattr(slivka.settings, 'FILE_VALIDATORS', {}).items():
    _built_in_validators[media_type] = slivka.utils.locate(path)

_validators = {}

for media_type in slivka.settings.ACCEPTED_MEDIA_TYPES:
    if media_type not in _built_in_validators:
        msg = (
            "{} has no validator set up. "
            "Every file with this mime type will be accepted."
            .format(media_type)
        )
        warn(msg, RuntimeWarning)
    _validators[media_type] = _built_in_validators.get(media_type, pass_validator)

del _built_in_validators


def validate_file_content(file, media_type):
    validator = _validators.get(media_type, reject_validator)
    return validator(file)
