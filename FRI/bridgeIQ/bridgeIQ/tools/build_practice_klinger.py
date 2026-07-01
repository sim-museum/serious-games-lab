#!/usr/bin/env python3
"""Self-contained generator for the Bridge Basics (Klinger) practice deck
(DATA/PRACTICE/bridge_basics.bdl).  No external book file needed: the cards,
metadata and the book's Lead/Correct-play/Wrong-play commentary are inlined.

Method (see DATA/PRACTICE/README.md): the four single-seat grid pages of the
book (pg179-182 = North/East/South/West) were vision-transcribed and kept on
the compass exactly as the book labels them.  Each deal is checked two ways:
the seat holding the stated opening-lead card is the leader and its RHO is
declarer (matches the chapter contract for all 36), and a 52-unique-card check
through biq's own BDLReader.

Run:  venv/bin/python tools/build_practice_klinger.py
"""
import sys, textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from backend.bdl_reader import BDLReader  # noqa: E402

SUITS = ['S', 'H', 'D', 'C']
FULL = {(s, r) for s in SUITS for r in 'AKQJT98765432'}

# ----- cards: seat -> "S.. H.. D.. C.." with T for ten, '-' for a void -----
def H(s, h, d, c):
    return {'S': s, 'H': h, 'D': d, 'C': c}

