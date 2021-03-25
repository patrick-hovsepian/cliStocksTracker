import utils
import warnings
import webcolors
import autocolors
import time
import threading
import configparser
import pytz

import numpy as np
import yfinance as market

from graph import Graph
from colorama import Fore, Style
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

@dataclass 
class TransactionType(Enum):
    NONE = None
    BUY = "buy"
    SELL = "sell"
    MARKET_SYNC = "sync"


@dataclass
class Stock:
    symbol: str
    data: list[int] = field(default_factory=lambda: [0])

    # TODO: better error handling on data
    def __post_init__(self):
        self.curr_value = self.data[-1]
        self.open_value = self.data[0]
        self.high = max(self.data)
        self.low = min(self.data)
        self.average = sum(self.data) / len(self.data)
        self.change_amount = self.curr_value - self.open_value
        self.change_percentage = (self.change_amount / self.curr_value) * 100 if self.curr_value > 0 else 0
        return

    def reinit(self):
        self.__post_init__()


@dataclass
class PortfolioEntry:
    stock: Stock
    count: float = 0
    average_cost: float = 0
    graph: bool = False
    color: str = None

    def __post_init__(self):
        self._realized_gains: float = 0
        self.holding_open_value = 0
        self.holding_market_value = 0
        self.cost_basis = 0
        self.gains = 0
        self.gains_per_share = 0

    # TODO track transactions so we can persist them
    def process_transaction(self, ttype: TransactionType, count: float = 0, pper_share: float = 0, data: list = (0)):
        if ttype is TransactionType.BUY:
            self.count += count
            self.cost_basis += (count * pper_share)
            self.average_cost = self.cost_basis / self.count
        elif ttype is TransactionType.SELL:
            self._realized_gains += ((pper_share - self.average_cost) * count)
            self.count -= count
            self.cost_basis -= (count * self.average_cost)
            self.average_cost = self.cost_basis / self.count if self.count > 0 else 0
        elif ttype is TransactionType.MARKET_SYNC:
            self.stock.data = data
            self.stock.reinit()

            self.holding_market_value = self.stock.curr_value * self.count
            self.holding_open_value = self.stock.open_value * self.count
            self.gains = self.holding_market_value - self.cost_basis
            self.gains_per_share = self.gains / self.count if self.count > 0 else 0

@dataclass
class Portfolio:

    def __post_init__(self):
        self.stocks = {} # entries TODO: rename

        # portfolio worth at market open
        self.open_market_value = 0
        # amount invested into the portfolio (sum of cost of share cost)
        self.cost_value = 0
        self.market_value = 0

    def calc_value(self):
        self.open_market_value = 0
        self.cost_value = 0
        self.market_value = 0

        for entry in self.stocks.values():
            self.open_market_value += entry.holding_open_value
            self.market_value += entry.holding_market_value
            self.cost_value += entry.cost_basis

    def get_stocks(self):
        return self.stocks

    def get_stock(self, symbol) -> PortfolioEntry:
        return self.stocks.get(symbol)

    def load_from_config(self, stocks_config):
        # process the config -- each stock is expected to have a section
        for ticker in stocks_config.sections():
            stock_data = stocks_config[ticker]

            entry: PortfolioEntry = self.stocks.get(ticker, 
                PortfolioEntry(
                    stock= Stock(ticker), 
                    color= stock_data.get("color"), 
                    graph= (stock_data.get("graph", False))))

            # translate transactions
            transactions = stock_data.get('transactions', "")
            for order in transactions.split(","):
                parts = order.strip().split()
                if (len(parts) != 2):
                    continue

                if (parts[0] != TransactionType.BUY.value and 
                    parts[0] != TransactionType.SELL.value):
                    continue

                ttype = TransactionType(parts[0])
                price_parts = parts[1].split("@")
                if (len(price_parts) != 2):
                    continue

                count = float(price_parts[0])
                price = float(price_parts[1])

                entry.process_transaction(ttype, count, price)
            self.stocks[ticker] = entry

        # finally, rebalance
        self.calc_value()

    def _download_market_data(self, stocks, time_period, time_interval, verbose):
        try:
            return market.download(
                tickers=stocks,
                period=time_period,
                interval=time_interval,
                progress=verbose,
            )
        except:
            if (verbose):
                print(f'{Fore.RED}Failed to download market data{Style.RESET_ALL}')

    def market_sync(self, time_period: str, time_interval: str, verbose: bool):
        stock_list = list(self.stocks.keys())

        if (len(stock_list) == 0):
            return

        # download all stock data        
        market_data = self._download_market_data(stock_list, time_period, time_interval, verbose)

        # iterate through each ticker data
         # TODO: add error handling to stocks not found
        data_key = "Open"
        for ticker in stock_list:
            entry: PortfolioEntry = self.stocks.get(ticker, PortfolioEntry(stock= Stock(ticker))) 

            data = [0]
            if (market_data.get(data_key) is not None and market_data[data_key].get(ticker) is not None):
                # convert the numpy array into a list of prices while removing NaN values
                data = market_data[data_key][ticker].values[
                    ~np.isnan(market_data[data_key][ticker].values)
                ]

            entry.process_transaction(ttype=TransactionType.MARKET_SYNC, data=data)
            self.stocks[ticker] = entry
        
        # finally, rebalance
        self.calc_value()

