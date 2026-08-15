from aiogram import Router

from bot.handlers import common, manage, newpost, templates


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_router(common.router)
    root.include_router(templates.router)
    root.include_router(newpost.router)
    root.include_router(manage.router)
    return root
