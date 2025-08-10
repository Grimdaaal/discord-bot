import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import random
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Jetons ---
balances = {}

def get_balance(user_id):
    return balances.get(user_id, 100)  # 100 par défaut

def add_balance(user_id, amount):
    balances[user_id] = get_balance(user_id) + amount

def remove_balance(user_id, amount):
    balances[user_id] = max(0, get_balance(user_id) - amount)

# --- Blackjack ---
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

# --- Blackjack View avec boutons ---
class BlackjackView(View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.has_stood = False
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce n'est pas ta partie !", ephemeral=True)
            return False
        if self.finished:
            await interaction.response.send_message("La partie est terminée.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, button: Button):
        game = blackjack_games.get(self.user_id)
        if not game:
            await interaction.response.edit_message(content="Partie non trouvée.", view=None)
            self.finished = True
            return

        if self.has_stood:
            await interaction.response.send_message("Tu as déjà choisi de rester.", ephemeral=True)
            return

        game['player_hand'].append(game['deck'].pop())
        player_value = calculate_hand_value(game['player_hand'])

        content = f"Tu tires : {game['player_hand'][-1]}\nTes cartes: {', '.join(game['player_hand'])} (Total: {player_value})"

        if player_value > 21:
            content += "\n💥 Tu as dépassé 21, tu perds 😢."
            del blackjack_games[self.user_id]
            self.finished = True
            self.clear_items()
        elif player_value == 21:
            content += "\n🎯 Blackjack ! Clique sur 'Stand' pour finir."
        else:
            content += "\nClique sur Hit pour tirer une carte, Stand pour rester."

        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, button: Button):
        game = blackjack_games.get(self.user_id)
        if not game:
            await interaction.response.edit_message(content="Partie non trouvée.", view=None)
            self.finished = True
            return

        self.has_stood = True
        player_value = calculate_hand_value(game['player_hand'])
        dealer_value = calculate_hand_value(game['dealer_hand'])

        while dealer_value < 17:
            game['dealer_hand'].append(game['deck'].pop())
            dealer_value = calculate_hand_value(game['dealer_hand'])

        content = (
            f"🃏 Dealer a: {', '.join(game['dealer_hand'])} (Total: {dealer_value})\n"
            f"👤 Tes cartes: {', '.join(game['player_hand'])} (Total: {player_value})\n"
        )

        if dealer_value > 21 or player_value > dealer_value:
            gain = game['bet'] * 2
            add_balance(self.user_id, gain)
            content += f"🎉 Tu gagnes {gain} 🪙 !"
        elif dealer_value == player_value:
            add_balance(self.user_id, game['bet'])
            content += "🤝 Égalité, ta mise est rendue."
        else:
            content += "💔 Le dealer gagne."

        del blackjack_games[self.user_id]
        self.finished = True
        self.clear_items()
        await interaction.response.edit_message(content=content, view=None)

# --- Commande Blackjack simplifiée ---
@bot.command(name='blackjack')
async def blackjack(ctx, amount: int = None):
    user_id = ctx.author.id
    if amount is None or amount <= 0:
        await ctx.send("Utilisation : `!blackjack <mise>` avec une mise positive.")
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
        'bet': amount
    }
    remove_balance(user_id, amount)

    player_value = calculate_hand_value(player_hand)
    dealer_show = dealer_hand[0]

    content = (
        f"🎲 Nouvelle partie Blackjack pour {ctx.author.mention} !\n"
        f"💰 Mise : {amount} 🪙\n"
        f"Tes cartes: {', '.join(player_hand)} (Total: {player_value})\n"
        f"Carte visible du dealer: {dealer_show}\n"
        f"Appuie sur les boutons pour jouer."
    )

    view = BlackjackView(user_id)
    await ctx.send(content=content, view=view)

# --- Roulette Modal ---
class RouletteModal(Modal):
    def __init__(self):
        super().__init__(title="Pari Roulette")

        self.mise = TextInput(
            label="Mise (🪙)",
            placeholder="Entrez votre mise",
            min_length=1,
            max_length=10,
            style=discord.TextStyle.short
        )
        self.pari = TextInput(
            label="Pari (pair, impair, ou nombre 0-36)",
            placeholder="Ex: pair, impair, 17",
            min_length=1,
            max_length=5,
            style=discord.TextStyle.short
        )

        self.add_item(self.mise)
        self.add_item(self.pari)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        try:
            mise = int(self.mise.value)
            if mise <= 0:
                await interaction.response.send_message("La mise doit être positive.", ephemeral=True)
                return
        except:
            await interaction.response.send_message("Mise invalide.", ephemeral=True)
            return

        pari = self.pari.value.lower()
        if pari not in ['pair', 'impair'] and not (pari.isdigit() and 0 <= int(pari) <= 36):
            await interaction.response.send_message("Pari invalide, mets 'pair', 'impair' ou un nombre de 0 à 36.", ephemeral=True)
            return

        if get_balance(user_id) < mise:
            await interaction.response.send_message("Tu n'as pas assez de 🪙.", ephemeral=True)
            return

        remove_balance(user_id, mise)
        result = random.randint(0, 36)
        result_parity = 'pair' if result != 0 and result % 2 == 0 else 'impair'
        msg = f"🎡 La roulette tourne... Résultat : **{result}**\n"

        if pari.isdigit():
            if int(pari) == result:
                gain = mise * 3
                add_balance(user_id, gain)
                msg += f"🎉 Bravo {interaction.user.mention}, tu as gagné {gain} 🪙 ! (numéro exact)"
            else:
                msg += f"💔 Dommage {interaction.user.mention}, tu perds {mise} 🪙."
        else:
            if result == 0:
                msg += f"💔 Le zéro sort, tu perds {mise} 🪙."
            elif pari == result_parity:
                gain = mise * 2
                add_balance(user_id, gain)
                msg += f"🎉 Bravo {interaction.user.mention}, tu as gagné {gain} 🪙 ! ({pari})"
            else:
                msg += f"💔 Dommage {interaction.user.mention}, tu perds {mise} 🪙."

        await interaction.response.send_message(msg)

# --- Commande roulette simplifiée ---
@bot.command(name='roulette')
async def roulette(ctx):
    modal = RouletteModal()
    await ctx.send_modal(modal)

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

# --- Commande pour role Directeur gérer jetons ---
@bot.command(name='jetons')
@commands.has_role("𝐃𝐢𝐫𝐞𝐜𝐭𝐞𝐮𝐫")
async def jetons(ctx, member: discord.Member, action: str, amount: int):
    action = action.lower()
    if action not in ['ajouter', 'enlever']:
        await ctx.send("Action invalide : 'ajouter' ou 'enlever' seulement.")
        return
    if amount <= 0:
        await ctx.send("Le montant doit être positif.")
        return

    user_id = member.id
    if action == 'ajouter':
        add_balance(user_id, amount)
        await ctx.send(f"{amount} 🪙 ont été ajoutés à {member.display_name}.")
    else:
        remove_balance(user_id, amount)
        await ctx.send(f"{amount} 🪙 ont été enlevés à {member.display_name}.")

# --- Lancer le bot ---
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if TOKEN is None:
        print("Erreur: La variable d'environnement DISCORD_TOKEN n'est pas définie.")
    else:
        bot.run(TOKEN)
