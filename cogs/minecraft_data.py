import asyncio
from datetime import datetime as dt

import discord
from discord.ext import commands, tasks
import voxelbotutils as utils


class MinecraftData(utils.Cog):

    # https://mcapi.us/server/status?ip=149.202.84.162&port=25588
    MINECRAFT_API = "https://mcapi.us/server/status"
    SERVER_IP = "vfl.mcserver.at"
    SERVER_PORT = 25565
    MINECRAFT_MESSAGE = (716321756171862048, 721771100790325321)  # ChannelID, MessageID

    def __init__(self, bot:utils.Bot):
        super().__init__(bot)
        self.server_status_update.start()

    def cog_unload(self):
        self.server_status_update.cancel()

    @tasks.loop(minutes=10)
    async def server_status_update(self):
        """Updates the Minecraft status message"""

        # Get message
        channel = self.bot.get_channel(self.MINECRAFT_MESSAGE[0])
        message = await channel.fetch_message(self.MINECRAFT_MESSAGE[1])

        # Get data
        async with self.bot.session.get(self.MINECRAFT_API, params={"ip": self.SERVER_IP, "port": self.SERVER_PORT}) as r:
            data = await r.json()

        # Create embed
        with utils.Embed() as embed:
            embed.colour = 0x00ff00 if data['online'] else 0xff0000
            embed.title = f"{self.SERVER_IP}:{self.SERVER_PORT}"
            embed.description = f"Currently running {data['server']['name']}"
            if data['players']['now'] > 0:
                embed.add_field("Currently Online", f"{data['players']['now']}/{data['players']['max']}\n{', '.join(data['players']['list'])}", inline=True)
            else:
                embed.add_field("Currently Online", f"{data['players']['now']}/{data['players']['max']}", inline=True)
            embed.add_field("Uptime", utils.TimeValue(data['duration'] / 1000).clean_spaced)
            embed.timestamp = dt.utcnow()
            embed.set_footer(text="Last updated")
        await message.edit(content=None, embed=embed)

    @server_status_update.before_loop
    async def before_server_status_update(self):
        await self.bot.wait_until_ready()

    @utils.command(aliases=['setminecraftname', 'setmcname', 'setmc', 'setminecraft'])
    @commands.bot_has_permissions(send_messages=True)
    async def setminecraftusername(self, ctx:utils.Context):
        """
        Binds your Minecraft username to your Discord account
        """

        try:
            await ctx.author.send("Open Minecraft, any version. Connect to the server `srv.mc-oauth.net:25565`, and give me the code that comes up.")
        except discord.Forbidden:
            return await ctx.send("I couldn't send you a DM!")
        if ctx.guild:
            await ctx.send("Sent you a DM!")

        # Wait for their message
        try:
            message = await self.bot.wait_for("message", check=lambda m: m.guild is None and m.author.id == ctx.author.id, timeout=60 * 5)
        except asyncio.TimeoutError:
            return await ctx.send("Timed out asking for your Minecraft Oauth code.")

        # Make sure it's right
        async with self.bot.session.get("https://mc-oauth.net/api/api?token", headers={"token": message.content}) as r:
            data = await r.json()
        if data['status'] != 'success':
            return await ctx.author.send("The code you gave is invalid! Please run this command again to provide another.")
        async with self.bot.database() as db:
            await db(
                """INSERT INTO user_settings (user_id, minecraft_username, minecraft_uuid) VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET minecraft_username=excluded.minecraft_username, minecraft_uuid=excluded.minecraft_uuid""",
                ctx.author.id, data['username'], data['uuid'],
            )
        return await ctx.send(f"Linked your Minecraft account **{data['username']}** (`{data['uuid']}`) to your Discord!")

    @utils.command(aliases=['getminecraftname', 'getmcname', 'getmc', 'getminecraft'])
    @commands.bot_has_permissions(send_messages=True)
    async def getminecraftusername(self, ctx:utils.Context, user:discord.Member):
        """
        Gets the Minecraft username for a user
        """

        async with self.bot.database() as db:
            rows = await db(
                """SELECT * FROM user_settings WHERE user_id=$1""", user.id
            )
        if not rows:
            return await ctx.send(f"{user.mention} hasn't linked a Minecraft account to their Discord - run `{ctx.clean_prefix}setminecraftusername` to do so.")
        return await ctx.send(f"{user.mention}'s Minecraft account is **{rows[0]['minecraft_username']}** (`{rows[0]['minecraft_uuid']}`).")


def setup(bot:utils.Bot):
    x = MinecraftData(bot)
    bot.add_cog(x)