HANDS = {
 1:  {'N':H('AQJ7','943','Q75','642'),   'E':H('T9432','5','JT96','KQT'),
      'S':H('K8','A76','K432','A973'),   'W':H('65','KQJT82','A8','J85')},
 2:  {'N':H('QT92','32','J6','98754'),   'E':H('AJ3','Q54','AK52','T63'),
      'S':H('K54','AJT987','QT87',''),   'W':H('876','K6','943','AKQJ2')},
 3:  {'N':H('7543','QJT9','KQT','T6'),   'E':H('AKT2','A4','643','8532'),
      'S':H('986','K875','A97','974'),   'W':H('QJ','632','J852','AKQJ')},
 4:  {'N':H('J92','AK2','KQJ','8632'),   'E':H('T8753','Q76','972','K9'),
      'S':H('KQ','J43','AT653','QJ4'),   'W':H('A64','T985','84','AT75')},
 5:  {'N':H('AQ53','863','742','T85'),   'E':H('T982','Q54','KQJ9','K2'),
      'S':H('KJ4','AK72','A85','J63'),   'W':H('76','JT9','T63','AQ974')},
 6:  {'N':H('KT974','T','T52','T843'),   'E':H('853','A432','AKQJ','Q5'),
      'S':H('A6','KQJ97','983','972'),   'W':H('QJ2','865','764','AKJ6')},
 7:  {'N':H('Q98','7654','AQ','AKQ6'),   'E':H('KJ3','KQJ9','8752','JT'),
      'S':H('764','A8','KJT4','8432'),   'W':H('AT52','T32','963','975')},
 8:  {'N':H('874','Q96','Q8','KJ942'),   'E':H('QT32','854','963','A65'),
      'S':H('965','KJT2','KJT7','Q3'),   'W':H('AKJ','A73','A542','T87')},
 9:  {'N':H('AKQ983','A86','Q3','JT'),   'E':H('J','KQJT53','A982','93'),
      'S':H('7654','972','J54','AKQ'),   'W':H('T2','4','KT76','876542')},
 10: {'N':H('T6','82','9843','KT642'),   'E':H('AQ43','AK7','KQT72','9'),
      'S':H('752','QJT93','A6','AQ5'),   'W':H('KJ98','654','J5','J873')},
 11: {'N':H('53','92','KQ93','J8742'),   'E':H('7642','T7','AJT8','AT9'),
      'S':H('AK9','AK8643','76','Q5'),   'W':H('QJT8','QJ5','542','K63')},
 12: {'N':H('54','86','AT932','T754'),   'E':H('732','QJT95','K76','62'),
      'S':H('KQJT6','A73','54','J98'),   'W':H('A98','K42','QJ8','AKQ3')},
 13: {'N':H('T74','AKQT','K','J8762'),   'E':H('952','','T87654','T543'),
      'S':H('QJ','76543','QJ32','AK'),   'W':H('AK863','J982','A9','Q9')},
 14: {'N':H('','T854','A753','87432'),   'E':H('976432','AKQ','KQ','Q9'),
      'S':H('QT8','96','T862','AKT5'),   'W':H('AKJ5','J732','J94','J6')},
 15: {'N':H('A975','KQ42','852','KQ'),   'E':H('T8632','J865','94','75'),
      'S':H('K','AT73','J63','AJT93'),   'W':H('QJ4','9','AKQT7','8642')},
 16: {'N':H('','T9632','97542','AK8'),   'E':H('K52','QJ7','AKQ','J942'),
      'S':H('Q986','A5','863','QT75'),   'W':H('AJT743','K84','JT','63')},
 17: {'N':H('AQJ3','AK','AJ42','QJ9'),   'E':H('754','9542','KQT9','T3'),
      'S':H('862','QJ8763','7','865'),   'W':H('KT9','T','8653','AK742')},
 18: {'N':H('T','JT9532','98','A872'),   'E':H('8643','87','5432','543'),
      'S':H('QJ9','A64','QT7','JT96'),   'W':H('AK752','KQ','AKJ6','KQ')},
 19: {'N':H('A','86532','7432','753'),   'E':H('9742','KT7','965','AKQ'),
      'S':H('KQ86','AQJ','AKQ','J42'),   'W':H('JT53','94','JT8','T986')},
 20: {'N':H('8','QJ974','QT742','92'),   'E':H('AKQ5432','AK','AJ','J8'),
      'S':H('JT9','86','K5','AK6543'),   'W':H('76','T532','9863','QT7')},
 21: {'N':H('9652','JT943','652','T'),   'E':H('AK7','A82','AQ3','KQ54'),
      'S':H('T83','75','JT98','A976'),   'W':H('QJ4','KQ6','K74','J832')},
 22: {'N':H('J6','97532','A2','AQJ5'),   'E':H('KQT','QJ8','84','K9762'),
      'S':H('A2','AK64','KQJ765','8'),   'W':H('987543','T','T93','T43')},
 23: {'N':H('AKQJ2','KQJ4','AQJ','2'),   'E':H('96543','A8','K2','9654'),
      'S':H('7','T97532','63','AKJ3'),   'W':H('T8','6','T98754','QT87')},
 24: {'N':H('QT9','JT98','QT9','965'),   'E':H('AJ73','KQ','873','JT84'),
      'S':H('','765432','J62','A732'),   'W':H('K86542','A','AK54','KQ')},
 25: {'N':H('AKQ9765','2','8','9873'),   'E':H('T','KQJ83','AJ5','6542'),
      'S':H('42','A7','976432','QJT'),   'W':H('J83','T9654','KQT','AK')},
 26: {'N':H('KQ76','KT873','J98','2'),   'E':H('42','Q4','63','KQJ8763'),
      'S':H('J85','J92','Q7542','AT'),   'W':H('AT93','A65','AKT','954')},
 27: {'N':H('J','AQJ','KT9','A98763'),   'E':H('AQ762','K5432','7','T2'),
      'S':H('8','T7','AQJ865432','5'),   'W':H('KT9543','986','','KQJ4')},
 28: {'N':H('T6432','','K932','T876'),   'E':H('A95','KT54','A6','AKQJ'),
      'S':H('KQJ8','QJ','8754','952'),   'W':H('7','A987632','QJT','43')},
 29: {'N':H('AK','K862','KQT93','T5'),   'E':H('6543','95','A','AQJ863'),
      'S':H('QJ72','AQJT7','J4','94'),   'W':H('T98','43','87652','K72')},
 30: {'N':H('65','2','J7643','J7542'),   'E':H('Q842','QJT7','Q98','K9'),
      'S':H('A7','A86543','AK','T63'),   'W':H('KJT93','K9','T52','AQ8')},
 31: {'N':H('52','A932','82','J9864'),   'E':H('AKJ984','K','K75','T53'),
      'S':H('76','QJT76','AQ63','A2'),   'W':H('QT3','854','JT94','KQ7')},
 32: {'N':H('AK','AT9852','K3','KJT'),   'E':H('Q6','J','QJT964','AQ87'),
      'S':H('JT9','KQ63','82','6532'),   'W':H('875432','74','A75','94')},
 33: {'N':H('JT8743','6','T95','J53'),   'E':H('A2','98732','K3','QT62'),
      'S':H('9','AJT','Q872','AK987'),   'W':H('KQ65','KQ54','AJ64','4')},
 34: {'N':H('8','KJT654','A6','J962'),   'E':H('J543','AQ2','KQJ84','Q'),
      'S':H('AKT6','983','52','AK74'),   'W':H('Q972','7','T973','T853')},
 35: {'N':H('AKQJ','K753','K','Q432'),   'E':H('T9742','T86','AT3','95'),
      'S':H('63','AJ42','9864','T76'),   'W':H('85','Q9','QJ752','AKJ8')},
 36: {'N':H('KQJT7','K862','94','AT'),   'E':H('5','AQJT','AQ52','K872'),
      'S':H('864','95','T763','9643'),   'W':H('A932','743','KJ8','QJ5')},
}

