import io
from warnings import warn

import slivka.utils

try:
    import Bio.SeqIO
except ImportError:
    Bio = None


def biopython_validator_factory(file_format):
    def validator(file):
        buffer = io.TextIOWrapper(file, encoding='ascii')
        try:
            return sum(1 for _ in Bio.SeqIO.parse(buffer, file_format)) > 0
        except (ValueError, IndexError):
            return False
        finally:
            # detach the buffer or it will close the underlying stream
            # when leaving the function scope
            buffer.detach()
    return validator


def plain_text_validator(file):
    text_chars = (
        {0x7, 0x8, 0x9, 0xa, 0xc, 0xd, 0x1b} | set(range(0x20, 0x100)) - {0x7f}
    )
    return set(file.read(256)).issubset(text_chars)


def reject_validator(_):
    return False


def pass_validator(_):
    return True


_builtin_validators = {
    'text/plain': plain_text_validator
}

if Bio is not None:
    _builtin_validators.update({
        'application/fasta': biopython_validator_factory('fasta'),
        'application/clustal': biopython_validator_factory('clustal'),
        'application/genbank': biopython_validator_factory('genbank'),
        'application/embl': biopython_validator_factory('embl')
    })

for mime_type, path in getattr(slivka.settings, 'FILE_VALIDATORS', {}).items():
    _builtin_validators[mime_type] = slivka.utils.locate(path)

_validators = {}

for file_type in slivka.settings.ACCEPTED_FILE_TYPES:
    if file_type not in _builtin_validators:
        msg = (
            "{} has no validator set up. "
            "Every file with this mime type will be accepted."
            .format(file_type)
        )
        warn(msg, RuntimeWarning)
    _validators[file_type] = _builtin_validators.get(file_type, pass_validator)

del _builtin_validators


def validate_file_type(file, mime_type):
    validator = _validators.get(mime_type, reject_validator)
    return validator(file)
