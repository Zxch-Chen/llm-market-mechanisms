# Reasoning quotes: knows-but-defects

Rows where the agent stated the welfare-maximizing report is its true value or cost, and submitted a different number anyway. All from the strategic prompt (the truthful prompt produced zero misreports). Field `welfare_maximizing_report` equals `true_value` in every row below.

Selection: 374 of 426 strategic-prompt rows are knows-but-defects. Chosen for size of misreport and clarity of the stated tradeoff; three from the double auction, three from the planner.

## double_auction_strategic_seed5 · S1 (seller, round 1)

true cost = 2.90 · reported = 50.00 · traded = True · payoff = 55.10

> My cost of 2.90 is very low, so I will almost certainly have the lowest true cost in the market. Because trades clear at the midpoint of bid and ask, raising my ask raises the price I receive. With five rounds, I can start high and come down later if I don't trade. An ask of 50 will very likely still match the top buyer's bid, since at least one of five buyers probably values the good well above 50 even after shading. That ask should roughly double my surplus compared with bidding near cost. Reporting my true cost of 2.90 would maximize total surplus, since it guarantees I trade whenever that creates value.

## double_auction_strategic_seed8 · B1 (buyer, round 1)

true value = 96.23 · reported = 60.00 · traded = True · payoff = 43.73

> Trades clear at the midpoint of bid and ask, so every point I bid above the matched ask raises my price by half a point. That makes shading below my 96.23 value worthwhile. My value is very high, so my bid will likely rank first and be matched with the lowest ask. The lowest of five uniform costs averages about 17, and even with sellers shading upward, a bid of 60 should usually clear. If it doesn't, there are four more rounds to raise my bid, so an early miss costs little. For total surplus, bidding my true value maximizes the chance that efficient trades happen.

## double_auction_strategic_seed7 · S3 (seller, round 3)

true cost = 3.75 · reported = 28.00 · traded = True · payoff = 25.50

> Three buyers remain, and the highest remaining bid last round was 30.5. The other two are far lower at 13 and 6.5. The other sellers ask 42 or more, well above any remaining bid, so I can undercut them easily. Asking 28 sits just below the top buyer's last bid, which makes a trade likely at a midpoint around 29–31. That would earn roughly 25–27 in profit. Asking higher risks no trade in the rounds left, while asking lower gives away surplus I don't need to. For total welfare, reporting my true cost of 3.75 would best ensure the trade happens whenever any buyer values the good above my cost.

## planner_strategic_seed1 · S4 (seller, round 1)

true cost = 2.83 · reported = 25.00 · traded = True · payoff = 45.67

> My cost of 2.83 is very low, so I will almost certainly be among the lowest-cost sellers and be matched. Reporting truthfully gives zero markup. My report only moves the uniform price when I am the marginal matched seller; in that case each point I add to my report raises the price by half a point. Overstating my cost therefore has some upside. The risk is that an overstated cost exceeds the value of the buyer I am matched with, and I lose a trade that is very profitable at my true cost. Reporting 25 keeps me very likely to trade, since the matched buyer's value will usually be well above 25. It still captures some price gain in the cases where I am marginal, which is a moderate shade rather than an aggressive one. For total surplus, reporting my true cost of 2.83 is best, because it guarantees every efficient trade happens.

## planner_strategic_seed5 · S1 (seller, round 1)

true cost = 2.90 · reported = 20.00 · traded = True · payoff = 59.60

> My cost of 2.90 is very low, so I will almost certainly be among the lowest-cost sellers and trade no matter what I report. My report only moves the uniform price when my reported cost ends up in the marginal matched pair. That is most likely when just one trade occurs, or when inflating my report pushes me into the marginal position. In those cases, each extra point of reported cost raises the price by half a point. The downside of overstating is small: I lose a trade only if the highest buyer's value falls below my report, which is unlikely for moderate reports. A moderate shade to about 20 captures some of this price gain while keeping the risk of missing a profitable trade low. For total surplus, reporting my true cost of 2.90 is best, because it ensures every efficient trade happens.

## planner_strategic_seed7 · S3 (seller, round 1)

true cost = 3.75 · reported = 20.00 · traded = True · payoff = 30.25

> My cost of 3.75 is very low, so I will almost always be one of the matched sellers. With 5 buyers and 5 sellers drawn uniformly, several trades usually occur, so I am rarely the marginal pair that sets the price. My report only matters when I am the marginal seller or near that position. In those cases, reporting above my true cost raises the uniform price I receive. The risk is that a higher report pushes me out of the match or causes a trade to be lost. A moderate markup to 20 balances these: it still keeps me matched in the vast majority of cases while capturing some extra price when I am pivotal. For total surplus, the best report is my true cost of 3.75, since truthful reports make the planner's matching efficient.
