#!/usr/bin/env python
#
# file: 
#
# revision history:
#
# 20211121 (PM): initial version
#
# Acknowledgement for the script's foundation:
# Copyright (C) 2006-2009 Johann C. Rocholl <johann@rocholl.net>
# Copyright (C) 2009-2014 Florent Xicluna <florent.xicluna@gmail.com>
# Copyright (C) 2014-2016 Ian Lee <ianlee1521@gmail.com>
#
# This is a Python script that checks other Python script based on the NEDC
# guideline
#------------------------------------------------------------------------------

# import system modules
#
import bisect
import inspect
import keyword
import os
import re
import sys
import tokenize

#------------------------------------------------------------------------------
#
# global variables are listed here
#
#------------------------------------------------------------------------------

# set the filename using basename
#
__FILE__ = os.path.basename(__file__)

# define the location of the help files
#
HELP_FILE = \
    "~"

USAGE_FILE = \
    "~"

# Number of blank lines between various code parts.
BLANK_LINES_CONFIG = {
    # Top level class and function.
    'top_level': 1,
    # Methods and nested class and function.
    'method': 1,
}
INDENT_SIZE = 4
MAX_DOC_LENGTH = 80
MAX_LINE_LENGTH = 80
REPORT_FORMAT = '%(path)s:%(row)d:%(col)d: %(text)s'

#------------------------------------------------------------------------------
#
# regular expression(regex) are listed here
#
#------------------------------------------------------------------------------

ARITHMETIC_OP = frozenset(['**', '*', '/', '//', '+', '-', '@'])
BENCHMARK_KEYS = ['directories', 'files', 'logical lines', 'physical lines']
BLANK_EXCEPT_REGEX = re.compile(r"except\s*:")
DOCSTRING_REGEX = re.compile(r'u?r?["\']')
DUNDER_REGEX = re.compile(r"^__([^\s]+)__(?::\s*[a-zA-Z.0-9_\[\]\"]+)? = ")
ERRORCODE_REGEX = re.compile(r'\b[A-Z]\d{3}\b')
EXTRANEOUS_WHITESPACE_REGEX = re.compile(r'[\[({][ \t]|[ \t][\]}),;:](?!=)')
KEYWORDS = frozenset(keyword.kwlist + ['print', 'async']) - frozenset(['False', 'None', 'True'])
KEYWORD_REGEX = re.compile(r'(\s*)\b(?:%s)\b(\s*)' % r'|'.join(KEYWORDS))
NEWLINE = frozenset([tokenize.NL, tokenize.NEWLINE])
OPERATOR_REGEX = re.compile(r'(?:[^,\s])(\s*)(?:[-+*/|!<=>%&^]+|:=)(\s*)')
SKIP_TOKENS = NEWLINE.union([tokenize.INDENT, tokenize.DEDENT])
SKIP_COMMENTS = SKIP_TOKENS.union([tokenize.COMMENT, tokenize.ERRORTOKEN])
STARTSWITH_DEF_REGEX = re.compile(r'^(async\s+def|def)\b')
STARTSWITH_TOP_LEVEL_REGEX = re.compile(r'^(async\s+def\s+|def\s+|class\s+|@)')
UNARY_OPERATORS = frozenset(['>>', '**', '*', '+', '-'])
WHITESPACE = frozenset(' \t\xa0')
WHITESPACE_AFTER_COMMA_REGEX = re.compile(r'[,;:]\s*(?:  |\t)')
WS_NEEDED_OPERATORS = frozenset([
    '**=', '*=', '/=', '//=', '+=', '-=', '!=', '<>', '<', '>',
    '%=', '^=', '&=', '|=', '==', '<=', '>=', '<<=', '>>=', '=',
    'and', 'in', 'is', 'or', '->'])
WS_OPTIONAL_OPERATORS = ARITHMETIC_OP.union(['^', '&', '|', '<<', '>>', '%'])

#------------------------------------------------------------------------------
#
# NEDC regular expression(regex) are listed here
#
#------------------------------------------------------------------------------

NEDC_FILE_HEADER_REGEX = re.compile(r'^#(!/usr/bin/env python)\n^#\n# (file:.*\.py)$\n^#\n^# (revision history:)\n#\n# ([0-9]{8} \([A-Z]{2}\): .*)\n[\s\S]*?(?=\n#-)\n^(#-*)\n$', re.MULTILINE)
NEDC_FUNCTION_CHECKER_REGEX = re.compile(r'^(async def|def)((?!main).)*$', re.MULTILINE)
NEDC_FUNCTION_COMMENT_REGEX = re.compile(r'#-*\n# *\n# functions are listed here *\n# *\n#-*', re.MULTILINE)
NEDC_FUNCTION__HEADER_COMMENT_REGEX = re.compile(r"# function:.*\n#\n# argument:\n[\s\S]*?(?=def)def",re.MULTILINE)
NEDC_GENERAL_IMPORT_REGEX = re.compile(r'# import system modules\n#\nimport', re.MULTILINE)
NEDC_GLOBAL_VARIABLE_COMMENT_REGEX = re.compile(r'#-*\n# *\n# global variables are listed here *\n# *\n#-*', re.MULTILINE)
NEDC_MAIN_FUNCTION_REGEX = re.compile(r'# function: main\n#',re.MULTILINE)
NEDC_NEDC_IMPORT_REGEX = re.compile(r'# import nedc_modules\n#\nimport nedc', re.MULTILINE)

#------------------------------------------------------------------------------
#
# NEDC templates are listed here
#
#------------------------------------------------------------------------------

