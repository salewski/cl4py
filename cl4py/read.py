import io
import re
from .readtable import SyntaxType,Readtable
from .data import *

readtable = Readtable()
labels = None

# An implementation of the Common Lisp reader algorithm, with the following
# simplifications and changes:
#
# 1. Whitespace is never preserved.
# 2. READ always assumes EOF error to be true.
# 3. READTABLE-CASE is always :UPCASE.
# 4. *READ-EVAL* is always false.
# 5. *READ-BASE* is always 10.
# 6. There are no invalid characters.

class Stream:
    def __init__(self, textstream):
        self.stream = textstream
        self.old = None
        self.new = None
    def read_char(self, eof_error=True):
        if self.new == None:
            c = self.stream.read(1)
            if eof_error and not c: raise EOFError()
        else:
            c = self.new
        self.old, self.new = c, None
        return c
    def unread_char(self):
        if self.old:
            self.old, self.new = None, self.old
        else:
            raise RuntimeError('Duplicate unread_char.')


def read_from_string(string):
    return read(io.StringIO(string))


def read(stream, recursive=False):
    if not isinstance(stream, Stream):
        stream = Stream(stream)
    while True:
        # 1. read one character
        x = stream.read_char()

        syntax_type = readtable.syntax_type(x)
        # 3. whitespace
        if syntax_type == SyntaxType.WHITESPACE:
            continue
        # 4. macro characters
        elif (syntax_type == SyntaxType.TERMINATING_MACRO_CHARACTER or
              syntax_type == SyntaxType.NON_TERMINATING_MACRO_CHARACTER):
            value = readtable.get_macro_character(x)(stream, x)
            if value == None:
                continue
            else:
                return value
        # 5. single escape character
        elif syntax_type == SyntaxType.SINGLE_ESCAPE:
            token = [stream.read_char()]
            escape = False
        # 6. multiple escape character
        elif syntax_type == SyntaxType.MULTIPLE_ESCAPE:
            token = []
            escape = True
        # 7. constituent character
        else:
            token = [x.upper()]
            escape = False

        while True:
            y = stream.read_char(False)
            if not y: break
            syntax_type = readtable.syntax_type(y)
            if not escape:
                # 8. even number of multiple escape characters
                if syntax_type == SyntaxType.SINGLE_ESCAPE:
                    token.append(stream.read_char())
                elif syntax_type == SyntaxType.MULTIPLE_ESCAPE:
                    escape = True
                elif syntax_type == SyntaxType.TERMINATING_MACRO_CHARACTER:
                    stream.unread_char()
                    break
                elif syntax_type == SyntaxType.WHITESPACE:
                    stream.unread_char()
                    break
                else:
                    token.append(y.upper())
            else:
                # 9. odd number of multiple escape characters
                if syntax_type == SyntaxType.SINGLE_ESCAPE:
                    token.append(stream.read_char())
                elif syntax_type == SyntaxType.MULTIPLE_ESCAPE:
                    escape = False
                else:
                    token.append(y)

        # 10.
        return parse(''.join(token))


def read_delimited_list(delim, stream, recursive):
    def skip_whitespace():
        while True:
            x = stream.read_char()
            if readtable.syntax_type(x) != SyntaxType.WHITESPACE:
                stream.unread_char()
                break

    head = Cons(None, None)
    tail = head
    while True:
        skip_whitespace()
        x = stream.read_char()
        if x == delim:
            return head.cdr
        elif x == '.':
            tail.cdr = read(stream, True)
            # TODO handle errors
        else:
            stream.unread_char()
            cons = Cons(read(stream, True), None)
            tail.cdr = cons
            tail = cons

def left_parenthesis(stream, char):
    return read_delimited_list(')', stream, True)


def right_parenthesis(stream, char):
    raise RuntimeError('Unmatched closing parenthesis.')


def single_quote(stream, char):
    return Cons("COMMON-LISP:QUOTE", Cons(read(stream, True), None))


def double_quote(stream, char):
    result = ''
    while True:
        c = stream.read_char()
        if c == '"':
            return String(result)
        elif c == '\\':
            result += stream.read_char()
        else:
            result += c


def semicolon(stream, char):
    while stream.read_char() != '\n': pass


def sharpsign(stream, char):
    digits = ''
    while True:
        c = stream.read_char()
        if c.isdigit():
            digits += c
        else:
            schar = c.upper()
            break
    n = int(digits) if digits else 0
    return readtable.get_dispatch_macro_character('#', schar)(stream, schar, n)


def sharpsign_backslash(s, c, n):
    # TODO
    return s.read()

def sharpsign_left_parenthesis(s, c, n):
    return list(read_delimited_list(")", s, True))


readtable.set_macro_character('(', left_parenthesis)
readtable.set_macro_character(')', right_parenthesis)
readtable.set_macro_character("'", single_quote)
readtable.set_macro_character('"', double_quote)
readtable.set_macro_character('#', sharpsign)
readtable.set_dispatch_macro_character('#', '\\', sharpsign_backslash)
readtable.set_dispatch_macro_character('#', '(', sharpsign_left_parenthesis)