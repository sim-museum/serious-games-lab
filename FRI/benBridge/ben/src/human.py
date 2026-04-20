import json
import numpy as np

import deck52

from binary import *
from bidding.binary import parse_hand_f
from bidding.bidding import can_double, can_redouble
from objects import Card, CardResp, BidResp
from botbidder import BotBid


def is_numeric(value):
    return isinstance(value, (int, float, complex))

def clear_screen():
    print('\033[H\033[J')


def render_hand(hands_str, indentation):
    suits = hands_str.split('.')
    print('\n')
    for suit in suits:
        print((' ' * indentation) + (suit or '-'))
    print('\n')


class Confirm:

    async def confirm(self):
        return

class ConfirmSocket:

    def __init__(self, socket):
        self.socket = socket

    async def confirm(self):
        # print('socket confirm')
        
        await self.socket.send(json.dumps({'message': 'trick_confirm'}))

        key = await self.socket.recv()

        # Check if this is a claim
        # print("Trick confirm:",key)
        return key


class Channel:

    trick = []
    async def send(self, message):
        if "card_played" in message:
            card = json.loads(message)['card']
            self.trick.append(card)
            if len(self.trick) > 3:
                print(self.trick)
                self.trick = []
        else:
            print_message = message.replace('"PAD_START", ','').replace('"PASS"','"P"')
            if len(print_message) > 200:
                #print(message[:197] + "...")
                print("..." + print_message[-197:])
            else:
                print(print_message)

class ChannelSocket:

    def __init__(self, socket, verbose):
        self.socket = socket
        self.verbose = verbose

    async def send(self, message):
        print_message = message.replace('"PAD_START", ','').replace('"PASS"','"P"')
        if len(print_message) > 200:
            #print(message[:197] + "...")
            print("..." + print_message[-197:])
        else:
            print(print_message)
        await self.socket.send(message)


class HumanBid:

    def __init__(self, vuln, hands_str, name, botbidder):
        self.hands_str = hands_str
        self.vuln = vuln
        self.name = name
        self.botbidder = botbidder

    async def async_bid(self, auction, alert=None):
        self.render_auction_hand(auction)
        print('\n')
        bid = input('enter bid: ').strip().upper()
        return BidResp(bid=bid, candidates=[], samples=[], shape=-1, hcp=-1, who="Human", quality=None, alert=alert, explanation="XXXX")

    def render_auction_hand(self, auction):
        clear_screen()

        print('\n')

        print('Vuln ', {(False, False): 'None', (False, True): 'E-W', (True, False): 'N-S', (True, True): 'Both'}[tuple(self.vuln)])

        print('\n')

        print('%5s %5s %5s %5s' % ('North', 'East', 'South', 'West'))
        print('-' * 23)
        bid_rows = []
        i = 0
        while i < len(auction):
            bid_rows.append(auction[i:i+4])
            i += 4

        for row in bid_rows:
            print('%5s %5s %5s %5s' % tuple([('' if s == 'PAD_START' else s) for s in (row + [''] * 3)[:4]]))
        
        render_hand(self.hands_str, 8)


class HumanBidSocket:

    def __init__(self, socket, vuln, hands_str, name, botbidder):
        self.socket = socket
        self.name = name
        self.botbidder = botbidder

    async def async_bid(self, auction, alert=None):
        await self.socket.send(json.dumps({
            'message': 'get_bid_input',
            'auction': auction,
            'can_double': can_double(auction),
            'can_redouble': can_redouble(auction)
        }))

        bid = await self.socket.recv()

        print(f"Human bid: {bid}")
        print("auction: ", auction)
        new_auction = auction + [bid] 
        explanation, alert = self.botbidder.explain(new_auction)

        return BidResp(bid=bid, candidates=[], samples=[], shape=-1, hcp=-1, who = "Human", quality=None, alert=alert, explanation=explanation)
    

class HumanLead:

    async def async_lead(self):
        card_str = input('opening lead: ').strip().upper()

        return CardResp(card=Card.from_symbol(card_str), candidates=[], samples=[], shape=-1, hcp=-1, quality=None, who = "Human", claim = -1)


