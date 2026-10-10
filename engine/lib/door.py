"""One door for a note taken away from the desk: a folder that syncs to this machine.

Usage:
    brain door                  where the door is and what waits there; writes nothing
    brain door FOLDER           open it: what is saved in FOLDER comes into inbox/
    brain door --pull           bring in what waits there now
    brain door --close          close it; FOLDER and what is in it stay as they are

FOLDER is one that a sync service keeps on this machine and on the phone
(iCloud Drive, Dropbox, Syncthing): a note or a file saved there from anywhere
is on this disk soon after. Each session's briefing brings in what it finds
(`--pull` does the same by hand): every file is moved, not copied, into
inbox/, so the door is empty again and nothing comes in twice. From there it
is a note like any other: `brain inbox` sorts it and /ingest encodes it.

The door is the link inbox/.door, which git ignores: it names a folder of this
machine, so a second machine opens its own. Nothing is kept anywhere else.

Never over a note that is there: a name already in inbox/ gets `-2`. Left at
the door, and said: folders, a file named README.md (inbox/ keeps that name
for its own note), and a file that cannot be moved yet (not downloaded, in
use). Passed over without a word: hidden files and the half-written files
sync services leave (.tmp, .part, .icloud, .crdownload).

FOLDER must be outside this brain. No log line: a note in inbox/ is no memory
yet, and /ingest logs it when it is.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402

INBOX, LINK = "inbox", os.path.join("inbox", ".door")
OWN = "README.md"                                    # inbox/ keeps this name for the note on the folder
UNFINISHED = (".tmp", ".part", ".icloud", ".crdownload")  # what a sync or a download has not finished writing


def door_of(root):
    """The folder the door leads to, or None when there is no door. It may not be there (a disk not mounted)."""
    link = os.path.join(root, LINK)
    return os.path.realpath(link) if os.path.islink(link) else None


def waiting(folder):
    """(the files at the door by name, what is there and stays: folders and a README.md)."""
    files, stays = [], []
    for name in sorted(os.listdir(folder)):
        if name.startswith(".") or name.lower().endswith(UNFINISHED):
            continue
        if os.path.isdir(os.path.join(folder, name)) or name == OWN:
            stays.append(name)
        else:
            files.append(name)
    return files, stays


def free_name(folder, name):
    """`name`, or `name-2`, `name-3`: the first that no file in `folder` has."""
    stem, kind = os.path.splitext(name)
    n, free = 1, name
    while os.path.lexists(os.path.join(folder, free)):
        n += 1
        free = f"{stem}-{n}{kind}"
    return free


def look(root):
    """{door, unreachable, waiting, left}: the door's folder, the files waiting at it, and what stays there."""
    found = {"door": door_of(root), "unreachable": False, "waiting": [], "left": []}
    if found["door"]:
        try:
            found["waiting"], found["left"] = waiting(found["door"])
        except OSError:  # not mounted, renamed, or a folder this program may not read
            found["unreachable"] = True
    return found


def pull(root):
    """Move what waits at the door into inbox/; {door, unreachable, brought, left}. Nothing to do without a door.

    `brought` is the notes as they are now named in inbox/; `left` is what stayed at the door.
    """
    found = look(root)
    brought = []
    for name in found.pop("waiting"):
        to = free_name(os.path.join(root, INBOX), name)
        try:
            shutil.move(os.path.join(found["door"], name), os.path.join(root, INBOX, to))
        except OSError:  # not downloaded yet, in use, no permission: it waits for the next time
            found["left"].append(name)
        else:
            brought.append(f"{INBOX}/{to}")
    return dict(found, brought=brought)


def open_door(root, folder):
    """Point inbox/.door at `folder`; the folder it led to before, or None."""
    target, brain = os.path.realpath(os.path.expanduser(folder)), os.path.realpath(root)
    if not os.path.isdir(target):
        raise Refused(f"not a folder: {target}")
    if os.path.commonpath([target, brain]) == brain:
        raise Refused("that folder is inside this brain: the door leads in from somewhere else")
    before, link = door_of(root), os.path.join(root, LINK)
    if os.path.lexists(link) and not os.path.islink(link):
        raise Refused(f"{LINK} is there and is not a link: move it away first")
    os.makedirs(os.path.join(root, INBOX), exist_ok=True)
    if before:
        os.remove(link)
    os.symlink(target, link)
    return before


def arguments(ap):
    ap.add_argument("folder", nargs="?")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--close", action="store_true")


def run(root, args):
    if sum(map(bool, (args.folder, args.pull, args.close))) > 1:
        raise Refused("brain door: one thing at a time: a FOLDER to open, --pull, or --close")
    if args.folder:
        try:
            before = open_door(root, args.folder)
        except Refused as why:
            raise Refused(f"brain door: {why}") from None
        return {"door": door_of(root), "was": before, "did": "opened"}
    if args.close:
        before = door_of(root)
        if before:
            os.remove(os.path.join(root, LINK))
        return {"door": None, "was": before, "did": "closed"}
    return dict(pull(root) if args.pull else look(root), did="pulled" if args.pull else "looked")


def render(r, args):
    if r["did"] == "opened":
        return (f"door open: what is saved in {r['door']} comes into inbox/ at the next session"
                + (f"\n  it led to {r['was']} before" if r["was"] and r["was"] != r["door"] else ""))
    if r["did"] == "closed":
        return f"door closed: {r['was']} and what is in it stay as they are" if r["was"] else "no door was open"
    if not r["door"]:
        return "no door: `brain door FOLDER` opens one, for a folder that syncs to this machine"
    if r["unreachable"]:
        return (f"the door leads to {r['door']}, which cannot be read (not mounted, renamed, or closed to this "
                "program): `brain door FOLDER` moves it")
    stays = f"\n  left there: {', '.join(r['left'])}" if r["left"] else ""
    if r["did"] == "pulled":
        return f"door: {len(r['brought'])} notes brought into inbox/ from {r['door']}" + "".join(
            f"\n  {note}" for note in r["brought"]) + stays
    return f"door: {r['door']}, {len(r['waiting'])} notes waiting there (the next session brings them in)" + stays
