#!/usr/bin/env python3
"""
Terraria Bestiary Tracker
Run this script and open http://localhost:8275 in your browser.
It scans your Terraria world save files, reads bestiary progress,
and shows you which entries you're missing with links to the wiki.
"""

import http.server
import json
import os
import struct
import html
import sys

TERRARIA_DIR = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Terraria")
PORT = 8275

# All directories to scan for world files (.wld)
def _find_world_dirs():
    """Find all directories that may contain Terraria world files."""
    dirs = []

    # Standard local worlds
    local_worlds = os.path.join(TERRARIA_DIR, "Worlds")
    if os.path.isdir(local_worlds):
        dirs.append(("Local", local_worlds))

    # Steam Cloud worlds — search all Steam userdata profiles for Terraria (app 105600)
    steam_paths = [
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Steam"),
        os.path.join(os.path.expanduser("~"), "Steam"),
    ]
    # Also check additional Steam library folders on other drives
    for drive in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        steam_paths.append(os.path.join(f"{drive}:", "SteamLibrary"))
        steam_paths.append(os.path.join(f"{drive}:", "Program Files (x86)", "Steam"))

    seen = set()
    for steam_root in steam_paths:
        userdata = os.path.join(steam_root, "userdata")
        if not os.path.isdir(userdata):
            continue
        try:
            for user_id in os.listdir(userdata):
                # Vanilla worlds
                vanilla = os.path.join(userdata, user_id, "105600", "remote", "worlds")
                if os.path.isdir(vanilla) and vanilla not in seen:
                    seen.add(vanilla)
                    dirs.append(("Steam Cloud", vanilla))
                # tModLoader worlds
                modloader = os.path.join(userdata, user_id, "105600", "remote", "ModLoader", "worlds")
                if os.path.isdir(modloader) and modloader not in seen:
                    seen.add(modloader)
                    dirs.append(("Steam Cloud (ModLoader)", modloader))
        except OSError:
            pass

    return dirs

