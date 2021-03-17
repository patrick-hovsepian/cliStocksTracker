import argparse
import io
import shlex
import os
import sys
import multiconfigparser

from colorama import Fore, Style
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Callable
from subprocess import call
from os import system, name

from .renderer import Renderer
from portfolio import Portfolio


@dataclass
class CommandType(Enum):
    NONE = None
    HELP = "help"
    LOAD = "load"
    PRINT_PORTFOLIO_SUMMARY = "summary"
    PRINT_PORTFOLIO_GRAPH = "graph"
    LIVE_TICKERS = "live"
    BUY_STOCK = "buy"
    SELL_STOCK = "sell"
    MARKET_SYNC = "sync"
    CLEAR = "clear"
    EXIT = "exit"

@dataclass
class CommandParser:
    # parsers per command 
    # TODO: should this be a single parser with sub parsers?
    parsers = {}
    _default_parser = argparse.ArgumentParser(description="Default No Arguments")

    def __post_init__(self):
        self.parsers[CommandType.NONE.value] = self._default_parser
        self.parsers[CommandType.LOAD.value] = self._generate_load_parser()
        self.parsers[CommandType.MARKET_SYNC.value] = self._generate_sync_parser()
        self.parsers[CommandType.PRINT_PORTFOLIO_SUMMARY.value] = self._generate_portfolio_summary_parser()
        self.parsers[CommandType.BUY_STOCK.value] = self._generate_buy_sell_parser()
        self.parsers[CommandType.SELL_STOCK.value] = self.parsers[CommandType.BUY_STOCK.value]

        for c in CommandType:
            if (self.parsers.get(c.value) is None):
                self.parsers[c.value] = self._default_parser

    def _generate_load_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Load Portfolio File")
        parser.add_argument(
            "-f", 
            "--filename",
            type=str,
            help="file path of portfolio to load",
            required=True
        )
        parser.add_argument(
            "-n", 
            "--name",
            type=str,
            help="name to give the portfolio",
            required=True
        )
        parser.add_argument(
            "--reload",
            help="re-initialize the portfolio even if it exists",
            action="store_true",
            default=False
        )
        return parser

    def _generate_portfolio_summary_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Print Portfolio Summary Table")
        parser.add_argument(
            "-n", 
            "--name",
            type=str,
            help="name of the portfolio to print",
            required=True
        )
        # TODO: add column argument
        return parser

    def _generate_sync_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Sync Market Data")
        parser.add_argument(
            "-n", 
            "--name",
            type=str,
            help="name of the portfolio to sync",
            required=True
        )
        parser.add_argument(
            "-ti",
            "--time-interval",
            type=str,
            help="specify time interval for graphs (ex: 1m, 15m, 1h) (default 1m)",
            default="1m",
        )
        parser.add_argument(
            "-tp",
            "--time-period",
            type=str,
            help="specify time period for graphs (ex: 15m, 1h, 1d) (default 1d)",
            default="1d",
        )
        return parser

    def _generate_buy_sell_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Buy or Sell Order", prog="buy | sell")
        parser.add_argument(
            "stock",
            type=str,
            help="stock"
        )
        parser.add_argument(
            "count",
            type=float,
            help="number of shares"
        )
        parser.add_argument(
            "price",
            type=float,
            help="price per share"
        )
        return parser

    def parse_command(self, raw_cmd: str) -> (CommandType, argparse.Namespace):
        if (len(raw_cmd) == 0):
            print(f'{Fore.RED}Please specify a command - Allowed Commands:\n{list(self.parsers.keys())}{Style.RESET_ALL}')
            return CommandType.NONE, None

        argument_list = shlex.split(raw_cmd)
        
        # first argument should be the actual command
        cmd = argument_list[0]
        if (cmd not in self.parsers):
            print(f'{Fore.RED}Invalid command "{cmd}" specified - Allowed Commands:\
                \n{[cmd.value for cmd in CommandType if cmd.value is not None]}\
                \nRun any of the following with the \'-h\' option for usage details{Style.RESET_ALL}')
            return CommandType.NONE, None

        # attempt to parse it
        try:
            # remove the command part to supply true args to parser
            # There's no option to control verbosity to print usage info it will print by default
            args, unknown = self.parsers[cmd].parse_known_args(argument_list[1:])
            return CommandType(cmd), args
        except SystemExit:
            # I guess since this isn't neccessarily meant to be used in a program itself, test for the help command explicity
            if ("-h" not in argument_list and "--help" not in argument_list):
                # redundant but prettier TODO: see if we can have the parser default to printing the full help
                self.parsers[cmd].print_help()
            return CommandType.NONE, None
        except:
            print(f'{Fore.RED}Failed to parse arguments for "{cmd}" command{Style.RESET_ALL}')
            return CommandType(cmd), None

