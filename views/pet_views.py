import asyncio
import random
import time

import discord

import state
from config import PET_SHOP, PET_RARITIES, PET_LOOT_PROBABILITIES, ADVENTURE_LOOT, ADVENTURE_EVENTS, FOOD_ITEMS
from database import eco_col, pets_col
from utils.economy import get_user_data
from utils.pets import get_current_hunger, get_pet_state


async def run_adventure(interaction: discord.Interaction, ctx, selected_pet: dict) -> None:
    user_id = str(ctx.author.id)
    user_data = get_user_data(user_id)
    cooldown = 1800
    now = time.time()
    last_adventure = user_data.get("last_adventure", 0)

    if now - last_adventure < cooldown:
        next_adv_ts = int(last_adventure + cooldown)
        return await interaction.response.send_message(
            f"⏳ Your pets are resting. Try again <t:{next_adv_ts}:R>.", ephemeral=True
        )

    pet_type = selected_pet["type"]
    rarity = PET_RARITIES.get(pet_type, "basic")
    chances = PET_LOOT_PROBABILITIES.get(
        pet_type.lower(), {"common": 80, "rare": 15, "epic": 4, "legendary": 1}
    )

    roll = random.randint(1, 100)
    cumulative = 0
    loot_rarity = "common"
    for r, chance in chances.items():
        cumulative += chance
        if roll <= cumulative:
            loot_rarity = r
            break

    item_name, item_value = random.choice(ADVENTURE_LOOT[loot_rarity])

    bonus_multiplier = {"basic": 1, "rare": 1.5, "epic": 2, "legendary": 4}
    final_value = int(item_value * bonus_multiplier[rarity])
    
    _, penalties = get_pet_state(selected_pet)
    if penalties.get("xp_penalty"):
        final_value = int(final_value * (1 - penalties["xp_penalty"]))

    eco_col.update_one(
        {"_id": user_id},
        {
            "$push": {"inventory": {"name": item_name, "value": final_value, "rarity": loot_rarity}},
            "$set": {"last_adventure": now},
        },
        upsert=True,
    )

    event_text = random.choice(ADVENTURE_EVENTS[loot_rarity])
    rarity_colors = {
        "common": 0x95A5A6,
        "rare": 0x3498DB,
        "epic": 0x9B59B6,
        "legendary": 0xF1C40F,
        "godly": 0xFF00FF,
    }
    pet_emoji = PET_SHOP[pet_type]["emoji"]
    next_adv_ts = int(now + cooldown)

    embed = discord.Embed(title="🌍 Pet Adventure", color=rarity_colors[loot_rarity])
    embed.description = (
        f"{pet_emoji} Your **{pet_type}** {event_text}...\n\n"
        f"🎁 It discovered:\n"
        f"## {item_name}\n\n"
        f"💰 Sold for: 🪙 **{final_value:,}**\n\n"
        f"🌍 Your pet can adventure again <t:{next_adv_ts}:R>."
    )
    embed.add_field(name="✨ Loot Rarity", value=loot_rarity.capitalize())
    embed.add_field(name="🐾 Pet Rarity", value=rarity.capitalize())

    await interaction.response.edit_message(content=None, embed=embed, view=None)


