import discord
from discord.ext import commands
from discord.ui import Button, View
import json
import random
import asyncio
import time
import os
import math
from dotenv import load_dotenv
from fuzzywuzzy import fuzz
import pyperclip

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('TOKEN')
PREFIX = os.getenv('PREFIX', '!')
JSON_FILE = 'levels.json'
SCORES_FILE = 'scores.json'

if not TOKEN:
    print("Error: TOKEN not found in .env file.")
    exit()

# --- GLOBAL STATE ---
channel_streaks = {}
active_channels = set()

# --- HELPERS ---

def load_levels():
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def load_scores():
    if os.path.exists(SCORES_FILE):
        try:
            with open(SCORES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}

def save_scores(scores):
    with open(SCORES_FILE, 'w', encoding='utf-8') as f:
        json.dump(scores, f, indent=4)

def update_score(user_id, points_won=0, wins_won=0, current_streak=0):
    scores = load_scores()
    user_id_str = str(user_id)
    
    # Initialize user if they don't exist
    if user_id_str not in scores:
        scores[user_id_str] = {
            "points": 0, 
            "wins": 0, 
            "last_daily": 0, 
            "highest_streak": 0
        }
    
    # Ensure highest_streak key exists for old users
    if "highest_streak" not in scores[user_id_str]:
        scores[user_id_str]["highest_streak"] = 0

    scores[user_id_str]["points"] += points_won
    scores[user_id_str]["wins"] += wins_won
    
    # Check if current streak is a new high score
    if current_streak > scores[user_id_str]["highest_streak"]:
        scores[user_id_str]["highest_streak"] = current_streak

    save_scores(scores)
    return scores[user_id_str]

levels_data = load_levels()

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# --- VIEWS ---
class RetryView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="Start a new game", style=discord.ButtonStyle.secondary)
    async def retry_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await guess_level(self.ctx)
        self.stop()

class LeaderboardView(View):
    def __init__(self, data):
        super().__init__(timeout=60)
        self.data = data
        self.page = 0
        self.per_page = 10
        self.max_page = math.ceil(len(data) / self.per_page) - 1
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = (self.page == 0)
        self.next_button.disabled = (self.page == self.max_page)

    def get_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        current_data = self.data[start:end]
        description_lines = []

        for i, (user_id, stats) in enumerate(current_data, start=start + 1):
            points = stats.get('points', 0)
            if i == 1: emoji = "🥇"
            elif i == 2: emoji = "🥈"
            elif i == 3: emoji = "🥉"
            else: emoji = "🏅"
            user_link = f"https://discord.com/users/{user_id}"
            user_display = stats.get('name', f"User {user_id}")
            line = f"**{i}\\.** {emoji} [{user_display}](<{user_link}>) | {points} Points"
            description_lines.append(line)

        description = "\n".join(description_lines) if description_lines else "No data yet."
        embed = discord.Embed(title="Top Completion", description=description, color=0xFFFFFF)
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/1457054873731334227/1459429057732153527/CompletionTrophy.png")
        embed.set_footer(text=f"Page {self.page + 1}/{self.max_page + 1}")
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: Button):
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