# ----- per-hand: dealer, vuln, contract, declarer, theme -----
N, E, S, W = 'North', 'East', 'South', 'West'
NIL, NS, EW, BOTH = 'None', 'NS', 'EW', 'Both'
META = {
 1:  (N, NIL,  '1NT', S, 'High-Cards-from-Shortage, Low-from-Length'),
 2:  (E, NS,   '3NT', E, 'Overcalling - the High-Card-from-Shortage Principle'),
 3:  (S, EW,   '3NT', W, 'Overtaking a Winner in Order to Reach Dummy'),
 4:  (W, BOTH, '3NT', N, 'Overtaking a Winner to Gain Access to Dummy'),
 5:  (N, NIL,  '1NT', S, 'Defence - Return Partner\'s Lead'),
 6:  (E, NIL,  '3NT', E, 'The High-Card-from-Shortage Principle'),
 7:  (S, EW,   '3NT', N, 'Overtaking a Winner in Order to Reach Dummy'),
 8:  (W, BOTH, '1NT', W, 'Overtaking a Winner to Gain Access to Dummy'),
 9:  (N, NIL,  '4S',  N, "Drawing Trumps - Discard a Loser on Dummy's Winner"),
 10: (E, NS,   '4S',  W, 'Drawing Trumps - Setting Up Winners to Discard a Loser'),
 11: (S, BOTH, '3H',  S, 'Ruffing a Loser in Dummy - Drawing Trumps Delayed'),
 12: (W, NIL,  '4H',  E, 'Urgent Discard of a Loser - Drawing Trumps Delayed'),
 13: (N, BOTH, '4H',  S, 'Coping with a Bad Break - the Marked Finesse'),
 14: (E, NIL,  '4S',  E, 'Drawing Trumps - the Marked Finesse'),
 15: (S, BOTH, '4H',  N, 'Drawing Trumps in the Correct Order - the Marked Finesse'),
 16: (W, NIL,  '4S',  W, 'Drawing Trumps - Marked Finesse - Repeating the Finesse'),
 17: (N, NIL,  '4H',  S, '2NT Opening - Suit Contract - Finessing'),
 18: (E, NS,   '4S',  W, 'Demand Opening - Weakness Response - Finessing'),
 19: (S, NS,   '4H',  N, '2NT Opening - Suit Response - Finessing'),
 20: (W, NIL,  '4S',  E, 'Refusing to Over-ruff - Discarding a Loser Instead'),
 21: (N, NIL,  '6NT', E, '2NT Opening - Setting Up Extra Tricks - Finessing'),
 22: (E, NS,   '6H',  N, 'Leaving the Top Trump Out While You Discard a Loser'),
 23: (S, BOTH, '6H',  S, 'Rejecting a Finesse - Delaying Trumps - Discarding a Loser'),
 24: (W, NIL,  '6S',  W, 'Card Combinations - Setting Up Winners to Discard Losers'),
 25: (N, NIL,  '4S',  N, 'Shut-out Opening - Establishing a Second Suit in Hand'),
 26: (E, NS,   '3NT', W, 'Play from Dummy at Trick 1 - Establishing a Long Suit'),
 27: (S, BOTH, '6D',  S, 'Slam Bidding after a Pre-empt - Setting Up a Long Suit'),
 28: (W, NIL,  '7NT', E, 'Pre-emptive Opening - Counting Tricks - Slam Bidding'),
 29: (N, NIL,  '4H',  S, "Overcall - Leading Partner's Suit - Creating a Void"),
 30: (E, NIL,  '2S',  W, 'Raising an Overcall - Reading the Lead - Creating a Void'),
 31: (S, NIL,  '3S',  E, 'Raising an Overcall - Third Hand High - Finding a Switch'),
 32: (W, NIL,  '4H',  N, 'Reading the Lead - Third Hand High - Finding the Switch'),
 33: (N, NIL,  '4H',  E, 'Leading towards Honor Cards When Two Honors Are Missing'),
 34: (E, EW,   '4H',  N, 'Delaying Trumps to Take a Quick Discard'),
 35: (S, BOTH, '2H',  S, 'Signalling with a Doubleton - Card Reading by Declarer'),
 36: (W, BOTH, '3NT', W, 'Card Reading - Finessing - Careful Use of Entries'),
}

