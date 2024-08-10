from discord.ext import commands, tasks
from dotenv import load_dotenv
import discord, requests, websockets, json, os

# Loading in the bot token from the .env file, in the future, it may be worth adding the Channel IDs in there too, but
# not super important in the short term

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")

CHANNEL_IDS = json.loads(os.environ.get("CHANNEL_IDS"))

bot = commands.Bot(command_prefix="&", intents=discord.Intents.all())

player_count = 0

# This variable is related to the "subscribe_to_game_events()" method, where it may at some point crash due to
# connection issues to the websocket, every five minutes, the method "websocket_restarter" will check if it's still true
# if not, it will bring the bot back to life

websocket_live = True

lobby_info = {}


def map_photo_generator(map_name):
    """Returns the appropriate photo of the relevant map picture for use in discord embed"""

    if map_name == "Brown Town":

        return "https://i.imgur.com/zqBPi4L.jpg"

    elif map_name == 'City Under Siege':

        return "https://i.imgur.com/FWs7yBe.jpg"

    elif map_name == "Ghost Factory":

        return "https://i.imgur.com/SfTmUIx.jpg"

    elif map_name == "Graniny Gorki Lab":

        return "https://i.imgur.com/9Nx7X9r.jpg"

    elif map_name == "High Ice":

        return "https://i.imgur.com/hdexoaN.jpg"

    elif map_name == "Killhouse A":

        return "https://i.imgur.com/Cid2W0h.jpg"

    elif map_name == "Killhouse B":

        return "https://i.imgur.com/kHKD9ns.jpg"

    elif map_name == "Killhouse C":

        return "https://i.imgur.com/JHsX0i1.jpg"

    elif map_name == "Lost Forest":

        return "https://i.imgur.com/nCLVMff.jpg"

    elif map_name == "Mountaintop":

        return "https://i.imgur.com/dCQuBaR.jpg"

    elif map_name == "Pillbox Purgatory":

        return "https://i.imgur.com/bBJNsOc.jpg"

    elif map_name == "Svyatogornyj East":

        return "https://i.imgur.com/DOsu6dy.jpg"


def id_and_name_converter(userid_or_name, id_or_name):
    """Takes in either a UserID or Username, then does an API search to find either a UserID if Username was
    provided or a Username if a UserID was provided, then the information is returned"""

    if id_or_name == "name":

        user_info = requests.get(url=f"https://api.mgo1.savemgo.com/api/v1/user/{userid_or_name}").json()["data"]

        name = user_info["display_name"]

        return name

    elif id_or_name == "id":

        user_info = requests.get(url=f"https://api.mgo1.savemgo.com/api/v1/user/search/{userid_or_name}").json()

        user_id = user_info["data"][0]["id"]

        return user_id


@tasks.loop(minutes=10)
async def api_player_count():
    """Every ten minutes, will do an API Search for the current amount of players connected to MGO1, then returns the
    player count for use in the number used in the Discord channels where the bot posts the lobbies to"""

    print("Gathering Player Count")

    global player_count

    response = requests.get(url="https://api.mgo1.savemgo.com/api/v1/lobby/list")
    response.raise_for_status()
    player_count = response.json()["data"][0]["players"]

    print("Updating lobby name")

    for guild_name, channel_id in CHANNEL_IDS.items():
        guild = discord.utils.get(bot.guilds, name=guild_name)
        channel = guild.get_channel(channel_id)

        await channel.edit(name=f"🌐mgo1-lobbies【{player_count}】")