# --- COMMANDS ---

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command(name='shop')
async def shop_command(ctx, *, item_name: str = None):
    shop_items = {
        "time": {"cost": 500, "name": "Time Extension", "type": "buff", "duration": 86400},
        "answer": {"cost": 2000, "name": "Answer Reveal", "type": "consumable"},
        "double": {"cost": 4000, "name": "Double Points", "type": "buff", "duration": 3600},
        "new": {"cost": 4000, "name": "New Level", "type": "consumable"},
        "boost": {"cost": 6000, "name": "Collection Boost", "type": "buff", "duration": 86400},
        "badge": {"cost": 100000, "name": "Profile Badge", "type": "badge"}
    }

    if item_name is None:
        embed = discord.Embed(title="Shop", color=0xFFFFFF)
        embed.add_field(name="<:ShopTime:1459435221018742784> **!shop time** | 500 <:CreatorPoints:1459435109743857861>", value="Get 5 extra seconds every time you start a game in all servers for the next 24 hours.", inline=False)
        embed.add_field(name="<:ShopAnswer:1459435237292642418> **!shop answer** | 2000 <:CreatorPoints:1459435109743857861>", value="Sends an Easy, Medium, or Hard Level, and if no one answers it correctly, the bot says the answer.", inline=False)
        embed.add_field(name="<:ShopDouble:1459435205122326692> **!shop double** | 4000 <:CreatorPoints:1459435109743857861>", value="Earn double Creator Points in this server for the next hour.", inline=False)
        embed.add_field(name="<:ShopNew:1459435179029434418> **!shop new** | 4000 <:CreatorPoints:1459435109743857861>", value="Sends a Level that you do not have in your Collection.", inline=False)
        embed.add_field(name="<:ShopBoost:1459435159081455667> **!shop boost** | 6000 <:CreatorPoints:1459435109743857861>", value="Increases the chance of getting Levels that you do not have in your Collection in all servers for the next 24 hours.", inline=False)
        embed.add_field(name="<:ShopBadge:1459435127959720109> **!shop badge** | 100000 <:CreatorPoints:1459435109743857861>", value="Get a special Badge for your Profile and Leaderboards in this server.", inline=False)
        await ctx.send(embed=embed)
        return

    item_key = item_name.lower()
    if item_key not in shop_items:
        await ctx.send(f"❌ **{item_name}** is not a valid shop item.")
        return

    item_data = shop_items[item_key]
    cost = item_data['cost']
    user_id = str(ctx.author.id)
    scores = load_scores()

    if user_id not in scores:
        scores[user_id] = {"points": 0, "wins": 0, "last_daily": 0}

    if scores[user_id]["points"] < cost:
        embed = discord.Embed(title="You do not have enough Creator Points! 🚫", color=0x2B2D31)
        await ctx.send(embed=embed)
        return

    scores[user_id]["points"] -= cost

    if "buffs" not in scores[user_id]:
        scores[user_id]["buffs"] = {}
    if "badges" not in scores[user_id]:
        scores[user_id]["badges"] = []
    if "inventory" not in scores[user_id]:
        scores[user_id]["inventory"] = {}

    current_time = time.time()
    purchase_msg = ""

    if item_data['type'] == 'buff':
        scores[user_id]["buffs"][item_key] = current_time + item_data['duration']
        purchase_msg = f"Active for the next {int(item_data['duration']/3600)} hours."
    elif item_data['type'] == 'badge':
        if "shop_badge" not in scores[user_id]["badges"]:
            scores[user_id]["badges"].append("shop_badge")
        purchase_msg = "Added to your profile."
    elif item_data['type'] == 'consumable':
        current_count = scores[user_id]["inventory"].get(item_key, 0)
        scores[user_id]["inventory"][item_key] = current_count + 1
        purchase_msg = f"You now have {current_count + 1}."

    save_scores(scores)

    embed = discord.Embed(
        title="Purchase Successful!",
        description=f"You bought **{item_data['name']}** for **{cost}** Creator Points.\n{purchase_msg}\n\nRemaining Balance: {scores[user_id]['points']}",
        color=0x2B2D31
    )
    await ctx.send(embed=embed)

