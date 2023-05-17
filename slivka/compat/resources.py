import importlib.resources
import sys
from importlib.resources import Package, Resource
from typing import BinaryIO, TextIO

__all__ = [
    'open_binary',
    'open_text',
    'read_binary',
    'read_text'
]

if sys.version_info < (3, 11):
    open_binary = importlib.resources.open_binary
    open_text = importlib.resources.open_text
    read_binary = importlib.resources.read_binary
    read_text = importlib.resources.read_text
else:
    def open_binary(package: Package, resource: Resource) -> BinaryIO:
        """Return a file-like object opened for binary reading of the resource."""
        return importlib.resources.files(package).joinpath(resource).open('rb')


    def open_text(
            package: Package,
            resource: Resource,
            encoding: str = 'utf-8',
            errors: str = 'strict',
    ) -> TextIO:
        return (importlib.resources.files(package)
                .joinpath(resource)
                .open('r', encoding=encoding, errors=errors))


    def read_binary(package: Package, resource: Resource) -> bytes:
        """Return the binary contents of the resource."""
        return (importlib.resources.files(package)
                .joinpath(resource)
                .read_bytes())


    def read_text(
            package: Package,
            resource: Resource,
            encoding: str = 'utf-8',
            errors: str = 'strict',
    ) -> str:
        """Return the decoded string of the resource.

        The decoding-related arguments have the same semantics as those of
        bytes.decode().
        """
        with open_text(package, resource, encoding, errors) as fp:
            return fp.read()
