---
die: d100
cost: 1d6x10gp
---
# Carousing
<!-- Engine starter table, original text (docs/design/02 → Table mechanics → Phase 16 →
     Carousing). Copied into a new campaign by `gm.py campaign new`; `gm.py carouse` rolls
     the campaign's own tables/carousing.md while `carousing: on`. A table found elsewhere
     comes in with `gm.py table import <file> --as carousing` and stays in the campaign.
     `effect` codes the tool applies: `coin -2d6x10` (gp unless a coin is named),
     `item +"…"`, `item -"…"`, `item -random`, `clock +3d "…"`, `no-rest` (the night
     isn't a long rest). Everything else in the result is filed by the GM with ordinary
     commands (stub npc, attitude, a rumor). `tags` are matched against the campaign's
     content `lines:` (re-rolled) and `veils:` (off screen). -->

| roll | result | effect | tags |
|------|--------|--------|------|
| 01-03 | You wake in the stable, cuddled up to a very content goat. It now follows you everywhere and eats anything you put down. | item +"a devoted goat" | animals |
| 04-05 | You bet your boots on a game of knucklebones and lost. Something else of yours went the same way. | item -random | gambling |
| 06-08 | You bought a round for the whole house, then another. People cheered your name, mostly correctly. | coin -2d6x10 | drink |
| 09-10 | You are married. Your spouse is delighted, has already moved your things into their spare room, and is nobody you remember meeting. | | romance, marriage |
| 11-13 | You won an arm-wrestling tournament. The trophy is a dented copper crown that turns your forehead green. | item +"a dented copper crown (arm-wrestling trophy)" | |
| 14-15 | You signed something. The paper in your pocket says you own a third of a leaky rowboat, and a third of its debts. | item +"a deed to one third of a leaky rowboat"; clock +5d "the rowboat's co-owners want your share of the mooring fees" | debt |
| 16-18 | You taught the regulars a drinking song you made up. By morning it has nine verses, and you're the villain in six of them. | | drink |
| 19-20 | You woke in the town lock-up, charged with "conduct unbecoming a chicken". The fine is steep. | coin -1d6x10 | law |
| 21-23 | You picked a fight with a statue in the square, and the statue won. Your knuckles are a mess and you hardly slept. | no-rest | violence |
| 24-25 | Someone sold you a genuine dragon egg. It's a painted rock, but it's warm every morning and nobody can say why. | coin -3d6; item +"a painted, oddly warm 'dragon egg'" | magic |
| 26-28 | You joined a secret society. You know the handshake. You don't know its name, its purpose or where it meets. | | |
| 29-30 | You got a tattoo: a portrait of the barkeep, beautifully done, across your back. | | body |
| 31-33 | A fortune teller read your palm, went pale, and paid you to leave. | coin +2d6 | magic |
| 34-35 | You adopted a raven. It knows one word, your name, and says it loudly at dawn. | item +"a raven that shouts your name at dawn" | animals |
| 36-38 | You won a horse at cards. The horse is two towns away, and its owner remembers the game differently. | clock +7d "a stranger arrives to settle the matter of the horse" | gambling |
| 39-40 | You ran up a tab. A very polite, very large person came by to say they'll be back for it. | clock +3d "the polite, very large tab collector returns" | debt |
| 41-43 | You swapped cloaks with somebody. Theirs has a bundle of letters in the lining, addressed to someone else. | item +"a stranger's cloak with letters sewn into the lining" | crime |
| 44-45 | You invented a cocktail. It's named after you, and it's now banned in this establishment. | | drink |
| 46-48 | You entered an eating contest and won. You don't feel like a winner, and you didn't sleep. | no-rest | |
| 49-50 | You gave a stirring speech about the dangers of something. People are now organizing, and they expect you to lead. | | |
| 51-53 | You lost your purse, found somebody else's, and lost that one too. | coin -1d6x10 | crime |
| 54-55 | A family of millers adopted you, with a ceremony. They expect you at every birthday from now on. | | |
| 56-58 | You performed a small miracle at the shrine (you think it was the wind). A pilgrim now follows you, taking notes. | | religion |
| 59-60 | You challenged the local champion to a duel. It's set for tomorrow noon, in front of everyone. | clock +12h "the duel with the local champion" | violence |
| 61-63 | You traded your spare clothes for a single, extraordinary hat. | item +"an extraordinary hat" | |
| 64-65 | You slept on the roof. You're fine. The roof isn't, and the owner wants it fixed. | coin -2d6 | |
| 66-68 | You found a map scrawled on the back of a menu. It might lead somewhere. It might be directions to the privy. | item +"a map on the back of a menu" | |
| 69-70 | You lost a bet and must wear a sign around your neck for a week. The sign is not flattering. | | gambling |
| 71-73 | You carried a stranger home. He's a minor noble, and he insists on repaying you in poetry. | | |
| 74-75 | You were robbed blind and remember none of it. | coin -3d6x10 | crime |
| 76-78 | You learned a few words of a language nobody around here speaks. All of them are rude. | | |
| 79-80 | You bought a cart. You don't have a horse. | coin -2d6x10; item +"a cart (no horse)" | |
| 81-83 | A ghost in the cellar beat you at cards and now claims a share of everything you win. | clock +2d "the cellar ghost comes to collect its share" | undead, gambling |
| 84-85 | You woke up engaged. The wedding is in a week and the whole village is invited. | clock +7d "the wedding" | romance, marriage |
| 86-88 | Someone slipped you a "potion" that was mostly onion. Your breath could strip paint for a day. | | drink |
| 89-90 | You got a job as the inn's official taster. The inn expects you at noon, every day. | coin +1d6 | |
| 91-93 | You won a pig in a raffle. It's a very good pig. | item +"a prize-winning pig" | animals |
| 94-95 | You insulted the wrong wizard. You're fine, apart from the smell of cheese that will follow you for a week. | | magic |
| 96-97 | You won big at dice and spent most of it commissioning a statue of yourself for the square. | coin +2d6x10 | gambling |
| 98-99 | You woke three villages away, in somebody else's boots, with no idea how. | no-rest | |
| 00 | You bought the tavern. Nobody knows with what. The previous owner is on a ship and very hard to reach. | item +"the deed to the tavern"; clock +5d "the tavern's creditors find their new owner" | debt |
