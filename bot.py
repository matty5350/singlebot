import asyncio
import discord
import json
import os
import a2s
import aiomysql
from discord.ext import commands
from ChatBot import ChatBot
from lifstats import fetch_guild_wealth_data, periodic_guildwealth_update
import logging

# ---------------- Logging Setup ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# ---------------- Message Manager ----------------
class MessageManager:
    def __init__(self):
        self.message_cache = {}

    async def delete_old_messages(self, channel, ignore_ids=[]):
        async for message in channel.history(limit=100):
            if message.author == channel.guild.me:
                if message.id not in ignore_ids:
                    try:
                        await message.delete()
                    except discord.NotFound:
                        pass
                    except Exception as e:
                        print(f"Failed to delete message {message.id}: {e}")

    async def send_embedded_message(self, channel, embed):
        message = await channel.send(embed=embed)
        return message

    async def get_or_create_message(self, channel, embed, cache_key):
        if cache_key in self.message_cache:
            try:
                message = self.message_cache[cache_key]
                await message.edit(embed=embed)
                return message
            except discord.NotFound:
                del self.message_cache[cache_key]

        message = await self.send_embedded_message(channel, embed)
        self.message_cache[cache_key] = message
        await self.limit_messages(channel)
        return message

    async def limit_messages(self, channel):
        if len(self.message_cache) > 10:
            oldest_key = next(iter(self.message_cache))
            oldest_message = self.message_cache[oldest_key]
            await oldest_message.delete()
            del self.message_cache[oldest_key]


# ---------------- Server Info Helper ----------------
async def get_server_info(address):
    try:
        ip = address.get('server_ip')
        port = int(address.get('query_port')) if address.get('query_port') else None
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, lambda: a2s.info((ip, port), timeout=5))
        return info.player_count, info.max_players, True
    except asyncio.TimeoutError:
        return 0, 0, False
    except Exception as e:
        logging.error(f"Error fetching server info: {e}")
        return 0, 0, False


# ---------------- Fetch Kill Data ----------------
async def fetch_kills_data(bot_config, bot_name):
    results = []
    try:
        async with aiomysql.connect(
            host=bot_config['database']['database_address'],
            port=int(bot_config['database']['database_port']),
            user=bot_config['database']['database_user'],
            password=bot_config['database']['database_password'],
            db=bot_config['database']['database_name'],
            autocommit=True
        ) as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                query = """
                    SELECT 
                        c.Name, 
                        c.Lastname, 
                        COUNT(CASE 
                                  WHEN d.KillerID = c.ID AND c.GuildID <> victim.GuildID 
                                  THEN 1 
                             END) AS kills,
                        COUNT(CASE 
                                  WHEN d.CharID = c.ID THEN 1 
                             END) AS deaths, 
                        COUNT(CASE 
                                  WHEN d.KillerID = c.ID AND c.GuildID = victim.GuildID 
                                  THEN 1 
                             END) AS team_kills,
                        CASE 
                            WHEN COUNT(CASE WHEN d.CharID = c.ID THEN 1 END) = 0 
                            THEN COUNT(CASE WHEN d.KillerID = c.ID AND c.GuildID <> victim.GuildID THEN 1 END)
                            ELSE ROUND(
                                COUNT(CASE WHEN d.KillerID = c.ID AND c.GuildID <> victim.GuildID THEN 1 END) / 
                                COUNT(CASE WHEN d.CharID = c.ID THEN 1 END), 2
                            ) 
                        END AS kd_ratio
                    FROM 
                        chars_deathlog d
                    JOIN 
                        `character` c ON d.KillerID = c.ID 
                    JOIN 
                        `character` victim ON d.CharID = victim.ID
                    WHERE 
                        d.KillerID <> 4294967294
                    GROUP BY 
                        c.ID, c.Name, c.Lastname
                    ORDER BY 
                        kills DESC
                    LIMIT 10;
                """
                await cursor.execute(query)
                results = await cursor.fetchall()

        logging.info(f"{bot_name} | Kill data fetched successfully.")
        return [
            {
                "name": record["Name"],
                "lastname": record["Lastname"],
                "kills": record["kills"],
                "deaths": record["deaths"],
                "team_kills": record["team_kills"],
                "kd_ratio": record["kd_ratio"]
            }
            for record in results
        ]
    except aiomysql.Error as db_error:
        logging.error(f"{bot_name} | Database error: {db_error}")
        return []
    except Exception as e:
        logging.error(f"{bot_name} | Unexpected error: {e}")
        return []