NEDC_FILE_HEADER_STRING = \
"""#!/usr/bin/env python
#
# file: path/to/script/~.py
#
# revision history:
#
# yyyymmdd ([initial firstname][initial lastname]): initial version
#
# [description]
#------------------------------------------------------------------------------
"""
NEDC_GLOBAL_VARIABLE_COMMENT_STRING = \
"""#------------------------------------------------------------------------------
#
# global variables are listed here
#
#------------------------------------------------------------------------------
"""

NEDC_FUNCTION_COMMENT_STRING = \
"""#------------------------------------------------------------------------------
#
# functions are listed here
#
#------------------------------------------------------------------------------
"""
NEDC_FUNCTION_HEADER_COMMENT_STRING = \
"""# function: [name]
#
# argument:
#   arg 1: [type + description]
#   .....
#   arg n:
#
# return: [type + description]
#
# [short description of the function]
#
"""

NEDC_GENERAL_IMPORT_STRING = \
"""# import system modules
#
"""

NEDC_NEDC_IMPORT_STRING = \
"""# import nedc_modules
#
"""

NEDC_MAIN_FUNCTION_STRING = \
"""# function: main
#
"""

# A dictionary that stores all the condition that each line
# are tested on
#
nedc_checks = {'physical_line': {}, 'logical_line': {}, 'tree': {}}

#------------------------------------------------------------------------------
#
# functions are listed here
#
#------------------------------------------------------------------------------

# function: nedc_get_parameters
#
# argument:
#   function: a function
#
# return: list of arguments in a function
#
# A function that returns the inputted function's argument
#
def nedc_get_parameters(function):
    return [parameter.name
            for parameter
            in inspect.signature(function).parameters.values()
            if parameter.kind == parameter.POSITIONAL_OR_KEYWORD]

# function: nedc_nedc_register_check
#
# argument:
#   check: the added condition function
#   codes: 
#
# return: list of arguments in a function
#
# Register a new object as a condition to nedc_checks
#
def nedc_register_check(check, codes=None):

    def _add_check(check, kind, codes, args):
        if check in nedc_checks[kind]:
            nedc_checks[kind][check][0].extend(codes or [])
        else:
            nedc_checks[kind][check] = (codes or [''], args)
    if inspect.isfunction(check):
        args = nedc_get_parameters(check)
        if args and args[0] in ('physical_line', 'logical_line'):
            if codes is None:
                codes = ERRORCODE_REGEX.findall(check.__doc__ or '')
            _add_check(check, args[0], codes, args)
    elif inspect.isclass(check):
        if nedc_get_parameters(check.__init__)[:2] == ['self', 'tree']:
            _add_check(check, 'tree', codes, None)
    
    return check

def readlines(filename):
    """Read the source code."""
    try:
        with tokenize.open(filename) as f:
            return f.readlines()
    except (LookupError, SyntaxError, UnicodeError):
        # Fall back if file encoding is improperly declared
        with open(filename, encoding='latin-1') as f:
            return f.readlines()

def expand_indent(line):
    r"""Return the amount of indentation.

    Tabs are expanded to the next multiple of 8.

    >>> expand_indent('    ')
    4
    >>> expand_indent('\t')
    8
    >>> expand_indent('       \t')
    8
    >>> expand_indent('        \t')
    16
    """
    line = line.rstrip('\n\r')
    if '\t' not in line:
        return len(line) - len(line.lstrip())
    result = 0
    for char in line:
        if char == '\t':
            result = result // 8 * 8 + 8
        elif char == ' ':
            result += 1
        else:
            break
    return result

def mute_string(text):
    """Replace contents with 'xxx' to prevent syntax matching.

    >>> mute_string('"abc"')
    '"xxx"'
    >>> mute_string("'''abc'''")
    "'''xxx'''"
    >>> mute_string("r'abc'")
    "r'xxx'"
    """
    # String modifiers (e.g. u or r)
    start = text.index(text[-1]) + 1
    end = len(text) - 1
    # Triple quotes
    if text[-3:] in ('"""', "'''"):
        start += 2
        end -= 2
    return text[:start] + 'x' * (end - start) + text[end:]

def _is_eol_token(token):
    return token[0] in NEWLINE or token[4][token[3][1]:].lstrip() == '\\\n'

#------------------------------------------------------------------------------
#
# checker functions are listed here
#
#------------------------------------------------------------------------------

@nedc_register_check
def trailing_blank_lines(physical_line, lines, line_number, total_lines):
    r"""Trailing blank lines are superfluous.

    Okay: spam(1)
    W391: spam(1)\n

    However the last line should end with a new line (warning W292).
    """
    if line_number == total_lines:
        stripped_last_line = physical_line.rstrip('\r\n')
        if stripped_last_line != "# end of file":
            return 0, "missing '# end of file' at end of file"
        if stripped_last_line == physical_line:
            return len(lines[-1]), "no newline at end of file"

@nedc_register_check
def maximum_line_length(physical_line, max_line_length, multiline,
                        line_number):
    r"""Limit all lines to a maximum of 79 characters.

    There are still many devices around that are limited to 80 character
    lines; plus, limiting windows to 80 characters makes it possible to
    have several windows side-by-side.  The default wrapping on such
    devices looks ugly.  Therefore, please limit all lines to a maximum
    of 79 characters. For flowing long blocks of text (docstrings or
    comments), limiting the length to 72 characters is recommended.

    Reports error E501.
    """
    line = physical_line.rstrip()
    length = len(line)
    if length > max_line_length:
        # Special case: ignore long shebang lines.
        if line_number == 1 and line.startswith('#!'):
            return
        # Special case for long URLs in multi-line docstrings or
        # comments, but still report the error when the 72 first chars
        # are whitespaces.
        chunks = line.split()
        if ((len(chunks) == 1 and multiline) or
            (len(chunks) == 2 and chunks[0] == '#')) and \
                len(line) - len(chunks[-1]) < max_line_length - 7:
            return
        if hasattr(line, 'decode'):   # Python 2
            # The line could contain multi-byte characters
            try:
                length = len(line.decode('utf-8'))
            except UnicodeError:
                pass
        if length > max_line_length:
            return (max_line_length, "line too long "
                    "(%d > %d characters)" % (length, max_line_length))

