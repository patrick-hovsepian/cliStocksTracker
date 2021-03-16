import argparse
import io
import shlex

from colorama import Fore, Style
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Callable

# TODO: better with a map like columns?
# give each command it's own arg parser?
@dataclass
class CommandType(Enum):
    NONE = ""
    PRINT_PORTFOLIO_SUMMARY = "print_port"
    PRINT_PORTFOLIO_GRAPH = "print_graph"
    LIVE_TICKERS = "live_ticker"
    EXIT = "exit"

@dataclass
class CommandParser:
    parsers = {}

    def __post_init__(self):
        self.parsers[CommandType.NONE.value] = None
        self.parsers[CommandType.PRINT_PORTFOLIO_SUMMARY.value] = self._generate_portfolio_summary_parser()
        self.parsers[CommandType.PRINT_PORTFOLIO_GRAPH.value] = self._generate_portfolio_summary_parser()
        self.parsers[CommandType.LIVE_TICKERS.value] = self._generate_portfolio_summary_parser()
        self.parsers[CommandType.EXIT.value] = self._generate_portfolio_summary_parser()

    def _generate_portfolio_summary_parser(self):
        parser = argparse.ArgumentParser(description="Print Portfolio Summary", )
        parser.add_argument(
            "--width",
            type=int,
            help="integer for the width of the table (default is 80)",
            default=80,
        )
        return parser

    def parse_command(self, raw_cmd: str) -> (CommandType, argparse.Namespace):
        if (len(raw_cmd) == 0):
            print(f'{Fore.RED} Please specify a command')
            return CommandType.NONE, None

        argument_list = shlex.split(raw_cmd)
        
        # first argument should be the actual command
        cmd = argument_list[0]
        if (cmd not in self.parsers):
            print(f'{Fore.RED} Invalid command "{cmd}" specified')
            return CommandType.NONE, None

        # remove the command part to supply true args to parser
        argument_list = argument_list[1:]
        parser = self.parsers[cmd]

        # return command type and the parsed arguments
        args, unknown = parser.parse_known_args(argument_list)
        return CommandType(cmd), args

@dataclass
class Commander:
    master_parser = CommandParser()
    curr_command = CommandType.NONE

    def prompt_and_handle_command(self):
        print(Fore.CYAN + "Please input a command: ", end="")

        raw_cmd = str(input())
        cType, args = self.master_parser.parse_command(raw_cmd)
