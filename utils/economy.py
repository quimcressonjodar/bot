from database import eco_col


def get_user_data(user_id: str) -> dict:
    user = eco_col.find_one({"_id": user_id})

    if not user:
        user = {"_id": user_id, "wallet": 0, "bank": 0}
        eco_col.insert_one(user)

    if "balance" in user:
        wallet_amount = user.get("balance", 0)
        eco_col.update_one(
            {"_id": user_id},
            {"$set": {"wallet": wallet_amount, "bank": 0}, "$unset": {"balance": ""}},
        )
        user["wallet"] = wallet_amount
        user["bank"] = 0

    return user


def parse_economy_amount(amount_input: str, max_balance: int) -> int:
    amount_input = str(amount_input).lower().strip()
    if amount_input == "all":
        return max_balance
    if amount_input == "half":
        return max(1, max_balance // 2)
    try:
        return int(amount_input)
    except ValueError:
        return -1


def get_wallet(user_id: str) -> int:
    return get_user_data(user_id)["wallet"]


def get_bank(user_id: str) -> int:
    return get_user_data(user_id)["bank"]


def update_wallet(user_id: str, amount: int) -> None:
    eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": amount}}, upsert=True)


def update_bank(user_id: str, amount: int) -> None:
    eco_col.update_one({"_id": user_id}, {"$inc": {"bank": amount}}, upsert=True)
