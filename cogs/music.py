from config.config import GOOGLE_API_KEY, DATA_DIRECTORY, FFMPEG_PATH, WORKING_DIRECTORY
from cogs.controller import Controller
from collections import deque
import asyncio
import helper
import time
import logging
import html

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError # can be thrown when max amount of youtube searches has been met/exceeded
import discord
from discord import Embed
from discord.ext import commands
from mutagen import mp3
import yt_dlp
from youtube_dl import YoutubeDL

# new music specific log
music_handler = logging.FileHandler(f"{WORKING_DIRECTORY}music.log", encoding="utf-8", mode="w")
logger = logging.Logger("music_logger")
logger.addHandler(music_handler)

def getTime() -> str:
    return time.asctime(time.localtime())

#TODO
# current goal: autoplay suggested videos/songs -
    # could extract tags from the video I'm on and perform a search of those tags, return first video
    # users can turn on / turn off autoplay (off by default and turns off whenever mongrel bot leaves voice)
        # when autoplay is turned off, next 5 songs in queue will stay, anything after will be cleared
 
#TODO
# backburner goal:
    # introduce database to handle all the files in 'data' folder. I think this would be a tradeoff between setup difficulty and ease of operating in the long term.
    # honestly, might not be worth it to most operators unless they are serving dozens of servers. either way, it would
    # be good practice for me. I could practice the dependency injection pattern by creating a class, ("FileManager" perhaps?) that is 
    # constructed upon booting the bot - which establishes a database client if DB url/creds are provided, otherwise handles all data in the ParkBot/data/ directory.

    # also, this would be a simple, pythonic way of doing this. I think the more safe way, which could more easily be done in something llike Java, 
    # would be to create an interface, let's call it "DataManager". then create subclasses which implement this interface, such as DBManager and FileManager.
    # then, only use calls to the DataManager interface whenever you need to work with IO operations.

    #pythonic way - the 'interface' would be a DataManager class which defines each method(including its parameters and return type), but doesn't implement them (passing on each method).
    # let classes that want to implement this interface just extend the DataManager class

#TODO
# planned feature : ability to play songs from URls (youtube, spotify, soundcloud) could pretty easily play spotify stuff. their API seems not bad. I think doing this would require me to provide my spotify login tho. and spotify limits to listening on one device so i dont like this idea.
class Song:
    def __init__(self):
        self.played = False
        self.title = None
        self.id = None
        self.slug_title = None
        self.path = None
        self.downloaded = False


    def setData(self, song_title_and_id:tuple) -> None:
        """Pass a tuple of (a video's title, and YouTube ID) as the argument to this method. The Song's title, ID, and path will be set accordingly to this input.\n
        Meant to take the result of the `YoutubeClient.getSearchResults()` method, as an argument."""
        self.title = song_title_and_id[0]
        self.id = song_title_and_id[1]
        self.slug_title = helper.slugify(self.title) + ".mp3"
        self.path = DATA_DIRECTORY + self.slug_title

    def setDownloaded(self) -> None:
        self.downloaded = True

    def isEmpty(self) -> bool:
        """Checks whether the Song contains any data or if its a ghost."""
        if self.id or self.title is None:
            return True
        return False

class PlayList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_song:Song = None 
        self.prev_song:Song = None
        self.playque:deque[Song] = deque()
        self.playhistory = deque(maxlen=5)

    def isEmpty(self) -> bool:
        return len(self.playque) == 0
    
    def add(self, song:Song) -> None:
        self.playque.append(song)

    async def _showQ(self, ctx) -> None:
        # if self.playing is False:
        #     await ctx.send(f"Playing nothing right now.")
        if self.current_song is not None:
            pretty_string = ""
            pretty_string += f"Playing: {self.current_song.title}\n\n"
            count = 1 # skip the first song in playque
            for song in self.playque:
                pretty_string += f"{count}: {song.title}\n"
                count += 1
            await ctx.send(embed = Embed(title=f"Current Queue", description=f"{pretty_string}"))
        else:
            await ctx.send(embed = Embed(title=f"No songs in queue yet."))

    async def _showHistory(self, ctx) -> None:
        if len(self.playhistory) > 1:
            pretty_string = ""
            pretty_string += f"Playing: {self.current_song.title}\n\n"
            playhistory = self.playhistory.copy()
            playhistory.pop() # copy current playhistory, leaving popping off the most recent edition (the current song)
            playhistory_with_index = enumerate(self.playhistory, start=1)

            for index, song in playhistory_with_index: # skip first song in playhistory as this is the current song
                pretty_string += f"{index}: {song.title}\n"
            await ctx.send(embed = Embed(title=f"Recently Played", description=f"{pretty_string}"))
        else:
            await ctx.send(embed = Embed(title=f"No songs have been played yet."))

    async def addToQ(self, ctx, song:Song) -> None:
        """Adds a song to the playque + sends a confirmation message to text chat."""
        self.add(song)
        await ctx.send(embed = Embed(title=f"{song.title} added to queue."))
        return

    def pop(self) -> Song: 
        """Pops the oldest song off the queue, and adds that song to the playhistory queue."""
        removed = self.playque.popleft()
        self.playhistory.append(removed)
        return removed

    def remove(self, song:Song) -> None:
        self.playque.remove(song)

    def getNextSong(self) -> Song | None:
        """Returns the next song in the queue, None if next song doesn't exist."""
        try: 
            return self.playque[1]
        except IndexError:
            return None
    
    def getNextUndownloadedSong(self) -> Song | None:
        queue = self.playque
        count = 0
        while count < len(queue):
            song = queue[count]
            if song.downloaded is False:
                return song
            count += 1
        return None
    
    def getNumDownloadedSongs(self) -> int:
        count = 0
        for song in self.playque:
            if song.downloaded is True:
                count += 1
        return count


