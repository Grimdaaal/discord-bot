import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

balances = {}

def get_balance(user_id):
    return balances.get(user_id, 100)  # 100 jetons par défaut

def add_balance(user_id, amount):
    balances[user_id] = get_balance(user_id) + amount

def remove_balance(user_id, amount):
    balances[user_id] = max(0, get_balance(user_id) - amount)

# Commande Directeur pour ajouter/enlever jetons
@bot.command(name="jetons")
@commands.has_role("𝐃𝐢𝐫𝐞𝐜𝐭𝐞𝐮𝐫")
async def jetons(ctx, member: discord.Member, action: str, amount: int):
    action = action.lower()
    if action not in ("ajouter", "enlever"):
        return await ctx.send("L'action doit être 'ajouter' ou 'enlever'.")
    if amount <= 0:
        return await ctx.send("Le montant doit être positif.")

    if action == "ajouter":
        add_balance(member.id, amount)
        await ctx.send(f"{amount} 🪙 ajoutés à {member.display_name}.")
    else:
        remove_balance(member.id, amount)
        await ctx.send(f"{amount} 🪙 enlevés à {member.display_name}.")

@jetons.error
async def jetons_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("Tu dois avoir le rôle 𝐃𝐢𝐫𝐞𝐜𝐭𝐞𝐮𝐫 pour utiliser cette commande.")

# Solde
@bot.command(name="solde")
async def solde(ctx):
    await ctx.send(f"{ctx.author.mention} tu as {get_balance(ctx.author.id)} 🪙.")

# Leaderboard
@bot.command(name="leaderboard")
async def leaderboard(ctx):
    if not balances:
        return await ctx.send("Aucun joueur enregistré.")
    sorted_bal = sorted(balances.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 **Leaderboard** 🏆\n"
    for i, (uid, bal) in enumerate(sorted_bal, 1):
        member = ctx.guild.get_member(uid)
        if member:
            text += f"{i}. {member.display_name} — {bal} 🪙\n"
    await ctx.send(text)

# Blackjack
def create_deck():
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♠', '♥', '♦', '♣']
    return [rank + suit for rank in ranks for suit in suits]

def calculate_hand_value(hand):
    value = 0
    aces = 0
    for card in hand:
        rank = card[:-1]
        if rank in ['J', 'Q', 'K']:
            value += 10
        elif rank == 'A':
            value += 11
            aces += 1
        else:
            value += int(rank)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value

class BlackjackView(View):
    def __init__(self, ctx, user_id, bet):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.user_id = user_id
        self.bet = bet
        self.deck = create_deck()
        random.shuffle(self.deck)
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce n'est pas ta partie !", ephemeral=True)
            return False
        if self.finished:
            await interaction.response.send_message("La partie est terminée.", ephemeral=True)
            return False
        return True

    def hand_display(self, hand):
        return ", ".join(hand)

    def game_status(self):
        player_value = calculate_hand_value(self.player_hand)
        return f"Tes cartes : {self.hand_display(self.player_hand)} (Total : {player_value})\nCarte visible du dealer : {self.dealer_hand[0]}"

    @discord.ui.button(label="Tirer une carte (Hit)", style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, button: Button):
        self.player_hand.append(self.deck.pop())
        player_value = calculate_hand_value(self.player_hand)

        content = f"Tu tires : {self.player_hand[-1]}\n{self.game_status()}"

        if player_value > 21:
            content += "\n💥 Tu as dépassé 21, tu perds 😢."
            self.finished = True
            self.clear_items()
        elif player_value == 21:
            content += "\n🎯 Blackjack ! Tu peux choisir de rester."
        else:
            content += "\nChoisis Hit pour tirer encore, ou Stand pour rester."

        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(label="Rester (Stand)", style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, button: Button):
        player_value = calculate_hand_value(self.player_hand)
        dealer_value = calculate_hand_value(self.dealer_hand)

        while dealer_value < 17:
            self.dealer_hand.append(self.deck.pop())
            dealer_value = calculate_hand_value(self.dealer_hand)

        content = (
            f"🃏 Cartes du dealer : {self.hand_display(self.dealer_hand)} (Total : {dealer_value})\n"
            f"👤 {self.ctx.author.display_name}, {self.game_status()}\n"
        )

        if dealer_value > 21 or player_value > dealer_value:
            gain = self.bet * 2
            add_balance(self.user_id, gain)
            content += f"🎉 Tu gagnes {gain} 🪙 !"
        elif dealer_value == player_value:
            add_balance(self.user_id, self.bet)  # remise mise
            content += "🤝 Égalité, ta mise est rendue."
        else:
            content += "💔 Le dealer gagne."

        self.finished = True
        self.clear_items()
        await interaction.response.edit_message(content=content, view=None)

@bot.command(name="blackjack")
async def blackjack(ctx, amount: int = None):
    if amount is None or amount <= 0:
        return await ctx.send("Utilisation : `!blackjack <mise>` (mise positive).")

    if get_balance(ctx.author.id) < amount:
        return await ctx.send("Tu n'as pas assez de 🪙.")

    remove_balance(ctx.author.id, amount)
    view = BlackjackView(ctx, ctx.author.id, amount)
    content = (
        f"🎲 Nouvelle partie Blackjack pour {ctx.author.mention} !\n"
        f"💰 Mise : {amount} 🪙\n"
        f"{view.game_status()}\n"
        "Clique sur un bouton pour jouer."
    )
    await ctx.send(content=content, view=view)

# Roulette simple : pari pair ou impair x2 la mise si victoire
class RouletteView(View):
    def __init__(self, ctx, user_id, bet):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.user_id = user_id
        self.bet = bet
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce n'est pas ton jeu !", ephemeral=True)
            return False
        if self.finished:
            await interaction.response.send_message("Le jeu est terminé.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Pair", style=discord.ButtonStyle.blurple)
    async def pair(self, interaction: discord.Interaction, button: Button):
        await self.resolve(interaction, 'pair')

    @discord.ui.button(label="Impair", style=discord.ButtonStyle.gray)
    async def impair(self, interaction: discord.Interaction, button: Button):
        await self.resolve(interaction, 'impair')

    async def resolve(self, interaction: discord.Interaction, choix: str):
        result = random.randint(0, 36)
        result_parity = 'pair' if result != 0 and result % 2 == 0 else 'impair'
        content = f"🎡 La roulette tourne... Résultat : **{result}**\n"

        if result == 0:
            content += f"💔 Le zéro sort, tu perds {self.bet} 🪙."
        elif choix == result_parity:
            gain = self.bet * 2
            add_balance(self.user_id, gain)
            content += f"🎉 Bravo {self.ctx.author.mention}, tu as gagné {gain} 🪙 !"
        else:
            content += f"💔 Dommage {self.ctx.author.mention}, tu perds {self.bet} 🪙."

        self.finished = True
        self.clear_items()
        await interaction.response.edit_message(content=content, view=None)

@bot.command(name="roulette")
async def roulette(ctx, amount: int = None):
    if amount is None or amount <= 0:
        return await ctx.send("Utilisation : `!roulette <mise>` (mise positive).")

    if get_balance(ctx.author.id) < amount:
        return await ctx.send("Tu n'as pas assez de 🪙.")

    remove_balance(ctx.author.id, amount)
    view = RouletteView(ctx, ctx.author.id, amount)
    await ctx.send(f"🎡 Roulette : mise de {amount} 🪙. Choisis Pair ou Impair :", view=view)

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} !")

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("Erreur : variable d'environnement DISCORD_TOKEN non définie.")
    else:
        bot.run(TOKEN)
