from dotenv import load_dotenv

load_dotenv()

import os
from io import BytesIO

import discord
from discord.ext import commands

import logger
from download import Downloader
from progress_bar import get_progress_bar

TOKEN = os.getenv("TOKEN")


if not TOKEN:
    print("No token provided. Exiting...")
    exit(1)


class Bot(commands.Bot):
    downloads: dict[str, Downloader] = {}

    async def on_ready(self):
        print("Logged on as", self.user)

    async def on_message(self, message: discord.Message):
        if message.author.id != 326751032489017346:
            return

        await self.process_commands(message)


intents = discord.Intents.default()
bot = Bot(command_prefix="", intents=intents)


@bot.command(name="d")
async def download(ctx: commands.Context[Bot], url: str, file_name: str):
    if not file_name.endswith(".mp4"):
        file_name += ".mp4"

    if file_name in ctx.bot.downloads:
        await ctx.reply("Already downloading")
        return

    downloader = Downloader(
        url=url,
        progress_interval=3,
        output_file=file_name,
    )
    ctx.bot.downloads[file_name] = downloader
    progress_iter = ctx.bot.downloads[file_name].download()

    reply_message = await ctx.reply("Downloading..")

    async for progress in progress_iter:
        if progress.error:
            ret = progress.get_error_stack()
            stderr = downloader.get_stderr()
            fp = BytesIO(stderr.encode("utf-8"))
            await reply_message.edit(
                content=(
                    f"```\n"
                    f"{ret}\n"
                    f"Last line of stderr:\n{stderr.splitlines().pop()}\n"
                    "```"
                ),
                attachments=[discord.File(fp=fp, filename="stderr.txt")],
            )
            break

        ret = "```\n"
        if progress.duration:
            bar = get_progress_bar(
                progress.time.total_seconds(),
                progress.duration.total_seconds(),
                bar_length=20,
            )
            ret += f"Progress:\n{bar}\n"

        ret += str(progress) + "\n```"
        await reply_message.edit(content=ret)

    ctx.bot.downloads.pop(file_name, None)


@bot.command()
async def cancel(ctx: commands.Context, name: str):
    if not name.endswith(".mp4"):
        name += ".mp4"

    if name not in ctx.bot.downloads:
        await ctx.reply("No such download")
        return

    await ctx.bot.downloads[name].cancel_download()
    ctx.bot.downloads.pop(name)
    await ctx.reply("Download cancelled")


def main():
    logger.setup()
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