class HumanLeadSocket:

    def __init__(self, socket):
        self.socket = socket

    async def async_lead(self):
        candidates = []
        samples = []

        while True:
            try:
                await self.socket.send(json.dumps({'message': 'get_card_input'}))

                human_card = await self.socket.recv()

                if (str(human_card).startswith("Cl") or str(human_card).startswith("Co")) :
                    return CardResp(card=human_card, candidates=candidates, samples=samples, shape=-1, hcp=-1, quality=None, who = None, claim = -1)
                else:    
                    return CardResp(card=Card.from_symbol(human_card), candidates=candidates, samples=samples, shape=-1, hcp=-1, quality=None, who = "Human", claim = -1)

            except Exception as ex:
                print(f"Exception receiving card ", ex)
                if "going away" in str(ex):
                    raise ex



class HumanCardPlayer:

    def __init__(self, models, player_i, hand_str, public_hand_str, contract, is_decl_vuln, quality):
        self.player_models = models.player_models
        self.model = models.player_models[player_i]
        self.player_i = player_i
        self.hand = parse_hand_f(32)(hand_str).reshape(32)
        self.hand52 = parse_hand_f(52)(hand_str).reshape(52)
        self.public52 = parse_hand_f(52)(public_hand_str).reshape(52)
        self.n_tricks_taken = 0
        self.contract = contract
        self.is_decl_vuln = is_decl_vuln
        self.level = int(contract[0])
        self.strain_i = bidding.get_strain_i(contract)
        self.init_x_play(parse_hand_f(32)(public_hand_str), self.level, self.strain_i)
    
    def init_x_play(self, public_hand, level, strain_i):
        self.level = level
        self.strain_i = strain_i

        self.x_play = np.zeros((1, 13, 298),dtype=np.int8)
        BinaryInput(self.x_play[:,0,:]).set_player_hand(self.hand)
        BinaryInput(self.x_play[:,0,:]).set_public_hand(public_hand)
        self.x_play[:,0,292] = level
        self.x_play[:,0,293+strain_i] = 1

    def set_real_card_played(self, card, playedBy):
        return

    def set_card_played(self, trick_i, leader_i, i, card):
        played_to_the_trick_already = (i - leader_i) % 4 > (self.player_i - leader_i) % 4

        if played_to_the_trick_already:
            return

        if self.player_i == i:
            return

        # update the public hand when the public hand played
        if self.player_i in (0, 2, 3) and i == 1 or self.player_i == 1 and i == 3:
            self.x_play[:, trick_i, 32 + card] -= 1

        # update the current trick
        offset = (self.player_i - i) % 4   # 1 = rho, 2 = partner, 3 = lho
        self.x_play[:, trick_i, 192 + (3 - offset) * 32 + card] = 1

    def set_own_card_played52(self, card52):
        self.hand52[card52] -= 1

    def set_public_card_played52(self, card52):
        self.public52[card52] -= 1

    async def get_card_input(self):
        card = input('your play: ').strip().upper()
        return deck52.encode_card(card)

    async def async_play_card(self, trick_i, leader_i, current_trick52, tricks52, players_states, worlds, bidding_scores, quality, probability_of_occurence, shown_out_suits, play_status, lead_scores, play_scores, logical_play_scores, discard_scores, features):
        candidates = []
        samples = []

        human_card = await self.get_card_input()

        # claim and conceed both starts with a C

        if (str(human_card).startswith("C")) :
            return CardResp(card=human_card, candidates=candidates, samples=samples, shape=-1, hcp=-1, quality=None, who = None, claim = -1)
        else:    
            return CardResp(card=Card.from_code(human_card), candidates=candidates, samples=samples, shape=-1, hcp=-1, quality=None, who = "Human", claim = -1)


class HumanCardPlayerSocket(HumanCardPlayer):

    def __init__(self, socket, models, player_i, hand_str, public_hand_str, contract, is_decl_vuln):
        super().__init__(models, player_i, hand_str, public_hand_str, contract, is_decl_vuln, None)

        self.socket = socket

    async def get_card_input(self):

        while True:
            try:
                await self.socket.send(json.dumps({
                    'message': 'get_card_input'
                }))
                human_card = await self.socket.recv()
                if (human_card.startswith("Cl") or human_card.startswith("Co")) :
                    return human_card
                else:
                    return deck52.encode_card(human_card)
            except Exception as ex:
                print(f"Exception receiving card", ex)
                if "going away" in str(ex):
                    raise ex

class ConsoleFactory:

    def create_human_bidder(self, vuln, hands_str, name, botbidder, abs_seat=-1):
        return HumanBid(vuln, hands_str, name, botbidder)

    def create_human_leader(self, abs_seat=-1):
        return HumanLead()

    def create_human_cardplayer(self, player_models, player_i, hand_str, public_hand_str, contract, is_decl_vuln, abs_seat=-1):
        return HumanCardPlayer(player_models, player_i, hand_str, public_hand_str, contract, is_decl_vuln)

    def create_confirmer(self):
        return Confirm()

    def create_channel(self):
        return Channel()


