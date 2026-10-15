"""Files written whole: how a file that is rewritten never stands half written.

Opening a file for writing empties it first. A process that dies before it has written, or
two that write at once (a session and the job nobody watches), leave it short, and git
gives back only what was committed. So a file that is rewritten from start to end is
written here:

    write_whole   the text goes into a new file beside the target, and that file then takes
                  the target's place in one step (os.replace). A reader finds the old file or
                  the new one, never a part of either

No dependencies. It is for a file one writer replaces. A file that grows by a line (the
log, the fingerprints) is appended to by its own writer and never comes here.
"""
import contextlib
import os
import shutil


def write_whole(path, text, encoding="utf-8", errors=None):
    """Put `text` at `path` in one step, in place of whatever is there. `encoding` and `errors` are `open`'s.

    The file written beside it is named after the target and this process, so two writers
    never share one, and it is removed if the write fails: the target is then as it was. A
    target that is there keeps its permissions, and a link is followed to the file it names.
    """
    path = os.path.realpath(path)
    beside = f"{path}.{os.getpid()}.tmp"
    try:
        with open(beside, "w", encoding=encoding, errors=errors) as fh:
            fh.write(text)
        if os.path.exists(path):
            shutil.copymode(path, beside)
        os.replace(beside, path)
    finally:
        with contextlib.suppress(FileNotFoundError):  # there only when the write or the move failed
            os.remove(beside)