# ── Complete bestiary entries (number, display_name, wiki_slug, internal_names) ──
# internal_names is a list of internal NPC identifiers used in world save files.
# Wiki URLs are constructed as: https://terraria.wiki.gg/wiki/{wiki_slug}
BESTIARY = [
    (1, "Guide", "Guide", ["Guide"]),
    (2, "Merchant", "Merchant", ["Merchant"]),
    (3, "Nurse", "Nurse", ["Nurse"]),
    (4, "Demolitionist", "Demolitionist", ["Demolitionist"]),
    (5, "Angler", "Angler", ["Angler"]),
    (6, "Dryad", "Dryad", ["Dryad"]),
    (7, "Arms Dealer", "Arms_Dealer", ["ArmsDealer"]),
    (8, "Dye Trader", "Dye_Trader", ["DyeTrader"]),
    (9, "Painter", "Painter", ["Painter"]),
    (10, "Stylist", "Stylist", ["Stylist"]),
    (11, "Zoologist", "Zoologist", ["Zoologist"]),
    (12, "Tavernkeep", "Tavernkeep", ["DD2Bartender", "Tavernkeep"]),
    (13, "Golfer", "Golfer", ["Golfer"]),
    (14, "Goblin Tinkerer", "Goblin_Tinkerer", ["GoblinTinkerer", "BoundGoblin"]),
    (15, "Witch Doctor", "Witch_Doctor", ["WitchDoctor"]),
    (16, "Mechanic", "Mechanic", ["Mechanic", "BoundMechanic"]),
    (17, "Clothier", "Clothier", ["Clothier"]),
    (18, "Wizard", "Wizard", ["Wizard", "BoundWizard"]),
    (19, "Steampunker", "Steampunker", ["Steampunker"]),
    (20, "Pirate", "Pirate_(NPC)", ["Pirate"]),
    (21, "Truffle", "Truffle", ["Truffle"]),
    (22, "Tax Collector", "Tax_Collector", ["TaxCollector"]),
    (23, "Cyborg", "Cyborg", ["Cyborg"]),
    (24, "Party Girl", "Party_Girl", ["PartyGirl"]),
    (25, "Princess", "Princess", ["Princess"]),
    (26, "Santa Claus", "Santa_Claus", ["SantaClaus"]),
    (27, "Town Cat", "Town_Cat", ["TownCat"]),
    (28, "Town Dog", "Town_Dog", ["TownDog"]),
    (29, "Town Bunny", "Town_Bunny", ["TownBunny"]),
    (30, "Nerdy Slime", "Town_Slimes", ["TownSlimeBlue"]),
    (31, "Cool Slime", "Town_Slimes", ["TownSlimeGreen"]),
    (32, "Elder Slime", "Town_Slimes", ["TownSlimeOld"]),
    (33, "Clumsy Slime", "Town_Slimes", ["TownSlimePurple"]),
    (34, "Diva Slime", "Town_Slimes", ["TownSlimeRainbow"]),
    (35, "Surly Slime", "Town_Slimes", ["TownSlimeRed"]),
    (36, "Mystic Slime", "Town_Slimes", ["TownSlimeYellow"]),
    (37, "Squire Slime", "Town_Slimes", ["TownSlimeCopper"]),
    (38, "Traveling Merchant", "Traveling_Merchant", ["TravellingMerchant"]),
    (39, "Skeleton Merchant", "Skeleton_Merchant", ["SkeletonMerchant"]),
    (40, "Old Man", "Old_Man", ["OldMan"]),
    (41, "Mystic Frog", "Mystic_Frog", ["MysticFrog"]),
    (42, "Bunny", "Bunny", ["Bunny"]),
    (43, "Bunny (With a Hat)", "Bunny", ["PartyBunny"]),
    (44, "Explosive Bunny", "Explosive_Bunny", ["ExplosiveBunny"]),
    (45, "Bunny (Slime)", "Bunny", ["BunnySlimed"]),
    (46, "Bunny (Xmas)", "Bunny", ["BunnyXmas"]),
    (47, "Gold Bunny", "Gold_Bunny", ["GoldBunny"]),
    (48, "Bird", "Bird", ["Bird"]),
    (49, "Blue Jay", "Blue_Jay", ["BirdBlue"]),
    (50, "Cardinal", "Cardinal_(critter)", ["BirdRed"]),
    (51, "Scarlet Macaw", "Scarlet_Macaw", ["ScarletMacaw"]),
    (52, "Blue Macaw", "Blue_Macaw", ["BlueMacaw"]),
    (53, "Toucan", "Toucan", ["Toucan"]),
    (54, "Yellow Cockatiel", "Yellow_Cockatiel", ["YellowCockatiel"]),
    (55, "Gray Cockatiel", "Gray_Cockatiel", ["GrayCockatiel"]),
    (56, "Gold Bird", "Gold_Bird", ["GoldBird"]),
    (57, "Goldfish", "Goldfish_(NPC)", ["Goldfish"]),
    (58, "Gold Goldfish", "Gold_Goldfish", ["GoldGoldfish"]),
    (59, "Squirrel", "Squirrel", ["Squirrel"]),
    (60, "Red Squirrel", "Squirrel", ["SquirrelRed"]),
    (61, "Gold Squirrel", "Gold_Squirrel", ["GoldSquirrel"]),
    (62, "Mouse", "Mouse", ["Mouse"]),
    (63, "Gold Mouse", "Gold_Mouse", ["GoldMouse"]),
    (64, "Frog", "Frog", ["Frog"]),
    (65, "Gold Frog", "Gold_Frog", ["GoldFrog"]),
    (66, "Grasshopper", "Grasshopper", ["Grasshopper"]),
    (67, "Gold Grasshopper", "Gold_Grasshopper", ["GoldGrasshopper"]),
    (68, "Butterfly", "Butterfly", ["Butterfly"]),
    (69, "Gold Butterfly", "Gold_Butterfly", ["GoldButterfly"]),
    (70, "Worm", "Worm_(critter)", ["Worm"]),
    (71, "Gold Worm", "Gold_Worm", ["GoldWorm"]),
    (72, "Dragonfly", "Dragonfly", ["Dragonfly", "BlackDragonfly", "BlueDragonfly", "GreenDragonfly", "OrangeDragonfly", "RedDragonfly", "YellowDragonfly"]),
    (73, "Gold Dragonfly", "Gold_Dragonfly", ["GoldDragonfly"]),
    (74, "Seahorse", "Seahorse", ["Seahorse"]),
    (75, "Gold Seahorse", "Gold_Seahorse", ["GoldSeahorse"]),
    (76, "Water Strider", "Water_Strider", ["WaterStrider"]),
    (77, "Gold Water Strider", "Gold_Water_Strider", ["GoldWaterStrider"]),
    (78, "Ladybug", "Ladybug", ["Ladybug"]),
    (79, "Gold Ladybug", "Gold_Ladybug", ["GoldLadybug"]),
    (80, "Stinkbug", "Stinkbug", ["Stinkbug"]),
    (81, "Faeling", "Faeling", ["Faeling"]),
    (82, "Mallard Duck", "Duck", ["Duck2", "DuckWhite"]),
    (83, "Duck", "Duck", ["Duck"]),
    (84, "Turtle", "Turtle_(critter)", ["Turtle"]),
    (85, "Owl", "Owl", ["Owl"]),
    (86, "Firefly", "Firefly", ["Firefly"]),
    (87, "Enchanted Nightcrawler", "Enchanted_Nightcrawler", ["EnchantedNightcrawler"]),
    (88, "Pink Fairy", "Fairy", ["FairyCritterPink"]),
    (89, "Green Fairy", "Fairy", ["FairyCritterGreen"]),
    (90, "Blue Fairy", "Fairy", ["FairyCritterBlue"]),
    (91, "Rat", "Rat", ["Rat"]),
    (92, "Maggot", "Maggot", ["Maggot"]),
    (93, "Amethyst Squirrel", "Gem_Squirrel", ["GemSquirrelAmethyst"]),
    (94, "Topaz Squirrel", "Gem_Squirrel", ["GemSquirrelTopaz"]),
    (95, "Sapphire Squirrel", "Gem_Squirrel", ["GemSquirrelSapphire"]),
    (96, "Emerald Squirrel", "Gem_Squirrel", ["GemSquirrelEmerald"]),
    (97, "Ruby Squirrel", "Gem_Squirrel", ["GemSquirrelRuby"]),
    (98, "Diamond Squirrel", "Gem_Squirrel", ["GemSquirrelDiamond"]),
    (99, "Amber Squirrel", "Gem_Squirrel", ["GemSquirrelAmber"]),
    (100, "Amethyst Bunny", "Gem_Bunny", ["GemBunnyAmethyst"]),
    (101, "Topaz Bunny", "Gem_Bunny", ["GemBunnyTopaz"]),
    (102, "Sapphire Bunny", "Gem_Bunny", ["GemBunnySapphire"]),
    (103, "Emerald Bunny", "Gem_Bunny", ["GemBunnyEmerald"]),
    (104, "Ruby Bunny", "Gem_Bunny", ["GemBunnyRuby"]),
    (105, "Diamond Bunny", "Gem_Bunny", ["GemBunnyDiamond"]),
    (106, "Amber Bunny", "Gem_Bunny", ["GemBunnyAmber"]),
    (107, "Snail", "Snail", ["Snail"]),
    (108, "Truffle Worm", "Truffle_Worm", ["TruffleWorm"]),
    (109, "Penguin", "Penguin", ["Penguin"]),
    (110, "Penguin (Black)", "Penguin", ["PenguinBlack"]),
    (111, "Scorpion", "Scorpion_(critter)", ["Scorpion"]),
    (112, "Black Scorpion", "Scorpion_(critter)", ["ScorpionBlack"]),
    (113, "Grebe", "Grebe", ["Grebe"]),
    (114, "Pupfish", "Pupfish", ["Pupfish"]),
    (115, "Seagull", "Seagull", ["Seagull"]),
    (116, "Sea Turtle", "Sea_Turtle", ["SeaTurtle"]),
    (117, "Pufferfish", "Pufferfish_(critter)", ["Pufferfish"]),
    (118, "Dolphin", "Dolphin", ["Dolphin"]),
    (119, "Jungle Turtle", "Jungle_Turtle", ["JungleTurtle"]),
    (120, "Grubby", "Grubby", ["Grubby"]),
    (121, "Sluggy", "Sluggy", ["Sluggy"]),
    (122, "Buggy", "Buggy", ["Buggy"]),
    (123, "Hell Butterfly", "Hell_Butterfly", ["HellButterfly"]),
    (124, "Lavafly", "Lavafly", ["Lavafly"]),
    (125, "Magma Snail", "Magma_Snail", ["MagmaSnail"]),
    (126, "Lightning Bug", "Lightning_Bug", ["LightningBug"]),
    (127, "Prismatic Lacewing", "Prismatic_Lacewing", ["EmpressButterfly"]),
    (128, "Glowing Snail", "Glowing_Snail", ["GlowingSnail"]),
    (129, "Gnome", "Gnome", ["Gnome"]),
    (130, "Goblin Scout", "Goblin_Scout", ["GoblinScout"]),
    (131, "Green Slime", "Green_Slime", ["GreenSlime"]),
    (132, "Blue Slime", "Blue_Slime", ["BlueSlime"]),
    (133, "Purple Slime", "Purple_Slime", ["PurpleSlime"]),
    (134, "Pinky", "Pinky", ["Pinky"]),
    (135, "Windy Balloon", "Windy_Balloon", ["WindyBalloon"]),
    (136, "Angry Dandelion", "Angry_Dandelion", ["AngryDandelion"]),
    (137, "Umbrella Slime", "Umbrella_Slime", ["UmbrellaSlime"]),
    (138, "Flying Fish", "Flying_Fish", ["FlyingFish"]),
    (139, "Angry Nimbus", "Angry_Nimbus", ["AngryNimbus"]),
    (140, "Demon Eye (Dilated)", "Demon_Eye", ["DialatedEye"]),
    (141, "Demon Eye (Sleepy)", "Demon_Eye", ["SleepyEye"]),
    (142, "Demon Eye (Purple)", "Demon_Eye", ["PurpleEye"]),
    (143, "Demon Eye", "Demon_Eye", ["DemonEye"]),
    (144, "Demon Eye (Green)", "Demon_Eye", ["GreenEye"]),
    (145, "Demon Eye (Cataract)", "Demon_Eye", ["CataractEye"]),
    (146, "Wandering Eye", "Wandering_Eye", ["WanderingEye"]),
    (147, "Zombie (Female)", "Zombie", ["FemaleZombie"]),
    (148, "Zombie (Slimed)", "Zombie", ["SlimedZombie"]),
    (149, "Zombie (Bald)", "Zombie", ["BaldZombie", "BigBaldZombie"]),
    (150, "Zombie", "Zombie", ["Zombie"]),
    (151, "Zombie (Twiggy)", "Zombie", ["TwiggyZombie"]),
    (152, "Zombie (Torch)", "Zombie", ["TorchZombie"]),
    (153, "Zombie (Swamp)", "Zombie", ["SwampZombie"]),
    (154, "Zombie (Pincushion)", "Zombie", ["PincushionZombie"]),
    (155, "Raincoat Zombie", "Raincoat_Zombie", ["RaincoatZombie"]),
    (156, "Possessed Armor", "Possessed_Armor", ["PossessedArmor"]),
    (157, "Werewolf", "Werewolf", ["Werewolf"]),
    (158, "Wraith", "Wraith", ["Wraith"]),
    (159, "Corrupt Bunny", "Corrupt_Bunny", ["CorruptBunny"]),
    (160, "Corrupt Penguin", "Corrupt_Penguin", ["CorruptPenguin"]),
    (161, "Vicious Bunny", "Vicious_Bunny", ["CrimsonBunny"]),
    (162, "Vicious Penguin", "Vicious_Penguin", ["CrimsonPenguin"]),
    (163, "Blood Zombie", "Blood_Zombie", ["BloodZombie"]),
    (164, "The Groom", "The_Groom", ["TheGroom"]),
    (165, "The Bride", "The_Bride", ["TheBride"]),
    (166, "Zombie Merman", "Zombie_Merman", ["ZombieMerman"]),
    (167, "Clown", "Clown", ["Clown"]),
    (168, "Blood Squid", "Blood_Squid", ["BloodSquid"]),
    (169, "Blood Eel", "Blood_Eel", ["BloodEelHead"]),
    (170, "Corrupt Goldfish", "Corrupt_Goldfish", ["CorruptGoldfish", "CrimsonGoldfish"]),
    (171, "Vicious Goldfish", "Vicious_Goldfish", ["CrimsonGoldfish"]),
    (172, "Drippler", "Drippler", ["Drippler"]),
    (173, "Chattering Teeth Bomb", "Chattering_Teeth_Bomb", ["ChatteringTeethBomb"]),
    (174, "Wandering Eye Fish", "Wandering_Eye_Fish", ["EyeballFlyingFish"]),
    (175, "Hemogoblin Shark", "Hemogoblin_Shark", ["GoblinShark"]),
    (176, "Dreadnautilus", "Dreadnautilus", ["BloodNautilus"]),
    (177, "Hoppin' Jack", "Hoppin%27_Jack", ["HoppinJack"]),
    (178, "Maggot Zombie", "Maggot_Zombie", ["MaggotZombie"]),
    (179, "Moss Zombie", "Zombie", ["MossZombie"]),
    (180, "Raven", "Raven", ["Raven"]),
    (181, "Ghost", "Ghost", ["Ghost"]),
    (182, "Statue", "Statues", ["ArmedZombie", "ArmedZombiePincushion", "ArmedZombieTwiggy", "ArmedZombieSwamp", "ArmedZombieCenx"]),
    (183, "Red Slime", "Red_Slime", ["RedSlime"]),
    (184, "Yellow Slime", "Yellow_Slime", ["YellowSlime"]),
    (185, "Toxic Sludge", "Toxic_Sludge", ["ToxicSludge"]),
    (186, "Giant Worm", "Giant_Worm", ["GiantWormHead"]),
    (187, "Digger", "Digger", ["DiggerHead"]),
    (188, "Baby Slime", "Baby_Slime", ["BabySlime"]),
    (189, "Black Slime", "Black_Slime", ["BlackSlime"]),
    (190, "Shimmer Slime", "Shimmer_Slime", ["ShimmerSlime"]),
    (191, "Mother Slime", "Mother_Slime", ["MotherSlime"]),
    (192, "Cochineal Beetle", "Cochineal_Beetle", ["CochinealBeetle"]),
    (193, "Skeleton (Misassembled)", "Skeleton", ["MisassembledSkeleton", "SmallMisassembledSkeleton", "BigMisassembledSkeleton"]),
    (194, "Skeleton", "Skeleton", ["Skeleton", "SmallSkeleton", "BigSkeleton"]),
    (195, "Salamander", "Salamander", ["Salamander", "Salamander2", "Salamander3", "Salamander4", "Salamander5", "Salamander6", "Salamander7", "Salamander8", "Salamander9"]),
    (196, "Skeleton (Headache)", "Skeleton", ["HeadacheSkeleton", "SmallHeadacheSkeleton", "BigHeadacheSkeleton"]),
    (197, "Skeleton (Pantless)", "Skeleton", ["PantlessSkeleton", "SmallPantlessSkeleton", "BigPantlessSkeleton"]),
    (198, "Crawdad", "Crawdad", ["Crawdad", "Crawdad2"]),
    (199, "Undead Miner", "Undead_Miner", ["UndeadMiner"]),
    (200, "Skeleton Archer", "Skeleton_Archer", ["SkeletonArcher"]),
    (201, "Nymph", "Nymph", ["Nymph"]),
    (202, "Armored Skeleton", "Armored_Skeleton", ["ArmoredSkeleton"]),
    (203, "Rock Golem", "Rock_Golem", ["RockGolem"]),
    (204, "Tim", "Tim", ["Tim"]),
    (205, "Rune Wizard", "Rune_Wizard", ["RuneWizard"]),
    (206, "Cave Bat", "Cave_Bat", ["CaveBat"]),
    (207, "Giant Bat", "Giant_Bat", ["GiantBat"]),
    (208, "Blue Jellyfish", "Blue_Jellyfish", ["BlueJellyfish"]),
    (209, "Green Jellyfish", "Green_Jellyfish", ["GreenJellyfish"]),
    (210, "Mimic", "Mimic", ["Mimic"]),
    (211, "Giant Shelly", "Giant_Shelly", ["GiantShelly", "GiantShelly2"]),
    (212, "Lost Girl", "Lost_Girl", ["LostGirl"]),
    (213, "Granite Golem", "Granite_Golem", ["GraniteGolem"]),
    (214, "Granite Elemental", "Granite_Elemental", ["GraniteFlyer"]),
    (215, "Hoplite", "Hoplite", ["GreekSkeleton"]),
    (216, "Medusa", "Medusa", ["Medusa"]),
    (217, "Spore Skeleton", "Spore_Skeleton", ["SporeSkeleton"]),
    (218, "Spore Bat", "Spore_Bat", ["SporeBat"]),
    (219, "Wall Creeper", "Wall_Creeper", ["WallCreeper", "WallCreeperWall"]),
    (220, "Black Recluse", "Black_Recluse", ["BlackRecluse", "BlackRecluseWall"]),
    (221, "Ice Slime", "Ice_Slime", ["IceSlime"]),
    (222, "Frozen Zombie", "Frozen_Zombie", ["FrozenZombie"]),
    (223, "Ice Golem", "Ice_Golem", ["IceGolem"]),
    (224, "Wolf", "Wolf", ["Wolf"]),
    (225, "Spiked Ice Slime", "Spiked_Ice_Slime", ["SpikedIceSlime"]),
    (226, "Cyan Beetle", "Cyan_Beetle", ["CyanBeetle"]),
    (227, "Undead Viking", "Undead_Viking", ["UndeadViking"]),
    (228, "Snow Flinx", "Snow_Flinx", ["SnowFlinx"]),
    (229, "Armored Viking", "Armored_Viking", ["ArmoredViking"]),
    (230, "Icy Merman", "Icy_Merman", ["IcyMerman"]),
    (231, "Ice Bat", "Ice_Bat", ["IceBat"]),
    (232, "Ice Elemental", "Ice_Elemental", ["IceElemental"]),
    (233, "Ice Mimic", "Ice_Mimic", ["IceMimic"]),
    (234, "Ice Tortoise", "Ice_Tortoise", ["IceTortoise"]),
    (235, "Vulture", "Vulture", ["Vulture"]),
    (236, "Sand Slime", "Sand_Slime", ["SandSlime"]),
    (237, "Antlion Larva", "Antlion_Larva", ["LarvaeAntlion"]),
    (238, "Giant Antlion Charger", "Antlion_Charger", ["WalkingAntlion"]),
    (239, "Mummy", "Mummy", ["Mummy"]),
    (240, "Ghoul", "Ghoul", ["DesertGhoul", "DesertGhoulCorruption", "DesertGhoulCrimson", "DesertGhoulHallow"]),
    (241, "Basilisk", "Basilisk", ["DesertBeast"]),
    (242, "Tomb Crawler", "Tomb_Crawler", ["TombCrawlerHead"]),
    (243, "Antlion", "Antlion", ["Antlion"]),
    (244, "Sand Poacher", "Sand_Poacher", ["DesertScorpionWalk", "DesertScorpionWall"]),
    (245, "Giant Antlion Swarmer", "Antlion_Swarmer", ["FlyingAntlion", "GiantFlyingAntlion"]),
    (246, "Antlion Charger", "Antlion_Charger", ["WalkingAntlion"]),
    (247, "Dune Splicer", "Dune_Splicer", ["DuneSplicerHead"]),
    (248, "Angry Tumbler", "Angry_Tumbler", ["AngryTumbler"]),
    (249, "Antlion Swarmer", "Antlion_Swarmer", ["FlyingAntlion"]),
    (250, "Sand Elemental", "Sand_Elemental", ["SandElemental"]),
    (251, "Sand Shark", "Sand_Shark", ["SandShark", "SandsharkCorrupt", "SandsharkCrimson", "SandsharkHallow"]),
    (252, "Crab", "Crab", ["Crab"]),
    (253, "Sea Snail", "Sea_Snail", ["SeaSnail"]),
    (254, "Shark", "Shark", ["Shark"]),
    (255, "Orca", "Orca", ["Orca"]),
    (256, "Squid", "Squid", ["Squid"]),
    (257, "Pink Jellyfish", "Pink_Jellyfish", ["PinkJellyfish"]),
    (258, "Jungle Slime", "Jungle_Slime", ["JungleSlime"]),
    (259, "Snatcher", "Snatcher", ["Snatcher"]),
    (260, "Giant Flying Fox", "Giant_Flying_Fox", ["GiantFlyingFox"]),
    (261, "Derpling", "Derpling", ["Derpling"]),
    (262, "Spiked Jungle Slime", "Spiked_Jungle_Slime", ["SpikedJungleSlime"]),
    (263, "Lac Beetle", "Lac_Beetle", ["LacBeetle"]),
    (264, "Doctor Bones", "Doctor_Bones", ["DoctorBones"]),
    (265, "Bee", "Bee", ["Bee"]),
    (266, "Bee (Larger)", "Bee", ["BeeSmall"]),
    (267, "Hornet (Stingy)", "Hornet", ["HornetStingy"]),
    (268, "Hornet (Spikey)", "Hornet", ["HornetSpikey"]),
    (269, "Hornet", "Hornet", ["Hornet"]),
    (270, "Hornet (Fatty)", "Hornet", ["HornetFatty"]),
    (271, "Hornet (Honey)", "Hornet", ["HornetHoney"]),
    (272, "Hornet (Leafy)", "Hornet", ["HornetLeafy"]),
    (273, "Moss Hornet", "Moss_Hornet", ["MossHornet"]),
    (274, "Moth", "Moth", ["Moth"]),
    (275, "Man Eater", "Man_Eater", ["ManEater"]),
    (276, "Angry Trapper", "Angry_Trapper", ["AngryTrapper"]),
    (277, "Jungle Bat", "Jungle_Bat", ["JungleBat"]),
    (278, "Piranha", "Piranha", ["Piranha"]),
    (279, "Angler Fish", "Angler_Fish", ["AnglerFish"]),
    (280, "Arapaima", "Arapaima", ["Arapaima"]),
    (281, "Giant Tortoise", "Giant_Tortoise", ["GiantTortoise"]),
    (282, "Jungle Creeper", "Jungle_Creeper", ["JungleCreeper", "JungleCreeperWall"]),
    (283, "Meteor Head", "Meteor_Head", ["MeteorHead"]),
    (284, "Dungeon Slime", "Dungeon_Slime", ["DungeonSlime"]),
    (285, "Angry Bones", "Angry_Bones", ["AngryBones"]),
    (286, "Angry Bones (Big)", "Angry_Bones", ["AngryBonesBig"]),
    (287, "Angry Bones (Big Muscle)", "Angry_Bones", ["AngryBonesBigMuscle"]),
    (288, "Angry Bones (Big Helmet)", "Angry_Bones", ["AngryBonesBigHelmet"]),
    (289, "Blue Armored Bones (Mace)", "Blue_Armored_Bones", ["BlueArmoredBones"]),
    (290, "Skeleton Sniper", "Skeleton_Sniper", ["SkeletonSniper"]),
    (291, "Tactical Skeleton", "Tactical_Skeleton", ["TacticalSkeleton"]),
    (292, "Skeleton Commando", "Skeleton_Commando", ["SkeletonCommando"]),
    (293, "Hell Armored Bones", "Hell_Armored_Bones", ["HellArmoredBones"]),
    (294, "Rusty Armored Bones (Sword No Armor)", "Rusty_Armored_Bones", ["RustyArmoredBonesAxe"]),
    (295, "Rusty Armored Bones (Flail)", "Rusty_Armored_Bones", ["RustyArmoredBonesFlail"]),
    (296, "Hell Armored Bones (Mace)", "Hell_Armored_Bones", ["HellArmoredBonesMace"]),
    (297, "Blue Armored Bones", "Blue_Armored_Bones", ["BlueArmoredBonesMace"]),
    (298, "Rusty Armored Bones (Sword)", "Rusty_Armored_Bones", ["RustyArmoredBonesSword"]),
    (299, "Hell Armored Bones (Spike Shield)", "Hell_Armored_Bones", ["HellArmoredBonesSpikeShield"]),
    (300, "Blue Armored Bones (No Pants)", "Blue_Armored_Bones", ["BlueArmoredBonesNoPants"]),
    (301, "Hell Armored Bones (Sword)", "Hell_Armored_Bones", ["HellArmoredBonesSword"]),
    (302, "Rusty Armored Bones (Axe)", "Rusty_Armored_Bones", ["RustyArmoredBonesAxe"]),
    (303, "Blue Armored Bones (Sword)", "Blue_Armored_Bones", ["BlueArmoredBonesSword"]),
    (304, "Bone Lee", "Bone_Lee", ["BoneLee"]),
    (305, "Paladin", "Paladin", ["Paladin"]),
    (306, "Dark Caster", "Dark_Caster", ["DarkCaster"]),
    (307, "Librarian Skeleton", "Angry_Bones", ["LibrarianSkeleton"]),
    (308, "Diabolist (Red)", "Diabolist", ["DiabolistRed"]),
    (309, "Diabolist (White)", "Diabolist", ["DiabolistWhite"]),
    (310, "Necromancer", "Necromancer", ["Necromancer"]),
    (311, "Ragged Caster", "Ragged_Caster", ["RaggedCaster"]),
    (312, "Necromancer (Armored)", "Necromancer", ["NecromancerArmored"]),
    (313, "Ragged Caster (Open Coat)", "Ragged_Caster", ["RaggedCasterOpenCoat"]),
    (314, "Water Bolt Mimic", "Dungeon_Slime", ["WaterBoltMimic"]),
    (315, "Cursed Skull", "Cursed_Skull", ["CursedSkull"]),
    (316, "Giant Cursed Skull", "Giant_Cursed_Skull", ["GiantCursedSkull"]),
    (317, "Dungeon Guardian", "Dungeon_Guardian", ["DungeonGuardian"]),
    (318, "Dungeon Spirit", "Dungeon_Spirit", ["DungeonSpirit"]),
    (319, "Lava Slime", "Lava_Slime", ["LavaSlime"]),
    (320, "Tortured Soul", "Tortured_Soul", ["TorturedSoul"]),
    (321, "Bone Serpent", "Bone_Serpent", ["BoneSerpentHead"]),
    (322, "Fire Imp", "Fire_Imp", ["FireImp"]),
    (323, "Hellbat", "Hellbat", ["Hellbat"]),
    (324, "Demon", "Demon", ["Demon"]),
    (325, "Voodoo Demon", "Voodoo_Demon", ["VoodooDemon"]),
    (326, "Lava Bat", "Lava_Bat", ["Lavabat"]),
    (327, "Red Devil", "Red_Devil", ["RedDevil"]),
    (328, "Wyvern", "Wyvern", ["WyvernHead"]),
    (329, "Harpy", "Harpy", ["Harpy"]),
    (330, "Martian Probe", "Martian_Probe", ["MartianProbe"]),
    (331, "Slimeling", "Slimeling", ["Slimeling"]),
    (332, "Corrupt Slime", "Corrupt_Slime", ["CorruptSlime"]),
    (333, "Eater of Souls", "Eater_of_Souls", ["EaterofSouls"]),
    (334, "Corruptor", "Corruptor", ["Corruptor"]),
    (335, "Devourer", "Devourer", ["DevourerHead"]),
    (336, "World Feeder", "World_Feeder", ["SeekerHead"]),
    (337, "Clinger", "Clinger", ["Clinger"]),
    (338, "Slimer", "Slimer", ["Slimer", "Slimer2"]),
    (339, "Cursed Hammer", "Cursed_Hammer", ["CursedHammer"]),
    (340, "Corrupt Mimic", "Corrupt_Mimic", ["BigMimicCorruption"]),
    (341, "Pigron (Corrupt)", "Pigron", ["PigronCorruption"]),
    (342, "Bone Biter", "Bone_Biter", ["DesertDjinn"]),
    (343, "Dark Mummy", "Dark_Mummy", ["DarkMummy"]),
    (344, "Vile Ghoul", "Ghoul", ["DesertGhoulCorruption"]),
    (345, "Crimslime", "Crimslime", ["Crimslime"]),
    (346, "Face Monster", "Face_Monster", ["FaceMonster"]),
    (347, "Crimera", "Crimera", ["Crimera"]),
    (348, "Blood Feeder", "Blood_Feeder", ["BloodFeeder"]),
    (349, "Blood Jelly", "Blood_Jelly", ["BloodJelly"]),
    (350, "Floaty Gross", "Floaty_Gross", ["FloatyGross"]),
    (351, "Ichor Sticker", "Ichor_Sticker", ["IchorSticker"]),
    (352, "Crimson Axe", "Crimson_Axe", ["CrimsonAxe"]),
    (353, "Blood Crawler", "Blood_Crawler", ["BloodCrawler", "BloodCrawlerWall"]),
    (354, "Herpling", "Herpling", ["Herpling"]),
    (355, "Crimson Mimic", "Crimson_Mimic", ["BigMimicCrimson"]),
    (356, "Pigron (Crimson)", "Pigron", ["PigronCrimson"]),
    (357, "Flesh Reaver", "Flesh_Reaver", ["DesertDjinn"]),
    (358, "Blood Mummy", "Blood_Mummy", ["BloodMummy"]),
    (359, "Tainted Ghoul", "Ghoul", ["DesertGhoulCrimson"]),
    (360, "Lamia", "Lamia", ["DesertLamiaDark"]),
    (361, "Desert Spirit", "Desert_Spirit", ["DesertDjinn"]),
    (362, "Rainbow Slime", "Rainbow_Slime", ["RainbowSlime", "GoldenSlime"]),
    (363, "Pixie", "Pixie", ["Pixie"]),
    (364, "Gastropod", "Gastropod", ["Gastropod"]),
    (365, "Unicorn", "Unicorn", ["Unicorn"]),
    (366, "Illuminant Slime", "Illuminant_Slime", ["IlluminantSlime"]),
    (367, "Chaos Elemental", "Chaos_Elemental", ["ChaosElemental"]),
    (368, "Illuminant Bat", "Illuminant_Bat", ["IlluminantBat"]),
    (369, "Enchanted Sword", "Enchanted_Sword_(NPC)", ["EnchantedSword"]),
    (370, "Hallowed Mimic", "Hallowed_Mimic", ["BigMimicHallow", "BigMimicJungle"]),
    (371, "Pigron", "Pigron", ["PigronHallow"]),
    (372, "Crystal Thresher", "Crystal_Thresher", ["DesertBeast"]),
    (373, "Light Mummy", "Light_Mummy", ["LightMummy"]),
    (374, "Dreamer Ghoul", "Ghoul", ["DesertGhoulHallow"]),
    (375, "Lamia (Light)", "Lamia", ["DesertLamiaLight"]),
    (376, "Spore Zombie (Mushroom)", "Spore_Zombie", ["ZombieMushroomHat"]),
    (377, "Spore Zombie (Hat Mushroom)", "Spore_Zombie", ["ZombieMushroom"]),
    (378, "Anomura Fungus", "Anomura_Fungus", ["AnomuraFungus"]),
    (379, "Mushi Ladybug", "Mushi_Ladybug", ["MushiLadybug"]),
    (380, "Fungi Bulb", "Fungi_Bulb", ["FungiBulb"]),
    (381, "Giant Fungi Bulb", "Giant_Fungi_Bulb", ["GiantFungiBulb"]),
    (382, "Fungo Fish", "Fungo_Fish", ["FungoFish"]),
    (383, "Lihzahrd", "Lihzahrd", ["Lihzahrd", "LihzahrdCrawler"]),
    (384, "Flying Snake", "Flying_Snake", ["FlyingSnake"]),
    (385, "Goblin Peon", "Goblin_Peon", ["GoblinPeon"]),
    (386, "Goblin Thief", "Goblin_Thief", ["GoblinThief"]),
    (387, "Goblin Archer", "Goblin_Archer", ["GoblinArcher"]),
    (388, "Goblin Warrior", "Goblin_Warrior", ["GoblinWarrior"]),
    (389, "Goblin Warlock", "Goblin_Summoner", ["GoblinSummoner"]),
    (390, "Goblin Sorcerer", "Goblin_Sorcerer", ["GoblinSorcerer"]),
    (391, "Shadowflame Apparition", "Shadowflame_Apparition", ["ShadowFlameApparition"]),
    (392, "Old One's Skeleton", "Old_One%27s_Skeleton", ["DD2SkeletonT1"]),
    (393, "Etherian Goblin", "Etherian_Goblin", ["DD2GoblinT1"]),
    (394, "Etherian Goblin Bomber", "Etherian_Goblin_Bomber", ["DD2GoblinBomberT1"]),
    (395, "Kobold", "Kobold", ["DD2KoboldWalkerT2"]),
    (396, "Etherian Javelin Thrower", "Etherian_Javelin_Thrower", ["DD2JavelinstT1"]),
    (397, "Wither Beast", "Wither_Beast", ["DD2WitherBeastT2"]),
    (398, "Drakin", "Drakin", ["DD2DrakinT2"]),
    (399, "Ogre", "Ogre", ["DD2OgreT2"]),
    (400, "Kobold Glider", "Kobold_Glider", ["DD2KoboldFlyerT2"]),
    (401, "Etherian Wyvern", "Etherian_Wyvern", ["DD2WyvernT1"]),
    (402, "Dark Mage", "Dark_Mage", ["DD2DarkMageT1"]),
    (403, "Betsy", "Betsy", ["DD2Betsy"]),
    (404, "Etherian Lightning Bug", "Etherian_Lightning_Bug", ["DD2LightningBugT3"]),
    (405, "Pirate Deadeye", "Pirate_Deadeye", ["PirateDeadeye"]),
    (406, "Pirate Deckhand", "Pirate_Deckhand", ["PirateDeckhand"]),
    (407, "Pirate Crossbower", "Pirate_Crossbower", ["PirateCrossbower"]),
    (408, "Pirate Corsair", "Pirate_Corsair", ["PirateCorsair"]),
    (409, "Pirate Captain", "Pirate_Captain", ["PirateCaptain"]),
    (410, "Parrot", "Parrot", ["Parrot"]),
    (411, "Flying Dutchman", "Flying_Dutchman", ["FlyingDutchman"]),
    (412, "Brain Scrambler", "Brain_Scrambler", ["BrainScrambler"]),
    (413, "Ray Gunner", "Ray_Gunner", ["RayGunner"]),
    (414, "Martian Engineer", "Martian_Engineer", ["MartianEngineer"]),
    (415, "Martian Officer", "Martian_Officer", ["MartianOfficer"]),
    (416, "Gigazapper", "Gigazapper", ["Gigazapper"]),
    (417, "Scutlix", "Scutlix", ["Scutlix"]),
    (418, "Gray Grunt", "Gray_Grunt", ["GrayGrunt"]),
    (419, "Martian Walker", "Martian_Walker", ["MartianWalker"]),
    (420, "Tesla Turret", "Tesla_Turret", ["MartianTurret"]),
    (421, "Martian Drone", "Martian_Drone", ["MartianDrone"]),
    (422, "Scutlix Gunner", "Scutlix_Gunner", ["ScutlixRider"]),
    (423, "Martian Saucer", "Martian_Saucer", ["MartianSaucer", "MartianSaucerCore"]),
    (424, "Fritz", "Fritz", ["Fritz"]),
    (425, "Frankenstein", "Frankenstein", ["Frankenstein"]),
    (426, "Creature from the Deep", "Creature_from_the_Deep", ["CreatureFromTheDeep"]),
    (427, "Swamp Thing", "Swamp_Thing", ["SwampThing"]),
    (428, "Dr. Man Fly", "Dr._Man_Fly", ["DrManFly"]),
    (429, "The Possessed", "The_Possessed", ["ThePossessed"]),
    (430, "Psycho", "Psycho", ["Psycho"]),
    (431, "Butcher", "Butcher", ["Butcher"]),
    (432, "Vampire", "Vampire", ["Vampire"]),
    (433, "Eyezor", "Eyezor", ["Eyezor"]),
    (434, "Nailhead", "Nailhead", ["Nailhead"]),
    (435, "Reaper", "Reaper", ["Reaper"]),
    (436, "Deadly Sphere", "Deadly_Sphere", ["DeadlySphere"]),
    (437, "Mothron", "Mothron", ["Mothron"]),
    (438, "Baby Mothron", "Mothron", ["MothronEgg", "MothronSpawn"]),
    (439, "Scarecrow (Cloth Face Stick)", "Scarecrow", ["Scarecrow1"]),
    (440, "Scarecrow (Cloth Face)", "Scarecrow", ["Scarecrow2"]),
    (441, "Scarecrow (Guy Fawkes Stick)", "Scarecrow", ["Scarecrow3"]),
    (442, "Scarecrow (Guy Fawkes)", "Scarecrow", ["Scarecrow4"]),
    (443, "Scarecrow (Cloth Hat Stick)", "Scarecrow", ["Scarecrow5"]),
    (444, "Scarecrow (Cloth Hat)", "Scarecrow", ["Scarecrow6"]),
    (445, "Scarecrow (Pumpkin Hat Stick)", "Scarecrow", ["Scarecrow7"]),
    (446, "Scarecrow (Pumpkin Hat)", "Scarecrow", ["Scarecrow8"]),
    (447, "Scarecrow (Pumpkin Head Stick)", "Scarecrow", ["Scarecrow9"]),
    (448, "Scarecrow (Pumpkin Head)", "Scarecrow", ["Scarecrow10"]),
    (449, "Splinterling", "Splinterling", ["Splinterling"]),
    (450, "Poltergeist", "Poltergeist", ["Poltergeist"]),
    (451, "Hellhound", "Hellhound", ["Hellhound"]),
    (452, "Headless Horseman", "Headless_Horseman", ["HeadlessHorseman"]),
    (453, "Mourning Wood", "Mourning_Wood", ["MourningWood"]),
    (454, "Pumpking", "Pumpking", ["Pumpking"]),
    (455, "Zombie Elf (Girl)", "Zombie_Elf", ["ZombieElfGirl"]),
    (456, "Zombie Elf", "Zombie_Elf", ["ZombieElf"]),
    (457, "Zombie Elf (Beard)", "Zombie_Elf", ["ZombieElfBeard"]),
    (458, "Gingerbread Man", "Gingerbread_Man", ["GingerbreadMan"]),
    (459, "Elf Archer", "Elf_Archer", ["ElfArcher"]),
    (460, "Nutcracker", "Nutcracker", ["Nutcracker"]),
    (461, "Krampus", "Krampus", ["Krampus"]),
    (462, "Yeti", "Yeti", ["Yeti"]),
    (463, "Present Mimic", "Present_Mimic", ["PresentMimic"]),
    (464, "Everscream", "Everscream", ["Everscream"]),
    (465, "Ice Queen", "Ice_Queen", ["IceQueen"]),
    (466, "Santa-NK1", "Santa-NK1", ["SantaNK1"]),
    (467, "Flocko", "Flocko", ["Flocko"]),
    (468, "Elf Copter", "Elf_Copter", ["ElfCopter"]),
    # ── Bosses ──
    (469, "King Slime", "King_Slime", ["KingSlime"]),
    (470, "Spiked Slime", "King_Slime", ["SlimeSpiked"]),
    (471, "Eye of Cthulhu", "Eye_of_Cthulhu", ["EyeofCthulhu"]),
    (472, "Servant of Cthulhu", "Servant_of_Cthulhu", ["ServantofCthulhu"]),
    (473, "Eater of Worlds (Head)", "Eater_of_Worlds", ["EaterofWorldsHead"]),
    (474, "Eater of Worlds (Body)", "Eater_of_Worlds", ["EaterofWorldsBody"]),
    (475, "Eater of Worlds (Tail)", "Eater_of_Worlds", ["EaterofWorldsTail"]),
    (476, "Brain of Cthulhu", "Brain_of_Cthulhu", ["BrainofCthulhu"]),
    (477, "Creeper", "Creeper_(enemy)", ["Creeper"]),
    (478, "Queen Bee", "Queen_Bee", ["QueenBee"]),
    (479, "Skeletron", "Skeletron", ["SkeletronHead"]),
    (480, "Skeletron Hand", "Skeletron", ["SkeletronHand"]),
    (481, "Deerclops", "Deerclops", ["Deerclops"]),
    (482, "Wall of Flesh", "Wall_of_Flesh", ["WallofFlesh", "WallofFleshEye"]),
    (483, "The Hungry", "The_Hungry", ["TheHungry"]),
    (484, "The Hungry II", "The_Hungry_II", ["TheHungryII"]),
    (485, "Leech", "Leech", ["LeechHead"]),
    (486, "Queen Slime", "Queen_Slime", ["QueenSlimeBoss"]),
    (487, "Crystal Slime", "Queen_Slime", ["QueenSlimeMinionBlue"]),
    (488, "Heavenly Slime", "Queen_Slime", ["QueenSlimeMinionPink"]),
    (489, "Bouncy Slime", "Queen_Slime", ["QueenSlimeMinionPurple"]),
    (490, "Retinazer", "Retinazer", ["Retinazer"]),
    (491, "Spazmatism", "Spazmatism", ["Spazmatism"]),
    (492, "The Destroyer", "The_Destroyer", ["TheDestroyer", "TheDestroyerBody", "TheDestroyerTail"]),
    (493, "Probe", "Probe", ["Probe"]),
    (494, "Skeletron Prime", "Skeletron_Prime", ["SkeletronPrime"]),
    (495, "Prime Cannon", "Skeletron_Prime", ["PrimeCannon"]),
    (496, "Prime Saw", "Skeletron_Prime", ["PrimeSaw"]),
    (497, "Prime Vice", "Skeletron_Prime", ["PrimeVice"]),
    (498, "Prime Laser", "Skeletron_Prime", ["PrimeLaser"]),
    (499, "Plantera", "Plantera", ["Plantera"]),
    (500, "Plantera's Tentacle", "Plantera", ["PlanterasTentacle"]),
    (501, "Plantera's Hook", "Plantera", ["PlanterasHook"]),
    (502, "Spore", "Plantera", ["Spore"]),
    (503, "Empress of Light", "Empress_of_Light", ["HallowBoss"]),
    (504, "Golem", "Golem", ["Golem"]),
    (505, "Golem Fist", "Golem", ["GolemFistLeft", "GolemFistRight"]),
    (506, "Golem Head", "Golem", ["GolemHead", "GolemHeadFree"]),
    (507, "Duke Fishron", "Duke_Fishron", ["DukeFishron"]),
    (508, "Sharkron", "Duke_Fishron", ["Sharkron", "Sharkron2"]),
    (509, "Sharknado", "Duke_Fishron", ["Sharknado"]),
    (510, "Lunatic Cultist", "Lunatic_Cultist", ["CultistBoss"]),
    (511, "Ancient Doom", "Ancient_Doom", ["CultistBossClone"]),
    (512, "Phantasm Dragon", "Phantasm_Dragon", ["CultistDragonHead"]),
    (513, "Ancient Vision", "Ancient_Vision", ["AncientCultistSquidhead"]),
    # ── Lunar Event ──
    (514, "Solar Pillar", "Solar_Pillar", ["LunarTowerSolar"]),
    (515, "Crawltipede", "Crawltipede", ["SolarCrawltipedeHead"]),
    (516, "Drakomire", "Drakomire", ["SolarDrakomire"]),
    (517, "Drakomire Rider", "Drakomire_Rider", ["SolarDrakomireRider"]),
    (518, "Selenian", "Selenian", ["SolarSolenian"]),
    (519, "Corite", "Corite", ["SolarCorite"]),
    (520, "Sroller", "Sroller", ["SolarSroller"]),
    (521, "Nebula Pillar", "Nebula_Pillar", ["LunarTowerNebula"]),
    (522, "Nebula Floater", "Nebula_Floater", ["NebulaSoldier"]),
    (523, "Brain Suckler", "Brain_Suckler", ["NebulaBrain"]),
    (524, "Predictor", "Predictor", ["NebulaHeadcrab"]),
    (525, "Evolution Beast", "Evolution_Beast", ["NebulaBeast"]),
    (526, "Stardust Pillar", "Stardust_Pillar", ["LunarTowerStardust"]),
    (527, "Milkyway Weaver", "Milkyway_Weaver", ["StardustWormHead"]),
    (528, "Star Cell", "Star_Cell", ["StardustCellBig"]),
    (529, "Flow Invader", "Flow_Invader", ["StardustJellyfishBig"]),
    (530, "Twinkle Popper", "Twinkle_Popper", ["StardustSpiderBig"]),
    (531, "Twinkle", "Twinkle", ["StardustSpiderSmall"]),
    (532, "Vortex Pillar", "Vortex_Pillar", ["LunarTowerVortex"]),
    (533, "Storm Diver", "Storm_Diver", ["VortexSoldier"]),
    (534, "Alien Hornet", "Alien_Hornet", ["VortexHornet", "VortexHornetQueen"]),
    (535, "Alien Queen", "Alien_Queen", ["VortexHornetQueen"]),
    (536, "Alien Larva", "Alien_Larva", ["VortexLarva"]),
    # ── Moon Lord ──
    (537, "Moon Lord", "Moon_Lord", ["MoonLordHead", "MoonLordHand", "MoonLordCore"]),
    (538, "Moon Lord's Hand", "Moon_Lord", ["MoonLordHand"]),
    (539, "Moon Lord's Head", "Moon_Lord", ["MoonLordHead"]),
    (540, "True Eye of Cthulhu", "Moon_Lord", ["MoonLordFreeEye"]),
    (541, "Moon Lord Core", "Moon_Lord", ["MoonLordCore"]),
    # ── Special / Late additions ──
    (542, "Torch God", "Torch_God", ["TorchGod"]),
    (543, "Zombie (Armed)", "Zombie", ["ArmedZombie", "ArmedZombiePincushion", "ArmedZombieTwiggy", "ArmedZombieSwamp", "ArmedZombieCenx"]),
    (544, "Zombie (Eskimo)", "Zombie", ["ArmedZombieEskimo", "ZombieEskimo"]),
    (545, "Blood Nautilus", "Dreadnautilus", ["BloodNautilus"]),
    (546, "Vile Spit", "Eater_of_Worlds", ["VileSpit"]),
]


