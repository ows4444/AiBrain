#!/bin/sh
# Install AiBrain on this machine.
#
#   ./install.sh               set up this folder as a brain
#   ./install.sh --new DIR     also create a fresh, empty brain in DIR
#   ./install.sh --no-path     skip linking `brain` into ~/.local/bin
#   ./install.sh --no-hook     skip the pre-commit gate
#   ./install.sh --no-plugin   skip registering the Claude Code plugin
#
# Steps: check requirements, register the aibrain plugin with Claude Code,
# turn on the pre-commit hook, put `brain` on PATH, run the engine's tests.
# Safe to run again; every step skips what is already done.
set -eu

root=$(cd "$(dirname "$0")" && pwd)
new_dir=""
link_path=1
git_hook=1
plugin=1

while [ $# -gt 0 ]; do
    case "$1" in
        --new) new_dir="${2:?--new needs a folder}"; shift 2 ;;
        --no-path) link_path=0; shift ;;
        --no-hook) git_hook=0; shift ;;
        --no-plugin) plugin=0; shift ;;
        -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "install: unknown option $1 (try --help)" >&2; exit 2 ;;
    esac
done

say() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() { printf 'install: %s\n' "$*" >&2; exit 1; }

# 1. Requirements: python3 >= 3.9 (stdlib only, no pip), git, Claude Code.
say "Checking requirements"
command -v python3 >/dev/null 2>&1 || die "python3 not found; install Python 3.9 or newer"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' \
    || die "Python 3.9 or newer is needed (found $(python3 --version 2>&1))"
command -v git >/dev/null 2>&1 || die "git not found"
have_claude=1
if ! command -v claude >/dev/null 2>&1; then
    have_claude=0
    warn "Claude Code (claude) not found; the skills (/ingest, /ask, ...) need it."
    warn "Install it from https://claude.com/claude-code, then run this script again."
fi
chmod +x "$root/engine/bin/brain" "$root/engine/githooks/pre-commit"

# 2. Optional: a fresh brain from the template.
if [ -n "$new_dir" ]; then
    if [ -e "$new_dir/cortex" ] || [ -e "$new_dir/hippocampus" ]; then
        die "$new_dir already holds a brain; not overwriting it"
    fi
    say "Creating a new brain in $new_dir"
    mkdir -p "$new_dir"
    cp -R "$root/engine/templates/brain/." "$new_dir/"
    mkdir -p "$new_dir/.claude"
    cp "$root/.claude/settings.json" "$new_dir/.claude/settings.json"
    # What git must not keep (.cache/, exports) and how it merges the append-only files.
    cp "$root/.gitignore" "$root/.gitattributes" "$new_dir/"
    if [ ! -d "$new_dir/.git" ]; then
        git -C "$new_dir" init -q
    fi
fi

# 3. The Claude Code plugin: this repo is its own marketplace (.claude-plugin/).
if [ "$have_claude" = 1 ] && [ "$plugin" = 1 ]; then
    if claude plugin marketplace list 2>/dev/null | grep -q '❯ aibrain$'; then
        say "Marketplace 'aibrain' already registered; refreshing"
        claude plugin marketplace update aibrain >/dev/null || warn "marketplace update failed"
    else
        say "Registering the aibrain marketplace from $root"
        claude plugin marketplace add "$root" || die "could not add the marketplace"
    fi
    if claude plugin list 2>/dev/null | grep -q 'aibrain@aibrain'; then
        say "Plugin aibrain@aibrain already installed"
    else
        say "Installing plugin aibrain@aibrain"
        claude plugin install aibrain@aibrain || die "could not install the plugin"
    fi
fi

# 4. The pre-commit gate: the same checks CI runs.
if [ "$git_hook" = 1 ]; then
    for dir in "$root" ${new_dir:+"$new_dir"}; do
        if git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
            if [ "$dir" = "$root" ]; then
                say "Turning on the pre-commit hook in $dir"
                git -C "$dir" config core.hooksPath engine/githooks
            else
                say "Turning on the pre-commit hook in $dir"
                mkdir -p "$dir/.git/hooks"
                cp "$root/engine/githooks/pre-commit" "$dir/.git/hooks/pre-commit"
                # A new brain has no engine/ of its own: point the hook at this one.
                sed -i.bak "s|^brain=.*|brain=\"$root/engine/bin/brain\"|" "$dir/.git/hooks/pre-commit"
                rm -f "$dir/.git/hooks/pre-commit.bak"
                chmod +x "$dir/.git/hooks/pre-commit"
            fi
        fi
    done
fi

# 5. `brain` on PATH outside Claude Code too.
if [ "$link_path" = 1 ]; then
    bin="$HOME/.local/bin"
    mkdir -p "$bin"
    ln -sf "$root/engine/bin/brain" "$bin/brain"
    say "Linked $bin/brain"
    case ":$PATH:" in
        *":$bin:"*) ;;
        *) warn "$bin is not on PATH; add to your shell profile: export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
    esac
fi

# 6. Prove it works.
say "Running the engine's tests"
python3 "$root/engine/bin/brain" test >/dev/null 2>&1 \
    || die "engine tests failed; run: python3 engine/bin/brain test"
say "Checking the brain"
if ! BRAIN_ROOT="${new_dir:-$root}" python3 "$root/engine/bin/brain" check >/dev/null 2>&1; then
    warn "brain check found defects; run: brain check"
fi

cat <<EOF

AiBrain is installed.

Next:
  cd ${new_dir:-$root}
  claude
  /start          guided first run (who you are, your goals)
  /ingest         after dropping notes in inbox/ or files in senses/
  /ask <question> answer from your pages
  brain --help    the command-line instruments
EOF