class WebsocketFactory:

    def __init__(self, socket, verbose):
        self.socket = socket
        self.verbose = verbose

    def create_human_bidder(self, vuln, hands_str, name, botbidder, abs_seat=-1):
        return HumanBidSocket(self.socket, vuln, hands_str, name, botbidder)

    def create_human_leader(self, abs_seat=-1):
        return HumanLeadSocket(self.socket)

    def create_human_cardplayer(self, models, player_i, hand_str, public_hand_str, contract, is_decl_vuln, abs_seat=-1):
        return HumanCardPlayerSocket(self.socket, models, player_i, hand_str, public_hand_str, contract, is_decl_vuln)

    def create_confirmer(self):
        return ConfirmSocket(self.socket)

    def create_channel(self):
        return ChannelSocket(self.socket, self.verbose)


class BroadcastChannelSocket:
    """Channel that broadcasts every outgoing message to every connected seat socket."""

    def __init__(self, sockets, verbose):
        # sockets: dict of {abs_seat: websocket} for seats that have human clients
        self.sockets = sockets
        self.verbose = verbose

    async def send(self, message):
        print_message = message.replace('"PAD_START", ', '').replace('"PASS"', '"P"')
        if len(print_message) > 200:
            print("..." + print_message[-197:])
        else:
            print(print_message)
        for sock in list(self.sockets.values()):
            try:
                await sock.send(message)
            except Exception as ex:
                print(f"Broadcast send failed on one socket: {ex}")


class SeatConfirmSocket:
    """Confirm trick from declarer's socket (same seat picks declarer + dummy cards)."""

    def __init__(self, sockets, seat_getter):
        self.sockets = sockets
        self.seat_getter = seat_getter

    async def confirm(self):
        seat = self.seat_getter()
        sock = self.sockets.get(seat)
        if sock is None:
            # fall back to any connected socket
            if not self.sockets:
                return ''
            sock = next(iter(self.sockets.values()))
        await sock.send(json.dumps({'message': 'trick_confirm'}))
        return await sock.recv()


class HumanBidMultiSocket(HumanBidSocket):
    """Bidder that reads/writes on the socket for a specific absolute seat."""

    def __init__(self, sockets, abs_seat, vuln, hands_str, name, botbidder):
        super().__init__(sockets[abs_seat], vuln, hands_str, name, botbidder)
        self.all_sockets = sockets
        self.abs_seat = abs_seat


class HumanLeadMultiSocket(HumanLeadSocket):

    def __init__(self, sockets, abs_seat):
        super().__init__(sockets[abs_seat])
        self.abs_seat = abs_seat


class HumanCardPlayerMultiSocket(HumanCardPlayerSocket):

    def __init__(self, sockets, abs_seat, models, player_i, hand_str, public_hand_str, contract, is_decl_vuln):
        super().__init__(sockets[abs_seat], models, player_i, hand_str, public_hand_str, contract, is_decl_vuln)
        self.abs_seat = abs_seat


class MultiSocketFactory:
    """Factory for a multi-client game: one websocket per human seat.

    sockets: dict of {abs_seat: websocket} for seats that have human clients.
             abs_seat: 0=N, 1=E, 2=S, 3=W. Bot seats are simply absent.
    """

    def __init__(self, sockets, verbose):
        self.sockets = sockets
        self.verbose = verbose
        self._current_decl_seat = [None]

    def set_declarer_seat(self, abs_seat):
        self._current_decl_seat[0] = abs_seat

    def create_human_bidder(self, vuln, hands_str, name, botbidder, abs_seat=-1):
        return HumanBidMultiSocket(self.sockets, abs_seat, vuln, hands_str, name, botbidder)

    def create_human_leader(self, abs_seat=-1):
        return HumanLeadMultiSocket(self.sockets, abs_seat)

    def create_human_cardplayer(self, models, player_i, hand_str, public_hand_str, contract, is_decl_vuln, abs_seat=-1):
        return HumanCardPlayerMultiSocket(self.sockets, abs_seat, models, player_i, hand_str, public_hand_str, contract, is_decl_vuln)

    def create_confirmer(self):
        return SeatConfirmSocket(self.sockets, lambda: self._current_decl_seat[0])

    def create_channel(self):
        return BroadcastChannelSocket(self.sockets, self.verbose)
