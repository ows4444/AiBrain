"""File names: how words become one, and what a file is called when its name is taken.

Whatever lands in the brain lands under a name made here, so each rule is written once:

    slug        lower-case letters and digits with a hyphen between them, which is the
                file name rule of CLAUDE.md > Page contracts
    free_name   a file never lands on another: the second of a name is `name-2`,
                the third `name-3`, the number before the file's ending
    quoted      a frontmatter value a reader could take for something else, as a
                double-quoted YAML string; unquoted is the way back
    some        the first few of a list of names on one line, and how many more there are

No dependencies, and nothing here writes: the caller creates the file under the name it is given.
"""
import os
import re

RUN = re.compile(r"[a-z0-9]+")


def slug(text, limit=None, words=None):
    """`text` as a file name: its runs of lower-case letters and digits, a hyphen between them; "" when it has none.

    At most `words` of them, then at most `limit` characters, and never a hyphen at the end.
    """
    return "-".join(RUN.findall(text.lower())[:words])[:limit].strip("-")


def numbered(name, n):
    """What the `n`-th file of one name is called: `name` for the first, then `name-2`, `name-3`."""
    stem, kind = os.path.splitext(name)
    return name if n == 1 else f"{stem}-{n}{kind}"


def free_name(folder, name):
    """`name`, or the first of `name-2`, `name-3`, ... that nothing in `folder` has. A link that leads nowhere has it too."""
    n = 1
    while os.path.lexists(os.path.join(folder, numbered(name, n))):
        n += 1
    return numbered(name, n)


def some(names, shown):
    """The first `shown` of these names with commas between them, then `and N more` when there are more."""
    return ", ".join(names[:shown]) + (f" and {len(names) - shown} more" if len(names) > shown else "")


def quoted(value):
    """`value` as a double-quoted YAML string."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def unquoted(value):
    """What `quoted` was given, from what a reader of the frontmatter is left with once the quotes are off."""
    return re.sub(r'\\(["\\])', r"\1", value)


def quoted_line(value):
    """The same on one line, its white space folded: a title taken from a page's markup breaks anywhere."""
    return quoted(re.sub(r"\s+", " ", value))
