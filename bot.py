import discord
from discord.ext import commands
import random
import os
from flask import Flask
from threading import Thread

# --- Mini serveur web pour Replit + UptimeRobot ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Discord actif !"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Bot Discord setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Système de jetons 🪙 ---
balances = {}

def get_balance(user_id):
    return balances.get(user_id, 100)  # Par défaut 100 🪙

def add_balance(user_id, amount):
    balances[user_id] = get_balance(user_id) + amount

def remove_balance(user_id, amount):
    balances[user_id] = max(0, get_balance(user_id) - amount)

# --- Blackjack functions ---
def calculate_hand_value(hand):
    value = 0
    aces = 0
    for card in hand:
        rank = card[:-1]
        if rank in ['J', 'Q', 'K']:
            value += 10
        elif rank == 'A':
            aces += 1
            value += 11
        else:
            value += int(rank)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value

def create_deck():
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♠', '♥', '♦', '♣']
    return [rank + suit for rank in ranks for suit in suits]

blackjack_games = {}

@bot.event
async def on_ready():
    print(f'✅ Connecté en tant que {bot.user} !')

@bot.command(name='blackjack')
async def blackjack(ctx, action: str = None, amount: int = None):
    user_id = ctx.author.id

    if action is None:
        await ctx.send("Utilisation : `!blackjack start <mise>`")
        return

    if action.lower() == "start":
        if amount is None or amount <= 0:
            await ctx.send("Mise invalide.")
            return
        if get_balance(user_id) < amount:
            await ctx.send("Tu n'as pas assez de 🪙.")
            return

        deck = create_deck()
        random.shuffle(deck)
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        blackjack_games[user_id] = {
            'deck': deck,
            'player_hand': player_hand,
            'dealer_hand': dealer_hand,
            'stand': False,
            'bet': amount
        }
        remove_balance(user_id, amount)
        player_value = calculate_hand_value(player_hand)
        dealer_show = dealer_hand[0]
        await ctx.send(
            f"🎲 Nouvelle partie Blackjack pour {ctx.author.mention} !\n"
            f"💰 Mise : {amount} 🪙\n"
            f"Tes cartes: {', '.join(player_hand)} (Total: {player_value})\n"
            f"Carte visible du dealer: {dealer_show}\n"
            f"Tape `!blackjack hit` pour tirer une carte, `!blackjack stand` pour rester."
        )
        return

    if user_id not in blackjack_games:
        await ctx.send("Tu n'as pas de partie en cours.")
        return

    game = blackjack_games[user_id]
    deck = game['deck']
    player_hand = game['player_hand']
    dealer_hand = game['dealer_hand']
    bet = game['bet']

    if action.lower() == 'hit':
        if game['stand']:
            await ctx.send("Tu as déjà choisi de rester.")
            return
        player_hand.append(deck.pop())
        player_value = calculate_hand_value(player_hand)
        await ctx.send(f"Tu tires : {player_hand[-1]}\nTes cartes: {', '.join(player_hand)} (Total: {player_value})")
        if player_value > 21:
            await ctx.send("💥 Tu as dépassé 21, tu perds 😢.")
            del blackjack_games[user_id]
        elif player_value == 21:
            await ctx.send("🎯 Blackjack ! Tape `!blackjack stand`.")
        else:
            await ctx.send("Tape `!blackjack hit` pour tirer une carte, `!blackjack stand` pour rester.")

    elif action.lower() == 'stand':
        game['stand'] = True
        player_value = calculate_hand_value(player_hand)
        dealer_value = calculate_hand_value(dealer_hand)

        while dealer_value < 17:
            dealer_hand.append(deck.pop())
            dealer_value = calculate_hand_value(dealer_hand)

        await ctx.send(
            f"🃏 Dealer a: {', '.join(dealer_hand)} (Total: {dealer_value})\n"
            f"👤 Tes cartes: {', '.join(player_hand)} (Total: {player_value})"
        )

        if dealer_value > 21 or player_value > dealer_value:
            gain = bet * 2
            add_balance(user_id, gain)
            await ctx.send(f"🎉 Tu gagnes {gain} 🪙 !")
        elif dealer_value == player_value:
            add_balance(user_id, bet)
            await ctx.send("🤝 Égalité, ta mise est rendue.")
        else:
            await ctx.send("💔 Le dealer gagne.")

        del blackjack_games[user_id]