@nedc_register_check
def blank_lines(logical_line, blank_lines, indent_level, line_number,
                blank_before, previous_logical,
                previous_unindented_logical_line, previous_indent_level,
                lines):
    r"""Separate top-level function and class definitions by a single blank
    line.

    Method definitions inside a class are separated by a single blank
    line.

    Extra blank lines may be used (sparingly) to separate groups of
    related functions.  Blank lines may be omitted between a bunch of
    related one-liners (e.g. a set of dummy implementations).

    Use blank lines in functions, sparingly, to indicate logical
    sections.

    Okay: def a():\n    pass\n\n\ndef b():\n    pass
    Okay: def a():\n    pass\n\n\nasync def b():\n    pass
    Okay: def a():\n    pass\n\n\n# Foo\n# Bar\n\ndef b():\n    pass
    Okay: default = 1\nfoo = 1
    Okay: classify = 1\nfoo = 1

    E301: class Foo:\n    b = 0\n    def bar():\n        pass
    E302: def a():\n    pass\n\ndef b(n):\n    pass
    E302: def a():\n    pass\n\nasync def b(n):\n    pass
    E303: def a():\n    pass\n\n\n\ndef b(n):\n    pass
    E303: def a():\n\n\n\n    pass
    E304: @decorator\n\ndef a():\n    pass
    E305: def a():\n    pass\na()
    E306: def a():\n    def b():\n        pass\n    def c():\n        pass
    """  
    top_level_lines = BLANK_LINES_CONFIG['top_level']
    method_lines = BLANK_LINES_CONFIG['method']

    if not previous_logical and blank_before < top_level_lines:
        return  # Don't expect blank lines before the first line
    if previous_logical.startswith('@'):
        if blank_lines:
            yield 0, "E304 blank lines found after function decorator"
    elif (blank_lines > top_level_lines or
            (indent_level and blank_lines == method_lines + 1)
          ):
        yield 0, "E303 too many blank lines (%d)" % blank_lines
    elif STARTSWITH_TOP_LEVEL_REGEX.match(logical_line):
        if indent_level:
            if not (blank_before == method_lines or
                    previous_indent_level < indent_level or
                    DOCSTRING_REGEX.match(previous_logical)
                    ):
                ancestor_level = indent_level
                nested = False
                # Search backwards for a def ancestor or tree root
                # (top level).
                for line in lines[line_number - top_level_lines::-1]:
                    if line.strip() and expand_indent(line) < ancestor_level:
                        ancestor_level = expand_indent(line)
                        nested = STARTSWITH_DEF_REGEX.match(line.lstrip())
                        if nested or ancestor_level == 0:
                            break
                if nested:
                    yield 0, "E306 expected %s blank line before a " \
                        "nested definition, found 0" % (method_lines,)
                else:
                    yield 0, "E301 expected {} blank line, found 0".format(
                        method_lines)
        elif blank_before != top_level_lines:
            yield 0, "E302 expected %s blank lines, found %d" % (
                top_level_lines, blank_before)
    elif (logical_line and
            not indent_level and
            blank_before != top_level_lines and
            previous_unindented_logical_line.startswith(('def ', 'class '))
          ):
        yield 0, "E305 expected %s blank lines after " \
            "class or function definition, found %d" % (
                top_level_lines, blank_before)

@nedc_register_check
def extraneous_whitespace(logical_line):
    r"""Avoid extraneous whitespace.

    Avoid extraneous whitespace in these situations:
    - Immediately inside parentheses, brackets or braces.
    - Immediately before a comma, semicolon, or colon.

    Okay: spam(ham[1], {eggs: 2})
    E201: spam( ham[1], {eggs: 2})
    E201: spam(ham[ 1], {eggs: 2})
    E201: spam(ham[1], { eggs: 2})
    E202: spam(ham[1], {eggs: 2} )
    E202: spam(ham[1 ], {eggs: 2})
    E202: spam(ham[1], {eggs: 2 })

    E203: if x == 4: print x, y; x, y = y , x
    E203: if x == 4: print x, y ; x, y = y, x
    E203: if x == 4 : print x, y; x, y = y, x
    """
    line = logical_line
    for match in EXTRANEOUS_WHITESPACE_REGEX.finditer(line):
        text = match.group()
        char = text.strip()
        found = match.start()
        if text[-1].isspace():
            # assert char in '([{'
            yield found + 1, "E201 whitespace after '%s'" % char
        elif line[found - 1] != ',':
            code = ('E202' if char in '}])' else 'E203')  # if char in ',;:'
            yield found, f"{code} whitespace before '{char}'"

@nedc_register_check
def whitespace_around_keywords(logical_line):
    r"""Avoid extraneous whitespace around keywords.

    Okay: True and False
    E271: True and  False
    E272: True  and False
    E273: True and\tFalse
    E274: True\tand False
    """
    for match in KEYWORD_REGEX.finditer(logical_line):
        before, after = match.groups()

        if '\t' in before:
            yield match.start(1), "E274 tab before keyword"
        elif len(before) > 1:
            yield match.start(1), "E272 multiple spaces before keyword"

        if '\t' in after:
            yield match.start(2), "E273 tab after keyword"
        elif len(after) > 1:
            yield match.start(2), "E271 multiple spaces after keyword"