async def start_pet_battle(channel, battle_id: str) -> None:
    battle = state.active_battles[battle_id]
    challenger = battle["challenger"]
    opponent = battle["opponent"]
    user_id = str(challenger.id)
    opp_id = str(opponent.id)
    user_pet = battle["challenger_pet"]
    opp_pet = battle["opponent_pet"]

    battle_msg = await channel.send(
        f"⚔️ **BATTLE INITIATED!**\n"
        f"{challenger.mention} ({user_pet['type']}) VS {opponent.mention} ({opp_pet['type']})"
    )

    animation_frames = [
        f"⚔️ **FIGHTING!**\n{user_pet['type'].capitalize()} lunges forward...\n`[▬▬▬       ] 30%`",
        f"⚔️ **FIGHTING!**\n{opp_pet['type'].capitalize()} strikes back hard!\n`[▬▬▬▬▬▬    ] 60%`",
        f"⚔️ **CLASHING!**\nDust is everywhere...\n`[▬▬▬▬▬▬▬▬▬ ] 99%`",
    ]
    for frame in animation_frames:
        await asyncio.sleep(1.2)
        await battle_msg.edit(content=frame)

    # Apply penalties
    _, c_penalties = get_pet_state(user_pet)
    _, o_penalties = get_pet_state(opp_pet)

    user_damage = user_pet["damage"]
    if c_penalties.get("damage_penalty"):
        user_damage = int(user_damage * (1 - c_penalties["damage_penalty"]))

    opp_damage = opp_pet["damage"]
    if o_penalties.get("damage_penalty"):
        opp_damage = int(opp_damage * (1 - o_penalties["damage_penalty"]))

    user_power = user_pet["hp"] + user_damage + random.randint(1, 50)
    opp_power = opp_pet["hp"] + opp_damage + random.randint(1, 50)
    bet_amount = random.randint(15000, 30000)

    if user_power >= opp_power:
        winner, loser = challenger, opponent
        winner_id, loser_id = user_id, opp_id
        winner_pet, loser_pet = user_pet, opp_pet
    else:
        winner, loser = opponent, challenger
        winner_id, loser_id = opp_id, user_id
        winner_pet, loser_pet = opp_pet, user_pet

    eco_col.update_one({"_id": winner_id}, {"$inc": {"wallet": bet_amount}}, upsert=True)
    eco_col.update_one({"_id": loser_id}, {"$inc": {"wallet": -bet_amount}}, upsert=True)

    from utils.economy import get_user_data as _get
    winner_data = _get(winner_id)
    loser_data = _get(loser_id)

    embed = discord.Embed(
        title="🏆 BATTLE RESULTS",
        description="The dust settles, and a victor emerges...",
        color=0xFFD700,
    )
    embed.add_field(
        name=f"👑 WINNER: {winner.display_name}",
        value=(
            f"**Pet:** {winner_pet['type'].capitalize()}\n"
            f"**Earned:** 🪙 {bet_amount:,}\n"
            f"**New Balance:** 🪙 {winner_data['wallet']:,}"
        ),
        inline=False,
    )
    embed.add_field(
        name=f"💀 LOSER: {loser.display_name}",
        value=(
            f"**Pet:** {loser_pet['type'].capitalize()}\n"
            f"**Lost:** 🪙 {bet_amount:,}\n"
            f"**New Balance:** 🪙 {loser_data['wallet']:,}"
        ),
        inline=False,
    )
    if loser_data["wallet"] < 0:
        embed.set_footer(text="📉 Bankrupt! The loser is now in crippling debt.")

    await asyncio.sleep(1)
    await battle_msg.edit(content="🛑 **The battle is over!**", embed=embed)
    del state.active_battles[battle_id]