# --- Roulette command ---
@bot.command(name='roulette')
async def roulette(ctx, bet_type: str = None, amount: int = None):
    user_id = ctx.author.id

    if bet_type is None or amount is None:
        await ctx.send("Utilisation : `!roulette <pari> <mise>` (pari = 0-36, pair ou impair)")
        return
    if get_balance(user_id) < amount:
        await ctx.send("Tu n'as pas assez de 🪙.")
        return

    bet_type = bet_type.lower()
    if bet_type not in ['pair', 'impair'] and (not bet_type.isdigit() or not (0 <= int(bet_type) <= 36)):
        await ctx.send("Pari invalide.")
        return
    if amount <= 0:
        await ctx.send("Mise invalide.")
        return

    remove_balance(user_id, amount)
    result = random.randint(0, 36)
    result_parity = 'pair' if result != 0 and result % 2 == 0 else 'impair'
    await ctx.send(f"🎡 La roulette tourne... Résultat : **{result}**")

    if bet_type.isdigit():
        if int(bet_type) == result:
            gain = amount * 3
            add_balance(user_id, gain)
            await ctx.send(f"🎉 Bravo {ctx.author.mention}, tu as gagné {gain} 🪙 ! (numéro exact)")
        else:
            await ctx.send(f"💔 Dommage {ctx.author.mention}, tu perds {amount} 🪙.")
    else:
        if result == 0:
            await ctx.send(f"💔 Le zéro sort, tu perds {amount} 🪙.")
        elif bet_type == result_parity:
            gain = amount * 2
            add_balance(user_id, gain)
            await ctx.send(f"🎉 Bravo {ctx.author.mention}, tu as gagné {gain} 🪙 ! ({bet_type})")
        else:
            await ctx.send(f"💔 Dommage {ctx.author.mention}, tu perds {amount} 🪙.")

# --- Commande solde ---
@bot.command(name="solde")
async def solde(ctx):
    await ctx.send(f"{ctx.author.mention} 💰 Tu as {get_balance(ctx.author.id)} 🪙.")

# --- Commande leaderboard ---
@bot.command(name="leaderboard")
async def leaderboard(ctx):
    if not balances:
        await ctx.send("Aucun joueur enregistré.")
        return
    sorted_balances = sorted(balances.items(), key=lambda x: x[1], reverse=True)
    leaderboard_text = "🏆 **Leaderboard** 🏆\n"
    for i, (user_id, coins) in enumerate(sorted_balances, start=1):
        user = ctx.guild.get_member(user_id)
        if user:
            leaderboard_text += f"{i}. {user.display_name} — {coins} 🪙\n"
    await ctx.send(leaderboard_text)

# --- Lancer le bot ---
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv('DISCORD_TOKEN')
    bot.run(TOKEN)import discord
from discord.ext import commands
import random
import os
from flask import Flask
from threading import Thread

# --- Mini serveur web pour Replit + UptimeRobot ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Discord actif !"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Bot Discord setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Système de jetons 🪙 ---
balances = {}

def get_balance(user_id):
    return balances.get(user_id, 100)  # Par défaut 100 🪙

def add_balance(user_id, amount):
    balances[user_id] = get_balance(user_id) + amount

def remove_balance(user_id, amount):
    balances[user_id] = max(0, get_balance(user_id) - amount)

# --- Blackjack functions ---
def calculate_hand_value(hand):
    value = 0
    aces = 0
    for card in hand:
        rank = card[:-1]
        if rank in ['J', 'Q', 'K']:
            value += 10
        elif rank == 'A':
            aces += 1
            value += 11
        else:
            value += int(rank)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value

def create_deck():
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♠', '♥', '♦', '♣']
    return [rank + suit for rank in ranks for suit in suits]

blackjack_games = {}

@bot.event
async def on_ready():
    print(f'✅ Connecté en tant que {bot.user} !')