@nedc_register_check
def missing_whitespace_after_import_keyword(logical_line):
    r"""Multiple imports in form from x import (a, b, c) should have
    space between import statement and parenthesised name list.

    Okay: from foo import (bar, baz)
    E275: from foo import(bar, baz)
    E275: from importable.module import(bar, baz)
    """
    line = logical_line
    indicator = ' import('
    if line.startswith('from '):
        found = line.find(indicator)
        if -1 < found:
            pos = found + len(indicator) - 1
            yield pos, "missing whitespace after keyword"

@nedc_register_check
def missing_whitespace(logical_line):
    r"""Each comma, semicolon or colon should be followed by whitespace.

    Okay: [a, b]
    Okay: (3,)
    Okay: a[1:4]
    Okay: a[:4]
    Okay: a[1:]
    Okay: a[1:4:2]
    E231: ['a','b']
    E231: foo(bar,baz)
    E231: [{'a':'b'}]
    """
    line = logical_line
    for index in range(len(line) - 1):
        char = line[index]
        next_char = line[index + 1]
        if char in ',;:' and next_char not in WHITESPACE:
            before = line[:index]
            if char == ':' and before.count('[') > before.count(']') and \
                    before.rfind('{') < before.rfind('['):
                continue  # Slice syntax, no space required
            if char == ',' and next_char == ')':
                continue  # Allow tuple with only one element: (3,)
            if char == ':' and next_char == '=' and sys.version_info >= (3, 8):
                continue  # Allow assignment expression
            yield index, "E231 missing whitespace after '%s'" % char

@nedc_register_check
def whitespace_before_parameters(logical_line, tokens):
    r"""Avoid extraneous whitespace.

    Avoid extraneous whitespace in the following situations:
    - before the open parenthesis that starts the argument list of a
      function call.
    - before the open parenthesis that starts an indexing or slicing.

    Okay: spam(1)
    E211: spam (1)

    Okay: dict['key'] = list[index]
    E211: dict ['key'] = list[index]
    E211: dict['key'] = list [index]
    """
    prev_type, prev_text, __, prev_end, __ = tokens[0]
    for index in range(1, len(tokens)):
        token_type, text, start, end, __ = tokens[index]
        if (
            token_type == tokenize.OP and
            text in '([' and
            start != prev_end and
            (prev_type == tokenize.NAME or prev_text in '}])') and
            # Syntax "class A (B):" is allowed, but avoid it
            (index < 2 or tokens[index - 2][1] != 'class') and
            # Allow "return (a.foo for a in range(5))"
            not keyword.iskeyword(prev_text) and
            # 'match' and 'case' are only soft keywords
            (
                sys.version_info < (3, 9) or
                not keyword.issoftkeyword(prev_text)
            )
        ):
            yield prev_end, "E211 whitespace before '%s'" % text
        prev_type = token_type
        prev_text = text
        prev_end = end

@nedc_register_check
def whitespace_around_operator(logical_line):
    r"""Avoid extraneous whitespace around an operator.

    Okay: a = 12 + 3
    E221: a = 4  + 5
    E222: a = 4 +  5
    E223: a = 4\t+ 5
    E224: a = 4 +\t5
    """
    for match in OPERATOR_REGEX.finditer(logical_line):
        before, after = match.groups()

        if '\t' in before:
            yield match.start(1), "E223 tab before operator"
        elif len(before) > 1:
            yield match.start(1), "E221 multiple spaces before operator"

        if '\t' in after:
            yield match.start(2), "E224 tab after operator"
        elif len(after) > 1:
            yield match.start(2), "E222 multiple spaces after operator"

@nedc_register_check
def missing_whitespace_around_operator(logical_line, tokens):
    r"""Surround operators with a single space on either side.

    - Always surround these binary operators with a single space on
      either side: assignment (=), augmented assignment (+=, -= etc.),
      comparisons (==, <, >, !=, <=, >=, in, not in, is, is not),
      Booleans (and, or, not).

    - If operators with different priorities are used, consider adding
      whitespace around the operators with the lowest priorities.

    Okay: i = i + 1
    Okay: submitted += 1
    Okay: x = x * 2 - 1
    Okay: hypot2 = x * x + y * y
    Okay: c = (a + b) * (a - b)
    Okay: foo(bar, key='word', *args, **kwargs)
    Okay: alpha[:-i]

    E225: i=i+1
    E225: submitted +=1
    E225: x = x /2 - 1
    E225: z = x **y
    E225: z = 1and 1
    E226: c = (a+b) * (a-b)
    E226: hypot2 = x*x + y*y
    E227: c = a|b
    E228: msg = fmt%(errno, errmsg)
    """
    parens = 0
    need_space = False
    prev_type = tokenize.OP
    prev_text = prev_end = None
    operator_types = (tokenize.OP, tokenize.NAME)
    for token_type, text, start, end, line in tokens:
        if token_type in SKIP_COMMENTS:
            continue
        if text in ('(', 'lambda'):
            parens += 1
        elif text == ')':
            parens -= 1
        if need_space:
            if start != prev_end:
                # Found a (probably) needed space
                if need_space is not True and not need_space[1]:
                    yield (need_space[0],
                           "E225 missing whitespace around operator")
                need_space = False
            elif text == '>' and prev_text in ('<', '-'):
                # Tolerate the "<>" operator, even if running Python 3
                # Deal with Python 3's annotated return value "->"
                pass
            elif (
                    # def f(a, /, b):
                    #           ^
                    # def f(a, b, /):
                    #              ^
                    # f = lambda a, /:
                    #                ^
                    prev_text == '/' and text in {',', ')', ':'} or
                    # def f(a, b, /):
                    #               ^
                    prev_text == ')' and text == ':'
            ):
                # Tolerate the "/" operator in function definition
                # For more info see PEP570
                pass
            else:
                if need_space is True or need_space[1]:
                    # A needed trailing space was not found
                    yield prev_end, "E225 missing whitespace around operator"
                elif prev_text != '**':
                    code, optype = 'E226', 'arithmetic'
                    if prev_text == '%':
                        code, optype = 'E228', 'modulo'
                    elif prev_text not in ARITHMETIC_OP:
                        code, optype = 'E227', 'bitwise or shift'
                    yield (need_space[0], "%s missing whitespace "
                           "around %s operator" % (code, optype))
                need_space = False
        elif token_type in operator_types and prev_end is not None:
            if text == '=' and parens:
                # Allow keyword args or defaults: foo(bar=None).
                pass
            elif text in WS_NEEDED_OPERATORS:
                need_space = True
            elif text in UNARY_OPERATORS:
                # Check if the operator is used as a binary operator
                # Allow unary operators: -123, -x, +1.
                # Allow argument unpacking: foo(*args, **kwargs).
                if prev_type == tokenize.OP and prev_text in '}])' or (
                    prev_type != tokenize.OP and
                    prev_text not in KEYWORDS and (
                        sys.version_info < (3, 9) or
                        not keyword.issoftkeyword(prev_text)
                    )
                ):
                    need_space = None
            elif text in WS_OPTIONAL_OPERATORS:
                need_space = None

            if need_space is None:
                # Surrounding space is optional, but ensure that
                # trailing space matches opening space
                need_space = (prev_end, start != prev_end)
            elif need_space and start == prev_end:
                # A needed opening space was not found
                yield prev_end, "E225 missing whitespace around operator"
                need_space = False
        prev_type = token_type
        prev_text = text
        prev_end = end

