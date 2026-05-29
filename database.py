import os
import pymongo

client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client["kirka_bot"]

pets_col = db["pets"]
warns_col = db["warns"]
snaps_col = db["snapshots"]
eco_col = db["economy"]
memory_col = db["memory"]
