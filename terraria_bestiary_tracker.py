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

# ── Complete bestiary entries ──
# (number, display_name, wiki_slug, internal_names, hardmode)
# hardmode: False = pre-hardmode / not applicable, True = hardmode-only
# Wiki URLs are constructed as: https://terraria.wiki.gg/wiki/{wiki_slug}
BESTIARY = [
    # ── Town NPCs ──
    (1, "Guide", "Guide", ["Guide"], False),
    (2, "Merchant", "Merchant", ["Merchant"], False),
    (3, "Nurse", "Nurse", ["Nurse"], False),
    (4, "Demolitionist", "Demolitionist", ["Demolitionist"], False),
    (5, "Angler", "Angler", ["Angler", "SleepingAngler"], False),
    (6, "Dryad", "Dryad", ["Dryad"], False),
    (7, "Arms Dealer", "Arms_Dealer", ["ArmsDealer"], False),
    (8, "Dye Trader", "Dye_Trader", ["DyeTrader"], False),
    (9, "Painter", "Painter", ["Painter"], False),
    (10, "Stylist", "Stylist", ["Stylist", "WebbedStylist"], False),
    (11, "Zoologist", "Zoologist", ["BestiaryGirl", "Zoologist"], False),
    (12, "Tavernkeep", "Tavernkeep", ["DD2Bartender", "Tavernkeep", "BartenderUnconscious"], False),
    (13, "Golfer", "Golfer", ["Golfer", "GolferRescue"], False),
    (14, "Goblin Tinkerer", "Goblin_Tinkerer", ["GoblinTinkerer", "BoundGoblin"], False),
    (15, "Witch Doctor", "Witch_Doctor", ["WitchDoctor"], False),
    (16, "Mechanic", "Mechanic", ["Mechanic", "BoundMechanic"], False),
    (17, "Clothier", "Clothier", ["Clothier"], False),
    (18, "Wizard", "Wizard", ["Wizard", "BoundWizard"], True),
    (19, "Steampunker", "Steampunker", ["Steampunker"], True),
    (20, "Pirate", "Pirate", ["Pirate"], True),
    (21, "Truffle", "Truffle", ["Truffle"], True),
    (22, "Tax Collector", "Tax_Collector", ["TaxCollector"], True),
    (23, "Cyborg", "Cyborg", ["Cyborg"], True),
    (24, "Party Girl", "Party_Girl", ["PartyGirl"], False),
    (25, "Princess", "Princess", ["Princess"], False),
    (26, "Santa Claus", "Santa_Claus", ["SantaClaus"], True),
    (27, "Town Cat", "Town_Cat", ["TownCat"], False),
    (28, "Town Dog", "Town_Dog", ["TownDog"], False),
    (29, "Town Bunny", "Town_Bunny", ["TownBunny"], False),
    (30, "Nerdy Slime", "Nerdy_Slime", ["TownSlimeBlue"], False),
    (31, "Cool Slime", "Cool_Slime", ["TownSlimeGreen"], False),
    (32, "Elder Slime", "Elder_Slime", ["TownSlimeOld"], False),
    (33, "Clumsy Slime", "Clumsy_Slime", ["TownSlimePurple"], False),
    (34, "Diva Slime", "Diva_Slime", ["TownSlimeRainbow"], False),
    (35, "Surly Slime", "Surly_Slime", ["TownSlimeRed"], False),
    (36, "Mystic Slime", "Mystic_Slime", ["TownSlimeYellow", "BoundTownSlimeYellow"], False),
    (37, "Squire Slime", "Squire_Slime", ["TownSlimeCopper"], False),
    (38, "Traveling Merchant", "Traveling_Merchant", ["TravellingMerchant"], False),
    (39, "Skeleton Merchant", "Skeleton_Merchant", ["SkeletonMerchant"], False),
    (40, "Old Man", "Old_Man", ["OldMan"], False),
    # ── Critters ──
    (41, "Mystic Frog", "Mystic_Frog", ["BoundTownSlimeYellow"], False),
    (42, "Bunny", "Bunny", ["Bunny"], False),
    (43, "Bunny (With a Hat)", "Bunny", ["PartyBunny"], False),
    (44, "Explosive Bunny", "Explosive_Bunny", ["ExplosiveBunny"], False),
    (45, "Bunny (Slime)", "Bunny", ["BunnySlimed"], False),
    (46, "Bunny (Xmas)", "Bunny", ["BunnyXmas"], False),
    (47, "Gold Bunny", "Gold_Bunny", ["GoldBunny", "GoldBird", "GoldGoldfish", "SquirrelGold", "GoldMouse", "GoldFrog", "GoldGrasshopper", "GoldButterfly", "GoldWorm", "GoldDragonfly", "GoldSeahorse", "GoldWaterStrider", "GoldLadybug"], False),
    (48, "Bird", "Bird", ["Bird"], False),
    (49, "Blue Jay", "Blue_Jay", ["BirdBlue"], False),
    (50, "Cardinal", "Cardinal", ["BirdRed"], False),
    (51, "Scarlet Macaw", "Scarlet_Macaw", ["ScarletMacaw"], False),
    (52, "Blue Macaw", "Blue_Macaw", ["BlueMacaw"], False),
    (53, "Toucan", "Toucan", ["Toucan"], False),
    (54, "Yellow Cockatiel", "Yellow_Cockatiel", ["YellowCockatiel"], False),
    (55, "Gray Cockatiel", "Gray_Cockatiel", ["GrayCockatiel"], False),
    (56, "Gold Bird", "Gold_Bird", ["GoldBunny", "GoldBird", "GoldGoldfish", "SquirrelGold", "GoldMouse", "GoldFrog", "GoldGrasshopper", "GoldButterfly", "GoldWorm", "GoldDragonfly", "GoldSeahorse", "GoldWaterStrider", "GoldLadybug"], False),
    (57, "Goldfish", "Goldfish", ["Goldfish"], False),
    (58, "Gold Goldfish", "Gold_Goldfish", ["GoldBunny", "GoldBird", "GoldGoldfish", "SquirrelGold", "GoldMouse", "GoldFrog", "GoldGrasshopper", "GoldButterfly", "GoldWorm", "GoldDragonfly", "GoldSeahorse", "GoldWaterStrider", "GoldLadybug"], False),
    (59, "Squirrel", "Squirrel", ["Squirrel"], False),
    (60, "Red Squirrel", "Red_Squirrel", ["SquirrelRed"], False),
    (61, "Gold Squirrel", "Gold_Squirrel", ["GoldBunny", "GoldBird", "GoldGoldfish", "SquirrelGold", "GoldMouse", "GoldFrog", "GoldGrasshopper", "GoldButterfly", "GoldWorm", "GoldDragonfly", "GoldSeahorse", "GoldWaterStrider", "GoldLadybug"], False),
    (62, "Mouse", "Mouse", ["Mouse"], False),
    (63, "Gold Mouse", "Gold_Mouse", ["GoldBunny", "GoldBird", "GoldGoldfish", "SquirrelGold", "GoldMouse", "GoldFrog", "GoldGrasshopper", "GoldButterfly", "GoldWorm", "GoldDragonfly", "GoldSeahorse", "GoldWaterStrider", "GoldLadybug"], False),
    (64, "Frog", "Frog", ["Frog"], False),
    (65, "Gold Frog", "Gold_Frog", ["GoldBunny", "GoldBird", "GoldGoldfish", "SquirrelGold", "GoldMouse", "GoldFrog", "GoldGrasshopper", "GoldButterfly", "GoldWorm", "GoldDragonfly", "GoldSeahorse", "GoldWaterStrider", "GoldLadybug"], False),
    (66, "Grasshopper", "Grasshopper", ["Grasshopper"], False),
    (67, "Gold Grasshopper", "Gold_Grasshopper", ["GoldBunny", "GoldBird", "GoldGoldfish", "SquirrelGold", "GoldMouse", "GoldFrog", "GoldGrasshopper", "GoldButterfly", "GoldWorm", "GoldDragonfly", "GoldSeahorse", "GoldWaterStrider", "GoldLadybug"], False),
    (68, "Butterfly", "Butterfly", ["Butterfly"], False),
    (69, "Gold Butterfly", "Gold_Butterfly", ["GoldBunny", "GoldBird", "GoldGoldfish", "SquirrelGold", "GoldMouse", "GoldFrog", "GoldGrasshopper", "GoldButterfly", "GoldWorm", "GoldDragonfly", "GoldSeahorse", "GoldWaterStrider", "GoldLadybug"], False),
    (70, "Worm", "Worm", ["Worm"], False),
    (71, "Gold Worm", "Gold_Worm", ["GoldBunny", "GoldBird", "GoldGoldfish", "SquirrelGold", "GoldMouse", "GoldFrog", "GoldGrasshopper", "GoldButterfly", "GoldWorm", "GoldDragonfly", "GoldSeahorse", "GoldWaterStrider", "GoldLadybug"], False),
    (72, "Dragonfly", "Dragonfly", ["Dragonfly", "BlackDragonfly", "BlueDragonfly", "GreenDragonfly", "OrangeDragonfly", "RedDragonfly", "YellowDragonfly"], False),
    (73, "Gold Dragonfly", "Gold_Dragonfly", ["GoldBunny", "GoldBird", "GoldGoldfish", "SquirrelGold", "GoldMouse", "GoldFrog", "GoldGrasshopper", "GoldButterfly", "GoldWorm", "GoldDragonfly", "GoldSeahorse", "GoldWaterStrider", "GoldLadybug"], False),
    (74, "Seahorse", "Seahorse", ["Seahorse"], False),
    (75, "Gold Seahorse", "Gold_Seahorse", ["GoldSeahorse"], False),
    (76, "Water Strider", "Water_Strider", ["WaterStrider"], False),
    (77, "Gold Water Strider", "Gold_Water_Strider", ["GoldWaterStrider"], False),
    (78, "Ladybug", "Ladybug", ["LadyBug"], False),
    (79, "Gold Ladybug", "Gold_Ladybug", ["GoldLadybug"], False),
    (80, "Stinkbug", "Stinkbug", ["Stinkbug"], False),
    (81, "Faeling", "Faeling", ["Faeling", "Shimmerfly"], True),
    (82, "Duck", "Mallard_Duck", ["Duck", "Duck2"], False),
    (83, "Duck", "White_Duck", ["DuckWhite", "DuckWhite2"], False),
    (84, "Turtle", "Turtle", ["Turtle"], False),
    (85, "Owl", "Owl", ["Owl"], False),
    (86, "Firefly", "Firefly", ["Firefly"], False),
    (87, "Enchanted Nightcrawler", "Enchanted_Nightcrawler", ["EnchantedNightcrawler"], False),
    (88, "Pink Fairy", "Pink_Fairy", ["FairyCritterPink"], False),
    (89, "Green Fairy", "Green_Fairy", ["FairyCritterGreen"], False),
    (90, "Blue Fairy", "Blue_Fairy", ["FairyCritterBlue"], False),
    (91, "Rat", "Rat", ["Rat"], False),
    (92, "Maggot", "Maggot", ["Maggot"], False),
    (93, "Amethyst Squirrel", "Amethyst_Squirrel", ["GemSquirrelAmethyst"], False),
    (94, "Topaz Squirrel", "Topaz_Squirrel", ["GemSquirrelTopaz"], False),
    (95, "Sapphire Squirrel", "Sapphire_Squirrel", ["GemSquirrelSapphire"], False),
    (96, "Emerald Squirrel", "Emerald_Squirrel", ["GemSquirrelEmerald"], False),
    (97, "Ruby Squirrel", "Ruby_Squirrel", ["GemSquirrelRuby"], False),
    (98, "Diamond Squirrel", "Diamond_Squirrel", ["GemSquirrelDiamond"], False),
    (99, "Amber Squirrel", "Amber_Squirrel", ["GemSquirrelAmber"], False),
    (100, "Amethyst Bunny", "Amethyst_Bunny", ["GemBunnyAmethyst"], False),
    (101, "Topaz Bunny", "Topaz_Bunny", ["GemBunnyTopaz"], False),
    (102, "Sapphire Bunny", "Sapphire_Bunny", ["GemBunnySapphire"], False),
    (103, "Emerald Bunny", "Emerald_Bunny", ["GemBunnyEmerald"], False),
    (104, "Ruby Bunny", "Ruby_Bunny", ["GemBunnyRuby"], False),
    (105, "Diamond Bunny", "Diamond_Bunny", ["GemBunnyDiamond"], False),
    (106, "Amber Bunny", "Amber_Bunny", ["GemBunnyAmber"], False),
    (107, "Snail", "Snail", ["Snail"], False),
    (108, "Truffle Worm", "Truffle_Worm", ["TruffleWorm", "TruffleWormDigger"], True),
    (109, "Penguin", "Penguin", ["Penguin"], False),
    (110, "Penguin (Black)", "Penguin", ["PenguinBlack"], False),
    (111, "Scorpion", "Scorpion", ["Scorpion"], False),
    (112, "Black Scorpion", "Black_Scorpion", ["ScorpionBlack"], False),
    (113, "Grebe", "Grebe", ["Grebe", "Grebe2"], False),
    (114, "Pupfish", "Pupfish", ["Pupfish"], False),
    (115, "Seagull", "Seagull", ["Seagull","Seagull2"], False),
    (116, "Sea Turtle", "Sea_Turtle", ["SeaTurtle"], False),
    (117, "Pufferfish", "Pufferfish", ["Pufferfish"], False),
    (118, "Dolphin", "Dolphin", ["Dolphin"], False),
    (119, "Jungle Turtle", "Jungle_Turtle", ["TurtleJungle"], False),
    (120, "Grubby", "Grubby", ["Grubby"], False),
    (121, "Sluggy", "Sluggy", ["Sluggy"], False),
    (122, "Buggy", "Buggy", ["Buggy"], False),
    (123, "Lavafly", "Lavafly", ["Lavafly"], False),
    (124, "Hell Butterfly", "Hell_Butterfly", ["HellButterfly"], False),
    (125, "Magma Snail", "Magma_Snail", ["MagmaSnail"], False),
    (126, "Lightning Bug", "Lightning_Bug", ["LightningBug"], True),
    (127, "Prismatic Lacewing", "Prismatic_Lacewing", ["EmpressButterfly"], True),
    (128, "Glowing Snail", "Glowing_Snail", ["GlowingSnail"], False),
    (129, "Gnome", "Gnome", ["Gnome"], False),
    # ── Pre-Hardmode Surface ──
    (130, "Goblin Scout", "Goblin_Scout", ["GoblinScout"], False),
    (131, "Green Slime", "Green_Slime", ["GreenSlime"], False),
    (132, "Blue Slime", "Blue_Slime", ["BlueSlime"], False),
    (133, "Purple Slime", "Purple_Slime", ["PurpleSlime"], False),
    (134, "Pinky", "Pinky", ["Pinky"], False),
    (135, "Windy Balloon", "Windy_Balloon", ["WindyBalloon"], False),
    (136, "Angry Dandelion", "Angry_Dandelion", ["Dandelion"], False),
    (137, "Umbrella Slime", "Umbrella_Slime", ["UmbrellaSlime"], False),
    (138, "Flying Fish", "Flying_Fish", ["FlyingFish"], False),
    (139, "Angry Nimbus", "Angry_Nimbus", ["AngryNimbus"], True),
    (140, "Demon Eye (Dilated)", "Demon_Eye", ["DialatedEye"], False),
    (141, "Demon Eye (Sleepy)", "Demon_Eye", ["SleepyEye"], False),
    (142, "Demon Eye (Purple)", "Demon_Eye", ["PurpleEye"], False),
    (143, "Demon Eye", "Demon_Eye", ["DemonEye"], False),
    (144, "Demon Eye (Green)", "Demon_Eye", ["GreenEye"], False),
    (145, "Demon Eye (Cataract)", "Demon_Eye", ["CataractEye"], False),
    (146, "Wandering Eye", "Wandering_Eye", ["WanderingEye"], False),
    (147, "Zombie (Female)", "Zombie", ["FemaleZombie"], False),
    (148, "Zombie (Slimed)", "Zombie", ["SlimedZombie"], False),
    (149, "Zombie (Bald)", "Zombie", ["BaldZombie", "BigBaldZombie", "SmallBaldZombie"], False),
    (150, "Zombie", "Zombie", ["Zombie"], False),
    (151, "Zombie (Twiggy)", "Zombie", ["TwiggyZombie"], False),
    (152, "Zombie (Torch)", "Zombie", ["TorchZombie"], False),
    (153, "Zombie (Swamp)", "Zombie", ["SwampZombie"], False),
    (154, "Zombie (Pincushion)", "Zombie", ["PincushionZombie"], False),
    (155, "Raincoat Zombie", "Raincoat_Zombie", ["ZombieRaincoat"], False),
    (156, "Possessed Armor", "Possessed_Armor", ["PossessedArmor"], True),
    (157, "Werewolf", "Werewolf", ["Werewolf"], True),
    (158, "Wraith", "Wraith", ["Wraith"], True),
    (159, "Corrupt Bunny", "Corrupt_Bunny", ["CorruptBunny"], False),
    (160, "Corrupt Penguin", "Corrupt_Penguin", ["CorruptPenguin"], False),
    (161, "Vicious Bunny", "Vicious_Bunny", ["CrimsonBunny"], False),
    (162, "Vicious Penguin", "Vicious_Penguin", ["CrimsonPenguin"], False),
    # ── Blood Moon ──
    (163, "Blood Zombie", "Blood_Zombie", ["BloodZombie"], False),
    (164, "The Groom", "The_Groom", ["TheGroom"], False),
    (165, "The Bride", "The_Bride", ["TheBride"], False),
    (166, "Zombie Merman", "Zombie_Merman", ["ZombieMerman"], False),
    (167, "Clown", "Clown", ["Clown"], True),
    (168, "Blood Squid", "Blood_Squid", ["BloodSquid"], True),
    (169, "Blood Eel", "Blood_Eel", ["BloodEelHead"], True),
    (170, "Corrupt Goldfish", "Corrupt_Goldfish", ["CorruptGoldfish"], False),
    (171, "Vicious Goldfish", "Vicious_Goldfish", ["CrimsonGoldfish"], False),
    (172, "Drippler", "Drippler", ["Drippler"], False),
    (173, "Chattering Teeth Bomb", "Chattering_Teeth_Bomb", ["ChatteringTeethBomb"], True),
    (174, "Wandering Eye Fish", "Wandering_Eye_Fish", ["EyeballFlyingFish"], True),
    (175, "Hemogoblin Shark", "Hemogoblin_Shark", ["GoblinShark"], True),
    (176, "Dreadnautilus", "Dreadnautilus", ["BloodNautilus"], True),
    # ── Seasonal / Special ──
    (177, "Hoppin' Jack", "Hoppin'_Jack", ["HoppinJack"], False),
    (178, "Maggot Zombie", "Maggot_Zombie", ["MaggotZombie"], False),
    (179, "Moss Zombie", "Moss_Zombie", ["MossZombie"], False),
    (180, "Raven", "Raven", ["Raven"], False),
    (181, "Ghost", "Ghost", ["Ghost"], False),
    (182, "Statue", "Statue", ["StatueMimic"], False),
    # ── Underground / Cavern ──
    (183, "Red Slime", "Red_Slime", ["RedSlime"], False),
    (184, "Yellow Slime", "Yellow_Slime", ["YellowSlime"], False),
    (185, "Toxic Sludge", "Toxic_Sludge", ["ToxicSludge"], True),
    (186, "Giant Worm", "Giant_Worm", ["GiantWormHead"], False),
    (187, "Digger", "Digger", ["DiggerHead"], True),
    (188, "Baby Slime", "Baby_Slime", ["BabySlime"], False),
    (189, "Black Slime", "Black_Slime", ["BlackSlime"], False),
    (190, "Shimmer Slime", "Shimmer_Slime", ["ShimmerSlime"], False),
    (191, "Mother Slime", "Mother_Slime", ["MotherSlime"], False),
    (192, "Cochineal Beetle", "Cochineal_Beetle", ["CochinealBeetle"], False),
    (193, "Skeleton (Misassembled)", "Skeleton", ["MisassembledSkeleton", "SmallMisassembledSkeleton", "BigMisassembledSkeleton"], False),
    (194, "Skeleton", "Skeleton", ["Skeleton", "SmallSkeleton", "BigSkeleton"], False),
    (195, "Salamander", "Salamander", ["Salamander", "Salamander2", "Salamander3", "Salamander4", "Salamander5", "Salamander6", "Salamander7", "Salamander8", "Salamander9"], False),
    (196, "Skeleton (Headache)", "Skeleton", ["HeadacheSkeleton", "SmallHeadacheSkeleton", "BigHeadacheSkeleton"], False),
    (197, "Skeleton (Pantless)", "Skeleton", ["PantlessSkeleton", "SmallPantlessSkeleton", "BigPantlessSkeleton"], False),
    (198, "Crawdad", "Crawdad", ["Crawdad", "Crawdad2"], False),
    (199, "Undead Miner", "Undead_Miner", ["UndeadMiner"], False),
    (200, "Skeleton Archer", "Skeleton_Archer", ["SkeletonArcher"], True),
    (201, "Nymph", "Nymph", ["Nymph"], False),
    (202, "Armored Skeleton", "Armored_Skeleton", ["ArmoredSkeleton"], True),
    (203, "Rock Golem", "Rock_Golem", ["RockGolem"], False),
    (204, "Tim", "Tim", ["Tim"], False),
    (205, "Rune Wizard", "Rune_Wizard", ["RuneWizard"], True),
    (206, "Cave Bat", "Cave_Bat", ["CaveBat"], False),
    (207, "Giant Bat", "Giant_Bat", ["GiantBat"], True),
    (208, "Blue Jellyfish", "Blue_Jellyfish", ["BlueJellyfish"], False),
    (209, "Green Jellyfish", "Green_Jellyfish", ["GreenJellyfish"], True),
    (210, "Mimic", "Mimic", ["Mimic"], True),
    (211, "Giant Shelly", "Giant_Shelly", ["GiantShelly", "GiantShelly2"], False),
    (212, "Lost Girl", "Lost_Girl", ["LostGirl", "Nymph"], False),
    (213, "Granite Golem", "Granite_Golem", ["GraniteGolem"], False),
    (214, "Granite Elemental", "Granite_Elemental", ["GraniteFlyer"], False),
    (215, "Hoplite", "Hoplite", ["GreekSkeleton"], False),
    (216, "Medusa", "Medusa", ["Medusa"], True),
    (217, "Spore Skeleton", "Spore_Skeleton", ["SporeSkeleton"], False),
    (218, "Spore Bat", "Spore_Bat", ["SporeBat"], False),
    (219, "Wall Creeper", "Wall_Creeper", ["WallCreeper", "WallCreeperWall"], False),
    (220, "Black Recluse", "Black_Recluse", ["BlackRecluse", "BlackRecluseWall"], True),
    # ── Snow Biome ──
    (221, "Ice Slime", "Ice_Slime", ["IceSlime"], False),
    (222, "Frozen Zombie", "Frozen_Zombie", ["ZombieEskimo"], False),
    (223, "Ice Golem", "Ice_Golem", ["IceGolem"], True),
    (224, "Wolf", "Wolf", ["Wolf"], True),
    (225, "Spiked Ice Slime", "Spiked_Ice_Slime", ["SpikedIceSlime"], False),
    (226, "Cyan Beetle", "Cyan_Beetle", ["CyanBeetle"], False),
    (227, "Undead Viking", "Undead_Viking", ["UndeadViking"], False),
    (228, "Snow Flinx", "Snow_Flinx", ["SnowFlinx"], False),
    (229, "Armored Viking", "Armored_Viking", ["ArmoredViking"], True),
    (230, "Icy Merman", "Icy_Merman", ["IcyMerman"], True),
    (231, "Ice Bat", "Ice_Bat", ["IceBat"], False),
    (232, "Ice Elemental", "Ice_Elemental", ["IceElemental"], True),
    (233, "Ice Mimic", "Ice_Mimic", ["IceMimic"], True),
    (234, "Ice Tortoise", "Ice_Tortoise", ["IceTortoise"], True),
    # ── Desert ──
    (235, "Vulture", "Vulture", ["Vulture"], False),
    (236, "Sand Slime", "Sand_Slime", ["SandSlime"], False),
    (237, "Antlion Larva", "Antlion_Larva", ["LarvaeAntlion"], False),
    (238, "Giant Antlion Charger", "Giant_Antlion_Charger", ["GiantWalkingAntlion"], False),
    (239, "Mummy", "Mummy", ["Mummy"], True),
    (240, "Ghoul", "Ghoul", ["DesertGhoul", "DesertGhoulCorruption", "DesertGhoulCrimson", "DesertGhoulHallow"], True),
    (241, "Basilisk", "Basilisk", ["DesertBeast"], True),
    (242, "Tomb Crawler", "Tomb_Crawler", ["TombCrawlerHead"], False),
    (243, "Antlion", "Antlion", ["Antlion"], False),
    (244, "Sand Poacher", "Sand_Poacher", ["DesertScorpionWalk", "DesertScorpionWall"], True),
    (245, "Giant Antlion Swarmer", "Giant_Antlion_Swarmer", ["GiantFlyingAntlion"], False),
    (246, "Antlion Charger", "Antlion_Charger", ["WalkingAntlion"], False),
    (247, "Dune Splicer", "Dune_Splicer", ["DuneSplicerHead"], True),
    (248, "Angry Tumbler", "Angry_Tumbler", ["Tumbleweed"], False),
    (249, "Antlion Swarmer", "Antlion_Swarmer", ["FlyingAntlion"], False),
    (250, "Sand Elemental", "Sand_Elemental", ["SandElemental"], True),
    (251, "Sand Shark", "Sand_Shark", ["SandShark", "SandsharkCorrupt", "SandsharkCrimson", "SandsharkHallow"], True),
    # ── Ocean ──
    (252, "Crab", "Crab", ["Crab"], False),
    (253, "Sea Snail", "Sea_Snail", ["SeaSnail"], False),
    (254, "Shark", "Shark", ["Shark"], False),
    (255, "Orca", "Orca", ["Orca"], False),
    (256, "Squid", "Squid", ["Squid"], False),
    (257, "Pink Jellyfish", "Pink_Jellyfish", ["PinkJellyfish"], False),
    # ── Jungle ──
    (258, "Jungle Slime", "Jungle_Slime", ["JungleSlime"], False),
    (259, "Snatcher", "Snatcher", ["Snatcher"], False),
    (260, "Giant Flying Fox", "Giant_Flying_Fox", ["GiantFlyingFox"], True),
    (261, "Derpling", "Derpling", ["Derpling"], True),
    (262, "Spiked Jungle Slime", "Spiked_Jungle_Slime", ["SpikedJungleSlime"], False),
    (263, "Lac Beetle", "Lac_Beetle", ["LacBeetle"], False),
    (264, "Doctor Bones", "Doctor_Bones", ["DoctorBones"], False),
    (265, "Bee", "Bee", ["Bee"], False),
    (266, "Bee (Larger)", "Bee", ["BeeSmall"], False),
    (267, "Hornet (Stingy)", "Hornet", ["HornetStingy"], False),
    (268, "Hornet (Spikey)", "Hornet", ["HornetSpikey"], False),
    (269, "Hornet", "Hornet", ["Hornet"], False),
    (270, "Hornet (Fatty)", "Hornet", ["HornetFatty"], False),
    (271, "Hornet (Honey)", "Hornet", ["HornetHoney"], False),
    (272, "Hornet (Leafy)", "Hornet", ["HornetLeafy"], False),
    (273, "Moss Hornet", "Moss_Hornet", ["MossHornet"], True),
    (274, "Moth", "Moth", ["Moth"], True),
    (275, "Man Eater", "Man_Eater", ["ManEater"], False),
    (276, "Angry Trapper", "Angry_Trapper", ["AngryTrapper"], True),
    (277, "Jungle Bat", "Jungle_Bat", ["JungleBat"], False),
    (278, "Piranha", "Piranha", ["Piranha"], False),
    (279, "Angler Fish", "Angler_Fish", ["AnglerFish"], False),
    (280, "Arapaima", "Arapaima", ["Arapaima"], True),
    (281, "Giant Tortoise", "Giant_Tortoise", ["GiantTortoise"], True),
    (282, "Jungle Creeper", "Jungle_Creeper", ["JungleCreeper", "JungleCreeperWall"], True),
    # ── Meteor / Dungeon ──
    (283, "Meteor Head", "Meteor_Head", ["MeteorHead"], False),
    (284, "Dungeon Slime", "Dungeon_Slime", ["DungeonSlime"], False),
    (285, "Angry Bones", "Angry_Bones", ["AngryBones"], False),
    (286, "Angry Bones (Big)", "Angry_Bones", ["AngryBonesBig"], False),
    (287, "Angry Bones (Big Muscle)", "Angry_Bones", ["AngryBonesBigMuscle"], False),
    (288, "Angry Bones (Big Helmet)", "Angry_Bones", ["AngryBonesBigHelmet"], False),
    (289, "Blue Armored Bones (Mace)", "Blue_Armored_Bones", ["BlueArmoredBones"], True),
    (290, "Skeleton Sniper", "Skeleton_Sniper", ["SkeletonSniper"], True),
    (291, "Tactical Skeleton", "Tactical_Skeleton", ["TacticalSkeleton"], True),
    (292, "Skeleton Commando", "Skeleton_Commando", ["SkeletonCommando"], True),
    (293, "Hell Armored Bones", "Hell_Armored_Bones", ["HellArmoredBones"], True),
    (294, "Rusty Armored Bones (Sword No Armor)", "Rusty_Armored_Bones", ["RustyArmoredBonesSwordNoArmor"], True),
    (295, "Rusty Armored Bones (Flail)", "Rusty_Armored_Bones", ["RustyArmoredBonesFlail"], True),
    (296, "Hell Armored Bones (Mace)", "Hell_Armored_Bones", ["HellArmoredBonesMace"], True),
    (297, "Blue Armored Bones", "Blue_Armored_Bones", ["BlueArmoredBonesMace"], True),
    (298, "Rusty Armored Bones (Sword)", "Rusty_Armored_Bones", ["RustyArmoredBonesSword"], True),
    (299, "Hell Armored Bones (Spike Shield)", "Hell_Armored_Bones", ["HellArmoredBonesSpikeShield"], True),
    (300, "Blue Armored Bones (No Pants)", "Blue_Armored_Bones", ["BlueArmoredBonesNoPants"], True),
    (301, "Hell Armored Bones (Sword)", "Hell_Armored_Bones", ["HellArmoredBonesSword"], True),
    (302, "Rusty Armored Bones (Axe)", "Rusty_Armored_Bones", ["RustyArmoredBonesAxe"], True),
    (303, "Blue Armored Bones (Sword)", "Blue_Armored_Bones", ["BlueArmoredBonesSword"], True),
    (304, "Bone Lee", "Bone_Lee", ["BoneLee"], True),
    (305, "Paladin", "Paladin", ["Paladin"], True),
    (306, "Dark Caster", "Dark_Caster", ["DarkCaster"], False),
    (307, "Librarian Skeleton", "Librarian_Skeleton", ["LibrarianSkeleton"], False),
    (308, "Diabolist (Red)", "Diabolist", ["DiabolistRed"], True),
    (309, "Diabolist (White)", "Diabolist", ["DiabolistWhite"], True),
    (310, "Necromancer", "Necromancer", ["Necromancer"], True),
    (311, "Ragged Caster", "Ragged_Caster", ["RaggedCaster"], True),
    (312, "Necromancer (Armored)", "Necromancer", ["NecromancerArmored"], True),
    (313, "Ragged Caster (Open Coat)", "Ragged_Caster", ["RaggedCasterOpenCoat"], True),
    (314, "Water Bolt Mimic", "Water_Bolt_Mimic", ["WaterBoltMimic"], False),
    (315, "Cursed Skull", "Cursed_Skull", ["CursedSkull"], False),
    (316, "Giant Cursed Skull", "Giant_Cursed_Skull", ["GiantCursedSkull"], True),
    (317, "Dungeon Guardian", "Dungeon_Guardian", ["DungeonGuardian", "SkeletronHead"], False),
    (318, "Dungeon Spirit", "Dungeon_Spirit", ["DungeonSpirit"], True),
    # ── Underworld ──
    (319, "Lava Slime", "Lava_Slime", ["LavaSlime"], False),
    (320, "Tortured Soul", "Tortured_Soul", ["DemonTaxCollector", "TaxCollector"], True),
    (321, "Bone Serpent", "Bone_Serpent", ["BoneSerpentHead"], False),
    (322, "Fire Imp", "Fire_Imp", ["FireImp"], False),
    (323, "Hellbat", "Hellbat", ["Hellbat"], False),
    (324, "Demon", "Demon", ["Demon"], False),
    (325, "Voodoo Demon", "Voodoo_Demon", ["VoodooDemon"], False),
    (326, "Lava Bat", "Lava_Bat", ["Lavabat"], True),
    (327, "Red Devil", "Red_Devil", ["RedDevil"], True),
    # ── Sky ──
    (328, "Wyvern", "Wyvern", ["WyvernHead"], True),
    (329, "Harpy", "Harpy", ["Harpy"], False),
    (330, "Martian Probe", "Martian_Probe", ["MartianProbe"], True),
    # ── Corruption ──
    (331, "Slimeling", "Slimeling", ["Slimeling"], True),
    (332, "Corrupt Slime", "Corrupt_Slime", ["CorruptSlime"], True),
    (333, "Eater of Souls", "Eater_of_Souls", ["EaterofSouls"], False),
    (334, "Corruptor", "Corruptor", ["Corruptor"], True),
    (335, "Devourer", "Devourer", ["DevourerHead"], False),
    (336, "World Feeder", "World_Feeder", ["SeekerHead"], True),
    (337, "Clinger", "Clinger", ["Clinger"], True),
    (338, "Slimer", "Slimer", ["Slimer", "Slimer2"], True),
    (339, "Cursed Hammer", "Cursed_Hammer", ["CursedHammer"], True),
    (340, "Corrupt Mimic", "Corrupt_Mimic", ["BigMimicCorruption"], True),
    (341, "Pigron (Corrupt)", "Pigron", ["PigronCorruption"], True),
    (342, "Bone Biter", "Bone_Biter", ["SandsharkCorrupt"], True),
    (343, "Dark Mummy", "Dark_Mummy", ["DarkMummy"], True),
    (344, "Vile Ghoul", "Vile_Ghoul", ["DesertGhoulCorruption"], True),
    # ── Crimson ──
    (345, "Crimslime", "Crimslime", ["Crimslime"], True),
    (346, "Face Monster", "Face_Monster", ["FaceMonster"], False),
    (347, "Crimera", "Crimera", ["Crimera"], False),
    (348, "Blood Feeder", "Blood_Feeder", ["BloodFeeder"], True),
    (349, "Blood Jelly", "Blood_Jelly", ["BloodJelly"], True),
    (350, "Floaty Gross", "Floaty_Gross", ["FloatyGross"], True),
    (351, "Ichor Sticker", "Ichor_Sticker", ["IchorSticker"], True),
    (352, "Crimson Axe", "Crimson_Axe", ["CrimsonAxe"], True),
    (353, "Blood Crawler", "Blood_Crawler", ["BloodCrawler", "BloodCrawlerWall"], False),
    (354, "Herpling", "Herpling", ["Herpling"], True),
    (355, "Crimson Mimic", "Crimson_Mimic", ["BigMimicCrimson"], True),
    (356, "Pigron (Crimson)", "Pigron", ["PigronCrimson"], True),
    (357, "Flesh Reaver", "Flesh_Reaver", ["SandsharkCrimson"], True),
    (358, "Blood Mummy", "Blood_Mummy", ["BloodMummy"], True),
    (359, "Tainted Ghoul", "Tainted_Ghoul", ["DesertGhoulCrimson"], True),
    (360, "Lamia", "Lamia", ["DesertLamiaDark"], True),
    (361, "Desert Spirit", "Desert_Spirit", ["DesertDjinn"], True),
    # ── Hallow ──
    (362, "Rainbow Slime", "Rainbow_Slime", ["RainbowSlime", "GoldenSlime"], True),
    (363, "Pixie", "Pixie", ["Pixie"], True),
    (364, "Gastropod", "Gastropod", ["Gastropod"], True),
    (365, "Unicorn", "Unicorn", ["Unicorn"], True),
    (366, "Illuminant Slime", "Illuminant_Slime", ["IlluminantSlime"], True),
    (367, "Chaos Elemental", "Chaos_Elemental", ["ChaosElemental"], True),
    (368, "Illuminant Bat", "Illuminant_Bat", ["IlluminantBat"], True),
    (369, "Enchanted Sword", "Enchanted_Sword_(NPC)", ["EnchantedSword"], True),
    (370, "Hallowed Mimic", "Hallowed_Mimic", ["BigMimicHallow", "BigMimicJungle"], True),
    (371, "Pigron", "Pigron", ["PigronHallow"], True),
    (372, "Crystal Thresher", "Crystal_Thresher", ["SandsharkHallow"], True),
    (373, "Light Mummy", "Light_Mummy", ["LightMummy"], True),
    (374, "Dreamer Ghoul", "Dreamer_Ghoul", ["DesertGhoulHallow"], True),
    (375, "Lamia (Light)", "Lamia", ["DesertLamiaLight"], True),
    # ── Mushroom ──
    (376, "Spore Zombie (Mushroom)", "Spore_Zombie", ["ZombieMushroomHat"], False),
    (377, "Spore Zombie (Hat Mushroom)", "Spore_Zombie", ["ZombieMushroom"], False),
    (378, "Anomura Fungus", "Anomura_Fungus", ["AnomuraFungus"], True),
    (379, "Mushi Ladybug", "Mushi_Ladybug", ["MushiLadybug"], True),
    (380, "Fungi Bulb", "Fungi_Bulb", ["FungiBulb"], True),
    (381, "Giant Fungi Bulb", "Giant_Fungi_Bulb", ["GiantFungiBulb"], True),
    (382, "Fungo Fish", "Fungo_Fish", ["FungoFish"], True),
    # ── Temple ──
    (383, "Lihzahrd", "Lihzahrd", ["Lihzahrd", "LihzahrdCrawler"], True),
    (384, "Flying Snake", "Flying_Snake", ["FlyingSnake"], True),
    # ── Goblin Invasion ──
    (385, "Goblin Peon", "Goblin_Peon", ["GoblinPeon"], False),
    (386, "Goblin Thief", "Goblin_Thief", ["GoblinThief"], False),
    (387, "Goblin Archer", "Goblin_Archer", ["GoblinArcher"], False),
    (388, "Goblin Warrior", "Goblin_Warrior", ["GoblinWarrior"], False),
    (389, "Goblin Warlock", "Goblin_Warlock", ["GoblinSummoner"], True),
    (390, "Goblin Sorcerer", "Goblin_Sorcerer", ["GoblinSorcerer"], False),
    (391, "Shadowflame Apparition", "Shadowflame_Apparition", ["ShadowFlameApparition"], True),
    # ── Old One's Army ──
    (392, "Old One's Skeleton", "Old_One's_Skeleton", ["DD2SkeletonT1","DD2SkeletonT3"], False),
    (393, "Etherian Goblin", "Etherian_Goblin", ["DD2GoblinT1","DD2GoblinT2","DD2GoblinT3"], False),
    (394, "Etherian Goblin Bomber", "Etherian_Goblin_Bomber", ["DD2GoblinBomberT1","DD2GoblinBomberT2","DD2GoblinBomberT3"], False),
    (395, "Kobold", "Kobold", ["DD2KoboldWalkerT2","DD2KoboldWalkerT3"], True),
    (396, "Etherian Javelin Thrower", "Etherian_Javelin_Thrower", ["DD2JavelinstT1","DD2JavelinstT2","DD2JavelinstT3"], False),
    (397, "Wither Beast", "Wither_Beast", ["DD2WitherBeastT2","DD2WitherBeastT3"], True),
    (398, "Drakin", "Drakin", ["DD2DrakinT2","DD2DrakinT3"], True),
    (399, "Ogre", "Ogre", ["DD2OgreT2","DD2OgreT3"], True),
    (400, "Kobold Glider", "Kobold_Glider", ["DD2KoboldFlyerT2","DD2KoboldFlyerT3"], True),
    (401, "Etherian Wyvern", "Etherian_Wyvern", ["DD2WyvernT1","DD2WyvernT2","DD2WyvernT3"], False),
    (402, "Dark Mage", "Dark_Mage", ["DD2DarkMageT1","DD2DarkMageT3"], False),
    (403, "Betsy", "Betsy", ["DD2Betsy"], True),
    (404, "Etherian Lightning Bug", "Etherian_Lightning_Bug", ["DD2LightningBugT3"], True),
    # ── Pirate Invasion ──
    (405, "Pirate Deadeye", "Pirate_Deadeye", ["PirateDeadeye"], True),
    (406, "Pirate Deckhand", "Pirate_Deckhand", ["PirateDeckhand"], True),
    (407, "Pirate Crossbower", "Pirate_Crossbower", ["PirateCrossbower"], True),
    (408, "Pirate Corsair", "Pirate_Corsair", ["PirateCorsair"], True),
    (409, "Pirate Captain", "Pirate_Captain", ["PirateCaptain"], True),
    (410, "Parrot", "Parrot", ["Parrot"], True),
    (411, "Flying Dutchman", "Flying_Dutchman", ["FlyingDutchman", "PirateShip", "PirateShipCannon", "PirateGhost"], True),
    # ── Martian Madness ──
    (412, "Brain Scrambler", "Brain_Scrambler", ["BrainScrambler"], True),
    (413, "Ray Gunner", "Ray_Gunner", ["RayGunner"], True),
    (414, "Martian Engineer", "Martian_Engineer", ["MartianEngineer"], True),
    (415, "Martian Officer", "Martian_Officer", ["MartianOfficer"], True),
    (416, "Gigazapper", "Gigazapper", ["GigaZapper"], True),
    (417, "Scutlix", "Scutlix", ["Scutlix"], True),
    (418, "Gray Grunt", "Gray_Grunt", ["GrayGrunt"], True),
    (419, "Martian Walker", "Martian_Walker", ["MartianWalker"], True),
    (420, "Tesla Turret", "Tesla_Turret", ["MartianTurret"], True),
    (421, "Martian Drone", "Martian_Drone", ["MartianDrone"], True),
    (422, "Scutlix Gunner", "Scutlix_Gunner", ["ScutlixRider"], True),
    (423, "Martian Saucer", "Martian_Saucer", ["MartianSaucer", "MartianSaucerCore", "MartianSaucerCannon", "MartianSaucerTurret"], True),
    # ── Solar Eclipse ──
    (424, "Fritz", "Fritz", ["Fritz"], True),
    (425, "Frankenstein", "Frankenstein", ["Frankenstein"], True),
    (426, "Creature from the Deep", "Creature_from_the_Deep", ["CreatureFromTheDeep"], True),
    (427, "Swamp Thing", "Swamp_Thing", ["SwampThing"], True),
    (428, "Dr. Man Fly", "Dr._Man_Fly", ["DrManFly"], True),
    (429, "The Possessed", "The_Possessed", ["ThePossessed"], True),
    (430, "Psycho", "Psycho", ["Psycho"], True),
    (431, "Butcher", "Butcher", ["Butcher"], True),
    (432, "Vampire", "Vampire", ["Vampire"], True),
    (433, "Eyezor", "Eyezor", ["Eyezor"], True),
    (434, "Nailhead", "Nailhead", ["Nailhead"], True),
    (435, "Reaper", "Reaper", ["Reaper"], True),
    (436, "Deadly Sphere", "Deadly_Sphere", ["DeadlySphere"], True),
    (437, "Mothron", "Mothron", ["Mothron"], True),
    (438, "Baby Mothron", "Baby_Mothron", ["MothronEgg", "MothronSpawn"], True),
    # ── Pumpkin Moon ──
    (439, "Scarecrow (Cloth Face Stick)", "Scarecrow", ["Scarecrow1","Scarecrow2","Scarecrow3","Scarecrow4","Scarecrow5","Scarecrow6","Scarecrow7","Scarecrow8""Scarecrow9","Scarecrow10"], True),
    (440, "Scarecrow (Cloth Face)", "Scarecrow", ["Scarecrow1","Scarecrow2","Scarecrow3","Scarecrow4","Scarecrow5","Scarecrow6","Scarecrow7","Scarecrow8""Scarecrow9","Scarecrow10"], True),
    (441, "Scarecrow (Guy Fawkes Stick)", "Scarecrow", ["Scarecrow1","Scarecrow2","Scarecrow3","Scarecrow4","Scarecrow5","Scarecrow6","Scarecrow7","Scarecrow8""Scarecrow9","Scarecrow10"], True),
    (442, "Scarecrow (Guy Fawkes)", "Scarecrow", ["Scarecrow1","Scarecrow2","Scarecrow3","Scarecrow4","Scarecrow5","Scarecrow6","Scarecrow7","Scarecrow8""Scarecrow9","Scarecrow10"], True),
    (443, "Scarecrow (Cloth Hat Stick)", "Scarecrow", ["Scarecrow1","Scarecrow2","Scarecrow3","Scarecrow4","Scarecrow5","Scarecrow6","Scarecrow7","Scarecrow8""Scarecrow9","Scarecrow10"], True),
    (444, "Scarecrow (Cloth Hat)", "Scarecrow", ["Scarecrow1","Scarecrow2","Scarecrow3","Scarecrow4","Scarecrow5","Scarecrow6","Scarecrow7","Scarecrow8""Scarecrow9","Scarecrow10"], True),
    (445, "Scarecrow (Pumpkin Hat Stick)", "Scarecrow", ["Scarecrow1","Scarecrow2","Scarecrow3","Scarecrow4","Scarecrow5","Scarecrow6","Scarecrow7","Scarecrow8""Scarecrow9","Scarecrow10"], True),
    (446, "Scarecrow (Pumpkin Hat)", "Scarecrow", ["Scarecrow1","Scarecrow2","Scarecrow3","Scarecrow4","Scarecrow5","Scarecrow6","Scarecrow7","Scarecrow8""Scarecrow9","Scarecrow10"], True),
    (447, "Scarecrow (Pumpkin Head Stick)", "Scarecrow", ["Scarecrow1","Scarecrow2","Scarecrow3","Scarecrow4","Scarecrow5","Scarecrow6","Scarecrow7","Scarecrow8""Scarecrow9","Scarecrow10"], True),
    (448, "Scarecrow (Pumpkin Head)", "Scarecrow", ["Scarecrow1","Scarecrow2","Scarecrow3","Scarecrow4","Scarecrow5","Scarecrow6","Scarecrow7","Scarecrow8""Scarecrow9","Scarecrow10"], True),
    (449, "Splinterling", "Splinterling", ["Splinterling"], True),
    (450, "Poltergeist", "Poltergeist", ["Poltergeist"], True),
    (451, "Hellhound", "Hellhound", ["Hellhound"], True),
    (452, "Headless Horseman", "Headless_Horseman", ["HeadlessHorseman"], True),
    (453, "Mourning Wood", "Mourning_Wood", ["MourningWood"], True),
    (454, "Pumpking", "Pumpking", ["Pumpking"], True),
    # ── Frost Moon ──
    (455, "Zombie Elf (Girl)", "Zombie_Elf", ["ZombieElfGirl"], True),
    (456, "Zombie Elf", "Zombie_Elf", ["ZombieElf"], True),
    (457, "Zombie Elf (Beard)", "Zombie_Elf", ["ZombieElfBeard"], True),
    (458, "Gingerbread Man", "Gingerbread_Man", ["GingerbreadMan"], True),
    (459, "Elf Archer", "Elf_Archer", ["ElfArcher"], True),
    (460, "Nutcracker", "Nutcracker", ["Nutcracker", "NutcrackerSpinning"], True),
    (461, "Krampus", "Krampus", ["Krampus"], True),
    (462, "Yeti", "Yeti", ["Yeti"], True),
    (463, "Present Mimic", "Present_Mimic", ["PresentMimic"], True),
    (464, "Everscream", "Everscream", ["Everscream"], True),
    (465, "Ice Queen", "Ice_Queen", ["IceQueen"], True),
    (466, "Santa-NK1", "Santa-NK1", ["SantaNK1"], True),
    (467, "Elf Copter", "Elf_Copter", ["ElfCopter"], True),
    (468, "Flocko", "Flocko", ["Flocko"], True),
    # ── Seasonal costume variants (Halloween) ──
    (469, "Slime (Bunny Mask)", "Slime", ["SlimeMasked"], False),
    (470, "Demon Eye (Spaceship)", "Demon_Eye", ["DemonEyeSpaceship"], False),
    (471, "Demon Eye (Owl Mask)", "Demon_Eye", ["DemonEyeOwl"], False),
    (472, "Zombie (Doctor)", "Zombie", ["ZombieDoctor"], False),
    (473, "Zombie (Superman)", "Zombie", ["ZombieSuperman"], False),
    (474, "Zombie (Pixie)", "Zombie", ["ZombiePixie"], False),
    (475, "Skeleton (Astronaut)", "Skeleton", ["SkeletonAstonaut"], False),
    (476, "Skeleton (Alien)", "Skeleton", ["SkeletonAlien"], False),
    (477, "Skeleton (Top Hat)", "Skeleton", ["SkeletonTopHat"], False),
    # ── Seasonal costume variants (Christmas) ──
    (478, "Slime (Red Present Slime)", "Slime", ["SlimeRibbonRed"], False),
    (479, "Slime (Yellow Present Slime)", "Slime", ["SlimeRibbonYellow"], False),
    (480, "Slime (White Present Slime)", "Slime", ["SlimeRibbonWhite"], False),
    (481, "Slime (Green Present Slime)", "Slime", ["SlimeRibbonGreen"], False),
    (482, "Zombie (Xmas)", "Zombie", ["ZombieXmas"], False),
    (483, "Zombie (Sweater)", "Zombie", ["ZombieSweater"], False),
    # ── Frost Legion (Christmas event) ──
    (484, "Snowman Gangsta", "Snowman_Gangsta", ["SnowmanGangsta"], False),
    (485, "Snow Balla", "Snow_Balla", ["SnowBalla"], False),
    (486, "Mister Stabby", "Mister_Stabby", ["MisterStabby"], False),
    # ── Nebula Pillar ──
    (487, "Predictor", "Predictor", ["NebulaHeadcrab"], True),
    (488, "Evolution Beast", "Evolution_Beast", ["NebulaBeast"], True),
    (489, "Brain Suckler", "Brain_Suckler", ["NebulaBrain"], True),
    (490, "Nebula Floater", "Nebula_Floater", ["NebulaSoldier"], True),
    # ── Solar Pillar ──
    (491, "Drakomire", "Drakomire", ["SolarDrakomire"], True),
    (492, "Selenian", "Selenian", ["SolarSolenian"], True),
    (493, "Drakanian", "Drakanian", ["SolarSpearman"], True),
    (494, "Crawltipede", "Crawltipede", ["SolarCrawltipedeHead"], True),
    (495, "Sroller", "Sroller", ["SolarSroller"], True),
    (496, "Corite", "Corite", ["SolarCorite"], True),
    (497, "Drakomire Rider", "Drakomire_Rider", ["SolarDrakomireRider"], True),
    # ── Vortex Pillar ──
    (498, "Alien Larva", "Alien_Larva", ["VortexLarva"], True),
    (499, "Alien Hornet", "Alien_Hornet", ["VortexHornet"], True),
    (500, "Vortexian", "Vortexian", ["VortexSoldier"], True),
    (501, "Storm Diver", "Storm_Diver", ["VortexRifleman"], True),
    (502, "Alien Queen", "Alien_Queen", ["VortexHornetQueen"], True),
    # ── Stardust Pillar ──
    (503, "Stargazer", "Stargazer", ["StardustSoldier"], True),
    (504, "Twinkle Popper", "Twinkle_Popper", ["StardustSpiderBig"], True),
    (505, "Milkyway Weaver", "Milkyway_Weaver", ["StardustWormHead"], True),
    (506, "Star Cell", "Star_Cell", ["StardustCellBig"], True),
    (507, "Mini Star Cell", "Mini_Star_Cell", ["StardustCellSmall"], True),
    (508, "Flow Invader", "Flow_Invader", ["StardustJellyfishBig"], True),
    # ── Events ──
    (509, "The Torch God", "The_Torch_God", ["TorchGod"], False),
    # ── Pre-Hardmode Bosses ──
    (510, "Eye of Cthulhu", "Eye_of_Cthulhu", ["EyeofCthulhu"], False),
    (511, "Servant of Cthulhu", "Servant_of_Cthulhu", ["ServantofCthulhu"], False),
    (512, "King Slime", "King_Slime", ["KingSlime"], False),
    (513, "Eater of Worlds", "Eater_of_Worlds", ["EaterofWorldsHead", "EaterofWorldsBody", "EaterofWorldsTail"], False),
    (514, "Brain of Cthulhu", "Brain_of_Cthulhu", ["BrainofCthulhu"], False),
    (515, "Creeper", "Creeper", ["Creeper"], False),
    (516, "Deerclops", "Deerclops", ["Deerclops"], False),
    (517, "Skeletron", "Skeletron", ["SkeletronHead", "SkeletronHand"], False),
    (518, "Queen Bee", "Queen_Bee", ["QueenBee"], False),
    (519, "Wall of Flesh", "Wall_of_Flesh", ["WallofFlesh", "WallofFleshEye"], False),
    # ── Hardmode Bosses ──
    (520, "Leech", "Leech", ["LeechHead"], False),
    (521, "The Hungry (attached)", "The_Hungry", ["TheHungry"], False),
    (522, "The Hungry (flying)", "The_Hungry", ["TheHungryII"], False),
    (523, "Queen Slime", "Queen_Slime", ["QueenSlimeBoss"], True),
    (524, "Crystal Slime", "Crystal_Slime", ["QueenSlimeMinionBlue"], True),
    (525, "Bouncy Slime", "Bouncy_Slime", ["QueenSlimeMinionPurple"], True),
    (526, "Heavenly Slime", "Heavenly_Slime", ["QueenSlimeMinionPink"], True),
    (527, "Retinazer", "Retinazer", ["Retinazer"], True),
    (528, "Spazmatism", "Spazmatism", ["Spazmatism"], True),
    (529, "The Destroyer", "The_Destroyer", ["TheDestroyer", "TheDestroyerBody", "TheDestroyerTail"], True),
    (530, "Probe", "Probe", ["Probe"], True),
    (531, "Skeletron Prime", "Skeletron_Prime", ["SkeletronPrime", "PrimeCannon", "PrimeSaw", "PrimeVice", "PrimeLaser"], True),
    (532, "Plantera", "Plantera", ["Plantera", "PlanterasTentacle", "PlanterasHook", "Spore"], True),
    (533, "Empress of Light", "Empress_of_Light", ["HallowBoss"], True),
    (534, "Golem", "Golem", ["Golem", "GolemFistLeft", "GolemFistRight", "GolemHead", "GolemHeadFree"], True),
    (535, "Duke Fishron", "Duke_Fishron", ["DukeFishron"], True),
    (536, "Sharkron", "Sharkron", ["Sharkron", "Sharkron2"], True),
    (537, "Lunatic Cultist", "Lunatic_Cultist", ["CultistBoss"], True),
    (538, "Lunatic Devotee", "Lunatic_Devotee", ["LunaticDevotee", "CultistDevote"], True),
    (539, "Blue Cultist Archer", "Blue_Cultist_Archer", ["CultistArcherBlue", "CultistArcherWhite"], True),
    (540, "Ancient Vision", "Ancient_Vision", ["AncientCultistSquidhead", "CultistBoss"], True),
    (541, "Phantasm Dragon", "Phantasm_Dragon", ["CultistDragonHead", "CultistBoss"], True),
    # ── Celestial Pillars ──
    (542, "Nebula Pillar", "Nebula_Pillar", ["LunarTowerNebula"], True),
    (543, "Solar Pillar", "Solar_Pillar", ["LunarTowerSolar"], True),
    (544, "Vortex Pillar", "Vortex_Pillar", ["LunarTowerVortex"], True),
    (545, "Stardust Pillar", "Stardust_Pillar", ["LunarTowerStardust"], True),
    # ── Final Boss ──
    (546, "Moon Lord", "Moon_Lord", ["MoonLordHead", "MoonLordHand", "MoonLordCore", "MoonLordFreeEye"], True),
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
    # Map each internal name to ALL entry numbers that use it
    internal_to_entry = {}
    for num, display, wiki, internals, hardmode in BESTIARY:
        for iname in internals:
            if iname not in internal_to_entry:
                internal_to_entry[iname] = []
            internal_to_entry[iname].append(num)

    # Build world data
    world_data = {}
    for fname, wdata in worlds.items():
        encountered = set()
        all_internal = set(wdata["kills"].keys()) | wdata["sights"] | wdata["chats"]
        for iname in all_internal:
            if iname in internal_to_entry:
                for num in internal_to_entry[iname]:
                    encountered.add(num)

        # Exclusive trio: Salamander/Crawdad/Giant Shelly — only 2 spawn per world;
        # seeing both present ones unlocks the missing one automatically.
        EXCLUSIVE_TRIO = {195, 198, 211}
        if len(encountered & EXCLUSIVE_TRIO) >= 2:
            encountered |= EXCLUSIVE_TRIO

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
    for num, display, wiki, internals, hardmode in BESTIARY:
        entries.append({
            "num": num,
            "name": display,
            "wiki": f"https://terraria.wiki.gg/wiki/{wiki}",
            "hm": hardmode,
        })

    return {"worlds": world_data, "entries": entries, "total": len(BESTIARY), "internalToEntry": internal_to_entry}

with open("assets/main_page.html") as file:
    HTML_TEMPLATE = file.read();

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

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
        elif self.path.startswith("/assets/"):
            # Serve files from the repo's assets/ folder
            rel = self.path.lstrip("/")  # e.g. "assets/background.jpg"
            asset_path = os.path.join(REPO_DIR, rel)
            if os.path.isfile(asset_path):
                ext = os.path.splitext(asset_path)[1].lower()
                mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".png": "image/png", ".gif": "image/gif",
                        ".webp": "image/webp"}.get(ext, "application/octet-stream")
                with open(asset_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "max-age=3600")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()
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


def build_static(out_path="index.html"):
    """Generate a static index.html suitable for GitHub Pages hosting."""
    data = build_bestiary_json({})  # no pre-loaded worlds
    data_json = json.dumps(data, separators=(',', ':'))
    with open("assets/main_page.html", encoding="utf-8") as f:
        template = f.read()
    static_html = template.replace("__DATA_PLACEHOLDER__", data_json)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(static_html)
    print(f"Generated {out_path}")


if __name__ == "__main__":
    if "--build" in sys.argv:
        build_static()
    else:
        main()