@dataclass
class ManagedState:
    portfolio: Portfolio

    quit_sync: bool = False
    sync_thread: threading.Thread = None

@dataclass
class PortfolioManager:
    portfolio_states = {}
    _stop_workers = False

    def _get(self, name: str):
        return self.portfolio_states.get(name)

    def cleanup(self):
        self._stop_workers = True
        for pstate in self.portfolio_states.values():
            if (pstate.sync_thread is not None):
                pstate.sync_thread.join()

    def get_portfolio(self, name: str):
        return self._get(name).portfolio if self._get(name) is not None else None

    def get_portfolio_names(self):
        return list(self.portfolio_states.keys())

    def load(self, name: str, filename: str):
        config = configparser.ConfigParser()
        config.read(filename)

        portfolio = Portfolio()
        portfolio.load_from_config(config)

        self.portfolio_states[name] = ManagedState(portfolio, None)

    def sync(self, name: str, time_period: str, time_interval: str, continuous: bool, verbose: bool):
        pstate = self._get(name)
        if (pstate is None or pstate.portfolio is None or pstate.sync_thread is not None):
            return

        pstate.portfolio.market_sync(time_period, time_interval, verbose)
        if (continuous != True):
            return

        syncer = threading.Thread(name=f'MarketSync_{name}', target=lambda: self._continuous_sync(pstate, time_period, time_interval, verbose))
        syncer.start()
        pstate.sync_thread = syncer

    def _continuous_sync(self, pstate, time_period, time_interval, verbose):
        while True:
            try:
                if (self._stop_workers == True or pstate.quit_sync == True):
                    return
                time.sleep(60)
                pstate.portfolio.market_sync(time_period, time_interval, verbose)
            except SystemExit as err:
                raise SystemExit
            except:
                pass

    def process_order(self, name: str, ttype: TransactionType, ticker: str, count: float, price: float):
        portfolio: Portfolio = self.get_portfolio(name)
        if (portfolio is None):
            return
        
        entry: PortfolioEntry = portfolio.stocks.get(ticker, PortfolioEntry(stock= Stock(ticker)))
        entry.process_transaction(ttype=ttype, count=count, pper_share=price)

        portfolio.stocks[ticker] = entry
        portfolio.calc_value()

    def graph(self, 
        name: str, 
        override_stocks: list,
        independent_graphs: bool, 
        graph_width: int, 
        graph_height: int, 
        cfg_timezone: str) -> list:
        #verify portfolio
        portfolio: Portfolio = self.get_portfolio(name)
        if (portfolio is None):
            return

        entries = portfolio.get_stocks().values
        if (len(override_stocks) > 0):
            entries = []
            for stock in override_stocks:
                found_entry = portfolio.get_stock(stock)
                if (found_entry is not None):
                    entries.append(found_entry)

        graphs = []
        if not independent_graphs:
            graphing_list = []
            color_list = []
            for sm in entries:
                if (sm.graph or (len(override_stocks) > 0)) and len(sm.stock.data) > 1:
                    graphing_list.append(sm.stock)
                    color_list.append(sm.color)
            if len(graphing_list) > 0:
                graphs.append(
                    Graph(
                        stocks=graphing_list,
                        width=graph_width,
                        height=graph_height,
                        colors=color_list,
                        timezone=pytz.timezone(cfg_timezone),
                    )
                )
        else:
            for sm in entries:
                if (sm.graph or (len(override_stocks) > 0)) and len(sm.stock.data) > 1:
                    graphs.append(
                        Graph(
                            stocks=[sm.stock],
                            width=graph_width,
                            height=graph_height,
                            colors=[sm.color],
                            timezone=pytz.timezone(cfg_timezone),
                        )
                    )

        for graph in graphs:
            graph.gen_graph(autocolors.color_list)
        
        return graphs