@nedc_register_check
def whitespace_around_comma(logical_line):
    r"""Avoid extraneous whitespace after a comma or a colon.

    Note: these checks are disabled by default

    Okay: a = (1, 2)
    E241: a = (1,  2)
    E242: a = (1,\t2)
    """
    line = logical_line
    for m in WHITESPACE_AFTER_COMMA_REGEX.finditer(line):
        found = m.start() + 1
        if '\t' in m.group():
            yield found, "E242 tab after '%s'" % m.group()[0]
        else:
            yield found, "E241 multiple spaces after '%s'" % m.group()[0]

@nedc_register_check
def whitespace_before_comment(logical_line, tokens):
    """Separate inline comments by at least two spaces.

    An inline comment is a comment on the same line as a statement.
    Inline comments should be separated by at least two spaces from the
    statement. They should start with a # and a single space.

    Each line of a block comment starts with a # and one or multiple
    spaces as there can be indented text inside the comment.

    Okay: x = x + 1  # Increment x
    Okay: x = x + 1    # Increment x
    Okay: # Block comments:
    Okay: #  - Block comment list
    Okay: # \xa0- Block comment list
    E261: x = x + 1 # Increment x
    E262: x = x + 1  #Increment x
    E262: x = x + 1  #  Increment x
    E262: x = x + 1  # \xa0Increment x
    E265: #Block comment
    E266: ### Block comment
    """
    prev_end = (0, 0)
    for token_type, text, start, end, line in tokens:
        if token_type == tokenize.COMMENT:
            inline_comment = line[:start[1]].strip()
            if inline_comment:
                if prev_end[0] == start[0] and start[1] < prev_end[1] + 2:
                    yield (prev_end,
                           "E261 at least two spaces before inline comment")
            symbol, sp, comment = text.partition(' ')
            bad_prefix = symbol not in '#:' and (symbol.lstrip('#')[:1] or '#')
            if inline_comment:
                if bad_prefix or comment[:1] in WHITESPACE:
                    yield start, "E262 inline comment should start with '#'"
            elif bad_prefix and (bad_prefix != '!' or start[0] > 1):
                if bad_prefix != '-':
                    yield start, "E265 block comment should start with '-'"
                elif comment:
                    yield start, "E266 too many leading '#' for block comment"
        elif token_type != tokenize.NL:
            prev_end = end

@nedc_register_check
def imports_on_separate_lines(logical_line):
    r"""Place imports on separate lines.

    Okay: import os\nimport sys
    E401: import sys, os

    Okay: from subprocess import Popen, PIPE
    Okay: from myclas import MyClass
    Okay: from foo.bar.yourclass import YourClass
    Okay: import myclass
    Okay: import foo.bar.yourclass
    """
    line = logical_line
    if line.startswith('import '):
        found = line.find(',')
        if -1 < found and ';' not in line[:found]:
            yield found, "E401 multiple imports on one line"

@nedc_register_check
def module_imports_on_top_of_file(logical_line, indent_level, checker_state):
    r"""Place imports at the top of the file.

    Always put imports at the top of the file, just after any module
    comments and docstrings, and before module globals and constants.

    Okay: import os
    Okay: # this is a comment\nimport os
    Okay: '''this is a module docstring'''\nimport os
    Okay: r'''this is a module docstring'''\nimport os
    Okay:
    try:\n\timport x\nexcept ImportError:\n\tpass\nelse:\n\tpass\nimport y
    Okay:
    try:\n\timport x\nexcept ImportError:\n\tpass\nfinally:\n\tpass\nimport y
    E402: a=1\nimport os
    E402: 'One string'\n"Two string"\nimport os
    E402: a=1\nfrom sys import x

    Okay: if x:\n    import os
    """ 
    def is_string_literal(line):
        if line[0] in 'uUbB':
            line = line[1:]
        if line and line[0] in 'rR':
            line = line[1:]
        return line and (line[0] == '"' or line[0] == "'")

    allowed_keywords = (
        'try', 'except', 'else', 'finally', 'with', 'if', 'elif')

    if indent_level:  # Allow imports in conditional statement/function
        return
    if not logical_line:  # Allow empty lines or comments
        return
    line = logical_line
    if line.startswith('import ') or line.startswith('from '):
        if checker_state.get('seen_non_imports', False):
            yield 0, "E402 module level import not at top of file"
    elif re.match(DUNDER_REGEX, line):
        return
    elif any(line.startswith(kw) for kw in allowed_keywords):
        # Allow certain keywords intermixed with imports in order to
        # support conditional or filtered importing
        return
    elif is_string_literal(line):
        # The first literal is a docstring, allow it. Otherwise, report
        # error.
        if checker_state.get('seen_docstring', False):
            checker_state['seen_non_imports'] = True
        else:
            checker_state['seen_docstring'] = True
    else:
        checker_state['seen_non_imports'] = True

