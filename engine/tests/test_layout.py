"""How the library is laid out: what each part imports, what it offers, what vaultlib hands on. Run: brain test"""
import ast
import importlib
import os
import types
import unittest

from support import ENGINE, HOOKS, SCRIPTS, vaultlib

import vault_model  # noqa: E402  (support puts engine/lib on the path)

MODULES = sorted(name[:-3] for name in os.listdir(SCRIPTS) if name.endswith(".py"))
# The parts of the library: vaultlib and the modules it is made of. vault_cache is one too, reached by its own name.
LIBRARY = [name for name in MODULES if name.startswith("vault")]


def imports(path):
    """[(module, name, line)] for every import in a file, wherever it stands; `import m` gives the name None."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    rows = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and not node.level:
            rows += [(node.module, alias.name, node.lineno) for alias in node.names]
        elif isinstance(node, ast.Import):
            rows += [(alias.name, None, node.lineno) for alias in node.names]
    return rows


def library_names(path):
    """[(module, name, line)] for every name a file takes from the library: `from vaultlib import X`, and
    `vaultlib.X` after `import vaultlib`."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    taken = [(module, name, line) for module, name, line in imports(path) if module in LIBRARY and name not in (None, "*")]
    known = {alias.asname or alias.name: alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
             for alias in node.names if alias.name in LIBRARY}
    taken += [(known[node.value.id], node.attr, node.lineno) for node in ast.walk(tree)
              if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in known]
    return taken


class Layout(unittest.TestCase):
    def test_the_vocabulary_imports_no_part_of_the_engine(self):
        # Every part may import vault_model, so it can import none of them; the policy stands as low.
        for name in ("vault_model", "vault_policy"):
            needs = {module for module, _, _ in imports(os.path.join(SCRIPTS, name + ".py"))}
            self.assertEqual(needs & set(MODULES), set(), name)

    def test_no_module_imports_in_a_circle(self):
        needs = {name: sorted({module for module, _, _ in imports(os.path.join(SCRIPTS, name + ".py"))} & set(MODULES))
                 for name in MODULES}
        clear = set()  # modules nothing under leads back to

        def follow(name, path):
            self.assertNotIn(name, path, " imports ".join(path + [name]))
            if name not in clear:
                for other in needs[name]:
                    follow(other, path + [name])
                clear.add(name)

        for name in MODULES:
            follow(name, [])
        self.assertIn("vault_model", needs["vault_schema"])  # the arrows point down: the checks need the vocabulary
        self.assertEqual({"vault_intentions", "vault_policy", "vault_tuning"} - set(needs["vault_schema"]), set())

    def test_each_part_says_what_it_offers_and_vaultlib_hands_on_exactly_that(self):
        self.assertEqual(sorted(part.__name__ for part in vaultlib.PARTS),
                         [name for name in LIBRARY if name not in ("vaultlib", "vault_cache")])
        offered = {}
        for part in vaultlib.PARTS:
            for name in part.__all__:
                self.assertNotIn(name, offered, f"{part.__name__} and {offered.get(name)} both offer it")
                offered[name] = part.__name__
                self.assertIs(getattr(vaultlib, name), getattr(part, name), name)
        self.assertEqual(sorted(vaultlib.__all__), sorted([*offered, "Vault"]))
        star = {}
        exec("from vaultlib import *", star)  # what a command gets that asks for everything
        del star["__builtins__"]
        self.assertEqual(sorted(star), sorted(vaultlib.__all__))
        self.assertEqual([name for name, value in star.items() if isinstance(value, types.ModuleType)], [])

    def test_the_vocabulary_offers_every_name_it_defines(self):
        defined = {name for name, value in vars(vault_model).items()
                   if not name.startswith("_") and not isinstance(value, types.ModuleType)}
        self.assertEqual(defined, set(vault_model.__all__))
        # What moved out of it is offered from where it went, under the name it had.
        for name, home in (("schema_problems", "vault_schema"), ("summary_problems", "vault_schema"),
                           ("claim_problems", "vault_schema"), ("verdicts", "vault_graph"),
                           ("Tuning", "vault_tuning"), ("intention_problems", "vault_intentions")):
            self.assertEqual((getattr(vaultlib, name).__module__, name in vaultlib.__all__), (home, True))
        self.assertEqual((vaultlib.CHARACTER_FILE, importlib.import_module("vault_tuning").CHARACTER_FILE),
                         ("CHARACTER.md", "CHARACTER.md"))
        self.assertIs(importlib.import_module("vault_intentions").END, vault_model.END)  # one closing mark, for a goal and a reminder

    def test_every_name_the_engine_takes_from_the_library_is_there(self):
        files = [os.path.join(folder, name) for folder in (SCRIPTS, HOOKS, os.path.join(ENGINE, "tests"))
                 for name in sorted(os.listdir(folder)) if name.endswith(".py")] + [os.path.join(ENGINE, "bin", "brain")]
        missing = [f"{os.path.relpath(path, ENGINE)}:{line}: {module}.{name}" for path in files
                   for module, name, line in library_names(path) if not hasattr(importlib.import_module(module), name)]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