class AdventurePetSelect(discord.ui.Select):
    def __init__(self, ctx, pets):
        self.ctx = ctx
        self.pets = pets

        options = []
        for pet in pets:
            pet_type = pet["type"]
            emoji = PET_SHOP[pet_type]["emoji"]
            rarity = PET_RARITIES.get(pet_type, "basic").capitalize()
            options.append(
                discord.SelectOption(
                    label=pet_type.capitalize(),
                    description=f"{rarity} Pet",
                    emoji=emoji,
                    value=pet_type,
                )
            )

        super().__init__(
            placeholder="Choose a pet for the adventure...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_pet_type = self.values[0]
        selected_pet = next(p for p in self.pets if p["type"] == selected_pet_type.lower())
        
        hunger = get_current_hunger(selected_pet)
        if hunger < 30:
            return await interaction.response.send_message("😿 Your pet is too weak and needs food before it can participate.", ephemeral=True)
            
        await run_adventure(interaction, self.ctx, selected_pet)


class AdventureView(discord.ui.View):
    def __init__(self, ctx, pets):
        super().__init__(timeout=60)
        self.add_item(AdventurePetSelect(ctx, pets))


class PetBattleSelect(discord.ui.Select):
    def __init__(self, user, pets, battle_id: str, role: str):
        self.user = user
        self.pets = pets
        self.battle_id = battle_id
        self.role = role

        options = []
        for pet in pets:
            pet_type = pet["type"]
            emoji = PET_SHOP[pet_type]["emoji"]
            options.append(
                discord.SelectOption(
                    label=pet_type.capitalize(),
                    emoji=emoji,
                    value=pet_type,
                )
            )

        super().__init__(
            placeholder="Choose your pet...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                "❌ This selection isn't for you.", ephemeral=True
            )

        selected_pet = next(p for p in self.pets if p["type"] == self.values[0])
        
        hunger = get_current_hunger(selected_pet)
        if hunger < 30:
            return await interaction.response.send_message("😿 Your pet is too weak and needs food before it can participate.", ephemeral=True)

        battle = state.active_battles[self.battle_id]
        battle[self.role] = selected_pet

        await interaction.response.send_message(
            f"✅ Selected {selected_pet['type'].capitalize()}!", ephemeral=True
        )

        if battle["challenger_pet"] and battle["opponent_pet"]:
            await start_pet_battle(interaction.channel, self.battle_id)


class PetBattleSelectView(discord.ui.View):
    def __init__(self, ctx, opponent, challenger_pets, opponent_pets, battle_id: str):
        super().__init__(timeout=60)
        self.add_item(PetBattleSelect(ctx.author, challenger_pets, battle_id, "challenger_pet"))
        self.add_item(PetBattleSelect(opponent, opponent_pets, battle_id, "opponent_pet"))


class BattleRequestView(discord.ui.View):
    def __init__(self, ctx, opponent):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.opponent = opponent

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message(
                "❌ This battle request isn't for you.", ephemeral=True
            )

        challenger_pets = pets_col.find_one({"_id": str(self.ctx.author.id)})["pets"]
        opponent_pets = pets_col.find_one({"_id": str(self.opponent.id)})["pets"]
        battle_id = f"{self.ctx.author.id}-{self.opponent.id}"

        state.active_battles[battle_id] = {
            "challenger": self.ctx.author,
            "opponent": self.opponent,
            "challenger_pet": None,
            "opponent_pet": None,
        }

        view = PetBattleSelectView(
            self.ctx, self.opponent, challenger_pets, opponent_pets, battle_id
        )
        embed = discord.Embed(
            title="🐾 Choose Your Battle Pets",
            description=(
                f"{self.ctx.author.mention} and {self.opponent.mention}\n\n"
                "Both players must choose a pet."
            ),
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message(
                "❌ This battle request isn't for you.", ephemeral=True
            )
        await interaction.response.edit_message(content="❌ Battle declined.", embed=None, view=None)


class ShopView(discord.ui.View):
    def __init__(self, ctx, pet_shop, role_shop):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.pet_shop = pet_shop
        self.role_shop = role_shop
        self.page = "pets"  # "pets", "roles", or "food"
        self.pet_subpage = 0
        self.pets_per_page = 15

    def _build_embed(self, guild):
        if self.page == "pets":
            embed = discord.Embed(
                title="🏪 Pet Shop",
                description="🐾 Buy pets for battles and adventures!",
                color=0x3498DB
            )
            
            pet_items = sorted(self.pet_shop.items(), key=lambda x: x[1]['price'])
            start = self.pet_subpage * self.pets_per_page
            end = start + self.pets_per_page
            current_pets = pet_items[start:end]
            
            total_subpages = (len(pet_items) - 1) // self.pets_per_page + 1
            embed.set_author(name=f"Page {self.pet_subpage + 1} of {total_subpages}")

            pet_fields = []
            current_field = ""
            for name, stats in current_pets:
                entry = f"{stats['emoji']} **{name.capitalize()}**\n🪙 {stats['price']:,} | ❤️ {stats['hp']} | ⚔️ {stats['damage']}\n\n"
                if len(current_field) + len(entry) > 1024:
                    pet_fields.append(current_field)
                    current_field = entry
                else:
                    current_field += entry
            if current_field:
                pet_fields.append(current_field)

            for i, field_content in enumerate(pet_fields):
                name = "🐾 Pets" if i == 0 else "\u200b"
                embed.add_field(name=name, value=field_content, inline=False)
        elif self.page == "roles":
            embed = discord.Embed(
                title="💎 Role Shop",
                description="✨ Buy roles for passive income!",
                color=0xF1C40F
            )
            
            role_text = ""
            for key, data_shop in self.role_shop.items():
                role = guild.get_role(int(data_shop["role_id"]))
                role_name = role.name if role else key.capitalize()
                role_text += f"**{role_name}**\n🪙 {data_shop['price']:,} | 💰 {data_shop['claim']:,}/h\n\n"
            
            if role_text:
                if len(role_text) > 1024:
                    role_parts = [role_text[i:i+1000] for i in range(0, len(role_text), 1000)]
                    for i, part in enumerate(role_parts):
                        embed.add_field(name="💎 Roles" if i == 0 else "💎 Roles (cont.)", value=part, inline=False)
                else:
                    embed.add_field(name="💎 Roles", value=role_text, inline=False)
        else: # Food page
            embed = discord.Embed(
                title="🍱 Food Shop",
                description="🍖 Buy food to keep your pets strong!",
                color=0x2ECC71
            )
            
            food_text = ""
            for key, data in FOOD_ITEMS.items():
                food_text += f"{data['emoji']} **{data['name']}**\n🪙 {data['price']:,} | 🍖 +{data['hunger']} Hunger\n\n"
            
            embed.add_field(name="🍱 Food Items", value=food_text, inline=False)

        embed.set_footer(text="/shop buy <name>")
        return embed

    def _update_buttons(self):
        pet_items = list(self.pet_shop.items())
        total_subpages = (len(pet_items) - 1) // self.pets_per_page + 1
        
        self.prev_button.disabled = (self.page != "pets" or self.pet_subpage == 0)
        self.next_button.disabled = (self.page != "pets" or self.pet_subpage >= total_subpages - 1)

    @discord.ui.button(label="🐾 Pets", style=discord.ButtonStyle.primary, row=0)
    async def show_pets(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = "pets"
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(interaction.guild), view=self)

    @discord.ui.button(label="💎 Roles", style=discord.ButtonStyle.secondary, row=0)
    async def show_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = "roles"
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(interaction.guild), view=self)

    @discord.ui.button(label="🍱 Food", style=discord.ButtonStyle.success, row=0)
    async def show_food(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = "food"
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(interaction.guild), view=self)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.gray, row=1, disabled=True)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.pet_subpage > 0:
            self.pet_subpage -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self._build_embed(interaction.guild), view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.gray, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pet_items = list(self.pet_shop.items())
        total_subpages = (len(pet_items) - 1) // self.pets_per_page + 1
        if self.pet_subpage < total_subpages - 1:
            self.pet_subpage += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self._build_embed(interaction.guild), view=self)