def read_world_bestiary(wld_path):
    """Parse a Terraria world file and extract bestiary data."""
    try:
        with open(wld_path, "rb") as f:
            version = struct.unpack("<i", f.read(4))[0]
            if version < 194:
                return None

            f.read(7)  # magic
            struct.unpack("<b", f.read(1))  # file_type
            struct.unpack("<I", f.read(4))  # revision
            struct.unpack("<Q", f.read(8))  # favorites

            num_sections = struct.unpack("<h", f.read(2))[0]
            sections = [struct.unpack("<i", f.read(4))[0] for _ in range(num_sections)]

            # Read world name from header section
            num_tile_types = struct.unpack("<h", f.read(2))[0]
            for _ in range(num_tile_types):
                f.read(1)

            f.seek(sections[0])

            def read_string():
                length = 0
                shift = 0
                while True:
                    byte = ord(f.read(1))
                    length |= (byte & 0x7F) << shift
                    if byte < 0x80:
                        break
                    shift += 7
                return f.read(length).decode("utf-8", errors="replace")

            world_name = read_string()

            if num_sections <= 8:
                return {"name": world_name, "kills": {}, "sights": set(), "chats": set()}

            # Seek to bestiary section
            f.seek(sections[8])

            # Kill counts
            kill_count = struct.unpack("<i", f.read(4))[0]
            kills = {}
            for _ in range(kill_count):
                name = read_string()
                count = struct.unpack("<i", f.read(4))[0]
                kills[name] = count

            # Sightings (was near player)
            sight_count = struct.unpack("<i", f.read(4))[0]
            sights = set()
            for _ in range(sight_count):
                sights.add(read_string())

            # Chats (was chatted with)
            chat_count = struct.unpack("<i", f.read(4))[0]
            chats = set()
            for _ in range(chat_count):
                chats.add(read_string())

            return {"name": world_name, "kills": kills, "sights": sights, "chats": chats}
    except Exception as e:
        print(f"  Error reading {wld_path}: {e}")
        return None


