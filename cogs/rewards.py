import pyttsx3
import discord
import asyncio
from discord.ext.commands import Cog
from discord.ext import commands

class Reward(Cog):
    def __init__(self, bot):
        self.bot = bot

    async def processAudio(self, ctx, string):
        engine = pyttsx3.init("sapi5")
        voices = engine.getProperty('voices')
        engine.setProperty("voice", voices[0].id) # 0 for male, 1 for female
        engine.save_to_file(string, "data/test.mp3")
        # default speaking rate is 200
        engine.setProperty("rate", 125)
        engine.runAndWait()
        message = await ctx.send("Processed Request")
        await message.delete(delay = 5.0)

    @commands.command()
    async def say(self, ctx, *args):
        speech = ""
        for arg in args:
            speech += f" {arg}"
        await self.processAudio(ctx, speech)

        current_channel = ctx.author.voice.channel
        voice = await current_channel.connect()
        try:
            audio = discord.FFmpegPCMAudio("data/test.mp3", executable="C:/Program Files/FFmpeg/bin/ffmpeg.exe")
        except:
            print("The audio was not properly stored in memory")
        voice.play(source=audio)
        await asyncio.sleep(10.0)
        await voice.disconnect()

        

async def setup(bot):
   await bot.add_cog(Reward(bot))