@bot.command(name='blackjack')
async def blackjack(ctx, action: str = None, amount: int = None):
    user_id = ctx.author.id

    if action is None:
        await ctx.send("Utilisation : `!blackjack start <mise>`")
        return

    if action.lower() == "start":
        if amount is None or amount <= 0:
            await ctx.send("Mise invalide.")
            return
        if get_balance(user_id) < amount:
            await ctx.send("Tu n'as pas assez de 🪙.")
            return

        deck = create_deck()
        random.shuffle(deck)
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        blackjack_games[user_id] = {
            'deck': deck,
            'player_hand': player_hand,
            'dealer_hand': dealer_hand,
            'stand': False,
            'bet': amount
        }
        remove_balance(user_id, amount)
        player_value = calculate_hand_value(player_hand)
        dealer_show = dealer_hand[0]
        await ctx.send(
            f"🎲 Nouvelle partie Blackjack pour {ctx.author.mention} !\n"
            f"💰 Mise : {amount} 🪙\n"
            f"Tes cartes: {', '.join(player_hand)} (Total: {player_value})\n"
            f"Carte visible du dealer: {dealer_show}\n"
            f"Tape `!blackjack hit` pour tirer une carte, `!blackjack stand` pour rester."
        )
        return

    if user_id not in blackjack_games:
        await ctx.send("Tu n'as pas de partie en cours.")
        return

    game = blackjack_games[user_id]
    deck = game['deck']
    player_hand = game['player_hand']
    dealer_hand = game['dealer_hand']
    bet = game['bet']

    if action.lower() == 'hit':
        if game['stand']:
            await ctx.send("Tu as déjà choisi de rester.")
            return
        player_hand.append(deck.pop())
        player_value = calculate_hand_value(player_hand)
        await ctx.send(f"Tu tires : {player_hand[-1]}\nTes cartes: {', '.join(player_hand)} (Total: {player_value})")
        if player_value > 21:
            await ctx.send("💥 Tu as dépassé 21, tu perds 😢.")
            del blackjack_games[user_id]
        elif player_value == 21:
            await ctx.send("🎯 Blackjack ! Tape `!blackjack stand`.")
        else:
            await ctx.send("Tape `!blackjack hit` pour tirer une carte, `!blackjack stand` pour rester.")

    elif action.lower() == 'stand':
        game['stand'] = True
        player_value = calculate_hand_value(player_hand)
        dealer_value = calculate_hand_value(dealer_hand)

        while dealer_value < 17:
            dealer_hand.append(deck.pop())
            dealer_value = calculate_hand_value(dealer_hand)

        await ctx.send(
            f"🃏 Dealer a: {', '.join(dealer_hand)} (Total: {dealer_value})\n"
            f"👤 Tes cartes: {', '.join(player_hand)} (Total: {player_value})"
        )

        if dealer_value > 21 or player_value > dealer_value:
            gain = bet * 2
            add_balance(user_id, gain)
            await ctx.send(f"🎉 Tu gagnes {gain} 🪙 !")
        elif dealer_value == player_value:
            add_balance(user_id, bet)
            await ctx.send("🤝 Égalité, ta mise est rendue.")
        else:
            await ctx.send("💔 Le dealer gagne.")

        del blackjack_games[user_id]

# --- Roulette command ---
@bot.command(name='roulette')
async def roulette(ctx, bet_type: str = None, amount: int = None):
    user_id = ctx.author.id

    if bet_type is None or amount is None:
        await ctx.send("Utilisation : `!roulette <pari> <mise>` (pari = 0-36, pair ou impair)")
        return
    if get_balance(user_id) < amount:
        await ctx.send("Tu n'as pas assez de 🪙.")
        return

    bet_type = bet_type.lower()
    if bet_type not in ['pair', 'impair'] and (not bet_type.isdigit() or not (0 <= int(bet_type) <= 36)):
        await ctx.send("Pari invalide.")
        return
    if amount <= 0:
        await ctx.send("Mise invalide.")
        return

    remove_balance(user_id, amount)
    result = random.randint(0, 36)
    result_parity = 'pair' if result != 0 and result % 2 == 0 else 'impair'
    await ctx.send(f"🎡 La roulette tourne... Résultat : **{result}**")

    if bet_type.isdigit():
        if int(bet_type) == result:
            gain = amount * 3
            add_balance(user_id, gain)
            await ctx.send(f"🎉 Bravo {ctx.author.mention}, tu as gagné {gain} 🪙 ! (numéro exact)")
        else:
            await ctx.send(f"💔 Dommage {ctx.author.mention}, tu perds {amount} 🪙.")
    else:
        if result == 0:
            await ctx.send(f"💔 Le zéro sort, tu perds {amount} 🪙.")
        elif bet_type == result_parity:
            gain = amount * 2
            add_balance(user_id, gain)
            await ctx.send(f"🎉 Bravo {ctx.author.mention}, tu as gagné {gain} 🪙 ! ({bet_type})")
        else:
            await ctx.send(f"💔 Dommage {ctx.author.mention}, tu perds {amount} 🪙.")

# --- Commande solde ---
@bot.command(name="solde")
async def solde(ctx):
    await ctx.send(f"{ctx.author.mention} 💰 Tu as {get_balance(ctx.author.id)} 🪙.")

# --- Commande leaderboard ---
@bot.command(name="leaderboard")
async def leaderboard(ctx):
    if not balances:
        await ctx.send("Aucun joueur enregistré.")
        return
    sorted_balances = sorted(balances.items(), key=lambda x: x[1], reverse=True)
    leaderboard_text = "🏆 **Leaderboard** 🏆\n"
    for i, (user_id, coins) in enumerate(sorted_balances, start=1):
        user = ctx.guild.get_member(user_id)
        if user:
            leaderboard_text += f"{i}. {user.display_name} — {coins} 🪙\n"
    await ctx.send(leaderboard_text)

# --- Lancer le bot ---
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv('GwTKw0pM5AS8bLuik_0ruZhuezpNgD6v3SBVBA')
    bot.run(TOKEN)