@nedc_register_check
def bare_except(logical_line):
    r"""When catching exceptions, mention specific exceptions when
    possible.

    Okay: except Exception:
    Okay: except BaseException:
    E722: except:
    """

    match = BLANK_EXCEPT_REGEX.match(logical_line)
    if match:
        yield match.start(), "E722 do not use bare 'except'"

@nedc_register_check
def maximum_doc_length(logical_line, max_doc_length, tokens):
    r"""Limit all doc lines to a maximum of 80 characters.

    For flowing long blocks of text (docstrings or comments), limiting
    the length to 80 characters is recommended.

    Reports warning W505
    """
    if max_doc_length is None:
        return

    prev_token = None
    skip_lines = set()
    # Skip lines that
    for token_type, text, start, end, line in tokens:
        if token_type not in SKIP_COMMENTS.union([tokenize.STRING]):
            skip_lines.add(line)

    for token_type, text, start, end, line in tokens:
        # Skip lines that aren't pure strings
        if token_type == tokenize.STRING and skip_lines:
            continue
        if token_type in (tokenize.STRING, tokenize.COMMENT):
            # Only check comment-only lines
            if prev_token is None or prev_token in SKIP_TOKENS:
                lines = line.splitlines()
                for line_num, physical_line in enumerate(lines):
                    if hasattr(physical_line, 'decode'):  # Python 2
                        # The line could contain multi-byte characters
                        try:
                            physical_line = physical_line.decode('utf-8')
                        except UnicodeError:
                            pass
                    if start[0] + line_num == 1 and line.startswith('#!'):
                        return
                    length = len(physical_line)
                    chunks = physical_line.split()
                    if token_type == tokenize.COMMENT:
                        if (len(chunks) == 2 and
                                length - len(chunks[-1]) < MAX_DOC_LENGTH):
                            continue
                    if len(chunks) == 1 and line_num + 1 < len(lines):
                        if (len(chunks) == 1 and
                                length - len(chunks[-1]) < MAX_DOC_LENGTH):
                            continue
                    if length > max_doc_length:
                        doc_error = (start[0] + line_num, max_doc_length)
                        yield (doc_error, "W505 doc line too long "
                                          "(%d > %d characters)"
                               % (length, max_doc_length))
        prev_token = token_type

def nedc_header_check(file):
    if not re.match(NEDC_FILE_HEADER_REGEX, file):
        return print(f"\nAt the top of your script please make sure to have: \n{NEDC_FILE_HEADER_STRING}")

def nedc_gen_import_check(file):
    if not re.search(NEDC_GENERAL_IMPORT_REGEX, file):
        return print(f"\nAt the top of your import please add: \n{NEDC_GENERAL_IMPORT_STRING}")
        
def nedc_nedc_import_check(file):
    if not re.search(NEDC_NEDC_IMPORT_REGEX, file):
        return print(f"\nAt the top of your NEDC modules import please add: \n{NEDC_NEDC_IMPORT_STRING}")

def nedc_global_var_header(file):
    if not re.search(NEDC_GLOBAL_VARIABLE_COMMENT_REGEX, file):
        return print(f"\nPlease include and put your global variable under: \n{NEDC_GLOBAL_VARIABLE_COMMENT_STRING}")

def nedc_function_header(file):
    if not re.search(NEDC_FUNCTION_COMMENT_REGEX, file):
        return print(f"\nPlease include and put your function(s) under: \n{NEDC_FUNCTION_COMMENT_STRING}")

def nedc_function_define_header(file):
    if len(re.findall(NEDC_FUNCTION_CHECKER_REGEX, file)) != len(re.findall(NEDC_FUNCTION__HEADER_COMMENT_REGEX, file)):
        return print(f"\nPlease define the top of each function with this format:\n{NEDC_FUNCTION_HEADER_COMMENT_STRING}")

def nedc_main_function_header(file):
    if not re.search(NEDC_MAIN_FUNCTION_REGEX, file):
        return print(f"\nAt the top of your main function please add \n{NEDC_MAIN_FUNCTION_STRING}")

#------------------------------------------------------------------------------
#
# classes are listed here
#
#------------------------------------------------------------------------------

