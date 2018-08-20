import io

from Bio import SeqIO


def biopython_validator_factory(file_format):
    def validator(file):
        buffer = io.TextIOWrapper(file, encoding='ascii')
        try:
            return sum(1 for _ in SeqIO.parse(buffer, file_format)) > 0
        except (ValueError, IndexError) as e:
            return False
        finally:
            buffer.detach()
    return validator


_validators = {
    'application/fasta': biopython_validator_factory('fasta'),
    'application/clustal': biopython_validator_factory('clustal'),
    'application/genbank': biopython_validator_factory('genbank'),
    'application/embl': biopython_validator_factory('embl')
}


def validate_file_type(file, mime_type):
    validator = _validators.get(mime_type)
    if validator is None:
        return False
    else:
        return validator(file)
