#!/bin/sh
# Undo what install.sh set up. Your memory is never touched: senses/,
# cortex/, hippocampus/, prefrontal/, dormant/, motor/ and inbox/ stay as
# they are. Delete the folder yourself if you want the brain gone too.
#
#   ./uninstall.sh               remove the scheduled job, plugin, pre-commit hook and `brain` link
#   ./uninstall.sh --hook DIR    also remove the job and the hook of a brain made with --new DIR
#   ./uninstall.sh --dry-run     list what would be removed, change nothing
#
# Safe to run again; every step skips what is already gone.
set -eu

root=$(cd "$(dirname "$0")" && pwd)
extra_dir=""
dry=0

while [ $# -gt 0 ]; do
    case "$1" in
        --hook) extra_dir="${2:?--hook needs a folder}"; shift 2 ;;
        --dry-run|dry-run) dry=1; shift ;;
        -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "uninstall: unknown option $1 (try --help)" >&2; exit 2 ;;
    esac
done

say() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
# Run a command, or only show it under --dry-run.
run() {
    if [ "$dry" = 1 ]; then printf '    would run: %s\n' "$*"; else "$@"; fi
}

# 1. The scheduled job (`brain schedule --set`), first: `brain` is what removes it, and it is
#    still here. Left in place it would go on running this engine every few minutes. A folder
#    that is no brain, or a machine where `brain` does not run, has no job to ask about.
for dir in "$root" ${extra_dir:+"$extra_dir"}; do
    # -B: looking writes nothing, not even Python's own cache, so a dry run changes nothing.
    if BRAIN_ROOT="$dir" python3 -B "$root/engine/bin/brain" schedule --json 2>/dev/null | grep -q '"set": true'; then
        say "Removing the scheduled job of $dir"
        run env BRAIN_ROOT="$dir" python3 "$root/engine/bin/brain" schedule --remove \
            || warn "the job was not removed; run: brain schedule --remove"
    else
        say "No scheduled job for $dir; skipping"
    fi
done

# 2. The Claude Code plugin and its marketplace.
if command -v claude >/dev/null 2>&1; then
    if claude plugin list 2>/dev/null | grep -q 'aibrain@aibrain'; then
        say "Uninstalling plugin aibrain@aibrain"
        run claude plugin uninstall aibrain@aibrain || warn "plugin uninstall failed"
    else
        say "Plugin aibrain@aibrain not installed; skipping"
    fi
    if claude plugin marketplace list 2>/dev/null | grep -q '❯ aibrain$'; then
        say "Removing the aibrain marketplace"
        run claude plugin marketplace remove aibrain || warn "marketplace remove failed"
    else
        say "Marketplace aibrain not registered; skipping"
    fi
else
    say "Claude Code not found; skipping the plugin"
fi

# 3. The pre-commit gate, only where install.sh put it.
if [ "$(git -C "$root" config --get core.hooksPath 2>/dev/null || true)" = "engine/githooks" ]; then
    say "Turning off the pre-commit hook in $root"
    run git -C "$root" config --unset core.hooksPath
else
    say "Pre-commit hook not set in $root; skipping"
fi
if [ -n "$extra_dir" ]; then
    hook="$extra_dir/.git/hooks/pre-commit"
    if [ -f "$hook" ] && grep -q "$root/engine/bin/brain" "$hook"; then
        say "Removing the pre-commit hook from $extra_dir"
        run rm -f "$hook"
    else
        say "No AiBrain pre-commit hook in $extra_dir; skipping"
    fi
fi

# 4. The `brain` link, only if it points at this engine.
link="$HOME/.local/bin/brain"
if [ -L "$link" ] && [ "$(readlink "$link")" = "$root/engine/bin/brain" ]; then
    say "Removing $link"
    run rm -f "$link"
elif [ -e "$link" ]; then
    warn "$link is not this AiBrain's link; leaving it"
else
    say "No brain link in ~/.local/bin; skipping"
fi

if [ "$dry" = 1 ]; then
    printf '\nDry run: nothing was changed.\n'
else
    printf '\nAiBrain is uninstalled. Your brain folder and its pages are untouched.\n'
    printf 'Reinstall any time with ./install.sh\n'
fi
