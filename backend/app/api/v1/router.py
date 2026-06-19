from fastapi import APIRouter
from app.api.v1.endpoints import (
    users, worlds, characters, sessions, dialogues,
    novels, chats, authors, api_logs, world_examples, author_chat, mypage, taste,
    proofread, illustrations, opening_scene,
)

router = APIRouter(prefix="/api/v1")

router.include_router(users.router,          prefix="/users",                             tags=["users"])
router.include_router(worlds.router,         prefix="/worlds",                            tags=["worlds"])
router.include_router(characters.router,     prefix="/worlds/{world_id}/characters",      tags=["characters"])
router.include_router(sessions.router,       prefix="/sessions",                          tags=["sessions"])
router.include_router(dialogues.router,      prefix="/sessions/{session_id}/dialogues",   tags=["dialogues"])
router.include_router(novels.router,         prefix="/sessions",                          tags=["novels"])
router.include_router(chats.router,          prefix="/chats",                             tags=["chats"])
router.include_router(author_chat.router,    prefix="/chats",                             tags=["author-chat"])
router.include_router(authors.router,        prefix="/authors",                           tags=["authors"])
router.include_router(api_logs.router,       prefix="/api-logs",                          tags=["api-logs"])
router.include_router(world_examples.router, prefix="/world-examples",                    tags=["world-examples"])
router.include_router(mypage.router,         prefix="/mypage",                             tags=["mypage"])
router.include_router(taste.router,          prefix="/chats",                              tags=["taste"])
router.include_router(proofread.router,                                                    tags=["proofread"])  # 풀경로(/chats·/users) 자체 정의
router.include_router(illustrations.router,  prefix="/sessions",                           tags=["illustrations"])
router.include_router(opening_scene.router,  prefix="/chats",                               tags=["opening-scene"])