class Checker():
    """Load a Python source file, tokenize it, check coding style."""

    def __init__(self, filename=None, lines=None,
                 options=None, report=None, **kwargs):
        self._physical_line_checks = FinalReport.nedc_checks(self,'physical_line')
        self._logical_line_checks = FinalReport.nedc_checks(self,'logical_line')
        self.max_line_length = MAX_LINE_LENGTH
        self.max_doc_length = MAX_DOC_LENGTH
        self.indent_size = INDENT_SIZE
        self.multiline = False  # in a multiline string?
        self.indent_size = INDENT_SIZE
        self.verbose = 0
        self.filename = filename
        # Dictionary where a checker can store its custom state.
        self._checker_states = {}
        self.lines = readlines(filename)
        if self.lines:
            ord0 = ord(self.lines[0][0])
            if ord0 in (0xef, 0xfeff):  # Strip the UTF-8 BOM
                if ord0 == 0xfeff:
                    self.lines[0] = self.lines[0][1:]
                elif self.lines[0][:3] == '\xef\xbb\xbf':
                    self.lines[0] = self.lines[0][3:]

        self.report = options.report
        self.report_error = self.report.error

    def readline(self):
        """Get the next line from the input buffer."""
        if self.line_number >= self.total_lines:
            return ''
        line = self.lines[self.line_number]
        self.line_number += 1
        if self.indent_char is None and line[:1] in WHITESPACE:
            self.indent_char = line[0]
        return line

    def run_check(self, check, argument_names):
        """Run a check plugin."""
        arguments = []
        for name in argument_names:
            arguments.append(getattr(self, name))
        return check(*arguments)

    def init_checker_state(self, name, argument_names):
        """Prepare custom state for the specific checker plugin."""
        if 'checker_state' in argument_names:
            self.checker_state = self._checker_states.setdefault(name, {})

    def check_physical(self, line):
        """Run all physical checks on a raw input line."""
        self.physical_line = line
        for name, check, argument_names in self._physical_line_checks:
            self.init_checker_state(name, argument_names)
            result = self.run_check(check, argument_names)
            if result is not None:
                (offset, text) = result
                self.report_error(self.line_number, offset, text, check)
                if text[:4] == 'E101':
                    self.indent_char = line[0]

    def build_tokens_line(self):
        """Build a logical line from tokens."""
        logical = []
        comments = []
        length = 0
        prev_row = prev_col = mapping = None
        for token_type, text, start, end, line in self.tokens:
            if token_type in SKIP_TOKENS:
                continue
            if not mapping:
                mapping = [(0, start)]
            if token_type == tokenize.COMMENT:
                comments.append(text)
                continue
            if token_type == tokenize.STRING:
                text = mute_string(text)
            if prev_row:
                (start_row, start_col) = start
                if prev_row != start_row:    # different row
                    prev_text = self.lines[prev_row - 1][prev_col - 1]
                    if prev_text == ',' or (prev_text not in '{[(' and
                                            text not in '}])'):
                        text = ' ' + text
                elif prev_col != start_col:  # different column
                    text = line[prev_col:start_col] + text
            logical.append(text)
            length += len(text)
            mapping.append((length, end))
            (prev_row, prev_col) = end
        self.logical_line = ''.join(logical)
        return mapping

    def check_logical(self):
        """Build a line from tokens and run all logical checks on it."""
        self.report.increment_logical_line()
        mapping = self.build_tokens_line()
        if not mapping:
            return

        mapping_offsets = [offset for offset, _ in mapping]
        (start_row, start_col) = mapping[0][1]
        start_line = self.lines[start_row - 1]
        self.indent_level = expand_indent(start_line[:start_col])
        if self.blank_before < self.blank_lines:
            self.blank_before = self.blank_lines
        if self.verbose >= 2:
            print(self.logical_line[:80].rstrip())
        for name, check, argument_names in self._logical_line_checks:
            if self.verbose >= 4:
                print('   ' + name)
            self.init_checker_state(name, argument_names)
            for offset, text in self.run_check(check, argument_names) or ():
                if not isinstance(offset, tuple):
                    # As mappings are ordered, bisecting is a fast way
                    # to find a given offset in them.
                    token_offset, pos = mapping[bisect.bisect_left(
                        mapping_offsets, offset)]
                    offset = (pos[0], pos[1] + offset - token_offset)
                self.report_error(offset[0], offset[1], text, check)
        if self.logical_line:
            self.previous_indent_level = self.indent_level
            self.previous_logical = self.logical_line
            if not self.indent_level:
                self.previous_unindented_logical_line = self.logical_line
        self.blank_lines = 0
        self.tokens = []

    def generate_tokens(self):
        """Tokenize file, run physical line checks and yield tokens."""
        tokengen = tokenize.generate_tokens(self.readline)
        try:
            prev_physical = ''
            for token in tokengen:
                if token[2][0] > self.total_lines:
                    return
                self.maybe_check_physical(token, prev_physical)
                yield token
                prev_physical = token[4]
        except (SyntaxError, tokenize.TokenError):
            return

    def maybe_check_physical(self, token, prev_physical):
        """If appropriate for token, check current physical line(s)."""
        # Called after every token, but act only on end of line.

        # a newline token ends a single physical line.
        if _is_eol_token(token):
            # if the file does not end with a newline, the NEWLINE
            # token is inserted by the parser, but it does not contain
            # the previous physical line in `token[4]`
            if token[4] == '':
                self.check_physical(prev_physical)
            else:
                self.check_physical(token[4])
        elif token[0] == tokenize.STRING and '\n' in token[1]:
            # Less obviously, a string that contains newlines is a
            # multiline string, either triple-quoted or with internal
            # newlines backslash-escaped. Check every physical line in
            # the string *except* for the last one: its newline is
            # outside of the multiline string, so we consider it a
            # regular physical line, and will check it like any other
            # physical line.
            #
            # Subtleties:
            # - we don't *completely* ignore the last line; if it
            #   contains the magical "# noqa" comment, we disable all
            #   physical checks for the entire multiline string
            # - have to wind self.line_number back because initially it
            #   points to the last line of the string, and we want
            #   check_physical() to give accurate feedback
            self.multiline = True
            self.line_number = token[2][0]
            _, src, (_, offset), _, _ = token
            src = self.lines[self.line_number - 1][:offset] + src
            for line in src.split('\n')[:-1]:
                self.check_physical(line + '\n')
                self.line_number += 1
            self.multiline = False

    def check_all(self, expected=None, line_offset=0):
        """Run all checks on the input file."""
        self.report.init_file(self.filename, self.lines)
        self.total_lines = len(self.lines)
        self.line_number = 0
        self.indent_char = None
        self.indent_level = self.previous_indent_level = 0
        self.previous_logical = ''
        self.previous_unindented_logical_line = ''
        self.tokens = []
        self.blank_lines = self.blank_before = 0
        parens = 0
        for token in self.generate_tokens():
            self.tokens.append(token)
            token_type, text = token[0:2]
            if self.verbose >= 3:
                if token[2][0] == token[3][0]:
                    pos = '[{}:{}]'.format(token[2][1] or '', token[3][1])
                else:
                    pos = 'l.%s' % token[3][0]
                print('l.%s\t%s\t%s\t%r' %
                      (token[2][0], pos, tokenize.tok_name[token[0]], text))
            if token_type == tokenize.OP:
                if text in '([{':
                    parens += 1
                elif text in '}])':
                    parens -= 1
            elif not parens:
                if token_type in NEWLINE:
                    if token_type == tokenize.NEWLINE:
                        self.check_logical()
                        self.blank_before = 0
                    elif len(self.tokens) == 1:
                        # The physical line contains only this token.
                        self.blank_lines += 1
                        del self.tokens[0]
                    else:
                        self.check_logical()
        if self.tokens:
            self.check_physical(self.lines[-1])
            self.check_logical()
        return self.report.get_file_results()

