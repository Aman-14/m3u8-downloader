import logging


def setup():
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filename="bot.log",
        level=logging.DEBUG,
    )
    logging.info("Logger setup complete")