def scan_worlds():
    """Scan all known directories for Terraria world files and extract bestiary data."""
    worlds = {}
    world_dirs = _find_world_dirs()

    if not world_dirs:
        print("No Terraria world directories found!")
        return worlds

    seen_paths = set()
    for source_label, dir_path in world_dirs:
        print(f"\n  [{source_label}] {dir_path}")
        try:
            for fname in sorted(os.listdir(dir_path)):
                if fname.endswith(".wld"):
                    path = os.path.join(dir_path, fname)
                    real = os.path.realpath(path)
                    if real in seen_paths:
                        continue
                    seen_paths.add(real)

                    print(f"    Reading {fname}...")
                    result = read_world_bestiary(path)
                    if result:
                        # Use a unique key combining source and filename to avoid collisions
                        key = f"{source_label}|{fname}"
                        result["source"] = source_label
                        worlds[key] = result
                        print(f"      {result['name']}: {len(result['kills'])} kills, {len(result['sights'])} sights, {len(result['chats'])} chats")
        except OSError as e:
            print(f"    Error scanning directory: {e}")

    return worlds


def build_bestiary_json(worlds):
    """Build JSON data for the web frontend."""
    # Build internal name -> entry number mapping
    internal_to_entry = {}
    for num, display, wiki, internals in BESTIARY:
        for iname in internals:
            if iname not in internal_to_entry:
                internal_to_entry[iname] = num

    # Build world data
    world_data = {}
    for fname, wdata in worlds.items():
        encountered = set()
        # Map internal names to entry numbers
        all_internal = set(wdata["kills"].keys()) | wdata["sights"] | wdata["chats"]
        for iname in all_internal:
            if iname in internal_to_entry:
                encountered.add(internal_to_entry[iname])

        world_data[fname] = {
            "name": wdata["name"],
            "source": wdata.get("source", "Local"),
            "encountered": sorted(encountered),
            "kill_count": len(wdata["kills"]),
            "sight_count": len(wdata["sights"]),
            "chat_count": len(wdata["chats"]),
        }

    # Build entry list
    entries = []
    for num, display, wiki, internals in BESTIARY:
        entries.append({
            "num": num,
            "name": display,
            "wiki": f"https://terraria.wiki.gg/wiki/{wiki}",
        })

    return {"worlds": world_data, "entries": entries, "total": len(BESTIARY)}


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Terraria Bestiary Tracker</title>
<style>
  :root {
    --bg: #1a1a2e;
    --surface: #16213e;
    --surface2: #0f3460;
    --accent: #e94560;
    --accent2: #533483;
    --text: #eee;
    --text-dim: #aaa;
    --found: #2d6a4f;
    --missing: #6a2d2d;
    --link: #7ec8e3;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }
  header {
    background: var(--surface);
    border-bottom: 3px solid var(--accent);
    padding: 1rem 2rem;
    display: flex;
    align-items: center;
    gap: 1.5rem;
    flex-wrap: wrap;
  }
  header h1 {
    font-size: 1.5rem;
    color: var(--accent);
    white-space: nowrap;
  }
  .controls {
    display: flex;
    gap: 1rem;
    align-items: center;
    flex-wrap: wrap;
    flex: 1;
  }
  select, input[type="text"] {
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--accent2);
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    font-size: 0.95rem;
    outline: none;
  }
  select:focus, input:focus { border-color: var(--accent); }
  select { min-width: 220px; }
  input[type="text"] { min-width: 200px; }
  .filter-btns { display: flex; gap: 0.5rem; }
  .filter-btns button {
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--accent2);
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    transition: all 0.15s;
  }
  .filter-btns button:hover { border-color: var(--accent); }
  .filter-btns button.active {
    background: var(--accent);
    border-color: var(--accent);
    color: white;
  }
  .stats {
    background: var(--surface);
    padding: 0.75rem 2rem;
    display: flex;
    gap: 2rem;
    font-size: 0.95rem;
    border-bottom: 1px solid var(--accent2);
  }
  .stats .stat { display: flex; gap: 0.4rem; align-items: center; }
  .stats .stat-val { color: var(--accent); font-weight: 700; font-size: 1.1rem; }
  .progress-bar {
    flex: 1;
    max-width: 300px;
    height: 20px;
    background: var(--surface2);
    border-radius: 10px;
    overflow: hidden;
    position: relative;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent2), var(--accent));
    border-radius: 10px;
    transition: width 0.4s ease;
  }
  .progress-text {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 0.5rem;
    padding: 1rem 2rem 2rem;
  }
  .entry {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 0.8rem;
    border-radius: 8px;
    border: 1px solid transparent;
    transition: all 0.15s;
  }
  .entry:hover { border-color: var(--accent2); }
  .entry.found {
    background: var(--found);
    opacity: 0.7;
  }
  .entry.missing {
    background: var(--missing);
  }
  .entry-num {
    color: var(--text-dim);
    font-size: 0.8rem;
    min-width: 28px;
    text-align: right;
  }
  .entry-name { flex: 1; }
  .entry-name a {
    color: var(--link);
    text-decoration: none;
    font-size: 0.95rem;
  }
  .entry-name a:hover { text-decoration: underline; color: white; }
  .entry-status {
    font-size: 0.75rem;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-weight: 600;
  }
  .entry.found .entry-status { color: #a3d9a5; }
  .entry.missing .entry-status { color: #f5a5a5; }
  .no-world {
    text-align: center;
    padding: 4rem 2rem;
    color: var(--text-dim);
    font-size: 1.1rem;
  }
  @media (max-width: 600px) {
    header { padding: 0.75rem 1rem; }
    .grid { padding: 0.75rem 1rem; grid-template-columns: 1fr; }
    .stats { padding: 0.5rem 1rem; flex-wrap: wrap; }
  }
</style>
</head>
<body>

<header>
  <h1>Terraria Bestiary Tracker</h1>
  <div class="controls">
    <select id="worldSelect">
      <option value="">-- Select a World --</option>
    </select>
    <input type="text" id="search" placeholder="Search entries...">
    <div class="filter-btns">
      <button id="btnAll" class="active" onclick="setFilter('all')">All</button>
      <button id="btnMissing" onclick="setFilter('missing')">Missing</button>
      <button id="btnFound" onclick="setFilter('found')">Found</button>
    </div>
  </div>
</header>

<div class="stats" id="statsBar" style="display:none">
  <div class="stat">Found: <span class="stat-val" id="statFound">0</span></div>
  <div class="stat">Missing: <span class="stat-val" id="statMissing">0</span></div>
  <div class="progress-bar">
    <div class="progress-fill" id="progressFill" style="width:0%"></div>
    <div class="progress-text" id="progressText">0%</div>
  </div>
</div>

<div id="content">
  <div class="no-world">Select a world above to see your bestiary progress.</div>
</div>

<script>
const DATA = __DATA_PLACEHOLDER__;

const worldSelect = document.getElementById('worldSelect');
const searchInput = document.getElementById('search');
const content = document.getElementById('content');
const statsBar = document.getElementById('statsBar');

let currentFilter = 'all';
let currentWorld = null;

// Populate world selector
Object.keys(DATA.worlds).forEach(fname => {
  const w = DATA.worlds[fname];
  const opt = document.createElement('option');
  opt.value = fname;
  opt.textContent = w.name + ' [' + w.source + '] (' + w.encountered.length + '/' + DATA.total + ')';
  worldSelect.appendChild(opt);
});

worldSelect.addEventListener('change', () => {
  currentWorld = worldSelect.value ? DATA.worlds[worldSelect.value] : null;
  render();
});

searchInput.addEventListener('input', () => render());

function setFilter(f) {
  currentFilter = f;
  document.querySelectorAll('.filter-btns button').forEach(b => b.classList.remove('active'));
  document.getElementById('btn' + f.charAt(0).toUpperCase() + f.slice(1)).classList.add('active');
  render();
}

function render() {
  if (!currentWorld) {
    content.innerHTML = '<div class="no-world">Select a world above to see your bestiary progress.</div>';
    statsBar.style.display = 'none';
    return;
  }

  const encountered = new Set(currentWorld.encountered);
  const search = searchInput.value.toLowerCase();
  const foundCount = encountered.size;
  const missingCount = DATA.total - foundCount;
  const pct = ((foundCount / DATA.total) * 100).toFixed(1);

  document.getElementById('statFound').textContent = foundCount;
  document.getElementById('statMissing').textContent = missingCount;
  document.getElementById('progressFill').style.width = pct + '%';
  document.getElementById('progressText').textContent = pct + '%';
  statsBar.style.display = 'flex';

  let html = '<div class="grid">';
  let visibleCount = 0;

  DATA.entries.forEach(entry => {
    const isFound = encountered.has(entry.num);
    if (currentFilter === 'missing' && isFound) return;
    if (currentFilter === 'found' && !isFound) return;
    if (search && !entry.name.toLowerCase().includes(search) && !String(entry.num).includes(search)) return;

    visibleCount++;
    const cls = isFound ? 'found' : 'missing';
    const status = isFound ? 'FOUND' : 'MISSING';
    html += '<div class="entry ' + cls + '">' +
      '<span class="entry-num">#' + entry.num + '</span>' +
      '<span class="entry-name"><a href="' + entry.wiki + '" target="_blank" rel="noopener">' +
      escapeHtml(entry.name) + '</a></span>' +
      '<span class="entry-status">' + status + '</span>' +
      '</div>';
  });

  if (visibleCount === 0) {
    html += '<div class="no-world">No entries match your filter.</div>';
  }

  html += '</div>';
  content.innerHTML = html;
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
</script>
</body>
</html>"""


class BestiaryHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, data_json, *args, **kwargs):
        self.data_json = data_json
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            page = HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", self.data_json)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logging


def main():
    print("Terraria Bestiary Tracker")
    print("=" * 40)
    world_dirs = _find_world_dirs()
    print(f"Scanning {len(world_dirs)} location(s) for worlds...")
    worlds = scan_worlds()

    if not worlds:
        print("\nNo world files found! Make sure Terraria is installed and you have world saves.")
        sys.exit(1)

    print(f"\nFound {len(worlds)} world(s)")
    data = build_bestiary_json(worlds)
    data_json = json.dumps(data)

    def handler(*args, **kwargs):
        BestiaryHandler(data_json, *args, **kwargs)

    server = http.server.HTTPServer(("127.0.0.1", PORT), handler)
    print(f"\nServer running at http://localhost:{PORT}")
    print("Open this URL in your browser to view your bestiary progress.")
    print("Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