@dataclass
class CommandRunner:
    # callables per command
    runners = {}
    _default_nop = lambda *_: _

    def __post_init__(self):
        self.runners[CommandType.NONE.value] = self._default_nop
        self.runners[CommandType.HELP.value] = lambda args: print(f'{Fore.CYAN}Available Commands:\n{[cmd.value for cmd in CommandType if cmd.value is not None]}\nRun any of the following with the \'-h\' option for usage details{Style.RESET_ALL}')
        self.runners[CommandType.LOAD.value] = self._load_portfolio
        self.runners[CommandType.PRINT_PORTFOLIO_SUMMARY.value] = lambda args: args.renderer.print_entries(args.portfolios[args.name])
        self.runners[CommandType.MARKET_SYNC.value] = lambda args: args.portfolios[args.name].market_sync(args)
        self.runners[CommandType.BUY_STOCK.value] = self._buy_sell_stock
        self.runners[CommandType.SELL_STOCK.value] = self.runners[CommandType.BUY_STOCK.value]
        self.runners[CommandType.EXIT.value] = lambda *_: exit() 
        self.runners[CommandType.CLEAR.value] = lambda *_: os.system("clear") if os.name =='posix' else os.system("cls")

        for c in CommandType:
            if (self.runners.get(c.value) is None):
                # print(f'{Fore.RED}Missing runner for command {c.value}{Style.RESET_ALL}')
                self.runners[c.value] = self._default_nop

    def _buy_sell_stock(self, args: argparse.Namespace):
        print(f'Order Type: {args.cmd} Stock: {args.stock} Count: {args.count} Price: {args.price}')
        return

    def _load_portfolio(self, args: argparse.Namespace):
        portfolio = args.portfolios.get(args.name)
        if (portfolio is not None and not args.reload):
            print(f'{Fore.YELLOW}Portfolio with name {args.name} already exists - You can re-load it with the --reload option{Style.RESET_ALL}')
            return
        
        #TODO make portfolio manager and put this in there for now
        stocks_config = multiconfigparser.ConfigParserMultiOpt()
        stocks_config.read(args.filename)

        portfolio = Portfolio()
        portfolio.load_from_config(stocks_config)
        args.portfolios[args.name] = portfolio

@dataclass
class Commander:
    renderer: Renderer    

    def __post_init__(self):
        self.master_parser = CommandParser()
        self.master_runner = CommandRunner()
        self.portfolios = {}

    def prompt_and_handle_command(self):
        # display prompt and get input
        print(f'{Fore.CYAN}$>>>>> {Style.RESET_ALL}', end="")
        raw_cmd = str(input())

        curr_command, args = self.master_parser.parse_command(raw_cmd)

        # check for any failures during parsing
        if (curr_command is CommandType.NONE or args is None):
            return

        # always set our 'special' arguments
        # TODO: clean this up later
        args.cmd = curr_command.value
        args.renderer = self.renderer
        args.portfolios = self.portfolios

        # try to execute the command
        try:
            runner = self.master_runner.runners[curr_command.value]
            
            # all functions should conform to this signature
            runner(args)
        except SystemExit as err:
            # expected as a result of the exit() python command, just re-raise
            # eventually can be used for cleanup time
            raise SystemExit
        except:
            e_type, e_value, e_trace = sys.exc_info()
            e_value = e_value if e_value is not None else "Unknown error"
            print(f'{Fore.RED}Failed to execute command \'{curr_command.value}\' - Error: {e_value}{Style.RESET_ALL}')