# ---------------- Bot Setup ----------------
class BotNameFilter(logging.Filter):
    def __init__(self, bot_name):
        super().__init__()
        self.bot_name = bot_name

    def filter(self, record):
        record.bot_name = self.bot_name
        return True


async def setup_discord_bot(message_manager, bot_name, bot_token, bot_config):
    logger = logging.getLogger(bot_name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(f'%(asctime)s - {bot_name} - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

    gateway_logger = logging.getLogger('discord.gateway')
    gateway_logger.addFilter(BotNameFilter(bot_name))

    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True
    intents.message_content = True

    client = commands.Bot(command_prefix="!", intents=intents)
    chat_bot = ChatBot(bot_config.get('active_response_file', 'responses.json'))
    webhooks = bot_config.get('webhooks', {})

    server_status_update_interval = int(webhooks.get('server_status', {}).get('update_interval', 120))
    server_info_update_interval = int(webhooks.get('server_information', {}).get('update_interval', 120))
    server_rules_update_interval = int(webhooks.get('server_rules', {}).get('update_interval', 120))
    killboard_update_interval = int(webhooks.get('killboard', {}).get('update_interval', 120))
    guildwealth_update_interval = int(webhooks.get('guildwealth', {}).get('update_interval', 120))

    @client.event
    async def on_ready():
        logger.info("Bot logged in as %s", client.user)

        try:
            server_status_channel_id = webhooks.get('server_status', {}).get('channel_id')
            server_info_channel_id = webhooks.get('server_information', {}).get('channel_id')
            server_rules_channel_id = webhooks.get('server_rules', {}).get('channel_id')
            killboard_channel_id = webhooks.get('killboard', {}).get('channel_id')
            guildwealth_channel_id = webhooks.get('guildwealth', {}).get('channel_id')

            server_status_channel = client.get_channel(int(server_status_channel_id)) if server_status_channel_id else None
            server_info_channel = client.get_channel(int(server_info_channel_id)) if server_info_channel_id else None
            server_rules_channel = client.get_channel(int(server_rules_channel_id)) if server_rules_channel_id else None
            killboard_channel = client.get_channel(int(killboard_channel_id)) if killboard_channel_id else None
            guildwealth_channel = client.get_channel(int(guildwealth_channel_id)) if guildwealth_channel_id else None

            if not all([server_status_channel, server_info_channel, server_rules_channel, killboard_channel, guildwealth_channel]):
                raise ValueError("One or more channels could not be found.")

            await message_manager.delete_old_messages(server_status_channel)
            await message_manager.delete_old_messages(server_info_channel)
            await message_manager.delete_old_messages(server_rules_channel)
            await message_manager.delete_old_messages(killboard_channel)
            await message_manager.delete_old_messages(guildwealth_channel)

            if webhooks.get('server_status', {}).get('enabled', False):
                client.loop.create_task(periodic_server_status_update(client, server_status_channel, bot_config, message_manager, bot_name, server_status_update_interval))

            if webhooks.get('server_information', {}).get('enabled', False):
                client.loop.create_task(periodic_server_info_update(server_info_channel, bot_config, message_manager, bot_name, server_info_update_interval))

            if webhooks.get('server_rules', {}).get('enabled', False):
                client.loop.create_task(periodic_server_rules_update(server_rules_channel, bot_config, message_manager, bot_name, server_rules_update_interval))

            if webhooks.get('killboard', {}).get('enabled', False):
                client.loop.create_task(periodic_killboard_update(killboard_channel, bot_config, message_manager, bot_name, killboard_update_interval))

            if webhooks.get('guildwealth', {}).get('enabled', False):
                client.loop.create_task(periodic_guildwealth_update(guildwealth_channel, bot_config, message_manager, bot_name, guildwealth_update_interval))

            client.loop.create_task(periodic_presence_update(client, bot_config, 0, bot_name))

        except Exception as e:
            logger.error("Error while setting up bot: %s", e)

    @client.event
    async def on_message(message):
        if message.author.bot:
            return
        response = await chat_bot.handle_message(message)
        if response:
            await message.channel.send(response)
        await client.process_commands(message)

    # ---------------- Periodic Tasks ----------------
    def get_status_message(players_online, max_players, conditionals):
        if players_online is None or max_players is None:
            return "Offline!"
        for condition in conditionals['players']:
            if condition['min'] <= players_online <= condition['max']:
                return f"{players_online}/{max_players}: {condition['message']}"
        return f"{players_online}/{max_players}: Status Unavailable"

    async def update_bot_presence(client, players_online, max_players, conditionals):
        status_message = get_status_message(players_online, max_players, conditionals)
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=status_message))
        logging.info(f"Updated presence: {status_message}")

    async def periodic_presence_update(client, bot_config, stagger_delay, bot_name):
        await client.wait_until_ready()
        while not client.is_closed():
            try:
                players_online, max_players, server_online = await get_server_info({
                    'server_ip': bot_config['server_ip'],
                    'query_port': bot_config['query_port']
                })
                if server_online:
                    await update_bot_presence(client, players_online, max_players, bot_config['conditionals'])
                else:
                    await update_bot_presence(client, None, None, bot_config['conditionals'])
                await asyncio.sleep(60 + stagger_delay)
            except Exception as e:
                logging.error(f"{bot_name} | Presence error: {e}")
                await asyncio.sleep(30)

    async def periodic_server_status_update(client, channel, bot_config, message_manager, bot_name, update_interval):
        await client.wait_until_ready()
        previous_status = None
        while not client.is_closed():
            try:
                players_online, max_players, server_online = await get_server_info({
                    'server_ip': bot_config['server_ip'],
                    'query_port': bot_config['query_port']
                })
                if server_online != previous_status:
                    embed = discord.Embed(title="Server Status", color=0x00FF00 if server_online else 0xFF0000)
                    embed.description = "Server is " + ("Online!" if server_online else "Offline.")
                    image_url = bot_config['webhooks']['server_status'].get(
                        'server_online_image' if server_online else 'server_offline_image'
                    )
                    if image_url:
                        embed.set_image(url=image_url)
                    embed.set_thumbnail(url="https://i.ibb.co/VC2vTMw/botimage.png")
                    await message_manager.get_or_create_message(channel, embed, "status")
                    previous_status = server_online
            except Exception as e:
                print(f"Status update error: {e}")
                await asyncio.sleep(5)
            await asyncio.sleep(update_interval)

    async def periodic_server_info_update(channel, bot_config, message_manager, bot_name, update_interval):
        await client.wait_until_ready()
        previous_info = None
        while not client.is_closed():
            try:
                players_online, max_players, server_online = await get_server_info({
                    'server_ip': bot_config['server_ip'],
                    'query_port': bot_config['query_port']
                })
                current_info = {"players_online": players_online, "max_players": max_players, "server_online": server_online}
                if current_info != previous_info:
                    embed = discord.Embed(title="Server Information", color=0x00FF00 if server_online else 0xFF0000)
                    embed.description = "Server is Online!" if server_online else "Server is Down..."
                    embed.add_field(name="Server Name", value=bot_config.get('server_name', 'Unknown'), inline=False)
                    embed.add_field(name="Server IP", value=bot_config.get('server_ip', 'Unknown'), inline=False)
                    embed.add_field(name="Connect Port", value=bot_config.get('server_port', 'Unknown'), inline=False)
                    embed.add_field(name="Last Wipe", value=bot_config.get('last_wipe', 'Unknown'), inline=False)
                    embed.add_field(name="Next Wipe", value=bot_config.get('next_wipe', 'Unknown'), inline=False)
                    embed.add_field(name="Players Online", value=f"{players_online}/{max_players}", inline=False)
                    embed.add_field(name="Map Name", value=bot_config.get('map_name', 'Unknown'), inline=False)
                    embed.add_field(name="Live Map", value=bot_config.get('livemap', 'None'), inline=False)
                    embed.set_thumbnail(url="https://i.ibb.co/VC2vTMw/botimage.png")
                    if bot_config.get('map_image'):
                        embed.set_image(url=bot_config['map_image'])
                    await message_manager.get_or_create_message(channel, embed, "info")
                    previous_info = current_info
            except Exception as e:
                print(f"Info update error: {e}")
                await asyncio.sleep(500)
            await asyncio.sleep(update_interval)

    async def periodic_server_rules_update(channel, bot_config, message_manager, bot_name, update_interval):
        await client.wait_until_ready()
        while not client.is_closed():
            try:
                current_rules = bot_config.get('rules', [])
                embed = discord.Embed(title="Server Rules", color=0x00FF00)
                embed.description = "\n".join([f"{i+1}. {rule}" for i, rule in enumerate(current_rules)])
                embed.set_thumbnail(url="https://i.ibb.co/VC2vTMw/botimage.png")
                rules_image_url = bot_config['webhooks']['server_rules'].get('rules_image')
                if rules_image_url:
                    embed.set_image(url=rules_image_url)
                await message_manager.get_or_create_message(channel, embed, "rules")
            except Exception as e:
                print(f"Rules update error: {e}")
            await asyncio.sleep(update_interval)

    async def periodic_killboard_update(channel, bot_config, message_manager, bot_name, interval):
        await client.wait_until_ready()
        while not client.is_closed():
            kills_data = await fetch_kills_data(bot_config, bot_name)
            embed = discord.Embed(title=f"{bot_name} Killboard", color=discord.Color.purple())
            for record in kills_data:
                embed.add_field(
                    name=f"{record['name']} {record['lastname']}",
                    value=f"Kills: {record['kills']} | Deaths: {record['deaths']} | TK: {record['team_kills']} | K/D: {record['kd_ratio']:.2f}",
                    inline=False
                )
            embed.set_thumbnail(url="https://i.ibb.co/VC2vTMw/botimage.png")
            killboard_image = bot_config['webhooks']['killboard'].get('killboard_image')
            if killboard_image:
                embed.set_image(url=killboard_image)
            await message_manager.get_or_create_message(channel, embed, "killboard")
            await asyncio.sleep(interval)

    try:
        await client.start(bot_token)
    except Exception as e:
        print(f"Failed to start bot: {e}")
    finally:
        await client.close()
        print(f"{bot_name} | Bot closed.")


# ---------------- Entrypoint ----------------
if __name__ == '__main__':
    async def main():
        bots_directory = 'Bots'
        bot_file = 'bot.json'
        bot_path = os.path.join(bots_directory, bot_file)

        if not os.path.exists(bot_path):
            raise FileNotFoundError(f"Config not found: {bot_path}")

        with open(bot_path, 'r') as f:
            bot_config = json.load(f)

        bot_name = os.path.splitext(bot_file)[0]
        bot_token = bot_config['bot_token']

        message_manager = MessageManager()
        await setup_discord_bot(message_manager, bot_name, bot_token, bot_config)

    asyncio.run(main())