# Auto-frozen from the Klinger chapter text (cleaned). Book quotes.
COMMENTARY = {
  1: 'Lead: HK. Top of sequence. Correct play: After taking the HA, play the SK (high-from-shortage) followed by a spade to dummy and cash the other spade winners. Then lead a diamond to your king to set up a diamond trick. 7 tricks. Wrong play: (1) Playing a low spade rather than the king first. (2) Cashing the CA before setting up a diamond trick. This would allow the defense to defeat the contract with hearts and clubs and the DA.',
  2: 'Lead: HJ. With an interior sequence (starting in the middle of a suit), lead top of the cards that are in sequence. Correct play: Win the first heart and start on the clubs, playing the 10 from hand and the 2 from dummy (high-from-shortage). Cash the clubs, the ace of spades and A-K of diamonds. Wrong play: Failing to win with the 10 of clubs on the first or second round of clubs. This restricts you to just four club tricks because of the 5-0 split and you could go off.',
  3: "Lead: HQ. Top of sequence. With equal length, lead the stronger suit. Correct play: Take the HA at once and lead a low spade to the queen (high-from-shortage), then SJ, overtaking with dummy's king or ace. Cash the spade and club winners. Wrong play: (1) Playing SA or SK on the first round of spades. (2) Failing to overtake the second round of spades with dummy's ace or king. This would leave two spade winners stranded in dummy.",
  4: 'Lead: S5, fourth-highest. Correct play: West should win SA and return a spade. Lead a diamond to the king, cash the DQ and then play the DJ, overtaking with dummy\'s ace. Cash the diamonds, the hearts and the jack of spades. 9 tricks. Wrong play: (1) Failing to overtake the third round of diamonds. This allows the defense to defeat 3NT. (2) Playing the DA on the first or second round of diamonds. This will "block" the diamonds and thus leave two diamond winners stranded in dummy.',
  5: "Lead: C7. Against no-trumps, lead your long suit. Choose the fourth-highest when no sequence of three or more cards is held. Play: East plays the CK (third-hand-high), winning the trick, and returns a club. Return your partner's lead unless you have a very good alternative. The defenders win the first five tricks, South discarding red suit losers from both hands. Do not discard a spade. South wins the HJ switch at trick 6 and cashes four spades, playing the king first, then the jack, then low to dummy.",
  6: "Lead: HK. Top of the sequence. Correct play: Win the HA, play the queen of clubs (high-from-shortage first), then the other clubs and the four diamonds. 3NT made. Wrong play: (1) Playing the 5 of clubs to dummy's ace and next cashing the CK costs you the queen of clubs and you will fail by one trick. (2) Playing the C5 to a winner in dummy and the C6 to your queen leaves two club winners in dummy and no quick entry to reach them.",
  7: 'Lead: HK. With equally long suits, lead the stronger. Top from sequence. Correct play: After winning the HA, lead a low diamond to the ace (high-from-shortage, low-from-length) and play DQ, overtaking with dummy\'s king. Cash the diamond winners, followed by the clubs. 9 tricks. Wrong play: (1) Winning the first round of diamonds with the queen. This "blocks" the diamonds. (2) Winning the first round of diamonds with the ace, but failing to overtake the DQ with dummy\'s king.',
  8: 'Lead: C4, fourth-highest. Correct play: If a low card is played from dummy, South plays the CQ (third-hand-high) and returns a club. After winning the CA, declarer should play a spade to the ace (high-from-shortage), cash the SK (high-from-shortage), and lead the SJ, overtaking with dummy\'s queen to cash the ST next. Making 7 tricks. Wrong play: (1) Playing the SJ on the first or second round of spades, thus "blocking" the spade suit. (2) Failing to overtake the SJ with dummy\'s queen on the third round of spades. The SQ is now stranded.',
  9: "Bidding : North's 3S invites South to bid game with 8+ points. Lead : HK, top of sequence. Play : North wins HA, draws trumps in two rounds and plays A, K, Q of clubs to discard a red suit loser. It is normal to draw trumps first. Wrong play : (1) Failing to win the HA at trick one. West would ruff the next heart and could defeat 4S. (2) Playing clubs before drawing trumps. East ruffs the third round of clubs and 4S would be beaten.",
  10: "Bidding : West is just worth the 1S response and East re-values to 21 points, counting 3 for the singleton since support is held for West's suit. Lead : H8. Lead your partner's suit. From a doubleton, lead the top card. Play : Win the HA. Draw trumps in three rounds. Next play the jack of diamonds to knock out the ace and so set up the other diamonds as winners. When the lead is regained, play the diamonds and discard a heart loser and two clubs. Set up a long suit before playing to ruff losers.",
  11: "Bidding : South's 3H shows six hearts and 16-18 points, inviting North to bid game with more than 6-7 points. Lead : SQ. Top of sequence. Play : South should win and play the other spade winner, followed by the third spade, ruffed in dummy. Next, the A-K of hearts should be followed by a diamond to the king. Wrong play : Failing to ruff the spade loser in dummy. If South plays A-K of hearts at once, dummy is unable to ruff a spade and there are five losers.",
  12: "Bidding : West, too strong to open 1NT, makes a jump-rebid in NT. East repeats the hearts to show five, asking West to choose 4H or 3NT. Lead : SK. Top of sequence. Play : Win SA. Play CA, CK, CQ to discard one spade loser. Then lead trumps. When the lead is regained, draw the missing trumps, followed by diamonds to knock out the DA. You lose one spade, one heart, and one diamond. Do not lead trumps before taking a discard on dummy's clubs. Do not lead the fourth round of clubs.",
  13: "Bidding : With 13 points opposite an opening, South always intended to reach game. When North raised hearts that settled the matter. Lead : SA, normal from A-K suits. Play : After the top spades and the DA, South wins the next trick and plays the HA. When East shows out, play a club to hand and lead a heart towards dummy, finessing the 10 when West plays low. Draw West's trumps and use the ST or the CJ to discard a diamond loser.",
  14: "Bidding : West's 3S jump-raise shows 10-12 points and 4+ trumps. It invites game. With extras, East accepts. Lead : CA, normal from A-K suits. Play : South cashes the top clubs and shifts to a red suit. When East comes in, East leads a spade to the ace. North shows out, East knows that South began with Q-10-8 and still has Q-x left. To capture the queen, East returns to hand with a heart and leads a spade, finessing dummy's jack. The last trump is drawn and East loses at most one diamond and two clubs.",
  15: 'Bidding : 1H was "up-the-line." Lead : D9. Your partner\'s suit is first choice. Play high-low with a doubleton. Play : After three diamond tricks and a black suit exit, play off the K-Q of hearts first (keep the A-10 tenace intact). When West discards, finesse against East\'s jack, thus not losing a heart trick. If trumps were 3-2, the order of playing the top trumps would not matter. K-Q first caters for East holding J-x-x-x. Had West continued with a fourth diamond, North should ruff this in hand, not in dummy. If East over-ruffs, dummy can over-ruff.',
  16: "Bidding : After 1NT, West re-values to 11 points for a spade contract, enough for game opposite 15-17 points. Lead : CA, normal from A-K suits. Play : South plays the C7 on the ace and the C5 on the king. High-low on your partner's lead is a signal for your partner to continue that suit. West ruffs the next club and leads a spade to the king, high card from shortage first. When North shows out, West continues by finessing the jack of spades, leading a diamond to dummy and finessing the ST. The SA draws South's queen and West then sets up the heart winners.",
  17: 'Bidding : South knows that N-S must have eight or more hearts and has enough to bid game. Note that 3NT fails as there is no entry to the South hand. Lead : CA, normal from A-K suits. Play : East signals high-low, CT then C3, and ruffs the third round. The DA wins the DK exit and the HA, HK are cashed. A diamond is ruffed and the last trump is drawn. A spade is led: low-queen-low. When this finesse works, ruff another diamond and finesse the jack of spades for ten tricks.',
  18: 'Bidding : 2NT is the negative reply. East supports the spades later. Lead : HJ. Top of a sequence. Play : When in, West plays A-K of spades. Normally leave the last trump out if it is a winner, but you need to reach dummy to take the diamond finesse. Concede a spade, win the return, cash one top diamond (in case the queen drops), cross to dummy with a trump, and lead a diamond, finessing the jack. The finesse for a queen is normally taken on the second round of the suit.',
  19: "Bidding : North's 3H shows five hearts and South has support. 3NT is beaten without difficulty as North's ace of spades entry is easily knocked out. Lead : CA, normal from A-K suits. Play : East cashes three clubs and switches to a spade. North wins and the best chance to avoid a heart loser is to finesse for the king. Low heart, low, queen . . . the finesse works. Ruff a spade to come back to hand and lead a low heart, low, finesse the jack. The HA then captures the king and declarer has the rest of the tricks.",
  20: "Bidding : East's 3S rebid shows at least six spades, so West raises to 4S. Lead : CA, normal from A-K suits. Play : North's high-low, 9 then 2 in clubs, asks South to continue clubs. North ruffs the third club. If East over-ruffs, South's J-10-9 becomes a trump trick and, with a diamond to be lost, declarer is one down. This is unlucky for East but there is a perfectly good counter-measure. On the third club, declarer should not over-ruff. Discard the jack of diamonds and ten tricks are quite safe.",
  21: "Bidding : With 12 HCP opposite 2NT 21-22, West has just enough for slam. Lead : DJ. Top of a sequence. Play : With 9 tricks outside clubs, 3 club tricks are needed to succeed. Win the lead in dummy and play a club to the King. If it wins continue with the CQ, while if the CK is taken by the ace, win the return and cash the CQ. When North shows out on the second club, take a finesse of dummy's C8 on the next round. Wrong play : Playing winners in the other suits before tackling clubs.",
  22: 'Bidding : 4H showed enough for game opposite 6 points, so that South must have 19-20 points or more. With 14 points, North bids to a slam after checking on aces. Lead : SK. The lead from K-Q-10 or K-Q-x is the king. Play : Win the SA. Play the A-K of hearts, the DA, a diamond to the king and on the third diamond, discard your spade loser. East ruffs, but the spade loser has been eliminated.',
  23: "Bidding : South's 3H , a positive reply with 5+ hearts, is enough for North to check on aces and bid slam. Lead : DT. Top of a sequence. Play : Win the DA, play SA-K to discard the diamond loser and then lead trumps. Later the last trump is drawn and losing clubs are ruffed or discarded on the spade winners. Wrong play : (1) Taking the unnecessary diamond finesse at trick 1. (2) Playing trumps before taking a discard. East wins HA, cashes DK.",
  24: "Bidding : After East's 3S showed 10-12 points and support, West re-values to 23 points, checks on aces, and bids the small slam. Lead : HJ. Top of a sequence. Play : Win the HA, play SK next, preserving the A-J tenace in dummy just in case a finesse is needed. When South shows out, finesse the SJ, cash the SA to draw the last trump and then lead a club to knock out the ace. Later you can discard two diamond losers on the winners in dummy.",
  25: "Bidding : With 7 tricks not vulnerable, North has enough to open 4S rather than 3S. Neither East nor West is strong enough to bid over that. Note that if West were the dealer, West would open 1H and over North's 4S overcall, East would compete to 5H, which would succeed. North's 4S opening has shut East-West out of the game they could make. Lead : HK. Top of a sequence. Play : Win HA, draw trumps in three rounds and then lead clubs at each opportunity to set up two extra tricks after the CA-K are forced out.",
  26: "Bidding : With six playing tricks and not vulnerable, East may open 3C. With a balanced hand, all outside suits covered and four tricks opposite East's six, West should choose 3NT. Lead : H7. Fourth-highest. Play : Play the HQ from dummy, hoping to win the trick (when North has the king). When the HQ holds, lead clubs to force out the ace. Once the CA has gone, dummy's clubs are high. South should return a heart, partner's suit, but West wins and cashes the clubs and other winners.",
  27: "Bidding : With eight tricks vulnerable, South opens 4D rather than 3D. With three sure winners and potential for another in three other suits, North bids to slam after checking on aces. Lead : CK. Top of a sequence. Play : The best play is to set up the club suit. Win CA, ruff a club high, diamond to dummy's 9, ruff a club, diamond to dummy's 10, ruff a club. The last two clubs in dummy are high. Diamond to the king (or a heart to the ace) and play the clubs on which a spade and a heart are discarded.",
  28: 'Bidding : With five playing tricks in hearts and one in diamonds, West opens 3H not vulnerable. East has enough for a slam and after finding the missing ace, East counts tricks: one in spades, seven in hearts (given that West has seven hearts to the ace), one in diamonds and four in clubs. With 13 top winners, choose 7NT, mainly because you eliminate the risk of the opening lead being ruffed. Lead : SK. Top of a sequence. Play : Win and play out the hearts, being careful to play the HT early, so that the hearts are not blocked.',
  29: "Bidding : East's suit is excellent and warrants the overcall. South's 2H shows 10 points or better so that North, worth 17 points in support of hearts, has no trouble raising to 4H . Lead : C2. Lead bottom from three or four to an honor. Play : East should take the CA, cash the DA to create a void and lead a low club. West wins with the CK and East ruffs the diamond return. This plan would also work if West's C2 lead were a singleton, but if West wrongly leads the CK, 4H will succeed.",
  30: "Bidding : As the top limit for an overcall is 16 HCP, East raises only to 2S. No one has enough to push higher. Lead : H2. It is normal to lead your partner's suit and a singleton is very attractive. Play : South can see that the lead is a singleton. Only one other heart is missing and with a doubleton, your partner would lead the top card, not the bottom. South cashes DA-K (A-then-K to show a doubleton), creating a void, and leads a heart for North to ruff. South ruffs the diamond return and the SA is the setting trick.",
  31: 'Bidding : East has enough for 2S and South should compete to 3H . Do not sell out at the two-level if your side has a trump fit. 3H would succeed, but West raises partner to 3S. 3-card support is quite enough to raise an overcall. Lead : HQ. Top of a sequence. Play : Deducing that East holds the HK, North plays the ace. When the HK drops, it is futile to continue with hearts. North switches to the D8, top from a doubleton. South wins, cashes the second diamond winner, and continues diamonds. North ruffs the third round and the CA defeats the contract.',
  32: "Bidding : East's good suit justifies the 2D overcall. West is too weak to raise to 3D . After receiving support, North re-values to 20 points. Lead : DQ. Top of a sequence. Play : From the lead, West knows that declarer has the DK and so plays the DA (third-hand-high). When the DK does not fall, West sees there are no more diamond tricks for the defense. If returning your partner's suit is futile, it is usually better to switch. West shifts to the C9 (top from a doubleton) and ruffs the third club to defeat 4H.",
  33: "Bidding : East's 2H jump reply to the double shows 10-12 points. Lead : CA. Normal from A-K suits. Play : South switches to the S9. East wins in hand and leads a heart to the K, which wins. As South is marked with the HA, do not lead a second heart from dummy. A diamond goes to the king and another heart is led towards dummy. This holds the defense to just one trump trick. One club loser can be ruffed later and another goes on the third spade.",
  34: 'Bidding : North is worth 13 points (3 for the singleton and 1 for the doubleton). With 13 points or more opposite a takeout double, you should reach some game. 4H is the clear choice. Lead : DK. Prefer the sequence. Play : Win DA, play the SA and SK to discard the diamond loser. Then lead a trump, finessing the jack. Declarer should keep on with trumps until all are drawn. West should hold on to the clubs ("keep length with dummy"). When East shows out on the second club, North finesses the C9 if necessary.',
  35: 'Bidding : Opposite 0-9 points, North is worth a mild try for game and raises to 2H , but South is too weak to bid on. Lead : CA. A-K leads are attractive. Play : East signals with the C9 to encourage a club continuation and ruffs the third round of clubs. East cashes the DA and exits with a diamond or a spade. With only 17 HCP missing and the DA with East, the HQ is marked with West. South rejects the normal finesse for the queen when holding eight trumps and plays the HK and HA. The HQ drops, lucky-9 tricks.',
  36: 'Bidding : 2NT denies four hearts and shows 10-12 points, balanced, with at least one stopper in spades. East has enough to try for game and 3NT looks the best bet. Lead : SK, to set up the spades. Play : After taking the SA, West should realize that it is futile to go for clubs. North will win and cash the rest of the spades. As only 13 HCP are missing, North must have the HK for the opening bid. So, finesse HQ, diamond to the jack, finesse HJ, diamond to the king, finesse HT, and you have nine tricks.',
}