@bot.event
async def on_ready():
    # Purges all messages from all channels the bot posts to, in order to get rid of outdated lobbies

    for guild_name, channel_id in CHANNEL_IDS.items():
        guild = discord.utils.get(bot.guilds, name=guild_name)
        channel = guild.get_channel(channel_id)

        await channel.purge(limit=100)

    print("Start Up Successful")

    # Does a quick API search to check if there are currently online lobbies, if the search doesn't return null,
    # it will retrieve host results and both send lobbies to Discord channels and store the data within the lobby_info
    # dictionary for future reference

    current_lobbies = requests.get(url="https://api.mgo1.savemgo.com/api/v1/games/list").json()["data"]

    if not current_lobbies:

        print("No active lobbies")

    else:

        print("Active lobbies found")

        for game in current_lobbies:

            game_id = game["id"]

            current_match = game["current_round"]

            player_cap = game["options"]["max_players"]
            description = game["options"]["description"].capitalize()

            player_list = []

            for player in game["players"]:

                # Since only the original hosting event from the websocket contains a player name (that of the host)
                # I made this method to search the API with the provided userID to get their name

                player_name = id_and_name_converter(player["user_id"], "name")

                # This was in reference to how MGO1 would accept usernames consisting of only spaces, causing the bot to
                # freak out and mess up the markup to the user's profile on the site due to having no characters to
                # display, so it just strips the spaces out of the name and makes sure it isn't 0 characters long

                if len(player_name.strip()) == 0:

                    print("Well boss, we seem to have detected a no name person, giving them safe name now")

                    # In the event that the user has no visible name, instead of marking up their username so while it
                    # looks like just the player name but links to their profile, the bot instead remarks on this,
                    # marks the players userID for moderation purposes and marks it up, then adds
                    # it to the "player_list"

                    player_name = f"[(No Username Was Found: {player['user_id']})]" \
                                  f"(https://mgo1.savemgo.com/users/{player['user_id']})"

                    player_list.append(player_name)

                else:

                    # Makes a markup of the player's name that links to the player's profile when clicked on

                    player_name = f"[{player_name}](https://mgo1.savemgo.com/users/{player['user_id']})"

                    player_list.append(player_name)

            player_number = len(player_list)

            # This is my new way of handling the player names on the bot, I used to just allocate the vacant player
            # spots as "" so the messages would all be the same size, but I decided this was kinda janky, so I've
            # removed it and replaced it with this method of putting all names in one string with \n so the message will
            # scale to player size and the jank is cut down on

            display_player_list = ""

            for player in player_list:

                display_player_list += f"{player}\n"

            # This is the format of saving information relating to a game, it is saved to the global "lobby_info"
            # dictionary and can be accessed by the using the game id in question the key

            lobby_info[game_id] = {"name": game["options"]["name"],
                                   "map": game["options"]["rules"][current_match]["map_string"].title(),
                                   "mode": game["options"]["rules"][current_match]["mode_string"].title(),
                                   "players": player_list,
                                   "max players": player_cap, "description": description, "player count": player_number}

            # This sets up the embeds for publishing the lobbies to the set discord channels in the .env file

            embed = discord.Embed(title=lobby_info[game_id]["name"],
                                  description=lobby_info[game_id]["description"],
                                  colour=discord.Colour.green(),
                                  url=f"https://mgo1.savemgo.com/games/{game_id}")
            embed.add_field(name="Map", value=f"{lobby_info[game_id]['map']}", inline=True)
            embed.add_field(name="Mode", value=f"{lobby_info[game_id]['mode']}", inline=True)
            embed.add_field(name="", value="", inline=True)
            embed.add_field(name=f"Players {lobby_info[game_id]['player count']}/"
                                 f"{lobby_info[game_id]['max players']}",
                            value=f"{display_player_list}", inline=True)

            # Making use of the "map_photo_generator()" method to retrieve a photo of the current game map

            embed.set_image(url=map_photo_generator(lobby_info[game_id]['map']))
            embed.set_footer(text="Thank you for playing MGO1!")

            # Sends the message to all lobby channels

            for guild_name, channel_id in CHANNEL_IDS.items():
                guild = discord.utils.get(bot.guilds, name=guild_name)

                channel = guild.get_channel(channel_id)

                await channel.send(embed=embed)

    # Sends the message "Kept you waiting huh?" to show it has successfully completed main start up

    for guild_name, channel_id in CHANNEL_IDS.items():
        guild = discord.utils.get(bot.guilds, name=guild_name)

        channel = guild.get_channel(channel_id)

        await channel.send("Kept you waiting huh?")

    api_player_count.start()

    bot.loop.create_task(subscribe_to_game_events())

    websocket_restarter.start()


