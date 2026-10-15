
from jsonlint_plus.lexer import Lexer

source = '{"age": 20}'

tokens = Lexer(source).tokenize()

for token in tokens:
    print(token)
