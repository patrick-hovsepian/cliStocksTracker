import argparse
import io
import shlex

from colorama import Fore, Style
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Callable

from .renderer import Renderer
from portfolio import Portfolio


@dataclass
class CommandType(Enum):
    NONE = None
    PRINT_PORTFOLIO_SUMMARY = "print_port"
    PRINT_PORTFOLIO_GRAPH = "print_graph"
    LIVE_TICKERS = "live_ticker"
    BUY_STOCK = "buy"
    SELL_STOCK = "sell"
    MARKET_SYNC = "market_sync"
    EXIT = "exit"

@dataclass
class CommandParser:
    # parsers per command -- perhaps this should be a single parser with sub parsers?
    parsers = {}
    _default_parser = argparse.ArgumentParser(description="Default No Arguments")

    def __post_init__(self):
        self.parsers[CommandType.NONE.value] = self._default_parser
        self.parsers[CommandType.PRINT_PORTFOLIO_SUMMARY.value] = self._generate_portfolio_summary_parser()
        self.parsers[CommandType.PRINT_PORTFOLIO_GRAPH.value] = self._default_parser
        self.parsers[CommandType.LIVE_TICKERS.value] = self._default_parser
        self.parsers[CommandType.BUY_STOCK.value] = self._generate_buy_sell_parser()
        self.parsers[CommandType.SELL_STOCK.value] = self.parsers[CommandType.BUY_STOCK.value]
        self.parsers[CommandType.MARKET_SYNC.value] = self._default_parser
        self.parsers[CommandType.EXIT.value] = self._default_parser

    def _generate_portfolio_summary_parser(self):
        parser = argparse.ArgumentParser(description="Print Portfolio Summary")

        # TODO: add portfolio argument
        # TODO: add stock argument
        # TODO: add column argument
        return parser

    def _generate_buy_sell_parser(self):
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
            print(f'{Fore.RED}Invalid command "{cmd}" specified - Allowed Commands:\n{list(self.parsers.keys())}{Style.RESET_ALL}')
            return CommandType.NONE, None

        # attempt to parse it
        try:
            # remove the command part to supply true args to parser
            # There's no option to control verbosity to print usage info it will print by default
            args, unknown = self.parsers[cmd].parse_known_args(argument_list[1:])
            return CommandType(cmd), args
        except:
            print(f'{Fore.RED}Failed to parse arguments for "{cmd}" command{Style.RESET_ALL}')
            # self.parsers[cmd].print_help()
            return CommandType(cmd), None

@dataclass
class CommandRunner:
    # callables per command
    runners = {}
    _default_nop = lambda _: _

    def __post_init__(self):
        self.runners[CommandType.NONE.value] = self._default_nop
        self.runners[CommandType.PRINT_PORTFOLIO_SUMMARY.value] = self._default_nop
        self.runners[CommandType.PRINT_PORTFOLIO_GRAPH.value] = self._default_nop
        self.runners[CommandType.LIVE_TICKERS.value] = self._default_nop
        self.runners[CommandType.MARKET_SYNC.value] = self._default_nop
        self.runners[CommandType.BUY_STOCK.value] = self._buy_sell_stock
        self.runners[CommandType.SELL_STOCK.value] = self.runners[CommandType.BUY_STOCK.value]
        self.runners[CommandType.EXIT.value] = lambda _: exit()

    def _buy_sell_stock(self, cType: CommandType, portfolio: Portfolio, args):
        return

@dataclass
class Commander:
    # portfolio: Portfolio
    renderer: Renderer
    main_args: argparse.Namespace

    def __post_init__(self):
        self.master_parser = CommandParser()
        self.master_runner = CommandRunner()

    def add_portfolio(self, portfolio: Portfolio):
        self.portfolio = portfolio

    def prompt_and_handle_command(self):
        print(f'{Fore.CYAN}$>>>>> {Style.RESET_ALL}', end="")

        raw_cmd = str(input())
        curr_command, args = self.master_parser.parse_command(raw_cmd)

        if (curr_command is CommandType.NONE or args is None):
            # NOP
            return

        runner = self.master_runner.runners[curr_command.value]
        if (curr_command is CommandType.PRINT_PORTFOLIO_SUMMARY):
            self.renderer.render()
        elif (curr_command is CommandType.EXIT):
            runner(1)
        elif (curr_command is CommandType.BUY_STOCK):
            runner(curr_command, self.renderer.portfolio, args)
        elif (curr_command is CommandType.MARKET_SYNC):
            self.renderer.portfolio.market_sync(self.main_args)