async def subscribe_to_game_events():
    """Connects to the MGO1 websocket and listens for 5 events, a game being created, a player joining a game,
    a player leaving a game, a game moving on to a new round and a game being deleted.

    This information will then be
    used to send messages to Discord channels listed in the .env file for near live game updates"""

    global websocket_live

    try:

        # This connects to MGO1's websocket sends an initial query to it, requesting to be informed about the events
        # specified in "initial_query['events']"

        async with websockets.connect("wss://api.mgo1.savemgo.com/api/v1/stream/events") as websocket:
            initial_query = {
                "type": "mgo1_bot",
                "events": ["EventGameCreated", "EventGamePlayerJoined", "EventGameNewRound", "EventGamePlayerLeft",
                           "EventGameDeleted"]
            }
            await websocket.send(json.dumps(initial_query))

            # After sending initial query to websocket, it will now listen for any messages from the websocket forever
            # (or until it crashes, whichever comes first lol)
            async for message in websocket:
                print("Received message:", message)
                # Prints a message to the console for future reference
                data = json.loads(message)

                # immediately stores gameID in a variable, due to being needed in every event response

                game_id = data["data"]["game_id"]

                if data["event"] == "game_created":
                    if game_id not in lobby_info:
                        print("New Game Created")

                        # Does a quick API search to gain vital information not provided in the websocket event
                        # message, such as the game's player limit or the game's description

                        response = requests.get(url=f"https://api.mgo1.savemgo.com/api/v1/games/{game_id}").json()[
                            "data"]
                        player_cap = response["options"]["max_players"]
                        description = response["options"]["description"].capitalize()

                        # this is to address that the websocket's message doesn't properly display unicode characters
                        # therefore we convert it to UTF-8 to get the true name of the user (NOTE: Do NOT try this on
                        # API searches, since the API is already UTF-8 and the double conversion has adverse affects)

                        try:

                            host_name = bytes(data["data"]["host"], 'utf-8').decode('unicode_escape')

                        except UnicodeDecodeError:

                            host_name = data["data"]["host"]

                        if len(host_name.strip()) == 0:

                            print("Well boss, we seem to have detected a unnamed person, giving them safe name now")

                            host_name = f"[(No Username Was Found: {response['user_id']})]" \
                                        f"(https://mgo1.savemgo.com/users/{response['user_id']})"

                        else:

                            host_name = data["data"]["host"]

                            host_name = f"[{host_name}](https://mgo1.savemgo.com/users/{response['user_id']})"

                        lobby_info[game_id] = {"name": data["data"]["name"],
                                               "map": data["data"]["rules"][0]["Map"].title(),
                                               "mode": data["data"]["rules"][0]["Mode"].title(),
                                               "players": [host_name],
                                               "max players": player_cap, "description": description, "player count": 1}

                        display_player_list = f"{host_name}\n"

                        embed = discord.Embed(title=lobby_info[game_id]["name"],
                                              description=lobby_info[game_id]["description"],
                                              colour=discord.Colour.green(),
                                              url=f"https://mgo1.savemgo.com/games/{game_id}")
                        embed.add_field(name="Map", value=f"{lobby_info[game_id]['map']}", inline=True)
                        embed.add_field(name="Mode", value=f"{lobby_info[game_id]['mode']}", inline=True)
                        embed.add_field(name="", value="", inline=True)
                        embed.add_field(name=f"Players {lobby_info[game_id]['player count']}/"
                                             f"{lobby_info[game_id]['max players']}",
                                        value=f"{display_player_list}", inline=True)
                        embed.set_image(url=map_photo_generator(lobby_info[game_id]['map']))
                        embed.set_footer(text="Thank you for playing MGO1!")

                        for guild_name, channel_id in CHANNEL_IDS.items():
                            guild = discord.utils.get(bot.guilds, name=guild_name)
                            channel = guild.get_channel(channel_id)

                            await channel.send(embed=embed)

                    else:

                        # Again, more a paranoia measure than an actual risk, but I added this if else because I
                        # worried that if the websocket's connection to the bot weakens, it could send the event more
                        # than once, causing issues, so now, if the GameID is already present in the "lobby_info"
                        # dictionary, it will just ignore it and wait for the next event

                        print(f"Oh shit lol, websocket having a stroke because {game_id}, just endure it")

                elif data["event"] == "game_player_joined":

                    print("Player Joined")

                    # Player name is not provided in websocket response, so using the "id_and_name_converter()" method,
                    # the bot will do a quick API search using the userID to quickly find the associated username and
                    # do the same verification procedures mentioned above

                    player_id = data["data"]["user_id"]

                    player_name = id_and_name_converter(player_id, "name")

                    if len(player_name.strip()) == 0:

                        print("Well boss, we seem to have detected a unnamed, giving them safe name now")

                        player_name = f"[(No Username Was Found: {'player_id'})]" \
                                      f"(https://mgo1.savemgo.com/users/{player_id})"

                        # Adding name to the list of players

                        lobby_info[game_id]["players"].append(player_name)

                    else:

                        player_name = f"[{player_name}](https://mgo1.savemgo.com/users/{player_id})"

                        lobby_info[game_id]["players"].append(player_name)

                    lobby_info[game_id]["player count"] += 1

                    for guild_name, channel_id in CHANNEL_IDS.items():
                        guild = discord.utils.get(bot.guilds, name=guild_name)
                        channel = guild.get_channel(channel_id)

                        await channel.purge(limit=100)

                    # Cycles through every single gameID

                    for key in lobby_info.keys():

                        player_list = lobby_info[key]["players"]

                        display_player_list = ""

                        for player in player_list:

                            display_player_list += f"{player}\n"

                        embed = discord.Embed(title=lobby_info[key]["name"],
                                              description=lobby_info[key]["description"],
                                              colour=discord.Colour.green(),
                                              url=f"https://mgo1.savemgo.com/games/{key}")
                        embed.add_field(name="Map", value=f"{lobby_info[key]['map']}", inline=True)
                        embed.add_field(name="Mode", value=f"{lobby_info[key]['mode']}", inline=True)
                        embed.add_field(name="", value="", inline=True)
                        embed.add_field(name=f"Players {lobby_info[key]['player count']}/"
                                             f"{lobby_info[key]['max players']}",
                                        value=f"{display_player_list}", inline=True)
                        embed.set_image(url=map_photo_generator(lobby_info[key]['map']))
                        embed.set_footer(text="Thank you for playing MGO1!")

                        for guild_name, channel_id in CHANNEL_IDS.items():
                            guild = discord.utils.get(bot.guilds, name=guild_name)
                            channel = guild.get_channel(channel_id)

                            await channel.send(embed=embed)

                elif data["event"] == "game_player_left":

                    print("Player Left")

                    player_id = data["data"]["user_id"]

                    player_name = id_and_name_converter(player_id, "name")

                    if len(player_name.strip()) == 0:

                        print("Player who is leaving is one of the unnamed, fixing immediately")

                        player_name = f"[(No Username Was Found: {player_id})]" \
                                      f"(https://mgo1.savemgo.com/users/{player_id})"

                        # Removing player name from player list

                        lobby_info[game_id]["players"].remove(player_name)

                    else:

                        player_name = f"[{player_name}](https://mgo1.savemgo.com/users/{player_id})"

                        lobby_info[game_id]["players"].remove(player_name)

                    lobby_info[game_id]["player count"] -= 1

                    for guild_name, channel_id in CHANNEL_IDS.items():
                        guild = discord.utils.get(bot.guilds, name=guild_name)
                        channel = guild.get_channel(channel_id)

                        await channel.purge(limit=100)

                    for key in lobby_info.keys():
                        player_list = lobby_info[key]["players"]

                        display_player_list = ""

                        for player in player_list:

                            display_player_list += f"{player}\n"

                        embed = discord.Embed(title=lobby_info[key]["name"],
                                              description=lobby_info[key]["description"],
                                              colour=discord.Colour.green(),
                                              url=f"https://mgo1.savemgo.com/games/{key}")
                        embed.add_field(name="Map", value=f"{lobby_info[key]['map']}", inline=True)
                        embed.add_field(name="Mode", value=f"{lobby_info[key]['mode']}", inline=True)
                        embed.add_field(name="", value="", inline=True)
                        embed.add_field(name=f"Players {lobby_info[key]['player count']}/"
                                             f"{lobby_info[key]['max players']}",
                                        value=f"{display_player_list}", inline=True)
                        embed.set_image(url=map_photo_generator(lobby_info[key]['map']))
                        embed.set_footer(text="Thank you for playing MGO1!")

                        for guild_name, channel_id in CHANNEL_IDS.items():
                            guild = discord.utils.get(bot.guilds, name=guild_name)
                            channel = guild.get_channel(channel_id)

                            await channel.send(embed=embed)

                elif data["event"] == "game_new_round":

                    print("New Round")

                    # Updating game mode and map to the current settings

                    lobby_info[game_id]["map"] = data["data"]["map"].title()
                    lobby_info[game_id]["mode"] = data["data"]["mode"].title()

                    for guild_name, channel_id in CHANNEL_IDS.items():
                        guild = discord.utils.get(bot.guilds, name=guild_name)
                        channel = guild.get_channel(channel_id)

                        await channel.purge(limit=100)

                    for key in lobby_info.keys():

                        player_list = lobby_info[key]["players"]

                        display_player_list = ""

                        for player in player_list:

                            display_player_list += f"{player}\n"

                        embed = discord.Embed(title=lobby_info[key]["name"],
                                              description=lobby_info[key]["description"],
                                              colour=discord.Colour.green(),
                                              url=f"https://mgo1.savemgo.com/games/{key}")
                        embed.add_field(name="Map", value=f"{lobby_info[key]['map']}", inline=True)
                        embed.add_field(name="Mode", value=f"{lobby_info[key]['mode']}", inline=True)
                        embed.add_field(name="", value="", inline=True)
                        embed.add_field(name=f"Players {lobby_info[key]['player count']}/"
                                             f"{lobby_info[key]['max players']}",
                                        value=f"{display_player_list}", inline=True)
                        embed.set_image(url=map_photo_generator(lobby_info[key]['map']))
                        embed.set_footer(text="Thank you for playing MGO1!")

                        for guild_name, channel_id in CHANNEL_IDS.items():
                            guild = discord.utils.get(bot.guilds, name=guild_name)
                            channel = guild.get_channel(channel_id)

                            await channel.send(embed=embed)

                elif data["event"] == "game_deleted":

                    print("Game Deleted")

                    # Removes all information regarding deleted host

                    del lobby_info[game_id]

                    for guild_name, channel_id in CHANNEL_IDS.items():
                        guild = discord.utils.get(bot.guilds, name=guild_name)
                        channel = guild.get_channel(channel_id)

                        await channel.purge(limit=100)

                    for key in lobby_info.keys():

                        player_list = lobby_info[key]["players"]

                        display_player_list = ""

                        for player in player_list:

                            display_player_list += f"{player}\n"

                        embed = discord.Embed(title=lobby_info[key]["name"],
                                              description=lobby_info[key]["description"],
                                              colour=discord.Colour.green(),
                                              url=f"https://mgo1.savemgo.com/games/{key}")
                        embed.add_field(name="Map", value=f"{lobby_info[key]['map']}", inline=True)
                        embed.add_field(name="Mode", value=f"{lobby_info[key]['mode']}", inline=True)
                        embed.add_field(name="", value="", inline=True)
                        embed.add_field(name=f"Players {lobby_info[key]['player count']}/"
                                             f"{lobby_info[key]['max players']}",
                                        value=f"{display_player_list}", inline=True)
                        embed.set_image(url=map_photo_generator(lobby_info[key]['map']))
                        embed.set_footer(text="Thank you for playing MGO1!")

                        for guild_name, channel_id in CHANNEL_IDS.items():
                            guild = discord.utils.get(bot.guilds, name=guild_name)
                            channel = guild.get_channel(channel_id)

                            await channel.send(embed=embed)

    # If anything goes wrong, the try except will catch it, print out a message about the exception, updates the
    # "websocket_live" variable to False, so that it can be restarted by the "websocket_restarter" method later on,
    # while this will catch any exception for stability reasons, the main thing this is designed for is the inevitable
    # disconnection from the websocket, used to be handled by just restarting the bot every 30 minutes, but this is
    # preferable if it works

    except Exception as e:

        print(f"Something went wrong error:{e}")

        websocket_live = False


