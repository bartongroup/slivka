import os
import re
from typing import Mapping

# Regular expression capturing variable names $VAR or ${VAR}
# and escaped dollar sign $$. Matches should be substituted
# for actual variable values.
_var_regex = re.compile(
    r'\$(?:(\$)|([_a-z]\w*)|{([_a-z]\w*)})',
    re.UNICODE | re.IGNORECASE
)


def expandvars(string: str, environ: Mapping = None) -> str:
    """ Interpolate variables in text using provided environ.

    Variables are specified in text using bash-like syntax i.e.
    $VARIABLE or ${VARIABLE}. Dollar sign escaped with another dollar
    sign ``$$`` is replaced with a single one. If environ is not
    specified, system environment variables are used.

    :param string: text containing variables to be interpolated
    :param environ: mapping used for environment variables
    :return: interpolated text
    """
    if environ is None:
        environ = os.environ

    def replace_vars(match: re.Match):
        if match.group(1):
            return '$'
        else:
            return environ.get(match.group(2) or match.group(3))

    return _var_regex.sub(replace_vars, string)
