"""Refused: how a command says it will not do what was asked, and why.

A command raises it with the reason. `brain` prints the reason on stderr and exits with
`code`: 1, or 2 for arguments it cannot read. A caller in the same process (a test, the
worker, the MCP server) catches it and goes on.

It is here, with nothing beside it, so that a module which only refuses does not load the
dispatcher to say so. lib/commands.py offers it again for a caller outside the engine:
`from commands import Refused, call`.
"""


class Refused(Exception):
    """The command did not do what was asked, and says why. `code` is what `brain` exits with."""

    def __init__(self, reason, code=1):
        super().__init__(reason)
        self.code = code