class SellPetSelect(discord.ui.Select):
    def __init__(self, ctx, pets):
        self.ctx = ctx
        self.pets = pets
        options = []
        for index, pet in enumerate(pets):
            pet_type = pet["type"]
            price = PET_SHOP.get(pet_type, {}).get("price", 0)
            sell_price = price // 2
            emoji = PET_SHOP.get(pet_type, {}).get("emoji", "🐾")
            options.append(
                discord.SelectOption(
                    label=f"{pet_type.capitalize()} (ID: {pet['pet_id'][:8]})",
                    description=f"Sell for 🪙 {sell_price:,}",
                    emoji=emoji,
                    value=str(index)
                )
            )
        super().__init__(placeholder="Choose a pet to sell...", options=options)

    async def callback(self, interaction: discord.Interaction):
        user_id = str(self.ctx.author.id)
        selected_index = int(self.values[0])
        pet_data = pets_col.find_one({"_id": user_id})
        pets = pet_data.get("pets", [])
        
        if selected_index >= len(pets):
            return await interaction.response.send_message("❌ Pet no longer exists.", ephemeral=True)
            
        pet = pets.pop(selected_index)
        shop_price = PET_SHOP.get(pet["type"], {}).get("price", 0)
        sell_price = shop_price // 2
        
        pets_col.update_one({"_id": user_id}, {"$set": {"pets": pets}})
        eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": sell_price}}, upsert=True)
        
        embed = discord.Embed(title="💰 Pet Sold", color=0x2ECC71)
        embed.description = f"Sold your **{pet['type'].capitalize()}**\n\nReceived: 🪙 **{sell_price:,}**"
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class FeedPetSelect(discord.ui.Select):
    def __init__(self, ctx, pets):
        options = []
        for pet in pets:
            hunger = get_current_hunger(pet)
            pet_type = pet["type"]
            emoji = PET_SHOP.get(pet_type, {}).get("emoji", "🐾")
            options.append(
                discord.SelectOption(
                    label=pet_type.capitalize(),
                    description=f"Hunger: {int(hunger)}/100",
                    emoji=emoji,
                    value=pet["pet_id"],
                )
            )
        super().__init__(placeholder="Select a pet to feed...", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_pet_id = self.values[0]
        await interaction.response.defer()


class FeedFoodSelect(discord.ui.Select):
    def __init__(self, food_items):
        options = []
        food_counts = {}
        for item in food_items:
            key = item["key"]
            food_counts[key] = food_counts.get(key, 0) + 1

        for key, count in food_counts.items():
            food_data = FOOD_ITEMS[key]
            options.append(
                discord.SelectOption(
                    label=f"{food_data['name']} (x{count})",
                    description=f"+{food_data['hunger']} Hunger",
                    emoji=food_data["emoji"],
                    value=key,
                )
            )
        super().__init__(placeholder="Select food...", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_food_key = self.values[0]
        await self.view.process_feed(interaction)


class FeedView(discord.ui.View):
    def __init__(self, ctx, pets, food_items):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.pets = pets
        self.food_items = food_items
        self.selected_pet_id = None
        self.selected_food_key = None

        self.add_item(FeedPetSelect(ctx, pets))
        self.add_item(FeedFoodSelect(food_items))

    async def process_feed(self, interaction: discord.Interaction):
        if not self.selected_pet_id:
            return await interaction.followup.send("❌ Please select a pet first!", ephemeral=True)

        user_id = str(self.ctx.author.id)
        pet_index = next(
            (i for i, p in enumerate(self.pets) if p["pet_id"] == self.selected_pet_id), None
        )
        if pet_index is None:
            return await interaction.followup.send("❌ Pet not found.", ephemeral=True)

        pet = self.pets[pet_index]
        current_hunger = get_current_hunger(pet)
        food_data = FOOD_ITEMS[self.selected_food_key]
        new_hunger = min(100, current_hunger + food_data["hunger"])

        self.pets[pet_index]["hunger"] = new_hunger
        self.pets[pet_index]["last_fed"] = time.time()
        self.pets[pet_index]["starvation_since"] = None

        pets_col.update_one({"_id": user_id}, {"$set": {"pets": self.pets}})

        user_data = eco_col.find_one({"_id": user_id})
        inventory = user_data.get("inventory", []) if user_data else []

        for i, item in enumerate(inventory):
            if item.get("type") == "food" and item.get("key") == self.selected_food_key:
                inventory.pop(i)
                break

        eco_col.update_one({"_id": user_id}, {"$set": {"inventory": inventory}})

        embed = discord.Embed(
            title="🍖 Pet Fed",
            description=(
                f"You fed your **{pet['type'].capitalize()}** {food_data['emoji']} **{food_data['name']}**.\n\n"
                f"🍖 Hunger: {int(current_hunger)} → **{int(new_hunger)}**/100"
            ),
            color=0x00FF00,
        )
        await interaction.message.edit(content=None, embed=embed, view=None)


class SellPetView(discord.ui.View):
    def __init__(self, ctx, pets):
        super().__init__(timeout=60)
        self.add_item(SellPetSelect(ctx, pets))
