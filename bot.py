import discord
from config.config import TOKEN, CANVAS_API_KEY
import logging
from discord.ext import commands
import helper
from get_assignments import get_new_assignments, datetime_file

#note for me:
# when using python keyword in terminal, u must reference the direct path to the venv python executable.
# don't forget this ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


# BE SURE TO SET REPLICATE API TOKEN TO ENV VARIABLE BEFORE RUNNING

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

# 'intents' specify what events our bot will be able to act on. default events covers a lot of events but
# i make sure to specifically set the 'message_content_ intent to True, bc that's the main intent I will be using

intents = discord.Intents.default()
intents.message_content = True

# instantiate an instance of the Bot class (Bot is a subclass of Client - so it has all the functionality of Client with the addition of Bot functionality
bot = commands.Bot(command_prefix='$', intents=intents)

# remove the default empty help command, so i can replace it with my own
bot.remove_command('help')


# on the event called `on_ready`, python terminal shows that the bot is logged in by printing 
@bot.event
async def on_ready():
    await bot.load_extension("cogs.economy")
    await bot.load_extension("cogs.blackjack")
    await bot.load_extension("cogs.rewards")
    return print(f'I\'m logged in as {bot.user}')

# defines help command. uses bot.group decorator to enable help to take further inputs after help - so that the
# user can specify which command they want clarification on. also set invoke_without_command to True so i can call 'help' as a 
# command by itself  (i think)

@bot.group(invoke_without_command=True)
async def help(ctx):
    em = discord.Embed(title='help', description='to get help with a command, use $help <command>.', color=ctx.author.color)
    em.add_field(name='pic commands', value='`milkies`, `creator`, `dallE`, `findFurry`')
    em.add_field(name='chat commands', value='`heymongrel`, `banmike`, `getNewAssignments`')
    em.add_field(name='blackjack commands', value="`joinQ`, `leaveQ`, `showQ`, `clearQ`, `setBet <amount>`, `playJack`, `resetJack`")
    await ctx.send(embed = em)

# all help commands are defined below

@help.command()
async def heymongrel(ctx):
    em = discord.Embed(title='heymongrel', description='returns a greeting :D')
    await ctx.send(embed = em)

@help.command()
async def milkies(ctx):
    em = discord.Embed(title='milkies', description='try it and find out sweet cheeks ;)')
    await ctx.send(embed = em)

@help.command()
async def creator(ctx):
    em = discord.Embed(title='creator', description='returns a picture perfect recreation of this bot\'s creator')
    await ctx.send(embed = em)

@help.command()
async def banmike(ctx):
    em = discord.Embed(title='banmike', description='use your head. this command bans mike of course :P')
    await ctx.send(embed = em)

@help.command()
async def dallE(ctx):
    em = discord.Embed(title='dallE', description='this command allows users to submit a prompt to Dall-E - then returns the results of their prompt :D')
    em.add_field(name='syntax/how to use', value='`$dallE "your prompt"`')
    await ctx.send(embed = em)

@help.command()
async def findFurry(ctx):
    em = discord.Embed(title='findFurry', description='step right up and use this command to find your buddys\' furry lookalikes! input a name, or input nothing at all.')
    await ctx.send(embed = em)


@help.command()
async def getNewAssignments(ctx):
    em = discord.Embed(title='getNewAssignments', description='takes a number of days as input. function returns all assignments from CSC 221 within given number of days ahead from current day.\n for example `getNewAssignments 15` will return any assignments due in the next 15 days.')
    await ctx.send(embed = em)

@help.command()
async def playJack(ctx):
    em = discord.Embed(title="playJack", description = "begin a game of blackjack. players must first have joined the queue using `joinQ`. players will remain in player queue until they leave.")
    await ctx.send(embed = em)

@help.command()
async def setBet(ctx):
    em = discord.Embed(title="setBet", description = "usage : `setBet <amount>`\nuse this command to bet your valuable GleepCoins in the next gambling game.")
    await ctx.send(embed = em)

@help.command()
async def balance(ctx):
    em = discord.Embed(title="balance", description = "show your GleepCoin bank balance. if nothing comes up, you don't have a balance yet. you will receive 1000 GleepCoins to bet with upon your first bet.")
    await ctx.send(embed = em)

@help.command()
async def joinQ(ctx):
    em = discord.Embed(title="joinQ", description= "join the blackjack players pool with this command.") 
    await ctx.send(embed = em)

@help.command()
async def leaveQ(ctx):
    em = discord.Embed(title="leaveQ", description= "leave the player pool and return any bets you had queued, back to your bank balance.") 
    await ctx.send(embed = em)

@help.command()
async def showQ(ctx):
    em = discord.Embed(title="showQ", description= "shows the player pool") 
    await ctx.send(embed = em)

@help.command()
async def clearQ(ctx):
    em = discord.Embed(title="clearQ", description= "removes all players from player pool, and returns their queued bets to each respective bank balance.") 
    await ctx.send(embed = em)

@help.command()
async def resetJack(ctx):
    em = discord.Embed(title="resetJack", description="use this command to hard reset the blackjack and ecnomoy cogs. (use if blackjack is buggy, it won't hurt anything)")
    await ctx.send(embed = em)
# now these are the actual commands corresponding to the list of commands in help


@bot.command()
async def heymongrel(ctx):
    em = discord.Embed(description='Zah dyood')
    await ctx.send(embed = em)

@bot.command()
async def milkies(ctx):
    await ctx.send(file=discord.File('images/milkies.jpg'))

@bot.command()
async def creator(ctx):
    await ctx.send(file=discord.File('images/gigachad.jpg'))

@bot.command()
async def dallE(ctx, args:str):
    em = discord.Embed()
    em.add_field(name='dallE', value='I\'m working on processing your prompt. This may take a minute.')
    image = helper.get_image(args=args)
    await ctx.send(embed =em, file=discord.File(image))

@bot.command()
async def findFurry(ctx):
    image = helper.get_furry_image()
    await ctx.send(file=discord.File(image))


@bot.command()
async def getNewAssignments(ctx, num:str):
    num = int(num)
    assignments, time_diff = get_new_assignments(datetime_file, num)
    pretty_string = ""
    for item in assignments:
        pretty_string += f"{item}\n"
    if len(assignments) == 0:
        pretty_string = "Yay, no new assignments in that range!"
    
    em = discord.Embed(title="New assignments", description=pretty_string)
    em.add_field(name="Time since last checked: (hours/minutes/seconds)", value=f"{time_diff}")
    await ctx.send(embed = em)


@bot.command()
async def resetJack(ctx):
    await bot.reload_extension("cogs.blackjack")
    await bot.reload_extension("cogs.economy")
    em = discord.Embed(title="Reset blackjack and economy cogs")
    await ctx.send(embed = em)

# @bot.command()
# async def imgTest(ctx):
#     em = discord.Embed()
#     em.add_field(name='dallE', value='I\'m working on processing your prompt. This may take a minute.')
#     image = test.img_test0()
#     await ctx.send(embed = em, file=discord.File(image))



bot.run(TOKEN, log_handler=handler)