@bot.command(name='daily')
async def daily_command(ctx):
    user_id = str(ctx.author.id)
    scores = load_scores()

    if user_id not in scores:
        scores[user_id] = {"points": 0, "wins": 0, "last_daily": 0}

    last_daily = scores[user_id].get("last_daily", 0)
    current_time = time.time()
    cooldown = 86400

    if current_time - last_daily < cooldown:
        remaining_seconds = cooldown - (current_time - last_daily)
        hours = int(remaining_seconds // 3600)
        minutes = int((remaining_seconds % 3600) // 60)
        time_str = f"{hours} hours" if hours > 0 else f"{minutes} minutes"

        embed = discord.Embed(
            title="You have already claimed your Daily reward in this server! 🚫",
            description=f"You can claim another reward in **{time_str}**.",
            color=0x2B2D31
        )
        await ctx.send(embed=embed)
        return

    reward_points = 25
    scores[user_id]["points"] += reward_points
    scores[user_id]["last_daily"] = current_time
    save_scores(scores)

    embed = discord.Embed(
        title="You claimed your Daily reward!",
        description=f"You earned **{reward_points} Creator Points**.\n\nClaimed by **{ctx.author.display_name}**.",
        color=0x2B2D31
    )
    embed.set_thumbnail(url="https://media.discordapp.net/ephemeral-attachments/1457054873731334227/1459432012011274240/daily.png")
    await ctx.send(embed=embed)

@bot.command(name='top')
async def top_command(ctx):
    scores = load_scores()
    if not scores:
        await ctx.send("No scores recorded yet!")
        return

    sorted_users = sorted(scores.items(), key=lambda item: item[1]['points'], reverse=True)
    final_data = []
    for user_id, stats in sorted_users:
        user = bot.get_user(int(user_id))
        if not user:
            try:
                user = await bot.fetch_user(int(user_id))
            except:
                user = None
        stats['name'] = user.name if user else "Unknown User"
        final_data.append((user_id, stats))

    view = LeaderboardView(final_data)
    await ctx.send(embed=view.get_embed(), view=view)

@bot.command(name='startTPL')
async def guess_level(ctx):
    if ctx.channel.name != 'sparky':
        return
    if ctx.channel.id in active_channels:
        return
    active_channels.add(ctx.channel.id)

    try:
        if not levels_data:
            await ctx.send("Level data is empty. Check levels.json.")
            return

        level = None
        file_path = None
        
        for _ in range(50):
            candidate_level = random.choice(levels_data)
            candidate_path = f"level/{candidate_level['rank']}.png"
            
            if os.path.exists(candidate_path):
                level = candidate_level
                file_path = candidate_path
                break

        if not level:
            await ctx.send("Could not find a level with a valid local thumbnail.")
            return

        answer = level['name']
        print(f"The answer is: {answer}")
        
        try:
            pyperclip.copy(answer.lower()) 
            print(">> Copied to clipboard (lowercase)!")
        except Exception as e:
            print(f">> Failed to copy to clipboard: {e}")

        embed_color = 0x8DD95F
        question_embed = discord.Embed(
            title="Guess the Level!",
            description=f"**Author:** {level['author']}",
            color=embed_color
        )
        
        file = discord.File(file_path, filename="level_image.png")
        question_embed.set_image(url="attachment://level_image.png")
        
        question_message = await ctx.send(embed=question_embed, file=file)

        def check(m):
            return m.channel == ctx.channel and m.author != bot.user

        end_time = time.time() + 30.0

        while True:
            remaining = end_time - time.time()
            if remaining <= 0:
                raise asyncio.TimeoutError

            msg = await bot.wait_for('message', check=check, timeout=remaining)

            guess = msg.content.lower()
            actual = level['name'].lower()

            if fuzz.ratio(guess, actual) > 95:
                base_points = random.randint(3, 8)
                cid = ctx.channel.id
                winner_id = msg.author.id

                if cid not in channel_streaks:
                    channel_streaks[cid] = {'last_winner_id': None, 'streak': 0}

                streak_data = channel_streaks[cid]
                if streak_data['last_winner_id'] == winner_id:
                    streak_data['streak'] *= 2
                else:
                    streak_data['last_winner_id'] = winner_id
                    streak_data['streak'] = 0

                current_streak_index = streak_data['streak']
                display_streak = current_streak_index + 1
                
                multiplier = 1 + (0.30 * current_streak_index)
                final_points = int(base_points * multiplier)

                # Update score and check for high streak
                user_stats = update_score(winner_id, points_won=final_points, wins_won=1, current_streak=display_streak)
                
                total_wins = user_stats['wins']
                total_points = user_stats['points']
                highest_streak = user_stats.get("highest_streak", display_streak)

                success_embed = discord.Embed(
                    title="Congratulations! You guessed the Level correctly!",
                    description=f"You have been awarded {final_points} Creator Points, {msg.author.mention}.\nThis Level has been added to your Collection.",
                    color=embed_color
                )

                footer_text = f"Total Wins: {total_wins} | Total Score: {total_points}"
                
                if current_streak_index > 0:
                    footer_text = f"🔥 Streak: {display_streak} (PB: {highest_streak}) | " + footer_text
                
                success_embed.set_footer(text=footer_text)

                view = RetryView(ctx)
                await msg.reply(embed=success_embed, view=view)
                return

    except asyncio.TimeoutError:
        time_up_embed = discord.Embed(
            title="Time is up!",
            description=f"The level was **{level['name']}**.",
            color=0xFFFFFF
        )
        view = RetryView(ctx)
        await question_message.reply(embed=time_up_embed, view=view)

    finally:
        active_channels.discard(ctx.channel.id)

bot.run(TOKEN)