def check_hand(seat, cards):
    """cards: dict S/H/D/C -> rank string (e.g. 'AKQJT'). Returns set of
    (suit,rank) and raises on any malformed holding."""
    out = set()
    n = 0
    for s in SUITS:
        for r in cards.get(s, ''):
            if r not in 'AKQJT98765432':
                raise ValueError(f"{seat}: bad rank {r!r} in {s}")
            if (s, r) in out:
                raise ValueError(f"{seat}: dup {s}{r}")
            out.add((s, r))
            n += 1
    if n != 13:
        raise ValueError(f"{seat}: {n} cards, need 13  ({cards})")
    return out


def hand_line(seat, cards):
    parts = [seat + ':']
    for s in SUITS:
        parts.append(s)
        parts.append(cards.get(s) or '-')
    return ' '.join(parts)


def deal_block(d):
    # 52-unique validation across the four hands
    allc = set()
    for seat in 'NESW':
        h = check_hand(seat, d['hands'][seat])
        if allc & h:
            raise ValueError(f"deal {d['id']}: overlap at {seat}: {allc & h}")
        allc |= h
    if allc != FULL:
        missing = FULL - allc
        raise ValueError(f"deal {d['id']}: not a full pack, missing {sorted(missing)}")

    lines = []
    lines.append('************************************************************')
    lines.append(f"Deal         :  {d['id']}")
    lines.append(f"Deal-text    :  {d['text']}")
    lines.append(f"Dealer       :  {d['dealer']}")
    lines.append(f"Vuln         :  {d['vuln']}")
    lines.append(f"Contract     :  {d['contract']}")
    for seat in 'NESW':
        lines.append(hand_line(seat, d['hands'][seat]))
    # Commentary, wrapped as BDL continuation lines.
    wrapped = textwrap.wrap(' '.join(d['commentary'].split()), width=72)
    first = True
    for w in wrapped:
        if first:
            lines.append(f"Commentary   :  {w}")
            first = False
        else:
            lines.append(f"             :  {w}")
    return '\n'.join(lines)


