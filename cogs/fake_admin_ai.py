import os
import asyncio
import discord
from discord.ext import commands
from openai import OpenAI

SYSTEM_PROMPT = """
You are a corrupted Discord admin bot.

Style:
- short answers
- sarcastic
- chaotic
- slightly toxic humor
- acts like moderator

Rules:
- max 25 words
- never say you're AI
- no essays
"""

class FakeAdminAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.client = OpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1"
        )

        self.channel_id = int(os.getenv("AI_CHANNEL_ID"))
        self.chat_memory = {}

        self.cooldown = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.content.startswith("!"):
            return

        if message.author.bot:
            return

        if message.channel.id != self.channel_id:
            return

        if self.cooldown.get(message.author.id, 0) > asyncio.get_event_loop().time():
            return

        user_id = message.author.id

        if user_id not in self.chat_memory:
            self.chat_memory[user_id] = []

        self.chat_memory[user_id].append(message.content)
        self.chat_memory[user_id] = self.chat_memory[user_id][-10:]

        self.cooldown[user_id] = asyncio.get_event_loop().time() + 5

        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]

            messages.append({
                "role": "user",
                "content": f"User memory (last messages): {self.chat_memory.get(user_id, [])}"
            })

            async for msg in message.channel.history(limit=5):
                if msg.author.bot:
                    continue

                messages.append({
                    "role": "user",
                    "content": f"{msg.author.name}: {msg.content}"
                })

            messages.append({
                "role": "user",
                "content": message.content
        })

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