@tasks.loop(minutes=5)
async def websocket_restarter():
    """In the event that the 'subscribe_to_game_events()' method crashes, this method will restart everything"""
    global websocket_live, lobby_info

    if not websocket_live:

        # Reset lobby info back to nothing to prevent dead hosts from showing up

        lobby_info = {}

        for guild_name, channel_id in CHANNEL_IDS.items():
            guild = discord.utils.get(bot.guilds, name=guild_name)

            channel = guild.get_channel(channel_id)

            await channel.purge(limit=100)

        current_lobbies = requests.get(url="https://api.mgo1.savemgo.com/api/v1/games/list").json()["data"]

        if not current_lobbies:

            print("No active lobbies")

        else:

            print("Active lobbies found")

            for game in current_lobbies:

                game_id = game["id"]

                current_match = game["current_round"]

                player_cap = game["options"]["max_players"]
                description = game["options"]["description"].capitalize()

                player_list = []

                for player in game["players"]:

                    player_name = id_and_name_converter(player["user_id"], "name")

                    if len(player_name.strip()) == 0:

                        print("Well boss, we seem to have detected a no name person, giving them safe name now")

                        player_name = f"[(No Username Was Found: {player['user_id']})](https://mgo1.savemgo.com/users/{player['user_id']})"

                        player_list.append(player_name)

                    else:

                        player_name = f"[{player_name}](https://mgo1.savemgo.com/users/{player['user_id']})"

                        player_list.append(player_name)

                player_number = len(player_list)

                display_player_list = ""

                for player in player_list:

                    display_player_list += f"{player}\n"

                lobby_info[game_id] = {"name": game["options"]["name"],
                                       "map": game["options"]["rules"][current_match]["map_string"].title(),
                                       "mode": game["options"]["rules"][current_match]["mode_string"].title(),
                                       "players": player_list,
                                       "max players": player_cap, "description": description,
                                       "player count": player_number}

                embed = discord.Embed(title=lobby_info[game_id]["name"],
                                      description=lobby_info[game_id]["description"],
                                      colour=discord.Colour.green(),
                                      url=f"https://mgo1.savemgo.com/games/{game_id}")
                embed.add_field(name="Map", value=f"{lobby_info[game_id]['map']}", inline=True)
                embed.add_field(name="Mode", value=f"{lobby_info[game_id]['mode']}", inline=True)
                embed.add_field(name="", value="", inline=True)
                embed.add_field(name=f"Players {lobby_info[game_id]['player count']}/"
                                     f"{lobby_info[game_id]['max players']}",
                                value=f"{display_player_list}", inline=True)
                embed.set_image(url=map_photo_generator(lobby_info[game_id]['map']))
                embed.set_footer(text="Thank you for playing MGO1!")

                for guild_name, channel_id in CHANNEL_IDS.items():
                    guild = discord.utils.get(bot.guilds, name=guild_name)

                    channel = guild.get_channel(channel_id)

                    await channel.send(embed=embed)

            for guild_name, channel_id in CHANNEL_IDS.items():
                guild = discord.utils.get(bot.guilds, name=guild_name)

                channel = guild.get_channel(channel_id)

                await channel.send("Loyalty to the end!")

            bot.loop.create_task(subscribe_to_game_events())

            websocket_live = True

            print("Websocket down, reconnecting")

    else:

        print("Everything is ok")


bot.run(BOT_TOKEN)
