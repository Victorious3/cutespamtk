import argparse
import importlib

from pathlib import Path

commands = {}
commands_dir = Path(__file__).parent / "commands"

for file in commands_dir.glob("*.py"):
    if file.stem == "__init__": continue
    command = importlib.import_module("cutespam.cli.commands." + file.stem)
    commands[file.stem] = command
         
def main():
    parser = argparse.ArgumentParser(description="Cutespam cli")
    subparser = parser.add_subparsers(dest = "command")
    subparser.required = True

    for name, command in commands.items():
        command_parser = subparser.add_parser(name, description = command.DESCRIPTION, formatter_class = argparse.RawTextHelpFormatter)
        command.args(command_parser)

    args = parser.parse_args()
    commands[args.command].main(args)

if __name__ == "__main__":
    main()