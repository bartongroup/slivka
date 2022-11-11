import re

# default escaping \xHH for all control characters
_control_trans = {
  i: '\\x%02X' % i for i in range(32)
}
_control_trans.update({
  0x00: '\\0',  # \0 for null
  0x07: '\\a',  # \a for bell
  0x08: '\\b',  # \b for backspace
  0x09: '\\t',  # \t for tab
  0x0A: '\\n',  # \n for LF
  0x0B: '\\v',  # \v for vertical tab
  0x0C: '\\f',  # \f for form feed
  0x0D: '\\r',  # \r for CR
  0x1B: '\\e'   # \e for ESC
})
# also escape backslash and single quote
_control_trans.update(str.maketrans({'\\': '\\\\', "'": "\\'"}))

_find_unsafe = re.compile(r'[^\w@%+=:,./-]', re.ASCII).search


def bash_quote(s):
    """Return a bash-escaped version of the string using ANSI-C quoting."""
    if not s:
        # empty string must be quoted to appear in the command
        # as an individual argument
        return "''"
    if _find_unsafe(s) is None:
        return s
    if s.isprintable() and "'" not in s:
        return "'" + s + "'"
    return "$'" + s.translate(_control_trans) + "'"