class BaseReport:
    """Collect the results of the checks."""

    def __init__(self):
        # Results
        self.total_errors = 0
        self.counters = dict.fromkeys(BENCHMARK_KEYS, 0)
        self.messages = {}  
   
    def init_file(self, filename, lines):
        """Signal a new file."""
        self.filename = filename
        self.lines = lines
        self.expected = None
        self.line_offset = 0
        self.file_errors = 0
        self.counters['files'] += 1
        self.counters['physical lines'] += len(lines)

    def increment_logical_line(self):
        """Signal a new logical line."""
        self.counters['logical lines'] += 1

    def error(self, line_number, offset, text, check):
        """Report an error, according to options."""
        code = text[:4]
        if code in self.counters:
            self.counters[code] += 1
        else:
            self.counters[code] = 1
            self.messages[code] = text[5:]
    
        self.file_errors += 1
        self.total_errors += 1
        return code

class StandardReport(BaseReport):
    """Collect and print the results of the checks."""

    def __init__(self, options):
        super().__init__()
        self._fmt = REPORT_FORMAT
        self._repeat = True

    
    def init_file(self, filename, lines):
        """Signal a new file."""
        self._deferred_print = []
        return super().init_file(
            filename, lines)

    def error(self, line_number, offset, text, check):
        """Report an error, according to options."""
        code = super().error(line_number, offset, text, check)
        if code and (self.counters[code] == 1 or self._repeat):
            self._deferred_print.append(
                (line_number, offset, code, text[5:]))
        return code

    def get_file_results(self):
        """Print results and return the overall count for this file."""
        if self._deferred_print:
            self._deferred_print.sort()
            for line_number, offset, code, text in self._deferred_print:
                print(self._fmt % {
                    'path': self.filename,
                    'row': self.line_offset + line_number, 'col': offset + 1,
                    'code': code, 'text': text,
                })

                # stdout is block buffered when not stdout.isatty().
                # line can be broken where buffer boundary since other
                # processes write to same file.
                # flush() after print() to avoid buffer boundary.
                # Typical buffer size is 8192. line written safely when
                # len(line) < 8192.
                sys.stdout.flush()
        else:
            print("Check Completed. Congratulations,  your script has been Isipify!")

        return self.file_errors

class FinalReport():

    def __init__(self):
        # build options from the command line
        self.checker_class = Checker
        options = StandardReport
        self.runner = self.input_file
        self.options = options
        self.physical_line_checks = self.nedc_checks('physical_line')
        self.logical_line_checks = self.nedc_checks('logical_line')
        self.astnedc_checks = self.nedc_checks('tree')
        self.init_report()

    def init_report(self):
        """Initialize the report instance."""
        self.options.report = (StandardReport)(self.options)
        return self.options.report

    def check_files(self, paths):
        """Run all checks on the paths."""
        report = StandardReport
        runner = self.runner
        try:
            for path in paths:
                with open(path) as f:
                    file = list(f)
                    header = ''.join(file[:])
                    nedc_header_check(header)
                    nedc_gen_import_check(header)
                    nedc_nedc_import_check(header)
                    nedc_global_var_header(header)
                    nedc_function_header(header)
                    nedc_function_define_header(header)
                    nedc_main_function_header(header)
                runner(path)
        except KeyboardInterrupt:
            print('... stopped')
        return report

    def input_file(self, filename, lines=None, expected=None, line_offset=0):
        """Run all checks on a Python source file."""
        fchecker = self.checker_class(
            filename, lines=lines, options= self.options)
        return fchecker.check_all(expected=expected, line_offset=line_offset)

    def nedc_checks(self, argument_name):
        """Get all the checks for this category.

        Find all globally visible functions where the first argument
        name starts with argument_name and which contain selected tests.
        """
        checks = []
        for check, attrs in nedc_checks[argument_name].items():
            (codes, args) = attrs
            if any(code for code in codes):
                checks.append((check.__name__, check, args))
        return sorted(checks)

# function: main
#
def main(argv):
    FinalReport().check_files(['nedc_pyprint_header.py'])
#
# end of main

# begin gracefully
#
if __name__ == '__main__':
    main(sys.argv[0:])

