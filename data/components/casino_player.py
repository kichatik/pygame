import os
import inspect
import datetime
from collections import OrderedDict
from .. import prepare
from . import loggable


class BankAccount(object):
    """
    Represents the player's bank account.
    A positive balance earns interest.
    Cash advances incur a one time borrowing fee
    added to the advance amount.
    """
    def __init__(self, player, balance=0):
        self.player = player
        self.balance = balance
        self.interest_rate = .02
        self.lending_rate = .05
        self.interest_period = 5 * 60 * 1000 #minutes * seconds * milliseconds
        self.last_interest_time = 0
        self.elapsed_interest_time = 0
        self.transactions = []
        self.max_advance = 500

    def update(self, current):
        diff = current - self.last_interest_time
        if diff >= self.interest_period:
            self.last_interest_time += self.interest_period
            self.update_interest()
        self.player.account_balance = self.balance

    def update_interest(self):
        if self.balance > 0:
            amount = self.balance * self.interest_rate
            self.balance += amount
            self.log_transaction("Interest Received", amount)
        elif self.balance < 0:
            amount = self.balance * self.lending_rate
            self.balance += amount
            self.log_transaction("Interest Charged", amount)

    def cash_advance(self, amount):
        fee = amount * self.lending_rate
        total = amount + fee
        self.balance -= total
        self.log_transaction("Cash Advance", -total)

    def withdrawal(self, amount):
        self.balance -= amount
        self.log_transaction("Withdrawal", -amount)

    def deposit(self, amount):
        self.balance += amount
        self.log_transaction("Deposit", amount)

    def log_transaction(self, msg, amount):
        if not amount:
            return
        if len(self.transactions) > 9:
            indx = len(self.transactions) - 9
            self.transactions = self.transactions[indx:]
        self.transactions.append((msg, amount))


class NoGameSet(Exception):
    """There is no current game defined for the player"""


class GameNotFound(Exception):
    """The game was not defined in the stats collection"""


class CasinoPlayer(loggable.Loggable):
    """Class to represent the player/user. A new
    CasinoPlayer will be instantiated each time the
    program launches. Passing a stats dict to __init__
    allows persistence of player statistics between
    sessions."""

    def __init__(self, stats_init=None):
        self.addLogger()
        self._current_game = None

        self._stats = OrderedDict([("cash", prepare.MONEY),
                                   ("account balance", 0)])

        if stats_init is not None:
            self.cash = stats_init.pop("cash")
            self.account_balance = stats_init.pop("account balance")
            for game_name, game_stats in stats_init.items():
                self._stats[game_name] = OrderedDict()
                self.current_game = game_name
                for stat_name, value in game_stats.items():
                    self.set(stat_name, value)

        self.account = BankAccount(self, self.account_balance)

    @property
    def stats(self):
        """Access stats directly - left here for backwards compatibility"""
        #
        # The following trickery is just to make the deprecation warning a bit
        # more helpful for the developers of the games
        frame, full_filename, line_number, function_name, lines, index = inspect.stack()[1]
        filename = os.path.split(full_filename)[1]
        component = os.path.split(os.path.split(full_filename)[0])[1]
        self.warnOnce(
            'Direct access to stats is deprecated - please use helper methods: game {0}, file {1}:{3} - {2}'.format(
                component, filename, function_name, line_number))
        #
        return self._stats

    @property
    def cash(self):
        """The current cash for the player"""
        return self._stats['cash']

    @cash.setter
    def cash(self, value):
        """Set the cash value"""
        self._stats['cash'] = value

    @property
    def account_balance(self):
        """The current cash for the player"""
        return self._stats['account balance']

    @account_balance.setter
    def account_balance(self, value):
        """Set the cash value"""
        self._stats['account balance'] = value

    @property
    def current_game(self):
        """The current game for storing stats"""
        return self._current_game

    @current_game.setter
    def current_game(self, value):
        """Set the current game"""
        #
        # The case of the the current game is not handled very consistently so
        # the following code makes sure this works whatever the case is
        # TODO: remove case inconsistencies and then remove this code
        for name in self._stats:
            if name.lower() == value.lower():
                self._current_game = name
                break
        else:
            raise GameNotFound('There was no game called "{0}" in the stats collection'.format(value))

    def increase(self, name, amount=1):
        """Increase the value of a stat"""
        self.set(name, self.get(name) + amount)

    def decrease(self, name, amount=1):
        """Decrease the value of a stat"""
        self.increase(name, -amount)

    def increase_time(self, name, seconds):
        """Increase a value, interpreted as a time"""
        initial_text = self.get(name, '00:00:00')
        dt = datetime.datetime.strptime(initial_text, '%H:%M:%S')
        new = dt + datetime.timedelta(seconds=seconds)
        self.set(name, new.strftime('%H:%M:%S'))

    def decrease_time(self, name, seconds):
        """Decrease a value, interpreted as a time"""
        self.increase(name, -seconds)

    def set(self, name, value):
        """Set the value of a stat"""
        if self.current_game is None:
            raise NoGameSet('No current game has been set (when trying to access stat "{0}")'.format(name))
        #
        self._stats[self.current_game][name] = value

    def get(self, name, default=0):
        """Return the value of a stat"""
        if self.current_game is None:
            raise NoGameSet('No current game has been set (when trying to access stat "{0}")'.format(name))
        #
        return self._stats[self.current_game].get(name, default)

    def game_names(self):
        """Return the names of all the stats"""
        return [name for name in self._stats.keys() if name not in ('cash', 'account balance')]

    def get_stat_names(self, game=None):
        """Return the names of the stats for a game"""
        if not game and self.current_game is None:
            raise NoGameSet('No current game has been set')
        #
        return list(self._stats[game if game else self.current_game].keys())

    def get_visible_stat_names(self, game=None):
        """Return the names of the stats that should be visible to the player"""
        return [name for name in self.get_stat_names(game) if not name.startswith('_')]
