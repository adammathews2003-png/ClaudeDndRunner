---
die: d100
cost: 1d6x10gp
---
# Carousing

Roll d100 for the number, then d4 for the slot after the dot (`gm.py carouse` rolls
both). Each slot is one source table, credited below.

## Credits

Slots 1-3 are other people's work, collected here with credit for non-commercial play.
All rights stay with their authors; if you're one of them and want your table out,
open an issue and it will be removed.

- **.1** "The Capital: You wake up..." by **bardicchef** (https://bardicchef.tumblr.com).
  Transcribed from the image.
- **.2** "The bigger, badder, longer, uncut d100 carousing table" by **u/Bellociraptor**
  and **u/pbghin** on r/DnD (https://www.reddit.com/r/DnD/comments/3uunbt/).
- **.3** "Carousing Table" on the **GRS DM wiki** (https://grsdm.fandom.com/wiki/Carousing_Table),
  from **Evil DM**'s "Hangover, sword & sorcery style"
  (http://evildm.blogspot.com/2010/03/hangover-sword-sorcery-style.html). Reworded to
  the second person; its 100 is replaced by "roll twice".
- **.4** Original to this engine.

<!-- How the tool reads this table (docs/design/04 → Random tables): a range with a slot
     (`24-40.3`) is that source's row for every number in the range. 100 is roll twice
     (`twice`). Effect codes the tool applies: `coin ±<dice>[xN] [coin]`, `item +"…"`,
     `item -"…"`, `item -random`, `clock +3d "…"`, `no-rest`, `twice`; dice in a result
     that no code rolls are the GM's. Tags feed the campaign's content lines (re-rolled)
     and veils (off screen). No scenario-breaking nights: a row that can't happen here
     or would put the scenario's goals out of reach is re-rolled (carouse --reroll <pc>)
     before the reveal; `disruptive` rows print that check, but any row can fail it.
     Copied into each new campaign by `gm.py campaign new`; a campaign may edit its copy. -->

| roll | result | effect | tags |
|------|--------|--------|------|
| 01-03.4 | You wake in the stable, cuddled up to a very content goat. It now follows you everywhere and eats anything you put down. | item +"a devoted goat" | animals |
| 01.1 | You wake up on the floor of your room, clothing torn, missing 1d10 gold. | coin -1d10 |  |
| 01.2 | You wake up in jail, pending charges for a serious crime (Treason, sedition, grand larceny, etc.). You actually did it. |  | law, disruptive |
| 01.3 | Shanghaied! You wake up on a ship that has already set sail. |  | travel, disruptive |
| 02-03.3 | You partied with a VIP: a dissolute noble, an up-and-coming merchant, or an entertainer of repute. |  |  |
| 02.1 | You wake up on the floor of your room, curled up with two armfuls of bread. | item +"two armfuls of bread" |  |
| 02.2 | You wake up in jail, pending charges for a serious crime (Treason, sedition, grand larceny, etc.). You didn't do it. |  | law, disruptive |
| 03.1 | You wake up on the floor of your room, the inn's four cats snoozing on top of you. |  | animals |
| 03.2 | You wake up in jail on minor charges. Pay 10gp for bail or spend 1d4 days behind bars. |  | law |
| 04-05.4 | You bet your boots on a game of knucklebones and lost. Something else of yours went the same way. | item -random | gambling |
| 04-06.3 | You got married while drunk. Your spouse is very attractive. |  | marriage |
| 04.1 | You wake up on the floor of your room, an angry city guard standing over you. |  | law |
| 04.2 | You wake up in jail on minor charges. Pay 10gp for bail or spend 1d4 days behind bars. Also, your cellmate is an NPC you previously made enemies with. |  | law |
| 05.1 | You wake up on the floor of your room, surrounded by 1d10 undressed strangers. |  | nudity, sex |
| 05.2 | You wake up in jail on minor charges. Pay 10gp for bail or spend 1d4 days behind bars. Also, your cellmate is an NPC you previously befriended. |  | law |
| 06-08.4 | You bought a round for the whole house, then another. People cheered your name, mostly correctly. | coin -2d6x10 | drink |
| 06.1 | You wake up in a strange carriage, with a rich old woman screaming in horror. |  |  |
| 06.2 | You wake up in bed with an NPC you previously made enemies with. |  | sex |
| 07-09.3 | You now own a blade of exquisite quality and workmanship. | item +"a blade of exquisite quality and workmanship" |  |
| 07.1 | You wake up in a strange carriage, and you notice it's already left the city gates. |  | travel, disruptive |
| 07.2 | You wake up in bed with an NPC you previously made friends with. |  | sex |
| 08.1 | You wake up in the back of a wheelbarrow, surrounded by crushed produce. |  |  |
| 08.2 | You wake up in bed with a total stranger when they wake up, they are: roll 1d6 1 = Friendly, 2 = Neutral, 3 = Hostile, 4 = Disgusted, 5 = Frightened, 6 = In Love. |  | sex |
| 09-10.4 | You are married. Your spouse is delighted, has already moved your things into their spare room, and is nobody you remember meeting. |  | romance, marriage |
| 09.1 | You wake up stuffed into a barrel, soaking wet, and reeking of rotten fish. |  |  |
| 09.2 | You wake up in bed with the spouse of an NPC you previously made friends with. |  | sex, adultery |
| 10-13.3 | You got married while drunk. Your spouse is not the slightest bit attractive. |  | marriage |
| 10.1 | You wake up in a strange bed, next to a stranger, and wearing a wedding band. |  | marriage, sex |
| 10.2 | You wake up in bed with the spouse of an NPC you previously made enemies with. |  | sex, adultery |
| 11-13.4 | You won an arm-wrestling tournament. The trophy is a dented copper crown that turns your forehead green. | item +"a dented copper crown (arm-wrestling trophy)" |  |
| 11.1 | You wake up in a strange bed, next to a familiar NPC (DM pick). |  | sex |
| 11.2 | You wake up in bed with the spouse of an important local noble or official. |  | sex, adultery |
| 12.1 | You wake up in a strange bed, with a very angry man hitting you with a broom. |  | violence |
| 12.2 | You wake up in a strange bed with no one, you can hear the family downstairs calling for the constables. |  | law |
| 13.1 | You wake up on the counter of the bar, patrons trying to eat and drink around you. |  |  |
| 13.2 | You wake up in a strange bed with no one. A moment later, a middle aged man invites you down for breakfast. He and his family know you by name and no one seems to find your presence unusual. |  |  |
| 14-15.4 | You signed something. The paper in your pocket says you own a third of a leaky rowboat, and a third of its debts. | item +"a deed to one third of a leaky rowboat"; clock +5d "the rowboat's co-owners want your share of the mooring fees" | debt |
| 14-16.3 | You wake up next to the poxed sex worker you were warned about last night. |  | sex, prostitution, disease |
| 14.1 | You wake up in the inn stables, cuddled up next to the innkeeper's prized cow. |  | animals |
| 14.2 | You wake up in a strange bed with no one, but there is a scent of long rotting flesh coming from under the mattress. |  | corpse, death, gore |
| 15.1 | You wake up in the inn stables, with the stable boy poking at your face angrily. |  |  |
| 15.2 | You wake up chained to a strange bed. A large man in leather comes to release you and shyly asks that you join him for breakfast. |  | bondage, sex |
| 16-18.4 | You taught the regulars a drinking song you made up. By morning it has nine verses, and you're the villain in six of them. |  | drink |
| 16.1 | You wake up in the inn stables, wearing a horse's saddle on your own back. |  | animals |
| 16.2 | You wake up on the floor of a seedy club. Looks like it was amateur night. Your clothing is in a pile in the corner and you don't know where the g-string came from, but you have an extra 3d10 cp. | coin +3d10 cp | nudity, sex |
| 17-18.3 | You overheard whispering thieves and have a lead on a vast sum of wealth. |  | crime |
| 17.1 | You wake up in the city barracks, wearing the full plate armor of an officer. | item +"an officer's full plate armor (not yours)" | law, military |
| 17.2 | You wake up on the floor of a seedy club. Looks like it was amateur night. Your clothing is in a pile in the corner and you don't know where the g-string came from, but you have an extra 2d10 cp and a token of admiration from an influential NPC. | coin +2d10 cp | nudity, sex |
| 18.1 | You wake up in the city barracks, holding a letter of acceptance to their ranks. |  | military, disruptive |
| 18.2 | You wake up on the floor of a seedy club. Looks like it was amateur night. Your clothing is in a pile in the corner and you don't know where the g-string came from, but you have an extra 2d10 cp and a token of admiration from an influential NPC's spouse. | coin +2d10 cp | nudity, sex |
| 19-20.3 | You won a ship or a deed. The ship's crew hasn't been paid in weeks; the land title is to a large, rundown, possibly haunted estate. | item +"a deed (a ship with an unpaid crew, or a rundown, possibly haunted estate)" |  |
| 19-20.4 | You woke in the town lock-up, charged with "conduct unbecoming a chicken". The fine is steep. | coin -1d6x10 | law |
| 19.1 | You wake up in the city barracks holding a letter of rejection to their ranks. |  | military |
| 19.2 | You wake up on the floor of a seedy club. Looks like it was amateur night. Your clothing is in a pile in the corner and you don't know where the g-string came from, but you have an extra 1d10 cp and a sympathy breakfast courtesy of the cleaning staff. | coin +1d10 cp | nudity, sex |
| 20.1 | You wake up in your own bed, with another party member snuggled next to you. |  | sex |
| 20.2 | You wake up on the floor of a seedy club. Looks like it was amateur night. Your clothing is in a pile in the corner and you don't know where the g-string came from, but you have an extra 1d10 gp and an invitation to attend a private, VIPs only gathering at an influential NPCs estate. (A leather animal mask will arrive wherever the PC is staying shortly.) | coin +1d10 | nudity, sex |
| 21-22.3 | You pledged your service and eternal friendship to a total stranger. |  |  |
| 21-23.4 | You picked a fight with a statue in the square, and the statue won. Your knuckles are a mess and you hardly slept. | no-rest | violence |
| 21.1 | You wake up in your own bed, with a familiar NPC (DM pick) beside you. |  | sex |
| 21.2 | You wake up in bed in an unfamiliar inn, the stranger next to you is: roll 1d6 1-2 = Unattractive, 3-4 = Incredibly Ugly, 5-6 = Unspeakably Hideous. |  | sex |
| 22.1 | You wake up in your own bed, surrounded by a group of five men in black cloaks. |  | cult |
| 22.2 | You wake up in bed in an unfamiliar inn, the stranger next to you is: roll 1d6 1-2 = Good Looking, 3-4 = Gorgeous, 5-6 = Way Out of Your League (You should probably just see yourself out before they wake up). |  | sex |
| 23.1 | You wake up in your own bed, having had a wonderful night's sleep. |  |  |
| 23.2 | You wake up in bed in an unfamiliar inn, the stranger next to you is: roll 1d6 1-2 = a Goat, 3-4 = a Pig, 5-6 = a Miniature Donkey. |  | sex, animals |
| 23.3 | Recruited! You have joined the army. |  | military, disruptive |
| 24-25.4 | Someone sold you a genuine dragon egg. It's a painted rock, but it's warm every morning and nobody can say why. | coin -3d6; item +"a painted, oddly warm 'dragon egg'" | magic |
| 24-40.3 | You spent half your earnings on wine, revelry and worse. |  | drink, drugs, sex |
| 24.1 | You wake up in your own bed, tied to your headboard with rough rope. |  | bondage |
| 24.2 | You wake up in your bed. You are wearing a full face of makeup and there are 1d4 gp on the nightstand. | coin +1d4 | sex, prostitution |
| 25.1 | You wake up in your own bed, naked and holding a wanted poster with your face. |  | nudity, law |
| 25.2 | You wake up in your bed. You would get up, but you are tied to it with leather straps. |  | bondage |
| 26-28.4 | You joined a secret society. You know the handshake. You don't know its name, its purpose or where it meets. |  |  |
| 26.1 | You wake up in a cobbler's shop wearing a mud-coated pair of expensive shoes. | item +"a mud-coated pair of expensive shoes" |  |
| 26.2 | You wake up in your bed. A dog you have never seen before is licking your left foot. |  | animals |
| 27.1 | You wake up in a dye maker's shop, with your skin stained a bright color (last 1 day). |  |  |
| 27.2 | You wake up in your bed. On you is a document from a local judge stating that you have legally changed your name to the same name as one of your fellow party members. |  |  |
| 28.1 | You wake up in a local brewery, floating in the middle of a vat of bubbling beer. |  | drink |
| 28.2 | You wake up in your bed. On you is a document from a local judge stating that you have legally changed your name to the same name as your worst NPC enemy. |  |  |
| 29-30.4 | You got a tattoo: a portrait of the barkeep, beautifully done, across your back. |  | body |
| 29.1 | You wake up in the city square, tarred, feathered, and being loudly laughed at. |  | humiliation, violence |
| 29.2 | You wake up in your bed. On you is a 'Thank you' note from an important local official, noble, or organization. It does not make any mention of what they are thanking you for. |  |  |
| 30.1 | You wake up in the city square, wearing a sign warning people that you bite. |  | humiliation |
| 30.2 | You wake up in your bed. You are spooning a whole ham. The ham is wearing a nightgown and lipstick. |  |  |
| 31-33.4 | A fortune teller read your palm, went pale, and paid you to leave. | coin +2d6 | magic |
| 31.1 | You wake up in the city square, dressed as a mime, with a crowd around you. |  |  |
| 31.2 | You wake up in your bed. You are spooning someone who looks almost exactly like you. |  |  |
| 32.1 | You wake up in a cheesemonger's shop, with every wheel bearing your teeth marks. |  |  |
| 32.2 | You wake up in your bed. You are dressed as a member of the local watch. A man in his underwear is hogtied at the foot of your bed. |  | law |
| 33.1 | You wake up in a general goods store, having constructed a Rube Goldberg machine. |  |  |
| 33.2 | You wake up in your bed. You are wearing a large hat, fake nose, and moustache. Walking around town later, you see a large number of wanted posters. The person depicted looks a lot like you. Only they have a bigger nose. And a moustache. And a hat. |  |  |
| 34-35.4 | You adopted a raven. It knows one word, your name, and says it loudly at dawn. | item +"a raven that shouts your name at dawn" | animals |
| 34.1 | You wake up in a general goods store, wearing every single shirt that they sell. |  |  |
| 34.2 | You wake up in your bed. You are 2d6 gp poorer. Within the hour, 300 freshly baked pastries are delivered. | coin -2d6 |  |
| 35.1 | You wake up in a general goods store, having eaten half their daily rations supply. |  |  |
| 35.2 | You wake up in your bed. You are 1d20 gp poorer, but now have 1d10 very fine hats. | coin -1d20; item +"a stack of very fine hats (1d10)" |  |
| 36-38.4 | You won a horse at cards. The horse is two towns away, and its owner remembers the game differently. | clock +7d "a stranger arrives to settle the matter of the horse" | gambling |
| 36.1 | You wake up in a general goods store, having made an epic fort using their tents. |  |  |
| 36.2 | You wake up in your bed. You are 1d10 gp richer and cradling a trophy with a giant pie on top. You have never felt more sick to your stomach. | coin +1d10; item +"a trophy topped with a giant pie" |  |
| 37.1 | You wake up in a basement, laid out in a glowing red summoning circle. |  | occult |
| 37.2 | You wake up in your bed. You are 1d20 gp poorer. Everything else seems normal, until the life size, lifelike bust of you carved from cheese is delivered. | coin -1d20; item +"a life-size bust of yourself, carved from cheese" |  |
| 38.1 | You wake up in a basement, surrounded by a make-shift shrine dedicated to you. |  | cult |
| 38.2 | You wake up in your bed. You are 3d20 gp poorer. Running around your room is a shocker lizard wearing a collar. It seems to be slightly domesticated. | coin -3d20; item +"a slightly domesticated shocker lizard (collared)" | animals |
| 39-40.4 | You ran up a tab. A very polite, very large person came by to say they'll be back for it. | clock +3d "the polite, very large tab collector returns" | debt |
| 39.1 | You wake up in a basement, with a cold corpse laying beside you, dressed in finery. |  | corpse, death |
| 39.2 | You wake up in your bed. You are wearing a very respectable suit. In your breast pocket is a folded stack of papers indicating that you have been elected to some minor local political position. (Ex: Town Cattle Inspector, District Cheese Quality Controller, etc.) |  |  |
| 40.1 | You wake up in a basement, with a large monster restrained in the corner (DM pick). |  | monster |
| 40.2 | You wake up in your bed. Everything seems normal. Soon a paladin arrives and tells you how glad he is that you helped him break all those vows last night. When asked which vows, he just winks and says, 'Oh, you know.' |  | sex |
| 41-43.3 | You spent all your earnings on wine, revelry and worse. |  | drink, drugs, sex |
| 41-43.4 | You swapped cloaks with somebody. Theirs has a bundle of letters in the lining, addressed to someone else. | item +"a stranger's cloak with letters sewn into the lining" | crime |
| 41.1 | You wake up in a basement, next to a small child, telling you that they're hungry. |  | child |
| 41.2 | You wake up in your bed. Everything seems normal. Soon a passive aggressive note is delivered explaining how in your intoxicated state, you wound up on the bad side of a middling local organization. (Scrivener's Guild, Esoteric Brotherhood of the Fish Mongers, town chapter of the Rotary Club, Home Owner's Association, whatever. They will probably not attempt to harm the PC, but they may try to foil them in petty ways whenever the PC is in the area.) |  |  |
| 42.1 | You wake up in a basement that appears to have been converted into a chapel. |  | religion |
| 42.2 | You wake up in your bed. Take the cost of your armor type (non-magical), multiply it by 1d4. You are that many gp poorer but you have the result of that 1d4 roll in otherwise cosmetically identical suits of armor in different colors. |  |  |
| 43.1 | You wake up in a local fighter guild, wearing a medal of champions you didn't win. | item +"a champion's medal (not won by you)" |  |
| 43.2 | You wake up in your bed. You are 1d10 gp poorer and have numerous bruises of unknown origin. | coin -1d10 | violence |
| 44-45.4 | You invented a cocktail. It's named after you, and it's now banned in this establishment. |  | drink |
| 44-56.3 | Robbed while drunk: you lose all your treasure and equipment. |  | crime, disruptive |
| 44.1 | You wake up in a local magic guild, with one unmarked potion bottle in each hand. | item +"two unmarked potions" | magic |
| 44.2 | You wake up in your bed. Your knuckles are bruised, bloodied, and full of splinters. Your pockets are filled with fresh produce. You have a vague memory of a fruit cart looking at you funny. | item +"pockets full of fresh produce" | violence |
| 45.1 | You wake up in a local merchant guild, holding a bill of sale for your own portrait. | item +"a bill of sale for your own portrait" |  |
| 45.2 | You wake up in your bed. From the corner of your room, you hear the sound of awful crying. It's a baby. |  | child |
| 46-48.4 | You entered an eating contest and won. You don't feel like a winner, and you didn't sleep. | no-rest |  |
| 46.1 | You wake up in a local thieves guild, stashed among 5x10 gold amount of loot. |  | crime |
| 46.2 | You wake up in your bed. You are wearing a suit cobbled together from bits and pieces of the skins of various animals. Later in the day, you hear stories of how some clawed, antlered monster was seen peeping in windows and climbing on roofs throughout the night. |  |  |
| 47.1 | You wake up inside of a barrel, and there's definitely someone rolling it. |  |  |
| 47.2 | You wake up in your bed. At your feet, you see 4d6 mice standing on their hind legs watching you. As soon as you stir, they scatter, leaving behind what appears to be a tiny altar with offerings of bread crust and cheese crumbles. One lock of your hair is now shorter than the rest. |  |  |
| 48.1 | You wake up inside of a barrel, buried up to your shoulders in baking flour. |  |  |
| 48.2 | You wake up on the floor of your room. In your bed, there are 2d4 sleeping prostitutes. You are still fully clothed and unsticky. |  | sex, prostitution |
| 49-50.4 | You gave a stirring speech about the dangers of something. People are now organizing, and they expect you to lead. |  |  |
| 49.1 | You wake up inside of a crate, curled tight and crammed, unable to move. |  |  |
| 49.2 | You wake up on the floor of your room. In your bed is a sleeping pig. The pig is covered in lipstick marks. Your face is also smeared with lipstick. |  | animals, sex |
| 50.1 | You wake up inside of a crate, nestled among many soft furs and blankets. |  |  |
| 50.2 | You wake up on the floor of your room. You are covered in dirt and mud. On your bed is a freshly exhumed corpse. |  | corpse, death |
| 51-53.4 | You lost your purse, found somebody else's, and lost that one too. | coin -1d6x10 | crime |
| 51.1 | You wake up in the church, having been snoring loudly through service. |  | religion |
| 51.2 | You wake up on the floor of your room. All the furniture and rugs have been moved up against the walls. In the center is a crudely drawn summoning circle ringed with the remains of black candles. At the center of the circle is a really fantastic looking sandwich. |  | occult |
| 52.1 | You wake up in the church, sitting up in a coffin during an ongoing funeral. |  | death, religion |
| 52.2 | You wake up in a temple. Several monks have gathered around you and are praying for your soul. |  | death |
| 53.1 | You wake up in the church, hanging from a large holy symbol on the ceiling. |  | religion |
| 53.2 | You wake up in a temple. In a coffin. Several monks are standing over you offering a pauper's last rites. They seem surprised when you start moving. |  | corpse, death |
| 54-55.4 | A family of millers adopted you, with a ceremony. They expect you at every birthday from now on. |  |  |
| 54.1 | You wake up in the church, wearing the robes of a priest as the bell rings. |  | religion |
| 54.2 | You wake up in a temple. You are wearing a fine suit. By the altar is a coffin, the corpse inside is wearing your clothes. |  | nudity, religion |
| 55.1 | You wake up in the church, naked and judged by many. |  | nudity, religion |
| 55.2 | You wake up in a temple. In the confessional. Naked. Services are beginning. |  | nudity, religion |
| 56-58.4 | You performed a small miracle at the shrine (you think it was the wind). A pilgrim now follows you, taking notes. |  | religion |
| 56.1 | You wake up in the graveyard, partially buried in an unmarked grave. |  | death |
| 56.2 | You wake up in a temple. In the confessional. Naked. Someone enters the other side and begins confessing their sins. |  | religion |
| 57-60.3 | Robbed and beaten while drunk: as above, and you wake up with a wound. |  | crime, violence, injury, disruptive |
| 57.1 | You wake up in the graveyard, trapped within an occupied coffin. |  | corpse, death |
| 57.2 | You wake up in a temple. In holy vestments. Crowds have begun gathering for service. |  | nudity, religion, excrement |
| 58.1 | You wake up in a busy marketplace, covered in 1d10 angry chickens. |  | animals |
| 58.2 | You wake up in a temple naked behind the altar. The first of the faithful are starting to enter for services. Someone has defecated in the offering dish. |  | nudity |
| 59-60.4 | You challenged the local champion to a duel. It's set for tomorrow noon, in front of everyone. | clock +12h "the duel with the local champion" | violence |
| 59.1 | You wake up in the middle of the street, just as a wagon runs over your leg. |  | injury |
| 59.2 | You wake up in the woods 1d4 miles from where you last remember being. You are naked and armed only with a wooden spear hastily carved from a sapling. |  |  |
| 60.1 | You wake up in the middle of the street, a guard slapping you awake. |  | law |
| 60.2 | You wake up in the woods 1d4 miles from where you last remember being. You are unarmed and only wearing one boot. A wolverine has the other. |  | nudity, animals |
| 61-63.3 | You now own a slave, or the contract of an indentured servant. |  | slavery |
| 61-63.4 | You traded your spare clothes for a single, extraordinary hat. | item +"an extraordinary hat" |  |
| 61.1 | You wake up in an alleyway, with 1d4 hooligans stealing your things. | item -random | crime |
| 61.2 | You wake up in the woods 1d4 miles from where you last remember being. You are in the middle of a perfect circle of trees, naked save for the freshly flayed skin of a lamb. |  |  |
| 62.1 | You wake up in an alleyway, clothing torn, having been fighting the night prior. |  | violence |
| 62.2 | You wake up in the woods 1d4 miles from where you last remember being. You head seems to be stuck in some kind of no-kill trap. |  |  |
| 63.1 | You wake up in an alleyway, wearing a royal crown and not much else. | item +"a royal crown (someone will want it back)" | nudity |
| 63.2 | You wake up in the woods 1d4 miles from where you last remember being. You are at the bottom of a deep pit trap. Two gap-toothed yokels are leering down at you. |  | animals |
| 64-65.4 | You slept on the roof. You're fine. The roof isn't, and the owner wants it fixed. | coin -2d6 |  |
| 64.1 | You wake up in an alleyway, with 1d6 of your gold missing from your pockets. | coin -1d6 | crime |
| 64.2 | You wake up in the woods 1d4 miles from where you last remember being. You are holding a bear cub. |  |  |
| 64.3 | You wake up holding a basket. In it is a baby and a note: "Her name is Emily. Be kind to her." |  | child |
| 65-66.3 | You drank some bad date wine and are incapacitated for a week. | no-rest | poison, disruptive |
| 65.1 | You wake up in an alleyway, nestled inside of a reeking pile of trash. |  |  |
| 65.2 | You wake up in the woods 1d4 miles from where you last remember being. 3d12 miconids are standing in a circle around you, singing a song you vaguely remember being soothed by in early childhood. |  | sex |
| 66-68.4 | You found a map scrawled on the back of a menu. It might lead somewhere. It might be directions to the privy. | item +"a map on the back of a menu" |  |
| 66.1 | You wake up in an alleyway, propped next to a mannequin that looks like you. |  |  |
| 66.2 | You wake up in humble country a barn. A slightly homely girl is asleep on the hay beside you. Someone is opening the front door. | coin +1d10 | sex, bondage |
| 67.1 | You wake up in the bed of a luxurious inn, alone, and with breakfast served. |  |  |
| 67.2 | You wake up in a nobleman's barn. You are wearing a saddle and there are whip marks on your buttocks. You are 1d10 gp richer. |  | nudity |
| 67.3 | You wake up wanted for murder. You're completely innocent, but that's not the point. |  | law, murder, disruptive |
| 68-69.3 | You now own an exotic mount (camel, elephant, ostrich or llama). | item +"an exotic mount (camel, elephant, ostrich or llama)" | animals |
| 68.1 | You wake up in the bed of a luxurious inn, with a noble's spouse at your side. |  | sex, adultery |
| 68.2 | You wake up in an alley. 1d6 hobos are wearing 1d6 articles of your clothing. |  | child |
| 69-70.4 | You lost a bet and must wear a sign around your neck for a week. The sign is not flattering. |  | gambling |
| 69.1 | You wake up in the bed of a dodgy inn, surrounded by 1d6 naked partners. |  | sex, nudity |
| 69.2 | You wake up in an alley. A group of local children are poking you with sticks and arguing about whether or not you're dead. |  |  |
| 70-72.3 | You defeated the town bully, ruffian or #1 bad guy. Everyone loves you, except the kin of the one you beat. |  | violence |
| 70.1 | You wake up in the bed of a dodgy inn, clothes soaked in blood that isn't yours. |  | blood |
| 70.2 | You wake up in an alley. A group of urchins are standing over you and arguing about how to split your money or how much they could sell your hair for if they shaved you. |  | nudity |
| 71-73.4 | You carried a stranger home. He's a minor noble, and he insists on repaying you in poetry. |  |  |
| 71.1 | You wake up in the bed of a dodgy inn, 3d10 gold richer from gambling wins. | coin +3d10 | gambling |
| 71.2 | You wake up in an alley. Your left ass cheek hurts. It now bears a lifelike tattoo of an NPC you have befriended in the past. |  |  |
| 72.1 | You wake up in the bed of a dodgy inn, tied up and gagged... not in a good way. |  | bondage |
| 72.2 | You wake up in an alley. Your left ass cheek hurts. It now bears a lifelike tattoo of an NPC you have made enemies with in the past. |  |  |
| 73-74.3 | You wake up in a luxury suite with a beautiful courtesan and twice the money you had last night. |  | sex, prostitution |
| 73.1 | You wake up in the bedroom of a well-known noble, guards yelling outside. |  | law |
| 73.2 | You wake up in an alley. There is a dead body next to you. |  | corpse, death |
| 74-75.4 | You were robbed blind and remember none of it. | coin -3d6x10 | crime |
| 74.1 | You wake up in the bedroom of a well-known noble, and they're next to you. |  | sex |
| 74.2 | You wake up in an alley. Your clothing is splattered in blood and you are carrying a sack with 1d10 gp worth of an illegal substance. | item +"a sack of an illegal substance (1d10 gp worth)" | drugs, blood, crime |
| 75-76.3 | You wake up clutching a note with a desperate message written on it. |  |  |
| 75.1 | You wake up in the bed of the ruler of the city, and they're happy to see you. |  | sex |
| 75.2 | You wake up in a sumptuous bed in a beautiful hotel. Along with the room service breakfast of caviar and sparkling wine comes the bill. Pay 2d10 gp or find a way out. | coin -2d10 |  |
| 76-78.4 | You learned a few words of a language nobody around here speaks. All of them are rude. |  |  |
| 76.1 | You wake up in the bed of the ruler of the city, and they're not happy to see you. |  | sex |
| 76.2 | You wake up in a sumptuous bed in a beautiful hotel. Next to you is a complete stranger. Both of you are wearing wedding bands. |  | marriage, sex |
| 77-79.3 | You wake up in a nobleman's guestroom and are mistaken for a legendary hero. |  |  |
| 77.1 | You wake up outside the city walls, with a decree of your exile for your crimes. |  | law, disruptive |
| 77.2 | You wake up in a sumptuous bed in a beautiful hotel. You are holding a whip. Someone else is asleep suspended from the ceiling by leather straps. |  | bondage, sex |
| 78.1 | You wake up outside the city walls, nestled up in the heights of a tree. |  |  |
| 78.2 | You wake up in a warehouse. It is used for fermenting fish. The smell lingers on you for 1d6 days. |  |  |
| 79-80.4 | You bought a cart. You don't have a horse. | coin -2d6x10; item +"a cart (no horse)" |  |
| 79.1 | You wake up outside the city walls, wet and shivering on a dock. |  |  |
| 79.2 | You wake up naked in an art school. A group of aspiring painters are in a circle around you, committing your likeness to canvas. |  | nudity |
| 80-85.3 | You now own the tavern, wine shop or brothel you woke up in. | item +"the deed to the tavern, wine shop or brothel you woke up in" |  |
| 80.1 | You wake up outside the city walls, with three traveling merchants poking you. |  |  |
| 80.2 | You wake up in the back room of an art gallery. Up front, you hear two people discussing the pairs of circles now covering all the paintings. One of them is using terms like 'Brilliant' and 'Revolutionary'. Your buttocks feel uncomfortably sticky. |  | crude |
| 81-83.4 | A ghost in the cellar beat you at cards and now claims a share of everything you win. | clock +2d "the cellar ghost comes to collect its share" | undead, gambling |
| 81.1 | You wake up outside the city walls, leaving in the back of a farmer's wagon. |  | travel, disruptive |
| 81.2 | You wake up naked in a fancy sculpture garden. The statues are all wearing various articles of your clothing. You can hear the sound of wealthy ladies beginning to gather for croquet. |  | nudity |
| 82.1 | You wake up outside the city walls, sleepwalking down the cobblestone path. |  |  |
| 82.2 | You wake up in the private garden of a local noble's wife. Her favorite topiary has been re-shaped into a crude likeness of a penis. You are covered in clippings. |  | crude |
| 83.1 | You wake up in a city prison cell, accused of murdering someone in town. |  | law, murder, disruptive |
| 83.2 | You wake up in the main square at the feet of a bronze statue of the city's founder. You and the statue are wearing matching outfits. You have in your possession 1d10 pairs of ladies' underwear of unknown origin. | item +"1d10 pairs of ladies' underwear" | sex |
| 84-85.4 | You woke up engaged. The wedding is in a week and the whole village is invited. | clock +7d "the wedding" | romance, marriage |
| 84.1 | You wake up in a city prison cell, accused of stealing from someone in town. |  | law |
| 84.2 | You wake up in the common room of an impoverished orphanage. You hear the voices of children around you. They are talking about how you ate the last of the cookies. |  | child |
| 85.1 | You wake up in a city prison cell, accused of setting fire to something in town. |  | law, fire |
| 85.2 | You wake up behind a stack of hay bales in the stable of an inn. On the other side of the stack, the innkeeper is interrogating the stable boy about why all the horses are wearing makeup and the oxen have bonnets. |  | animals |
| 86-88.4 | Someone slipped you a "potion" that was mostly onion. Your breath could strip paint for a day. |  | drink |
| 86-96.3 | You are locked up for drunken hooliganism. |  | law |
| 86.1 | You wake up in a city prison cell, accused of treason against the ruler. |  | law, disruptive |
| 86.2 | You wake up on the edge of a field. You are wearing a heavy full-body suit made from the skin of a bear. From the sound of things, the annual Town Watch vs Paladin's Order Tackleball game is about to start. |  |  |
| 87.1 | You wake up in stocks in the middle of the square, covered in tomato juice. |  | law, humiliation |
| 87.2 | You wake up on the front steps of the local administrative building. You are wearing war paint and a bandana. A treatise of radical political and religious ideologies has been nailed to the door. |  | politics, religion |
| 88.1 | You wake up in stocks in the middle of the square, covered in berry jam. |  | law, humiliation |
| 88.2 | You wake up behind a tailor's shop. You are wearing a ball gown made for a noblewoman. The rest of your clothing is missing. |  |  |
| 89-90.4 | You got a job as the inn's official taster. The inn expects you at noon, every day. | coin +1d6 |  |
| 89.1 | You wake up in the armory, wearing the expensive plate suit in the window. |  |  |
| 89.2 | You wake up in an alchemist's shop. There are a number of empty vials on the floor around you. For the next 2d6 days, everything that should be green looks purple and food tastes like it's vibrating. Occasionally, you burp multi-colored bubbles. |  | drugs |
| 90.1 | You wake up in the armory, inside a fort you built out of shields. |  |  |
| 90.2 | You wake up in a crypt. You hear retreating footsteps as one person complains to another that nothing makes him go soft faster than realizing they're still alive. |  | corpse, death |
| 91-93.4 | You won a pig in a raffle. It's a very good pig. | item +"a prize-winning pig" | animals |
| 91.1 | You wake up in the blacksmith's shop, covered head to toe in ash and soot. |  |  |
| 91.2 | You wake up in a closed coffin, crammed in next to you is someone recently deceased. Outside, you hear the sounds of a funeral service. |  | corpse, death |
| 92.1 | You wake up in the blacksmith's shop, having been trying to cut off manacles. |  |  |
| 92.2 | You wake up in the communal lodge of a fraternal order. You clothing and all exposed skin are now covered in crudely drawn pictures of genitalia. (Ink takes 1d6 days or 2d12 washes to fade completely.) |  | crude, sex |
| 93.1 | You wake up in a fine dress shop, wearing their fanciest wedding gown. |  |  |
| 93.2 | You wake up in the communal lodge of a sororal order. You are wearing feathers, lace, and a full face of makeup. Your buttock is sore and bears bruises in the same shapes as the cutouts on that paddle hanging above the fireplace. |  | sex, hazing |
| 94-95.4 | You insulted the wrong wizard. You're fine, apart from the smell of cheese that will follow you for a week. |  | magic |
| 94.1 | You wake up in a jeweler's store, covered in over 2,000 gold worth of gems. |  | law |
| 94.2 | You wake up in the communal lodge of an esoteric order. The room is full of burned out candles. There is a pen in your hand and a note, but the handwriting isn't yours. It is a letter to you from a long-dead friend or relative detailing fond memories or talking about how well or poorly you are doing carrying on the family legacy. |  |  |
| 95.1 | You wake up in a clothier's, half dressed, obviously trying to swap out clothing. |  |  |
| 95.2 | You wake up in the office of the dean of the local bardic college. You are wearing an immaculate suit. Moments later, the first in a line of students outside enters to begin their admission interview. |  |  |
| 96-97.4 | You won big at dice and spent most of it commissioning a statue of yourself for the square. | coin +2d6x10 | gambling |
| 96.1 | You wake up in a carvery, surrounded by hanging meat, and one looks human. |  | gore, cannibalism |
| 96.2 | You wake up in a cozy bed in the groundskeeper's cottage on a wealthy noble's estate. You have a number of bound minor wounds and on the nearest chair is a suit made from fox skins that looks to have been savaged by dogs. Waiting for you on the table are a warm pot of tea, 4d10gp in a bag, and a 'Thank you' note. | coin +4d10 | violence, animals |
| 97-99.3 | You wake up with the "mother of all hangovers" but no other ill effects. |  |  |
| 97.1 | You wake up in a bakery, curled up inside of a giant hollow cake. |  |  |
| 97.2 | You wake up in the hut of a local witch. Her cauldron is upended and it looks as though much of the content has been drunk. You are now: Roll 1d6- 1= green and slimey, 2 = 1/10 your original size, 3 = a toad, 4 = covered entirely in fur, 5 = walking around on giant chicken feet, 6 = modular (Your body parts are all easily removable but can be harmlessly snapped back into place. They're also scattered around the house.) You will remain this way for 1d12 hours. |  | magic, transformation |
| 98-99.4 | You woke three villages away, in somebody else's boots, with no idea how. | no-rest | disruptive |
| 98.1 | You wake up in a toymaker's shop, and one of the dolls looks exactly like you. |  |  |
| 98.2 | You wake up in the tower of a local wizard. You seem to have broken his enchanted celestial mapping device by putting your head through it. It will now only tell him what is visible in the night sky relative to the location of your head. |  |  |
| 99.1 | You wake up in a library, books scattered, having been sleeping on the shelf. |  |  |
| 99.2 | You wake up to find yourself seated at a table. There is a quill in one hand and a small cut on the other. Across from you sits a well-dressed but sinister man, a man of wealth and taste. In front of you is a contract detailing in extremely complex terms, the exchange of power for your immortal soul. (Once the contract is signed or if the PC refuses, the man disappears in a cloud of sulfurous smoke.) |  | devil, soul, disruptive |
| 100 | Roll twice more and combine the outcomes into one monstrous night. | twice | |
