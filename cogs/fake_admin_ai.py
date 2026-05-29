import os
import asyncio
import discord
from discord.ext import commands
from openai import OpenAI
from pymongo import MongoClient

SYSTEM_PROMPT = """
You are a Discord assistant bot.

Style:
- short answers
- sarcastic but not toxic
- humorous
- no real moderation actions
- max 25 words
- can bully some users but in a funny way
"""

# 🔌 MongoDB
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["kirka_bot"]
memory_col = db["memory"]


class FakeAdminAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.client = OpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1"
        )

        self.channel_id = int(os.getenv("AI_CHANNEL_ID"))
        self.cooldown = {}

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.content.startswith("!"):
            return

        if message.author.bot:
            return

        if message.channel.id != self.channel_id:
            return

        # cooldown
        if self.cooldown.get(message.author.id, 0) > asyncio.get_event_loop().time():
            return

        self.cooldown[message.author.id] = asyncio.get_event_loop().time() + 5

        user_id = str(message.author.id)

        try:
            # 💾 guardar memoria en MongoDB
            memory_col.update_one(
                {"user_id": user_id},
                {"$push": {"messages": {"$each": [message.content], "$slice": -10}}},
                upsert=True
            )

            # 📥 leer memoria
            data = memory_col.find_one({"user_id": user_id})
            memory = data["messages"] if data and "messages" in data else []

            # 🧠 construir prompt
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]

            if memory:
                messages.append({
                    "role": "system",
                    "content": "User memory:\n" + "\n".join(memory)
                })

            # 💬 contexto corto del canal
            async for msg in message.channel.history(limit=3):
                if msg.author.bot:
                    continue

                messages.append({
                    "role": "user",
                    "content": f"{msg.author.name}: {msg.content}"
                })

            # 🆕 mensaje actual
            messages.append({
                "role": "user",
                "content": message.content
            })

            # 🤖 IA call
            res = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=1.2,
                max_tokens=50
            )

            reply = res.choices[0].message.content

            if reply:
                await message.reply(reply)

        except Exception as e:
            print("AI error:", e)


async def setup(bot):
    await bot.add_cog(FakeAdminAI(bot))
