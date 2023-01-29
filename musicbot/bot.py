import asyncio
import json
import discord
import itertools
import threading
from discord.ext import commands
from essentials import InvalidVoiceChannel, VoiceConnectionError, YTDLSource
from player import MusicPlayer
from ext import contains, time_to_string, add_list_time


def create_bot(data, token):
    players = {}
    lock = threading.Lock()
    bot_index = contains(data, lambda x: x['token'] == token)

    intents = discord.Intents.default()
    intents.message_content = True
    if 'main' in data[bot_index]:
        bot = commands.Bot(command_prefix='.', description='Bitte funktioniere heiliger MusikBot', intents=intents)
    else:
        bot = commands.Bot(command_prefix='.', description='Bitte funktioniere nicht so heiliger MusikBot',
                           intents=intents,
                           help_command=None)

    async def cleanup(guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del players[guild.id]
        except KeyError:
            pass

    def get_player(ctx):
        """Retrieve the guild player.py, or generate one."""
        try:
            player = players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            players[ctx.guild.id] = player

        return player

    def is_it_for_me(ctx):
        if data[bot_index]['voice_channel_id'] == 0:
            with lock:
                for d in data:
                    if d['token'] != token:
                        if d['voice_channel_id'] == ctx.author.voice.channel.id:
                            return False
                data[bot_index]['in_use'] = True
                data[bot_index]['voice_channel_id'] = ctx.author.voice.channel.id
                return True
        return True if data[bot_index]['voice_channel_id'] == ctx.author.voice.channel.id else False

    @bot.command(name='play', aliases=['sing', 'p'], description="Streamt Musik")
    async def play_(ctx: commands.Context):
        if not is_it_for_me(ctx): return
        """Request a song and add it to the queue.
        This command attempts to join a valid voice channel if the bot is not already in one.
        Uses YTDL to automatically search and retrieve a song.
        Parameters
        ------------
        search: str [Required]
            The song to search and retrieve using YTDL. This could be a simple search, an ID or URL.
        """
        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(connect_)

        player = get_player(ctx)

        # If download is False, source will be a dict which will be used later to regather the stream.
        # If download is True, source will be a discord.FFmpegPCMAudio with a VolumeTransformer.
        search = ctx.message.content.split(' ', 1)[1]
        source = await YTDLSource.create_source(ctx, search=search, loop=bot.loop, download=False)

        player.volume = data[bot_index]['volume'] / 100

        await player.queue.put(source)

    async def connect_(ctx: commands.Context):
        if not is_it_for_me(ctx): return
        """Connect to voice.
        Parameters
        ------------
        channel: discord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voice channel you are in
            will be made.
        This command also handles moving the bot to different channels.
        """
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            embed = discord.Embed(title="",
                                  description="Kein Sprachkanal zum beitreten. Gib ´.join´ ein nachdem du einem Sprachkanal betreten hast",
                                  color=discord.Color.purple())
            await ctx.send(embed=embed)
            raise InvalidVoiceChannel('No channel to join. Please either specify a valid channel or join one.')

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Connecting to channel: <{channel}> timed out.')
        await ctx.message.add_reaction('👍')

    @bot.command(name='pause', description="Pausiert den Song")
    async def pause_(ctx: commands.Context):
        if not is_it_for_me(ctx): return
        """Pause the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            embed = discord.Embed(title="", description="Ich spiele zurzeit nichts ab",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.send("Pausiert ⏸️")

    @bot.command(name='resume', description="Wiedergibt die Musik")
    async def resume_(ctx: commands.Context):
        if not is_it_for_me(ctx): return
        """Resume the currently paused song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="Ich bin mit keinem Sprachkanal verbunden",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)
        elif not vc.is_paused():
            return

        vc.resume()
        await ctx.send("Wiedergeben ⏯️")

    @bot.command(name='skip', aliases=['next'], description="Spielt den nächsten Song in der Warteschlange ab")
    async def skip_(ctx: commands.Context):
        if not is_it_for_me(ctx): return
        """Skip the song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="Ich bin mit keinem Sprachkanal verbunden",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()

    @bot.command(name='remove', aliases=['rm', 'rem'], description="Entfernt bestimmten Song aus der Warteschlange")
    async def remove_(ctx: commands.Context, pos: int = None):
        if not is_it_for_me(ctx): return
        """Removes specified song from queue"""

        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="Ich bin mit keinem Sprachkanal verbunden",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)

        player = get_player(ctx)
        if pos == None:
            player.queue._queue.pop()
        else:
            try:
                s = player.queue._queue[pos - 1]
                del player.queue._queue[pos - 1]
                embed = discord.Embed(title="",
                                      description=f"Entfernt [{s['title']}]({s['webpage_url']}) [{s['requester'].mention}]",
                                      color=discord.Color.purple())
                await ctx.send(embed=embed)
            except:
                embed = discord.Embed(title="", description=f'Konnte keine Song an Position "{pos}" finden',
                                      color=discord.Color.purple())
                await ctx.send(embed=embed)

    @bot.command(name='clear', aliases=['clr', 'cl', 'cr'], description="Löscht die Warteschlange")
    async def clear_(ctx: commands.Context):
        if not is_it_for_me(ctx): return
        """Deletes entire queue of upcoming songs."""

        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="Ich bin mit keinem Sprachkanal verbunden",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)

        player = get_player(ctx)
        player.queue._queue.clear()
        await ctx.send('**Cleared**')

    @bot.command(name='queue', aliases=['q', 'playlist', 'que'], description="Zeigt die Warteschlange")
    async def queue_info(ctx: commands.Context):
        if not is_it_for_me(ctx): return
        """Retrieve a basic queue of upcoming songs."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="Ich bin mit keinem Sprachkanal verbunden",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)

        player = get_player(ctx)
        if player.queue.empty():
            embed = discord.Embed(titcdmtle="", description="Warteschlange ist leer", color=discord.Color.purple())
            return await ctx.send(embed=embed)

        # Grabs the songs in the queue...
        upcoming = list(itertools.islice(player.queue._queue, 0, int(len(player.queue._queue))))
        fmt = '\n'.join(
            f"`{(upcoming.index(_)) + 1}.` [{_['title']}]({_['webpage_url']}) | ` {time_to_string(_['duration'])} Angefragt von: {_['requester']}`\n"
            for _ in upcoming)
        fmt = f"\n__Jetzt Spielt__:\n[{vc.source.title}]({vc.source.web_url}) | ` {time_to_string(vc.source.duration % (24 * 3600))} Angefragt von: {vc.source.requester}`\n\n__Als Nächstes:__\n" + \
              fmt + \
              f"\n**{len(upcoming)} Songs in Warteschlange**" + \
              f"\n**Gesamtdauer der Warteschlange: {time_to_string(add_list_time(upcoming))}**"
        embed = discord.Embed(title=f'Warteschlange für {ctx.guild.name}', description=fmt,
                              color=discord.Color.purple())
        embed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.display_icon)

        await ctx.send(embed=embed)

    @bot.command(name='np', aliases=['song', 'current', 'currentsong', 'playing'],
                 description="Zeigt den aktuell abgespielten Song")
    async def now_playing_(ctx: commands.Context):
        if not is_it_for_me(ctx): return
        """Display information about the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="Ich bin mit keinem Sprachkanal verbunden",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)

        player = get_player(ctx)
        if not player.current:
            embed = discord.Embed(title="", description="Ich spiele zurzeit keine Musik ab",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)

        embed = discord.Embed(title="",
                              description=f"[{vc.source.title}]({vc.source.web_url}) [{vc.source.requester.mention}] | `{time_to_string(vc.source.duration % (24 * 3600))}`",
                              color=discord.Color.purple())
        embed.set_author(icon_url=bot.user.display_avatar, name=f"Jetzt Spielt 🎶")
        await ctx.send(embed=embed)

    @bot.command(name='volume', aliases=['vol', 'v'], description="Ändert die Lautstärke")
    async def change_volume(ctx: commands.Context, *, vol: float = None):
        if not is_it_for_me(ctx): return
        """Change the player.py volume.
        Parameters
        ------------
        volume: float or int [Required]
            The volume to set the player.py to in percentage. This must be between 1 and 100.
        """
        vc = ctx.voice_client

        player = get_player(ctx)

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="Ich bin mit keinem Sprachkanal verbunden",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)

        if not vol:
            embed = discord.Embed(title="", description=f"🔊 **{player.volume * 100}%**",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)

        if not 0 < vol < 101:
            embed = discord.Embed(title="", description="Bitte gebe eine Zahl zwischen 1 und 100 ein",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)

        with lock:
            data[bot_index]['volume'] = vol
            with open('config.json', 'w') as f:
                f.write(json.dumps({'data': data}))

        if vc.source:
            vc.source.volume = vol / 100

        player.volume = vol / 100
        embed = discord.Embed(title="", description=f'**`{ctx.author}`** hat die Lautstärke auf **{vol}% geändert**',
                              color=discord.Color.purple())
        await ctx.send(embed=embed)

    @bot.command(name='leave', aliases=["stop", "dc", "disconnect", "bye", "quit", "l"],
                 description="Stoppt die Musik und verlässt den Sprachkanal")
    async def leave_(ctx: commands.Context):
        if not is_it_for_me(ctx): return
        """Stop the currently playing song and destroy the player.py.
        !Warning!
            This will destroy the player.py assigned to your guild, also deleting any queued songs and settings.
        """
        await ctx.invoke(quit_)

    @bot.command(name='quit_not_for_user', alias=['restart_bot'],
                 help='!!! Falls kaputt !!! --> Startet den Bot neu (also zumindest einen Teil, also ja vielleicht funktioniert der Bot nach diesem Befehl wieder, ansonsten ja, ... sry i guess)')
    async def quit_(ctx: commands.Context):
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="Ich bin mit keinem Sprachkanal verbunden",
                                  color=discord.Color.purple())
            return await ctx.send(embed=embed)

        with lock:
            data[bot_index]['in_use'] = False
            data[bot_index]['voice_channel_id'] = 0

        msg = await ctx.send('**Sprachkanal verlassen**')
        await msg.add_reaction('👋')

        await cleanup(ctx.guild)

    bot.run(token=token)
