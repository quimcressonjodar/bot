from datetime import datetime, timezone
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import is_admin, parse_duration, load_warns, save_warns
from database import eco_col, pets_col
from config import ROLE_SHOP


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="ban", description="Ban a member from the server (Admin only)")
    @app_commands.describe(member="The member to ban", reason="The reason for the ban")
    @app_commands.default_permissions(administrator=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        try:
            await member.send(f"🔨 You have been **banned** from **{ctx.guild.name}**.\n**Reason:** {reason}")
        except discord.Forbidden:
            pass
        try:
            await member.ban(reason=reason)
            await ctx.send(f"🔨 **{member.name}** has been permanently banned. Reason: {reason}")
        except Exception as e:
            await ctx.send(f"❌ Failed to ban user: {e}", ephemeral=True)

    @commands.hybrid_command(name="unban", description="Unban a user by their Discord ID (Admin only)")
    @app_commands.describe(user_id="The unique ID of the user to unban")
    @app_commands.default_permissions(administrator=True)
    async def unban(self, ctx: commands.Context, user_id: str):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        try:
            user = await self.bot.fetch_user(int(user_id))
            await ctx.guild.unban(user)
            await ctx.send(f"✅ Successfully unbanned **{user.name}** from the server.")
        except Exception as e:
            await ctx.send(f"❌ Failed to unban user. Make sure the ID is correct: {e}", ephemeral=True)

    @commands.hybrid_command(name="kick", description="Kick a member from the server (Admin only)")
    @app_commands.describe(member="The member to kick", reason="The reason for the kick")
    @app_commands.default_permissions(administrator=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        try:
            await member.send(f"👢 You have been **kicked** from **{ctx.guild.name}**.\n**Reason:** {reason}")
        except discord.Forbidden:
            pass
        try:
            await member.kick(reason=reason)
            await ctx.send(f"👢 **{member.name}** has been kicked from the server. Reason: {reason}")
        except Exception as e:
            await ctx.send(f"❌ Failed to kick user: {e}", ephemeral=True)

    @commands.hybrid_command(name="timeout", description="Timeout/Mute a member temporarily (Admin only)")
    @app_commands.describe(member="The member", duration="Duration (e.g. 10m, 2h, 1d)", reason="Reason for timeout")
    @app_commands.default_permissions(administrator=True)
    async def timeout(self, ctx: commands.Context, member: discord.Member, duration: str, reason: str = "No reason provided"):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        time_delta = parse_duration(duration)
        if not time_delta:
            return await ctx.send(
                "❌ Invalid duration format! Use formats like `10m` (minutes), `2h` (hours), or `1d` (days).",
                ephemeral=True,
            )
        try:
            await member.send(f"🔇 You have been **timed out** in **{ctx.guild.name}** for `{duration}`.\n**Reason:** {reason}")
        except discord.Forbidden:
            pass
        try:
            await member.timeout(time_delta, reason=reason)
            await ctx.send(f"🔇 **{member.name}** has been timed out for `{duration}`. Reason: {reason}")
        except Exception as e:
            await ctx.send(f"❌ Failed to apply timeout: {e}", ephemeral=True)

    @commands.hybrid_command(name="untimeout", description="Remove timeout from a member (Admin only)")
    @app_commands.describe(member="The member to untimeout")
    @app_commands.default_permissions(administrator=True)
    async def untimeout(self, ctx: commands.Context, member: discord.Member):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        try:
            await member.timeout(None)
            await ctx.send(f"🔊 Timeout removed. **{member.name}** can now talk again.")
        except Exception as e:
            await ctx.send(f"❌ Failed to remove timeout: {e}", ephemeral=True)

    @commands.hybrid_command(name="purge", description="Purge a specified amount of messages (Admin only)")
    @app_commands.describe(amount="Amount of messages to delete")
    @app_commands.default_permissions(administrator=True)
    async def purge(self, ctx: commands.Context, amount: int):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        if amount <= 0:
            return await ctx.send("Please specify a number greater than 0.", ephemeral=True)
        await ctx.defer(ephemeral=True)
        try:
            # If prefix command, we need to delete the command message itself as well
            limit = amount if ctx.interaction else amount + 1
            deleted = await ctx.channel.purge(limit=limit)
            
            # Count excludes the command message if it was a prefix command
            count = len(deleted) if ctx.interaction else len(deleted) - 1
            
            msg = await ctx.send(f"🧹 Successfully deleted **{count}** messages.", ephemeral=True)
            
            # Auto-delete success message for prefix commands
            if not ctx.interaction:
                await asyncio.sleep(3)
                try:
                    await msg.delete()
                except discord.NotFound:
                    pass
        except Exception as e:
            await ctx.send(f"❌ Failed to purge messages: {e}", ephemeral=True)

    @commands.hybrid_command(name="lock", description="Lock a text channel (Admin only)")
    @app_commands.describe(channel="The channel to lock (Defaults to current)")
    @app_commands.default_permissions(administrator=True)
    async def lock(self, ctx: commands.Context, channel: discord.TextChannel = None):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        target_channel = channel or ctx.channel
        try:
            await target_channel.set_permissions(ctx.guild.default_role, send_messages=False)
            await ctx.send(f"🔒 **{target_channel.mention}** has been locked down.")
        except Exception as e:
            await ctx.send(f"❌ Failed to lock channel: {e}", ephemeral=True)

    @commands.hybrid_command(name="unlock", description="Unlock a previously locked channel (Admin only)")
    @app_commands.describe(channel="The channel to unlock (Defaults to current)")
    @app_commands.default_permissions(administrator=True)
    async def unlock(self, ctx: commands.Context, channel: discord.TextChannel = None):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        target_channel = channel or ctx.channel
        try:
            await target_channel.set_permissions(ctx.guild.default_role, send_messages=None)
            await ctx.send(f"🔓 **{target_channel.mention}** is now unlocked.")
        except Exception as e:
            await ctx.send(f"❌ Failed to unlock channel: {e}", ephemeral=True)

    @commands.hybrid_command(name="slowmode", description="Set slowmode delay for a channel (Admin only)")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)", channel="The channel")
    @app_commands.default_permissions(administrator=True)
    async def slowmode(self, ctx: commands.Context, seconds: int, channel: discord.TextChannel = None):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        target_channel = channel or ctx.channel
        try:
            await target_channel.edit(slowmode_delay=seconds)
            if seconds == 0:
                await ctx.send(f"⏱️ Slowmode has been disabled in {target_channel.mention}.")
            else:
                await ctx.send(f"⏱️ Slowmode set to **{seconds}** seconds in {target_channel.mention}.")
        except Exception as e:
            await ctx.send(f"❌ Failed to set slowmode: {e}", ephemeral=True)

    @commands.hybrid_command(name="warn", description="Issue a warning to a member (Admin only)")
    @app_commands.describe(member="The member to warn", reason="The reason for the warning")
    @app_commands.default_permissions(administrator=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, reason: str):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        warns_data = load_warns()
        user_id = str(member.id)
        if user_id not in warns_data:
            warns_data[user_id] = []
        warn_id = str(len(warns_data[user_id]) + 1)
        new_warn = {
            "id": warn_id,
            "reason": reason,
            "moderator": ctx.author.name,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        }
        warns_data[user_id].append(new_warn)
        save_warns(warns_data)
        try:
            await member.send(
                f"⚠️ You received a **warning** in **{ctx.guild.name}**.\n"
                f"**Reason:** {reason}\n*You now have {len(warns_data[user_id])} warnings.*"
            )
        except discord.Forbidden:
            pass
        embed = discord.Embed(
            title="⚠️ Member Warned",
            description=f"**User:** {member.mention}\n**Reason:** {reason}\n**Total Warns:** {len(warns_data[user_id])}",
            color=0xFFAA00,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="warns", description="Check a member's warning history (Admin only)")
    @app_commands.describe(member="The member to check")
    @app_commands.default_permissions(administrator=True)
    async def check_warns(self, ctx: commands.Context, member: discord.Member):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        warns_data = load_warns()
        user_id = str(member.id)
        user_warns = warns_data.get(user_id, [])
        if not user_warns:
            return await ctx.send(f"✅ **{member.name}** has a clean record (0 warnings).")
        embed = discord.Embed(title=f"⚠️ Warning Record: {member.name}", color=0xFFAA00)
        for w in user_warns:
            embed.add_field(
                name=f"ID: {w['id']} | {w['date']}",
                value=f"**Reason:** {w['reason']}\n**Staff:** {w['moderator']}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="delwarn", description="Delete a specific warning from a member (Admin only)")
    @app_commands.describe(member="The member", warn_id="The ID of the warning to remove")
    @app_commands.default_permissions(administrator=True)
    async def delwarn(self, ctx: commands.Context, member: discord.Member, warn_id: str):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        warns_data = load_warns()
        user_id = str(member.id)
        user_warns = warns_data.get(user_id, [])
        updated_warns = [w for w in user_warns if w["id"] != warn_id]
        if len(updated_warns) == len(user_warns):
            return await ctx.send("❌ Warning ID not found for this user.", ephemeral=True)
        for idx, w in enumerate(updated_warns):
            w["id"] = str(idx + 1)
        warns_data[user_id] = updated_warns
        save_warns(warns_data)
        await ctx.send(f"✅ Successfully removed warning ID `{warn_id}` from **{member.name}**.")

    @commands.hybrid_command(name="clearwarns", description="Clear all warnings from a member (Admin only)")
    @app_commands.describe(member="The member to clear")
    @app_commands.default_permissions(administrator=True)
    async def clearwarns(self, ctx: commands.Context, member: discord.Member):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        warns_data = load_warns()
        user_id = str(member.id)
        if user_id in warns_data:
            del warns_data[user_id]
            save_warns(warns_data)
        await ctx.send(f"✅ Cleared all warnings for **{member.name}**.")

    @commands.hybrid_command(name="setnick", description="Quickly change a member's nickname (Admin only)")
    @app_commands.describe(member="The member", nickname="New nickname (Leave empty to reset)")
    @app_commands.default_permissions(administrator=True)
    async def setnick(self, ctx: commands.Context, member: discord.Member, nickname: str = None):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        try:
            await member.edit(nick=nickname)
            await ctx.send(f"✅ Changed nickname for **{member.name}** to `{nickname or member.name}`.")
        except Exception as e:
            await ctx.send(f"❌ Failed to change nickname: {e}", ephemeral=True)

    @commands.hybrid_command(name="role_add", description="Assign a role to a member (Admin only)")
    @app_commands.describe(member="The member", role="The role to assign")
    @app_commands.default_permissions(administrator=True)
    async def role_add(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        try:
            await member.add_roles(role)
            await ctx.send(f"✅ Assigned the role **{role.name}** to **{member.name}**.")
        except Exception as e:
            await ctx.send(f"❌ Failed to add role: {e}", ephemeral=True)

    @commands.hybrid_command(name="role_remove", description="Remove a role from a member (Admin only)")
    @app_commands.describe(member="The member", role="The role to remove")
    @app_commands.default_permissions(administrator=True)
    async def role_remove(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        try:
            await member.remove_roles(role)
            await ctx.send(f"✅ Removed the role **{role.name}** from **{member.name}**.")
        except Exception as e:
            await ctx.send(f"❌ Failed to remove role: {e}", ephemeral=True)

    @commands.hybrid_command(name="say", description="Make the bot say something (Admin only)")
    @app_commands.describe(message="The message you want the bot to repeat")
    @app_commands.default_permissions(administrator=True)
    async def say(self, ctx: commands.Context, message: str):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        if ctx.interaction is None:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            await ctx.send(message)
        else:
            await ctx.send("Message sent!", ephemeral=True)
            await ctx.channel.send(message)

    @commands.hybrid_command(name="sayembed", description="Send a custom embed message (Admin only)")
    @app_commands.describe(
        title="Title of the embed",
        description="The main text of the embed",
        color="Hex color code (e.g. 2b2d31 or ff0000)",
    )
    @app_commands.default_permissions(administrator=True)
    async def sayembed(self, ctx: commands.Context, title: str, description: str, color: str = "2b2d31"):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        try:
            color_int = int(color.lstrip("#"), 16)
        except ValueError:
            color_int = 0x2B2D31
        embed = discord.Embed(title=title, description=description, color=color_int)
        if ctx.interaction is None:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            await ctx.send(embed=embed)
        else:
            await ctx.send("Embed sent!", ephemeral=True)
            await ctx.channel.send(embed=embed)

    @commands.hybrid_command(name="add", description="Add coins to a user (Admin only)")
    @app_commands.describe(member="The member to give coins to", amount="Amount of coins to add")
    @app_commands.default_permissions(administrator=True)
    async def add(self, ctx: commands.Context, member: discord.Member, amount: int):
        if not is_admin(ctx):
            return await ctx.send("❌ Admin only command.", ephemeral=True)
        if amount <= 0:
            return await ctx.send("❌ Amount must be greater than 0.", ephemeral=True)
        from utils.economy import update_wallet, get_wallet
        update_wallet(str(member.id), amount)
        wallet = get_wallet(str(member.id))
        embed = discord.Embed(
            title="💰 Coins Added",
            description=f"Added 🪙 **{amount:,}** to {member.mention}\n\nNew Wallet Balance: 🪙 **{wallet:,}**",
            color=0x00FF00,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="reset_economy", description="RESETS EVERYTHING: coins, pets, items, and roles (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def reset_economy(self, ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("❌ Admin only command.", ephemeral=True)

        await ctx.defer()

        # 1. Clear coins, inventory and all cooldowns in eco_col for all users
        eco_col.update_many(
            {},
            {
                "$set": {"wallet": 0, "bank": 0, "inventory": []},
                "$unset": {
                    "last_daily": "",
                    "last_weekly": "",
                    "last_claim": "",
                    "last_work": "",
                    "last_crime": "",
                    "last_rob": "",
                    "last_adventure": "",
                    "balance": ""
                }
            }
        )

        # 2. Clear pets in pets_col for all users
        pets_col.update_many({}, {"$set": {"pets": []}})

        # 3. Remove shop roles from all members in the guild
        role_ids = [data["role_id"] for data in ROLE_SHOP.values() if "role_id" in data]
        roles_to_remove = []
        for rid in role_ids:
            role = ctx.guild.get_role(rid)
            if role:
                roles_to_remove.append(role)

        removed_count = 0
        if roles_to_remove:
            for member in ctx.guild.members:
                member_roles_to_remove = [r for r in roles_to_remove if r in member.roles]
                if member_roles_to_remove:
                    try:
                        await member.remove_roles(*member_roles_to_remove, reason="Economy Reset")
                        removed_count += 1
                    except Exception:
                        pass

        embed = discord.Embed(
            title="🧨 Economy Reset Complete",
            description=(
                "The economy has been fully reset!\n\n"
                "✅ All wallets and banks set to 🪙 0\n"
                "✅ All inventories and cooldowns cleared\n"
                "✅ All pets removed\n"
                f"✅ Removed shop roles from **{removed_count}** members"
            ),
            color=0xFF0000,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