class YoutubeClient:
    """
    The YoutubeClient is used to grab resources from youtube, using both the youtube API and ytdl.\n
    It's two methods are used to poll the YouTube API for search results given a query string,\n
    and to download a song given the youtube video ID returned by the previous method."""
    def __init__(self, bot):
        self.bot = bot
        self.downloading = False
        self.service = build('youtube', 'v3', developerKey=GOOGLE_API_KEY)
    
    async def getSearchResults(self, ctx=None, *args, maxResults=1) -> list[tuple[str, str]] | None:
        query = ""
        args = args[0]
        for arg in args:
            query += f"{arg} "

        request = self.service.search().list(
        part='snippet',
        maxResults=int(maxResults),
        q=str(query))

        try:
            response = request.execute() # response is a json object in dict format
            titles_and_ids = []
            for item in response["items"]:
                id = item["id"]["videoId"]
                title = html.unescape(item["snippet"]["title"])
                titles_and_ids.append((title, id))

            if ctx is None:
                return titles_and_ids
        except HttpError as e:
            err_message = f"You have run out of requests to the YouTube API for today. Wait until the next day to get another 100 search requests. Error: {e}"
            if ctx:
                await ctx.send(err_message)
            else:
                logger.error(f"{getTime()}: {err_message}")

    
    def downloadSong(self, song:Song):
        id = str(song.id)
        title = song.title
        base_address = "https://www.youtube.com/watch?v="
        ytdl_format_options = {
            # add an option to limit download size to maybe 20 mb
            "max_filesize": 10000000, # I think this is bytes, so this should be around 10mb (10 mil)
            "no_playlist": True,
            # "max_downloads": 1,
            'format': 'mp3/bestaudio/best',
            "outtmpl": DATA_DIRECTORY + helper.slugify(title) + ".%(ext)s",  
            "ffmpeg_location": FFMPEG_PATH,
            # ℹ️ See help(yt_dlp.postprocessor) for a list of available Postprocessors and their arguments
            'postprocessors': [{  # Extract audio using ffmpeg
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        }

        youtube_url = [base_address + id]
        
        with yt_dlp.YoutubeDL(ytdl_format_options) as ydl:
            ydl.download(youtube_url)
        song.setDownloaded()
        return

class Player(commands.Cog):
    """Class that performs logic pertaining to playing or skipping songs. Constructed with a PlayList and YoutubeClient."""
    def __init__(self, bot, playlist:PlayList, client: YoutubeClient):
        self.playing = False
        self.from_skip = False
        self.bot = bot
        self.playlist = playlist
        self.client = client
        self.voice = None

    def play_next(self, err = None):
        # print(f"***starting play_next method")
        playlist = self.playlist
        self.playing = False
        playlist.prev_song = playlist.current_song
        song_titles_to_save = [song.slug_title for song in playlist.playque]
        helper.deleteSongsBesidesThese(song_titles_to_save)
        logger.info(f"{time.asctime(time.localtime())}: ParkBot songs besides those in this list, {song_titles_to_save}")
        if not playlist.isEmpty():
            if not self.from_skip: # if coming from a skip, don't iterate current song to the next song. (why? current song should be None if coming from a skip.)
                playlist.current_song = playlist.playque[0]
            playlist.pop()
            self.from_skip = False
            next_song = playlist.getNextSong()
            # download next song if its not downloaded
            if (next_song is not None) and (next_song.downloaded is False):
                try: 
                    self.client.downloadSong(next_song)
                except yt_dlp.utils.DownloadError:
                    logger.error(f"{getTime()}: The video you wanted to download was too large. Deleting this song from the queue.")
                    playlist.remove(next_song)
                    helper.cleanupSong(next_song.slug_title)
            # otherwise, pre download a song ahead in the queue after a song is playing
            audio = discord.FFmpegPCMAudio(playlist.current_song.path, executable=FFMPEG_PATH)
            if self.playing is False:
                self.playing = True
                self.voice.play(source = audio, after = self.play_next)
                # check if num of downloaded songs is < 4, if so then download the next undownloaded song.
                preload_song = playlist.getNextUndownloadedSong()
                if preload_song is not None:
                    try:
                        self.client.downloadSong(preload_song)
                    except yt_dlp.utils.DownloadError:
                        logger.error(f"{time.asctime(time.localtime())}: Error preloading the next undownloaded song in play_next method")
                        helper.cleanupSong(preload_song.slug_title)
        elif err:
            logger.error(f"{getTime()}: Error in play_next method: {err}" )
            return
        
    def _play_song(self):
        # print(f"***starting _play_song method")
        playlist = self.playlist
        if not playlist.isEmpty():
            # logger.debug(f"{getTime()}: Playlist is not empty! Contents: {[song.title for song in playlist.playque]}")
            if self.voice.is_playing():
                return
            playlist.current_song = playlist.playque[0]
            playlist.playque.pop()
            song_titles_to_save = [song.slug_title for song in playlist.playque] + [playlist.current_song.slug_title]
            playlist.playhistory.append(playlist.current_song)
            try:
                helper.deleteSongsBesidesThese(song_titles_to_save)
                logger.info(f"{time.asctime(time.localtime())}: ParkBot deleted all songs besides those in this list, {song_titles_to_save}")
            except:
                pass
            # print(f"Loading current song from this path: {playlist.current_song.path}")
            audio = discord.FFmpegPCMAudio(playlist.current_song.path, executable=FFMPEG_PATH)

            if self.playing is False:
                self.playing = True
                # print(f"Attempting to play current song.")
                self.voice.play(source = audio, after = self.play_next)

    #TODO make bot join different voice channel if caller is in different voice channel than bot
    #TODO current song is being handled incorrectly, example: when skipping last song in queue, "showQ" still shows the now skipped song as the current song.
    async def _play(self, ctx, *args) -> None:
        playlist = self.playlist
        new_song = Song()
        # check if user is in a voice channel
        if ctx.author.voice is None:
            await ctx.send(embed=Embed(title=f"Please join a voice channel and try again."))
            return
        song_titles_and_ids = await self.client.getSearchResults(None, args, maxResults=1)
        if song_titles_and_ids is None:
            await ctx.send(embed=Embed(title=f"Search Error", description=f"There was an issue with the results of the search for your song. Please try again, but change your search term slightly."))
            return
        else:
            new_song.setData(song_titles_and_ids[0])
            # make this check in each of the play functions.
            await playlist.addToQ(ctx, new_song)
            if len(playlist.playque) < 4: # download up to 3 songs ahead of time
                try:
                    self.client.downloadSong(new_song)
                    logger.info(f"{time.asctime(time.localtime())}: ParkBot {ctx.guild} instance downloaded a song - {new_song.title}")
                except yt_dlp.utils.DownloadError as e:
                    logger.error(f"{time.asctime(time.localtime())}: ParkBot {ctx.guild} instance had a download Error - {e}", exc_info=True, stack_info=True)
                    await ctx.send(embed=Embed(title="Download Error", description=f"{e}"))
                    playlist.remove(new_song) # removes the song without adding it to playhistory, since it wasn't played
                    helper.cleanupSong(new_song.slug_title)
            # check if there's already a voice connection

            if self.voice is None:
                current_channel = ctx.author.voice.channel
                # create voice connection
                self.voice = await current_channel.connect(timeout = None)
                self._play_song()
                await self.leaveWhenDone(ctx)
            elif self.playing is False: # perhaps use self.voice.is_playing() instead
                # check if bot is in the correct channel
                # if 
                self._play_song()
            else:
                return
    
    async def _skip(self, ctx):
        playlist = self.playlist
        if playlist.current_song is not None:
            await ctx.send(embed=Embed(title=f"Skipping {playlist.current_song.title}."))
            self.voice.stop()
            self.playing = False
            self.from_skip = True
            playlist.current_song = None
            self._play_song()
        # need to be able to skip even if no songs are in queue after the current song.
        else:
            await ctx.send(embed=Embed(title=f"Queue is already empty."))

    async def leaveWhenDone(self, ctx):
        playlist = self.playlist
        print(f"sleeping for 600 seconds before checking if voice is playing")    
        await asyncio.sleep(600.0)
        # this didn't work last time, INVESTIGATE!
        print(f"done sleeping, checking if voice client playing")
        # message = await ctx.send(f"checking if voice client playing")
        # await message.delete(delay=7.0)
        if self.voice is not None:
            if self.voice.is_connected():
                # get the voice channel it's connected to and check the amount of users in the voice channel.
                if not self.voice.is_playing(): # or if len(users in channel) < 2:
                    try:
                        await self.voice.disconnect()
                        await ctx.send(embed=Embed(title=f'Left voice chat due to inactivity.'))
                        self.voice = None
                        playlist.current_song = None
                        return
                    except Exception as e:
                        error_message = await ctx.send(f"Bot was cleared to leave the voice channel, however It was unable to execute this action. Exception: {e}")
                        logger.error(error_message, exc_info=True)
                        await error_message.delete(delay=7.0)
                        return
                elif self.voice.is_playing():
                    await self.leaveWhenDone(ctx)
            elif not self.voice.is_connected():
                print(f"self.voice is already disconnected. setting self.voice to none.")
                playlist.current_song = None
                self.voice = None
                return
        else:
            print(f"self.voice is already None.")
            return

class MusicController(Controller):
    """Class that has top-level control of playing music. The MusicController constructs a PlayList, YoutubeClient,\n
    and Player for each guild the ParkBot is a part of. The `play` and `skip` commands access the appropriate Player instance,\n
    then execute the lower level `_play` or `_skip` commands on the instance. In other words, the MusicController directs users' commands
    to their guild's instance of the ParkBot."""

    # the songs_to_save doesn't 
    def __init__(self, bot):
        logger.info(f"{time.asctime(time.localtime())}: MusicController constructed.")
        super().__init__(bot, PlayList)
        #self.guilds_to_clazzs:dict[discord.Guild, PlayList] - this exists but isnt explicit here
        self.players:dict[PlayList, Player] = {playlist: Player(self.bot, playlist, YoutubeClient(self.bot)) for playlist in self.guilds_to_clazzs.values()}
        self.client = YoutubeClient(bot)
        self.voice = None
        self.playing = False
        self.from_skip = False

    @commands.command()
    async def showGuilds(self, ctx):
        guilds = self.bot.guilds
        string = ""
        for guild in guilds:
            string += f"{guild.name}, "
        await ctx.send(embed=Embed(title="Guilds", description=string))

    @commands.command()
    async def showQ(self, ctx):
        """Gets the playlist associated with the caller's guild, and shows it in a text channel."""
        playlist:PlayList = self.getGuildClazz(ctx)
        await playlist._showQ(ctx)

    @commands.command()
    async def showHistory(self, ctx):
        playlist:PlayList = self.getGuildClazz(ctx)
        await playlist._showHistory(ctx)

    @commands.command()
    async def currentSong(self, ctx):
        playlist:PlayList = self.getGuildClazz(ctx)
        await ctx.send(embed=Embed(title=f"Current Song", description=f"{playlist.current_song.title}"))


    #NOTE - I want to continue experimenting with this later down the line -
    #seems there's some way to play songs without downloading ? not sure
    async def playURL(self, ctx, url):
        author_vc = ctx.author.voice.channel
        if not self.voice:
            self.voice = await author_vc.connect()
        
        with YoutubeDL() as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['formats'][0]['url']
            self.voice.play(discord.FFmpegPCMAudio(audio_url))
 
    @commands.command()
    async def play(self, ctx, *args) -> None:
        """Accesses a guild's Player and attempts to play a song through it."""
        playlist = self.getGuildClazz(ctx)
        player = self.players[playlist]
        await player._play(ctx, args)

    @commands.command()
    async def skip(self, ctx):
        playlist = self.getGuildClazz(ctx)
        player = self.players[playlist]
        await player._skip(ctx)
            
    @commands.command()
    async def kickBot(self, ctx):
        # check whether a voice connection exists in this guild, and terminate it if so
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice is not None:
            if voice.is_connected():
                if voice.is_playing():
                    voice.stop()
                await voice.disconnect()
        self.voice = None
        self.playing = False

    def getAudioLength(self, path_to_audio):
        audio = mp3.MP3(path_to_audio)
        audio = audio.info
        audiolen = int(audio.length)
        return audiolen

    def formatAudioLength(self, audio_length):
        seconds = audio_length % (24 * 3600)
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        return hour, minutes, seconds
    

async def setup(bot):
    await bot.add_cog(MusicController(bot))
        