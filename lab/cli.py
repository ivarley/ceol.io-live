"""`venv/bin/python -m lab <command>`.

Each command is a module under lab/ exposing `add_parser(subparsers)` and
`main(args)`. Modules are imported lazily so `lab --help` does not pay for
librosa, and so a half-built command cannot break the others.
"""

import argparse
import importlib
import sys

import lab.env  # noqa: F401  (sys.path + .env)

# command name -> module path. Order is the order in --help.
COMMANDS = {
    "pull": "lab.corpus.pull",
    "prepare": "lab.audio.prepare",
    "index": "lab.corpus.index",
    "bench": "lab.bench.cli",
    "run": "lab.engine.run",
    "eval": "lab.eval.report",
    "diff": "lab.eval.diff",
    "display": "lab.eval.display",
    "runs": "lab.tools.runs",
    "board": "lab.tools.dump",
    "transcribe": "lab.tools.transcribe",
    "timeline": "lab.tools.timeline",
    "trace-set": "lab.tools.traceset",
    "compare": "lab.tools.compare",
    "suspects": "lab.tools.suspects",
    "view": "lab.tools.viewer",
    "listen": "lab.tools.listen",
    "drafts": "lab.tools.drafts",
    "coreml": "lab.tools.coreml",
}


def build_parser():
    parser = argparse.ArgumentParser(prog="lab", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", metavar="command")
    for name, module_path in COMMANDS.items():
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as e:
            # Only swallow "the command module itself is missing" (not built
            # yet); a missing dependency inside a built command should surface.
            if e.name and module_path.startswith(e.name):
                continue
            raise
        module.add_parser(sub)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
