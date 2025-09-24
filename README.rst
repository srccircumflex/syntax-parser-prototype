syntax-parser-prototype
#######################

Basic objects for the specific implementation of a syntax parser.

Object categories
-----------------

[.*]Token
    (Parsing result) single token

[.*]Branch
    (Parsing result) container for tokens

Root[.*]
    objects for the top level (not intended for modification)

Phrase
    configuration object whose behavior is to be implemented by modifying the class.

    The main behavior is implemented by the more detailed definition of the ``start`` and ``end`` methods.
    Additional predetermined interfaces are also declared in the corresponding docstrings.

    Nesting, branches, and suffixes are defined by passing additional phrase derivatives to a instace.

Parsing
-------

The top-level object ``RootPhrase`` provides the entry points for the parsing process.
The result will be a ``RootBranch``.