"""Entrypoint: wires config, database, handlers, scheduler; runs polling or webhook."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat

from bot.config import Config, load_config
from bot.db.repo import Repo
from bot.db.seed import DEFAULT_TEMPLATES
from bot.db.session import init_db, make_engine, make_session_factory
from bot.handlers import build_root_router
from bot.handlers.deps import Deps
from bot.services.publisher import Publisher
from bot.services.scheduler import Scheduler

logger = logging.getLogger(__name__)

ADMIN_COMMANDS = [
    BotCommand(command="new", description="Новый пост"),
    BotCommand(command="templates", description="Пост из шаблона"),
    BotCommand(command="posts", description="Последние посты"),
    BotCommand(command="scheduled", description="Отложенные посты"),
    BotCommand(command="addtemplate", description="Добавить шаблон"),
    BotCommand(command="cancel", description="Отменить действие"),
    BotCommand(command="id", description="Показать мой ID"),
    BotCommand(command="help", description="Справка"),
]


async def setup_commands(bot: Bot, config: Config) -> None:
    await bot.set_my_commands([
        BotCommand(command="id", description="Показать мой ID"),
        BotCommand(command="help", description="Справка"),
    ])
    for admin_id in config.admin_ids:
        try:
            await bot.set_my_commands(
                ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except Exception:  # noqa: BLE001 - admin may not have started the bot yet
            logger.debug("could not set commands for admin %s", admin_id)


async def build() -> tuple[Bot, Dispatcher, Scheduler, Config]:
    config = load_config()

    engine = make_engine(config.database_url)
    await init_db(engine)
    repo = Repo(make_session_factory(engine))

    added = await repo.seed_templates(DEFAULT_TEMPLATES)
    if added:
        logger.info("seeded %s default templates", added)

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    publisher = Publisher(bot, repo, config.channel_id)
    deps = Deps(config=config, repo=repo, publisher=publisher)

    dp = Dispatcher()
    dp["deps"] = deps
    dp.include_router(build_root_router())

    scheduler = Scheduler(repo, publisher, bot)
    return bot, dp, scheduler, config


async def run_polling(bot: Bot, dp: Dispatcher, scheduler: Scheduler, config: Config) -> None:
    await bot.delete_webhook(drop_pending_updates=False)
    await setup_commands(bot, config)
    scheduler.start()
    logger.info("starting long polling")
    try:
        await dp.start_polling(bot)
    finally:
        await scheduler.stop()


async def run_webhook(bot: Bot, dp: Dispatcher, scheduler: Scheduler, config: Config) -> None:
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    from aiohttp import web

    webhook_path = "/webhook"
    webhook_url = config.webhook_url + webhook_path

    await setup_commands(bot, config)
    scheduler.start()

    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=config.webhook_secret or None
    ).register(app, path=webhook_path)

    async def health(_request: web.Request) -> web.Response:
        return web.Response(text="ok")

    app.router.add_get("/health", health)
    setup_application(app, dp, bot=bot)

    await bot.set_webhook(webhook_url, secret_token=config.webhook_secret or None,
                          drop_pending_updates=False)
    logger.info("webhook set to %s, listening on 0.0.0.0:%s", webhook_url, config.port)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=config.port)
    await site.start()
    try:
        await asyncio.Event().wait()
    finally:
        await scheduler.stop()
        await runner.cleanup()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    bot, dp, scheduler, config = await build()
    if config.run_mode == "webhook":
        await run_webhook(bot, dp, scheduler, config)
    else:
        await run_polling(bot, dp, scheduler, config)


if __name__ == "__main__":
    asyncio.run(main())