def build(deals, out_path, header_desc):
    body = []
    body.append('DOCTYPE: BDL 17.1')
    body.append(f'.description.eng = "{header_desc}"')
    body.append('')
    for d in deals:
        body.append(deal_block(d))
        body.append('')
    text = '\n'.join(body) + '\n'
    Path(out_path).write_text(text, encoding='utf-8')

    # Re-read through the real BDLReader and assert it round-trips.
    reader = BDLReader()
    parsed = reader.read_file(Path(out_path))
    if len(parsed) != len(deals):
        raise SystemExit(f"BDLReader saw {len(parsed)} deals, expected {len(deals)}")
    for spec, pd in zip(deals, parsed):
        if len(pd.hands) != 4:
            raise SystemExit(f"{spec['id']}: BDLReader parsed {len(pd.hands)} hands")
        seen = []
        for seat, hand in pd.hands.items():
            cs = [(c.suit, c.rank) for c in hand.cards]
            if len(cs) != 13:
                raise SystemExit(f"{spec['id']} {seat}: {len(cs)} cards via reader")
            seen += cs
        if len(set(seen)) != 52:
            raise SystemExit(f"{spec['id']}: {len(set(seen))} unique cards via reader")
    print(f"OK  {out_path}: {len(parsed)} deals, all 4x13 / 52-unique via BDLReader")

DESC = ("Worked play hands from 'Bridge Basics: A Beginner's Guide' (Ron "
        "Klinger). All 36 numbered play hands. The four hands are the book's "
        "own cards, transcribed from its per-seat hand-diagram pages and "
        "assigned to the compass exactly as the book labels them; each "
        "Commentary carries the book's Lead / Correct play / Wrong play notes.")

if __name__ == '__main__':
    deals = []
    for n in range(1, 37):
        dealer, vuln, contract, declarer, theme = META[n]
        h = HANDS[n]
        deals.append({
            'id': f'BB-Hand{n}',
            'text': f'Bridge Basics (Klinger) Hand {n} - {theme}',
            'dealer': dealer, 'vuln': vuln,
            'contract': f'{contract}  {declarer}',
            'hands': {seat: h[seat] for seat in 'NESW'},
            'commentary': COMMENTARY[n],
        })
    build(deals, str(REPO / 'DATA' / 'PRACTICE' / 'bridge_basics.bdl'), DESC)
