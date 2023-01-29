import asyncio
import discord
from async_timeout import timeout
from essentials import YTDLSource


class MusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
        This class implements a queue and loop, which allows for different guilds to listen to different playlists
        simultaneously.
        When the bot disconnects from the Voice it's instance will be destroyed.
        """

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'context', 'queue', 'next', 'current', 'np', 'volume')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog
        self.context = ctx

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(10):  # 10 seconds...
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return await self.destroy()

            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(f'Ein Fehler beim Verarbeiten ist aufgetreten.\n'
                                             f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            embed = discord.Embed(title="Jetzt Spielt",
                                  description=f"[{source.title}]({source.web_url}) [{source.requester.mention}]",
                                  color=discord.Color.purple())
            self.np = await self._channel.send(embed=embed)
            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

    async def destroy(self):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self.context.invoke(self.bot.get_command('quit_not_for_user')))
