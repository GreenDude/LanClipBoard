from fastapi import FastAPI

from clipboard_factory import get_clipboard
from api_module import rest_router

clipboard = get_clipboard()
print(clipboard.get_clipboard_entry())

app = FastAPI()
app.include_router(rest_router)

