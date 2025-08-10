import discord
from discord.ext import commands
import random
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

balances = {}

def get_balance(user_id):
    return balances.get(user_id, 100)

def add_balance(user_id, amount):
    balances[user_id] = get_balance(user_id) + amount

def remove_balance(user_id, amount):
    balances[user_id] = max(0, get_balance(user_id) - amount)

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

# --- Interface Blackjack avec Buttons ---

class BlackjackView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce n'est pas ta partie !", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = blackjack_games.get(self.user_id)
        if not game or game['stand']:
            await interaction.response.send_message("Partie terminée ou inexistante.", ephemeral=True)
            return
        deck = game['deck']
        player_hand = game['player_hand']
        player_hand.append(deck.pop())
        player_value = calculate_hand_value(player_hand)

        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="Tes cartes", value=f"{', '.join(player_hand)} (Total: {player_value})", inline=False)

        if player_value > 21:
            del blackjack_games[self.user_id]
            embed.title = "💥 Tu as dépassé 21, tu perds 😢."
            self.stop()
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
            return
        elif player_value == 21:
            embed.title = "🎯 Blackjack ! Tape sur Stand."
        else:
            embed.title = "Blackjack - À toi de jouer."

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = blackjack_games.get(self.user_id)
        if not game:
            await interaction.response.send_message("Partie inexistante.", ephemeral=True)
            return

        game['stand'] = True
        player_hand = game['player_hand']
        dealer_hand = game['dealer_hand']
        deck = game['deck']
        bet = game['bet']

        player_value = calculate_hand_value(player_hand)
        dealer_value = calculate_hand_value(dealer_hand)

        while dealer_value < 17:
            dealer_hand.append(deck.pop())
            dealer_value = calculate_hand_value(dealer_hand)

        embed = interaction.message.embeds[0]
        embed.title = "Fin de la partie Blackjack"
        embed.set_field_at(0, name="Tes cartes", value=f"{', '.join(player_hand)} (Total: {player_value})", inline=False)
        embed.set_field_at(1, name="Cartes du dealer", value=f"{', '.join(dealer_hand)} (Total: {dealer_value})", inline=False)

        if dealer_value > 21 or player_value > dealer_value:
            gain = bet * 2
            add_balance(self.user_id, gain)
            embed.description = f"🎉 Tu gagnes {gain} 🪙 !"
        elif dealer_value == player_value:
            add_balance(self.user_id, bet)
            embed.description = "🤝 Égalité, ta mise est rendue."
        else:
            embed.description = "💔 Le dealer gagne."

        del blackjack_games[self.user_id]

        self.stop()
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

@bot.command(name='blackjack')
async def blackjack(ctx, action: str = None, amount: int = None):
    user_id = ctx.author.id

    if action is None or action.lower() != 'start' or amount is None or amount <= 0:
        await ctx.send("Utilisation : `!blackjack start <mise>` (mise > 0)")
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

    embed = discord.Embed(title="Blackjack - À toi de jouer", color=discord.Color.dark_green())
    embed.add_field(name="Tes cartes", value=f"{', '.join(player_hand)} (Total: {player_value})", inline=False)
    embed.add_field(name="Carte visible du dealer", value=f"{dealer_show}", inline=False)
    embed.set_footer(text=f"Mise : {amount} 🪙")

    view = BlackjackView(user_id)
    await ctx.send(f"{ctx.author.mention}", embed=embed, view=view)

# --- Roulette améliorée avec embed (commande classique) ---
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

    embed = discord.Embed(title="Roulette", color=discord.Color.dark_blue())
    embed.add_field(name="Résultat", value=f"🎡 **{result}**", inline=False)

    if bet_type.isdigit():
        if int(bet_type) == result:
            gain = amount * 3
            add_balance(user_id, gain)
            embed.description = f"🎉 Bravo {ctx.author.mention}, tu as gagné {gain} 🪙 ! (numéro exact)"
        else:
            embed.description = f"💔 Dommage {ctx.author.mention}, tu perds {amount} 🪙."
    else:
        if result == 0:
            embed.description = f"💔 Le zéro sort, tu perds {amount} 🪙."
        elif bet_type == result_parity:
            gain = amount * 2
            add_balance(user_id, gain)
            embed.description = f"🎉 Bravo {ctx.author.mention}, tu as gagné {gain} 🪙 ! ({bet_type})"
        else:
            embed.description = f"💔 Dommage {ctx.author.mention}, tu perds {amount} 🪙."

    await ctx.send(embed=embed)

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

# --- Commande modérateur pour gérer les jetons ---
@bot.command(name="jetons")
@commands.has_role("𝐃𝐢𝐫𝐞𝐜𝐭𝐞𝐮𝐫")
async def jetons(ctx, action: str = None, member: discord.Member = None, amount: int = None):
    if action not in ["add", "remove"]:
        await ctx.send("Usage: `!jetons <add/remove> @membre <montant>`")
        return
    if member is None or amount is None or amount <= 0:
        await ctx.send("Usage: `!jetons <add/remove> @membre <montant>`")
        return

    if action == "add":
        add_balance(member.id, amount)
        await ctx.send(f"✅ Ajouté {amount} 🪙 à {member.display_name}. Nouveau solde : {get_balance(member.id)} 🪙.")
    else:
        remove_balance(member.id, amount)
        await ctx.send(f"✅ Retiré {amount} 🪙 de {member.display_name}. Nouveau solde : {get_balance(member.id)} 🪙.")

@jetons.error
async def jetons_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("❌ Tu dois avoir le rôle **𝐃𝐢𝐫𝐞𝐜𝐭𝐞𝐮𝐫** pour utiliser cette commande.")

# --- Lancer le bot ---
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if TOKEN is None:
        print("Erreur: La variable d'environnement DISCORD_TOKEN n'est pas définie.")
    else:
        bot.run(TOKEN)
