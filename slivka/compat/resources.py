import importlib.resources
import os.path
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
    def _shift_path(package, resource):
        parts = os.path.normpath(resource).split(os.path.sep)
        return '.'.join([package, *parts[:-1]]), parts[-1]


    def open_binary(package: Package, resource: Resource) -> BinaryIO:
        return importlib.resources.open_binary(*_shift_path(package, resource))


    def open_text(
            package: Package,
            resource: Resource,
            encoding: str = 'utf-8',
            errors: str = 'strict'
    ) -> TextIO:
        return importlib.resources.open_text(
            *_shift_path(package, resource),
            encoding=encoding,
            errors=errors
        )


    def read_binary(package: Package, resource: Resource) -> bytes:
        return importlib.resources.read_binary(*_shift_path(package, resource))


    def read_text(
            package: Package,
            resource: Resource,
            encoding: str = 'utf-8',
            errors: str = 'strict',
    ) -> str:
        return importlib.resources.read_text(
            *_shift_path(package, resource),
            encoding=encoding,
            errors=errors
        )
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
