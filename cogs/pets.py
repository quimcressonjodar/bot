import uuid

import discord
from discord import app_commands
from discord.ext import commands

from config import PET_SHOP, ROLE_SHOP
from database import pets_col
from utils.economy import get_wallet, update_wallet
from views.pet_views import AdventureView, BattleRequestView


class PetsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_response(self, target, content=None, embed=None, ephemeral=False):
        if isinstance(target, discord.Interaction):
            await target.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
        else:
            await target.send(content=content, embed=embed)

    def _build_shop_embed(self, guild: discord.Guild) -> discord.Embed:
        embed = discord.Embed(
            title="🏪 Shop",
            description="🐾 Buy pets for battles\n💎 Buy roles for passive income",
            color=0x3498DB,
        )

        pet_text = ""
        for name, stats in PET_SHOP.items():
            pet_text += (
                f"{stats['emoji']} **{name.capitalize()}**\n"
                f"🪙 {stats['price']:,}\n"
                f"❤️ {stats['hp']} | ⚔️ {stats['damage']}\n\n"
            )
        if pet_text:
            embed.add_field(name="🐾 Pets", value=pet_text, inline=True)

        role_text = ""
        for key, data_shop in ROLE_SHOP.items():
            role = guild.get_role(int(data_shop["role_id"]))
            role_name = role.name if role else key.capitalize()
            role_text += (
                f"{role_name}\n"
                f"🪙 {data_shop['price']:,}\n"
                f"💰 {data_shop['claim']:,}/hour\n\n"
            )
        if role_text:
            embed.add_field(name="💎 Roles", value=role_text, inline=True)

        embed.set_footer(text="/shop buy <pet/role>")
        return embed

    async def _process_shop(self, target, action: str = "view", pet_name: str = None):
        guild = target.guild
        author = target.user if isinstance(target, discord.Interaction) else target.author
        user_id = str(author.id)

        if action.lower() == "view":
            embed = self._build_shop_embed(guild)
            return await self._send_response(target, embed=embed)

        if action.lower() == "buy":
            if not pet_name:
                return await self._send_response(target, content="❌ Please specify a pet or role name.")

            item_key = pet_name.lower()
            balance = get_wallet(user_id)

            if item_key in PET_SHOP:
                pet_data = PET_SHOP[item_key]
                if balance < pet_data["price"]:
                    return await self._send_response(target, content=f"❌ You need 🪙 {pet_data['price']:,}")
                pet_instance = {
                    "pet_id": str(uuid.uuid4()),
                    "type": item_key,
                    "hp": pet_data["hp"],
                    "damage": pet_data["damage"],
                }
                pets_col.update_one({"_id": user_id}, {"$push": {"pets": pet_instance}}, upsert=True)
                update_wallet(user_id, -pet_data["price"])
                embed = discord.Embed(
                    title="🎉 Pet Purchased",
                    description=f"You bought a {pet_data['emoji']} **{item_key.capitalize()}**!",
                    color=0x00FF00,
                )
                return await self._send_response(target, embed=embed)

            if item_key in ROLE_SHOP:
                role_data = ROLE_SHOP[item_key]
                if balance < role_data["price"]:
                    return await self._send_response(target, content=f"❌ You need 🪙 {role_data['price']:,}")
                role = guild.get_role(int(role_data["role_id"]))
                if not role:
                    return await self._send_response(target, content=f"❌ Role ID {role_data['role_id']} not found.")
                if role in author.roles:
                    return await self._send_response(target, content="❌ You already own this role.")
                update_wallet(user_id, -role_data["price"])
                await author.add_roles(role)
                embed = discord.Embed(
                    title="💎 Role Purchased",
                    description=(
                        f"You bought **{role.name}**\n\n"
                        f"Cost: 🪙 {role_data['price']:,}\n"
                        f"Claim: 🪙 {role_data['claim']:,}/hour"
                    ),
                    color=0xF1C40F,
                )
                return await self._send_response(target, embed=embed)

            return await self._send_response(target, content="❌ That pet or role does not exist.")

    @commands.command(name="shop", aliases=["buy"], description="View and buy pets or roles")
    async def shop(self, ctx: commands.Context, action: str = "view", pet_name: str = None):
        await self._process_shop(ctx, action, pet_name)

    @app_commands.command(name="shop", description="View and buy pets or roles")
    @app_commands.describe(
        action="Choose 'view' to see the shop or 'buy' to purchase",
        pet_name="Name of the pet or role to buy",
    )
    async def shop_slash(self, interaction: discord.Interaction, action: str = "view", pet_name: str = None):
        await self._process_shop(interaction, action, pet_name)

    @commands.hybrid_command(name="pets", description="View your pets")
    async def pets(self, ctx: commands.Context):
        data = pets_col.find_one({"_id": str(ctx.author.id)})
        if not data or not data.get("pets"):
            return await ctx.send("❌ You don't own any pets.")
        embed = discord.Embed(title=f"🐾 {ctx.author.display_name}'s Pets", color=0x3498DB)
        for pet in data["pets"]:
            embed.add_field(
                name=f"🐾 {pet['type'].capitalize()}",
                value=f"❤️ HP: {pet['hp']}\n⚔️ Damage: {pet['damage']}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="battle", description="Battle your pet against another member's pet!")
    async def battle(self, ctx: commands.Context, opponent: discord.Member):
        if opponent.bot:
            return await ctx.send("❌ You can't battle a bot!", ephemeral=True)
        if opponent.id == ctx.author.id:
            return await ctx.send("❌ You can't battle yourself!", ephemeral=True)

        user_id = str(ctx.author.id)
        opp_id = str(opponent.id)
        user_pets_data = pets_col.find_one({"_id": user_id})
        opp_pets_data = pets_col.find_one({"_id": opp_id})

        if not user_pets_data or not user_pets_data.get("pets"):
            return await ctx.send("❌ You don't have any pets!")
        if not opp_pets_data or not opp_pets_data.get("pets"):
            return await ctx.send(f"❌ {opponent.display_name} has no pets!")

        embed = discord.Embed(
            title="⚔️ Pet Battle Challenge",
            description=(
                f"{ctx.author.mention} has challenged {opponent.mention} to a pet battle!\n\n"
                "Waiting for response..."
            ),
            color=0xE74C3C,
        )
        view = BattleRequestView(ctx, opponent)
        await ctx.send(content=opponent.mention, embed=embed, view=view)

    @commands.hybrid_command(name="adventures", aliases=["adv"], description="Send your pet on an adventure")
    async def adventures(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_pets = pets_col.find_one({"_id": user_id})
        if not user_pets or not user_pets.get("pets"):
            return await ctx.send("❌ You don't own any pets.", ephemeral=True)
        await ctx.send("🌍 Choose a pet for the adventure:", view=AdventureView(ctx, user_pets["pets"]))


async def setup(bot: commands.Bot):
    await bot.add_cog(PetsCog(bot))
