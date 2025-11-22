import discord
import logging
import aiomysql
import asyncio

async def fetch_guild_wealth_data(bot_config, bot_name):
    """Fetch guild wealth data from the database with additional details."""
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
    g.ID AS GuildID,
    g.Name AS GuildName,
    COUNT(DISTINCT c.AccountID) AS TotalMembers,
    COUNT(DISTINCT c.ID) AS TotalCharacters,
    COALESCE(SUM(movable.TotalWealth), 0) AS TotalGuildWealth, -- Total movable wealth
    COUNT(DISTINCT o.ID) AS TotalOutposts,
    COALESCE(SUM(immovable.TotalWealth), 0) AS TotalUnmovableWealth, -- Total unmovable wealth
    COALESCE(SUM(movable.TotalWealth), 0) + COALESCE(SUM(immovable.TotalWealth), 0) AS TotalWealth -- Combined total wealth
FROM 
    guilds g
LEFT JOIN 
    `character` c ON c.GuildID = g.ID
LEFT JOIN 
    outposts o ON o.OwnerGuildID = g.ID

-- Subquery for calculating movable wealth from character items
LEFT JOIN (
    SELECT 
        c.GuildID,
        SUM(ot.BasePrice) AS TotalWealth
    FROM 
        items i
    JOIN 
        objects_types ot ON i.ObjectTypeID = ot.ID
    JOIN 
        `character` c ON i.ContainerID = c.RootContainerID OR i.ContainerID = c.EquipmentContainerID
    GROUP BY 
        c.GuildID
) AS movable ON movable.GuildID = g.ID

-- Subquery for calculating unmovable wealth from unmovable objects
LEFT JOIN (
    SELECT 
        gl.GuildID,
        SUM(ot2.BasePrice) AS TotalWealth
    FROM 
        unmovable_objects_claims uoc
    JOIN 
        unmovable_objects uo ON uo.ID = uoc.UnmovableObjectID
    JOIN 
        guild_lands gl ON gl.ID = uoc.ClaimID
    LEFT JOIN 
        items i2 ON i2.ContainerID = uo.RootContainerID
    LEFT JOIN 
        objects_types ot2 ON i2.ObjectTypeID = ot2.ID
    GROUP BY 
        gl.GuildID
) AS immovable ON immovable.GuildID = g.ID

-- Additionally calculate movable wealth from items directly associated with guild members
LEFT JOIN (
    SELECT 
        g.ID AS GuildID,
        SUM(ot.BasePrice) AS TotalWealth
    FROM 
        guilds g
    JOIN 
        `character` c ON c.GuildID = g.ID
    JOIN 
        items i ON i.ContainerID = c.RootContainerID OR i.ContainerID = c.EquipmentContainerID
    JOIN 
        objects_types ot ON i.ObjectTypeID = ot.ID
    GROUP BY 
        g.ID
) AS guildMovable ON guildMovable.GuildID = g.ID

GROUP BY 
    g.ID, g.Name
ORDER BY 
    TotalWealth DESC; -- Order by the combined total wealth
                """
                await cursor.execute(query)
                results = await cursor.fetchall()

        logging.info(f"{bot_name} | Guild wealth data fetched successfully.")
        return [
            {
                "guild_id": record["GuildID"],
                "guild_name": record["GuildName"],
                "total_members": record["TotalMembers"],
                "total_characters": record["TotalCharacters"],
                "total_guild_wealth": record["TotalGuildWealth"],
                "total_outposts": record["TotalOutposts"],
                "total_unmovable_wealth": record["TotalUnmovableWealth"],
                "total_wealth": record["TotalWealth"]
            }
            for record in results
        ]
    except aiomysql.Error as db_error:
        logging.error(f"{bot_name} | Database error: {db_error}")
        return []
    except Exception as e:
        logging.error(f"{bot_name} | An unexpected error occurred: {e}")
        return []

async def periodic_guildwealth_update(channel, bot_config, message_manager, bot_name, interval):
    """Periodically update the guild wealth data in the Discord channel with a backoff strategy."""
    max_backoff = 300  # Maximum backoff time in seconds (5 minutes)
    current_interval = interval
    
    try:
        while True:
            try:
                guild_wealth_data = await fetch_guild_wealth_data(bot_config, bot_name)
                embed = discord.Embed(title=f"{bot_name} Guild Wealth Leaderboard", color=discord.Color.gold())

                # Limit to 13 entries
                max_entries = 13
                guild_info_lines = []

                for index, record in enumerate(guild_wealth_data):
                    if index < max_entries:
                        line = (f"**#{index + 1}** | {record['guild_name']} | "
                                f"🏰 **Outposts:** {record['total_outposts']} | "
                                f"🪙 **:** {record['total_wealth']}")
                        if len(line) <= 1024:
                            guild_info_lines.append(line)
                    else:
                        break

                guild_info = "\n".join(guild_info_lines)
                if len(guild_info) > 1024:
                    guild_info = guild_info[:1021] + "..."

                embed.add_field(
                    name="**Top Wealthy Guilds**", 
                    value=guild_info or "No data available.", 
                    inline=False
                )

                wealth_image = bot_config['webhooks']['guildwealth'].get('wealth_image', None)
                if wealth_image:
                    embed.set_image(url=wealth_image)

                await message_manager.get_or_create_message(channel, embed, "guildwealth")
                logging.info(f"{bot_name} | Guild wealth data updated successfully.")

                # Reset backoff interval after successful run
                current_interval = interval

            except asyncio.CancelledError:
                logging.info(f"{bot_name} | Guild wealth update task cancelled.")
                break

            except Exception as e:
                logging.error(f"{bot_name} | Error during guild wealth update: {e}")
                # Increase backoff time after failure, up to the maximum
                current_interval = min(current_interval * 2, max_backoff)
                logging.info(f"{bot_name} | Retrying in {current_interval} seconds after error.")
                
            await asyncio.sleep(current_interval)
    finally:
        logging.info(f"{bot_name} | Guild wealth update loop has exited.")