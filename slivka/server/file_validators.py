import io

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
            buffer.detach()
    return validator


def plain_text_validator(file):
    text_chars = (
        {0x7, 0x8, 0x9, 0xa, 0xc, 0xd, 0x1b} | set(range(0x20, 0x100)) - {0x7f}
    )
    return set(file.read(256)).issubset(text_chars)


_default_validators = {
    'text/plain': plain_text_validator
}

if Bio is not None:
    _default_validators.update({
        'application/fasta': biopython_validator_factory('fasta'),
        'application/clustal': biopython_validator_factory('clustal'),
        'application/genbank': biopython_validator_factory('genbank'),
        'application/embl': biopython_validator_factory('embl')
    })

for mime_type, validator \
        in getattr(slivka.settings, 'FILE_VALIDATORS', {}).items():
    _default_validators[mime_type] = slivka.utils.locate(validator)

_validators = {}

for file_type in slivka.settings.ACCEPTED_FILE_TYPES:
    _validators[file_type] = _default_validators[file_type]

del _default_validators


def validate_file_type(file, mime_type):
    validator = _validators.get(mime_type)
    if validator is None:
        return False
    else:
        return validator(file)
