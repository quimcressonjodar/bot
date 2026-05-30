import discord

from database import eco_col
from utils.economy import get_user_data


class SellSelect(discord.ui.Select):
    def __init__(self, ctx, inventory):
        self.ctx = ctx
        self.inventory = inventory

        rarity_emojis = {
            "common": "⚪",
            "rare": "🔵",
            "epic": "🟣",
            "legendary": "🟡",
            "godly": "🌌",
        }
        options = []
        for index, item in enumerate(inventory[:25]):
            rarity = item.get("rarity", "common")
            options.append(
                discord.SelectOption(
                    label=item["name"][:100],
                    description=f"{rarity.capitalize()} • 🪙 {item['value']:,}",
                    emoji=rarity_emojis.get(rarity, "⚪"),
                    value=str(index),
                )
            )

        super().__init__(
            placeholder="Choose an item to sell...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        user_id = str(self.ctx.author.id)
        selected_index = int(self.values[0])
        user_data = get_user_data(user_id)
        inventory = user_data.get("inventory", [])

        if selected_index >= len(inventory):
            return await interaction.response.send_message("❌ Item no longer exists.", ephemeral=True)

        item = inventory[selected_index]
        inventory.pop(selected_index)

        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": item["value"]}, "$set": {"inventory": inventory}},
        )

        embed = discord.Embed(title="💰 Item Sold", color=0x2ECC71)
        embed.description = f"Sold {item['name']}\n\nReceived: 🪙 **{item['value']:,}**"
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class SellView(discord.ui.View):
    def __init__(self, ctx, inventory):
        super().__init__(timeout=60)
        self.add_item(SellSelect(ctx, inventory))
