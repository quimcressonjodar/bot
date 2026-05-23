class WeeklyXPBot(commands.Bot):
    def __init__(self, clan_client: ClanClient):
        # Configuramos los intents AQUÍ
        intents = discord.Intents.default()
        # intents.presences = True <-- ELIMINADO: No hace falta para tu propio estado
        intents.members = True
        intents.message_content = True
        
        # Le pasamos el status y la activity directamente al constructor
        super().__init__(
            command_prefix="!", 
            intents=intents,
            status=discord.Status.online,
            activity=discord.Game(name="Kirka.io 🏆")
        )
        self.clan_client = clan_client

    async def setup_hook(self) -> None:
        await self.clan_client.start()
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def on_ready(self):
        # Solo dejamos el print/log, ya no necesitamos change_presence aquí
        logger.info(f"✅ ¡Bot conectado y listo como {self.user}!")

    async def close(self) -> None:
        await self.clan_client.close()
        await super().close()
