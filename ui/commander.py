import argparse
import io
import shlex
import os
import sys
import time
import threading

from colorama import Fore, Style
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Callable

from .renderer import Renderer
from portfolio import Portfolio, PortfolioManager, TransactionType


@dataclass
class CommandType(Enum):
    NONE = None
    HELP = "help"
    LOAD = "load"
    LIST = "list"
    SUMMARY = "summary"
    GRAPH = "graph"
    LIVE_TICKERS = "live"
    BUY_STOCK = "buy"
    SELL_STOCK = "sell"
    MARKET_SYNC = "sync"
    CLEAR = "clear"
    EXIT = "exit"

@dataclass
class CommandParser:
    # parser per command 
    # TODO: should this be a single parser with sub parsers?
    parsers = {}
    _default_parser = argparse.ArgumentParser(description="Default No Arguments")

    # TODO: create version of each command that can parse an ini file
    # can have a amster config.ini that every command just looks for the relevant sections
    def __post_init__(self):
        self.parsers[CommandType.NONE.value] = self._default_parser
        self.parsers[CommandType.LOAD.value] = self._generate_load_parser()
        self.parsers[CommandType.MARKET_SYNC.value] = self._generate_sync_parser()
        self.parsers[CommandType.SUMMARY.value] = self._generate_portfolio_summary_parser()
        self.parsers[CommandType.BUY_STOCK.value] = self._generate_buy_sell_parser()
        self.parsers[CommandType.SELL_STOCK.value] = self.parsers[CommandType.BUY_STOCK.value]
        self.parsers[CommandType.GRAPH.value] = self._generate_graph_parser()
        self.parsers[CommandType.LIVE_TICKERS.value] = self._generate_live_parser()

        for c in CommandType:
            if (self.parsers.get(c.value) is None):
                self.parsers[c.value] = self._default_parser

    def _generate_load_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Load Portfolio File")
        parser.add_argument(
            "name", 
            type=str,
            help="name to give the portfolio"
        )
        parser.add_argument(
            "filename",
            type=str,
            help="file path of portfolio to load"
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
            "name",
            type=str,
            help="name of the portfolio to print"
        )
        # TODO: add column argument
        return parser

    def _generate_sync_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Sync Market Data")
        parser.add_argument(
            "name",
            type=str,
            help="name of the portfolio to sync"
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
        parser.add_argument(
            "--continuous",
            help="specify to enable continuous syncing in the background",
            action="store_true",
            default=False
        )
        parser.add_argument(
            "-v", 
            "--verbose",
            help="display progress bar on sync",
            action="store_true",
            default=False
        )
        return parser

    def _generate_graph_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Graph Stock Data")
        parser.add_argument(
            "name",
            type=str,
            help="name of the portfolio to graph"
        )
        parser.add_argument(
            "--independent-graphs",
            help="independent graph per stock",
            action="store_true",
            default=False
        )
        parser.add_argument(
            "--override",
            type=str,
            help="csv of stocks to graph",
            default=""
        )
        parser.add_argument(
            "--width",
            type=int,
            help="graph width",
            default=80
        )
        parser.add_argument(
            "--height",
            type=int,
            help="graph height",
            default=20
        )
        parser.add_argument(
            "--timezone",
            type=str,
            help="your timezone (exmple and default: America/New_York)",
            default="America/New_York"
        )
        return parser

    def _generate_buy_sell_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Buy or Sell Order", prog="buy | sell")
        parser.add_argument(
            "name",
            type=str,
            help="portfolio name"
        )
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

    def _generate_live_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Live Ticker View")
        parser.add_argument(
            "name",
            type=str,
            help="portfolio name"
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
            args.cmd = CommandType(cmd) # for reference sake
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
        self.runners[CommandType.LIST.value] = lambda args: print(f'{Fore.YELLOW}Loaded Portfolios: {args.manager.get_portfolio_names()}{Style.RESET_ALL}')
        self.runners[CommandType.HELP.value] = lambda args: print(f'{Fore.YELLOW}Available Commands:\n{[cmd.value for cmd in CommandType if cmd.value is not None]}\nRun any of the following with the \'-h\' option for usage details{Style.RESET_ALL}')
        self.runners[CommandType.LOAD.value] = self._load_portfolio
        self.runners[CommandType.SUMMARY.value] = lambda args: args.renderer.print_entries(args.manager.get_portfolio(args.name))
        self.runners[CommandType.GRAPH.value] = self._graph
        self.runners[CommandType.MARKET_SYNC.value] = self._sync_portfolio
        self.runners[CommandType.LIVE_TICKERS.value] = self._live_view
        self.runners[CommandType.BUY_STOCK.value] = self._buy_sell_stock
        self.runners[CommandType.SELL_STOCK.value] = self.runners[CommandType.BUY_STOCK.value]
        self.runners[CommandType.EXIT.value] = lambda *_: exit() 
        self.runners[CommandType.CLEAR.value] = lambda *_: os.system("clear") if os.name =='posix' else os.system("cls")

        for c in CommandType:
            if (self.runners.get(c.value) is None):
                # print(f'{Fore.RED}Missing runner for command {c.value}{Style.RESET_ALL}')
                self.runners[c.value] = self._default_nop

    def _buy_sell_stock(self, args: argparse.Namespace):
        args.manager.process_order(args.name, ttype=TransactionType(args.cmd.value), ticker=args.stock, count=args.count, price=args.price)

    def _load_portfolio(self, args: argparse.Namespace):
        portfolio = args.manager.get_portfolio(args.name)
        if (portfolio is not None and not args.reload):
            print(f'{Fore.YELLOW}Portfolio with name {args.name} already exists - You can re-load it with the --reload option{Style.RESET_ALL}')
            return
        
        args.manager.load(args.name, args.filename)
    
    def _sync_portfolio(self, args: argparse.Namespace):
        args.manager.sync(args.name, args.time_period, args.time_interval, args.continuous, args.verbose)

    def _live_view(self, args: argparse.Namespace):
        # force sync mode so we can view ticker data "live"
        args.manager.sync(args.name, "1d", "1m", True, False)

        print(f'Press Ctrl + C to stop viewing')
        while True:
            args.renderer.print_tickers(args.manager.get_portfolio(args.name))
            time.sleep(5)

    def _graph(self, args: argparse.Namespace):
        graphs = args.manager.graph(name=args.name, 
            independent_graphs=args.independent_graphs, 
            graph_width=args.width, 
            graph_height=args.height, 
            cfg_timezone=args.timezone, 
            override_stocks=args.override.split(","))
        args.renderer.print_graphs(graphs)
        return

@dataclass
class Commander:
    renderer: Renderer

    def __post_init__(self):
        self.master_parser = CommandParser()
        self.master_runner = CommandRunner()
        self.manager = PortfolioManager()

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
        args.renderer = self.renderer
        args.manager = self.manager

        # try to execute the command
        try:
            runner = self.master_runner.runners[curr_command.value]
            
            # all functions should conform to this signature
            runner(args)
        except SystemExit as err:
            # expected as a result of the exit() python command, just re-raise
            self.manager.cleanup()
            self.master_runner.runners[CommandType.CLEAR.value]()
            raise SystemExit
        except KeyboardInterrupt:
            if (curr_command is CommandType.LIVE_TICKERS):
                self.master_runner.runners[CommandType.CLEAR.value]()
                return
        except:
            e_type, e_value, e_trace = sys.exc_info()
            e_value = e_value if e_value is not None else "Unknown error"
            print(f'{Fore.RED}Failed to execute command \'{curr_command.value}\' - Error: {e_value}{Style.RESET_ALL}')
