import pytz
import utils
import plotille
import warnings
import webcolors
import autocolors
import time
import threading
import configparser
import multiconfigparser

import numpy as np
import yfinance as market

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
    stocks = {} # entries TODO: rename

    # portfolio worth at market open
    open_market_value = 0
    # amount invested into the portfolio (sum of cost of share cost)
    cost_value = 0
    market_value = 0

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

    def average_buyin(self, buys: list, sells: list):
        buy_c, buy_p, sell_c, sell_p, count, bought_at = 0, 0, 0, 0, 0, 0
        buys = [_.split("@") for _ in ([buys] if type(buys) is not tuple else buys)]
        sells = [_.split("@") for _ in ([sells] if type(sells) is not tuple else sells)]

        for buy in buys:
            next_c = float(buy[0])
            if next_c <= 0:
                print(
                    'A negative "buy" key was detected. Use the sell key instead to guarantee accurate calculations.'
                )
                exit()
            buy_c += next_c
            buy_p += float(buy[1]) * next_c

        for sell in sells:
            next_c = float(sell[0])
            if next_c <= 0:
                print(
                    'A negative "sell" key was detected. Use the buy key instead to guarantee accurate calculations.'
                )
                exit()
            sell_c += next_c
            sell_p += float(sell[1]) * next_c

        count = buy_c - sell_c
        if count == 0:
            return 0, 0

        bought_at = (buy_p - sell_p) / count

        return count, bought_at

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

    def gen_graphs(self, independent_graphs, graph_width, graph_height, cfg_timezone):
        graphs = []
        if not independent_graphs:
            graphing_list = []
            color_list = []
            for sm in self.get_stocks().values():
                if sm.graph:
                    graphing_list.append(sm.stock)
                    color_list.append(sm.color)
            if len(graphing_list) > 0:
                graphs.append(
                    Graph(
                        graphing_list,
                        graph_width,
                        graph_height,
                        color_list,
                        timezone=cfg_timezone,
                    )
                )
        else:
            for sm in self.get_stocks().values():
                if sm.graph:
                    graphs.append(
                        Graph(
                            [sm.stock],
                            graph_width,
                            graph_height,
                            [sm.color],
                            timezone=cfg_timezone,
                        )
                    )

        for graph in graphs:
            graph.gen_graph(autocolors.color_list)
        self.graphs = graphs
        return

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
                time.sleep(2)
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


class Graph:
    def __init__(
        self, stocks: list, width: int, height: int, colors: list, *args, **kwargs
    ):
        self.stocks = stocks
        self.graph = ""
        self.colors = colors
        self.plot = plotille.Figure()

        self.plot.width = width
        self.plot.height = height
        self.plot.color_mode = "rgb"
        self.plot.X_label = "Time"
        self.plot.Y_label = "Value"

        if "timezone" in kwargs.keys():
            self.timezone = pytz.timezone(kwargs["timezone"])
        else:
            self.timezone = pytz.utc

        if "starttime" in kwargs.keys():
            self.start = (
                kwargs["startend"].replace(tzinfo=pytz.utc).astimezone(self.timezone)
            )
        else:
            self.start = (
                datetime.now()
                .replace(hour=14, minute=30, second=0)
                .replace(tzinfo=pytz.utc)
                .astimezone(self.timezone)
            )

        if "endtime" in kwargs.keys():
            self.end = (
                kwargs["endtime"].replace(tzinfo=pytz.utc).astimezone(self.timezone)
            )
        else:
            self.end = (
                datetime.now()
                .replace(hour=21, minute=0, second=0)
                .replace(tzinfo=pytz.utc)
                .astimezone(self.timezone)
            )

        self.plot.set_x_limits(min_=self.start, max_=self.end)

        return

    def __call__(self):
        return self.graph

    def draw(self):
        print(self.graph)
        return

    def gen_graph(self, auto_colors):
        self.y_min, self.y_max = self.find_y_range()
        self.plot.set_y_limits(min_=self.y_min, max_=self.y_max)

        for i, stock in enumerate(self.stocks):
            if self.colors[i] == None:
                color = webcolors.hex_to_rgb(auto_colors[i % 67])
            elif self.colors[i].startswith("#"):
                color = webcolors.hex_to_rgb(self.colors[i])
            else:
                color = webcolors.hex_to_rgb(
                    webcolors.CSS3_NAMES_TO_HEX[self.colors[i]]
                )

            self.plot.plot(
                [self.start + timedelta(minutes=i) for i in range(len(stock.data))],
                stock.data,
                lc=color,
                label=stock.symbol,
            )

        self.graph = self.plot.show(legend=True)
        return

    def find_y_range(self):
        y_min = 10000000000000  # Arbitrarily large number (bigger than any single stock should ever be worth)
        y_max = 0

        for stock in self.stocks:
            if y_min > min(stock.data):
                y_min = min(stock.data)
            if y_max < max(stock.data):
                y_max = max(stock.data)

        return y_min, y_max
