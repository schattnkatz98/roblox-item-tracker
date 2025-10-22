from keep_alive import keep_alive
import requests
import json
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
import os
import time
import asyncio

# Lade Umgebungsvariablen
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initiale Einstellungen
user_robux = 5000
desired_demand = 2
reduction_threshold = 10

item_table_url = "https://www.rolimons.com/itemtable"

intents = discord.Intents.default()
discord.Intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

reported_items = set()
printed_items = set()
sent_messages = []
cache = {"data": None, "last_fetch": 0}


def get_item_data():
    global cache
    current_time = time.time()
    if (cache["data"] and current_time - cache["last_fetch"]
            < 300):  # 300 Sekunden Cache (5 Minuten)
        return cache["data"]

    response = requests.get(item_table_url, timeout=10)
    response.raise_for_status()
    js_content = response.text
    start_index = js_content.find("var item_details = {")
    if start_index == -1:
        raise ValueError("Item-Daten konnten nicht gefunden werden.")
    start_index += len("var item_details = ")
    end_index = js_content.find("};", start_index) + 1
    json_data_str = js_content[start_index:end_index]
    item_data = json.loads(json_data_str)

    cache["data"] = item_data
    cache["last_fetch"] = current_time
    return item_data


def calculate_reduction(current_price, rap):
    if rap > 0:
        return round((rap - current_price) / rap * 100, 2)
    return 0


def get_reduction_color(reduction_percentage):
    if reduction_percentage >= 50:
        return 0xED023D
    elif reduction_percentage >= 20:
        return 0xD40074
    elif reduction_percentage >= 10:
        return 0xE60000
    elif reduction_percentage >= 5:
        return 0xFFA500
    return 0xFFFFFF


def filter_items_by_criteria(item_data, robux_limit, desired_demand,
                             reduction_threshold):
    filtered_items = []
    for item_id, item_info in item_data.items():
        name = item_info[0]
        current_price = item_info[5]
        rap = item_info[8]
        demand = item_info[17]
        trend = item_info[18]
        projected = item_info[19]
        image_url = item_info[24]
        reduction_percentage = calculate_reduction(current_price, rap)

        if (projected is None and current_price > 100
                and current_price <= robux_limit and demand is not None
                and reduction_percentage >= reduction_threshold):
            filtered_items.append({
                "id": item_id,
                "name": name,
                "current_price": current_price,
                "rap": rap,
                "demand": demand,
                "trend": trend,
                "reduction": reduction_percentage,
                "image_url": image_url,
            })
    return filtered_items


async def send_to_discord(channel, items):
    for item in items:
        if item["id"] not in reported_items:
            reported_items.add(item["id"])
            item_url = f"https://www.roblox.com/catalog/{item['id']}"
            color = get_reduction_color(item["reduction"])

            embed = discord.Embed(
                title=item["name"],
                url=item_url,
                description=(f"**Preis:** {item['current_price']} Robux\n"
                             f"**RAP:** {item['rap']}\n"
                             f"**Reduktion:** {item['reduction']}%\n"
                             f"**Demand:** {item['demand']}\n"
                             f"**Trend:** {item['trend']}"),
                color=color,
            )
            embed.set_thumbnail(url=item["image_url"])
            embed.set_footer(text="Rolimons Item Tracking")
            msg = await channel.send(embed=embed)
            sent_messages.append(msg)


async def continuous_track_items():
    while True:
        try:
            channel = discord.utils.get(bot.get_all_channels(),
                                        name="limiteds")
            if channel is None:
                print("Kein Kanal mit dem Namen 'limiteds' gefunden.")
                await asyncio.sleep(10)
                continue

            item_data = get_item_data()
            filtered_items = filter_items_by_criteria(item_data, user_robux,
                                                      desired_demand,
                                                      reduction_threshold)

            for item in filtered_items:
                if item["id"] not in printed_items:
                    printed_items.add(item["id"])
                    print(
                        f"Neues reduziertes Item gefunden: {item['name']} "
                        f"(Preis: {item['current_price']} Robux, RAP: {item['rap']}, "
                        f"Reduktion: {item['reduction']}%)")

            if filtered_items:
                await send_to_discord(channel, filtered_items)

            await asyncio.sleep(1)

        except Exception as e:
            print(f"Fehler beim Tracken von Items: {e}")
            await asyncio.sleep(3)


@bot.command(name="clear")
async def clear(ctx):
    try:
        for msg in sent_messages:
            await msg.delete()
        sent_messages.clear()
        await ctx.send("Alle vom Bot gesendeten Nachrichten wurden gelöscht.")
    except Exception as e:
        await ctx.send(f"Fehler beim Löschen: {e}")


@bot.command(name="set_robux")
async def set_robux(ctx, robux: int):
    global user_robux
    user_robux = robux
    await ctx.author.send(f"Robux wurde auf {robux} gesetzt.")


@bot.command(name="set_demand")
async def set_demand(ctx, demand: int):
    global desired_demand
    desired_demand = demand
    await ctx.author.send(f"Demand wurde auf {demand} gesetzt.")


@bot.command(name="set_reduction")
async def set_reduction(ctx, reduction: int):
    global reduction_threshold
    reduction_threshold = reduction
    await ctx.author.send(f"Reduktion wurde auf {reduction}% gesetzt.")


@bot.event
async def on_ready():
    print(f"Eingeloggt als {bot.user}")
    keep_alive()
    bot.loop.create_task(continuous_track_items())


bot.run(BOT_TOKEN)
