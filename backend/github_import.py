"""Public GitHub URL validation and safe, API-only repository browsing."""
from __future__ import annotations

import re
from urllib.parse import urlparse
import httpx

URL_RE=re.compile(r"^/([^/]+)/([^/]+)(?:/tree/([^/]+)(?:/(.*))?)?/?$")
def parse_github_url(url: str) -> dict[str,str]:
    parsed=urlparse(url)
    if parsed.scheme not in {"http","https"} or parsed.netloc.lower() not in {"github.com","www.github.com"}: raise ValueError("Provide a public https://github.com/owner/repository URL.")
    match=URL_RE.match(parsed.path)
    if not match: raise ValueError("GitHub URL must include an owner and repository.")
    owner,repo,branch,path=match.groups(); return {"owner":owner,"repo":repo.removesuffix(".git"),"branch":branch or "HEAD","path":path or ""}
async def repository_files(url: str, token: str | None = None) -> dict:
    target=parse_github_url(url); headers={"Accept":"application/vnd.github+json"}
    if token: headers["Authorization"]=f"Bearer {token}"
    api=f"https://api.github.com/repos/{target['owner']}/{target['repo']}/git/trees/{target['branch']}?recursive=1"
    async with httpx.AsyncClient(timeout=10) as client: response=await client.get(api,headers=headers)
    if response.status_code == 404: raise ValueError("Repository or branch was not found, or is private.")
    if response.status_code == 403: raise ValueError("GitHub rate limit reached; configure GITHUB_TOKEN on the backend.")
    response.raise_for_status()
    supported=(".py",".js",".ts",".tsx",".c",".cpp",".h",".java",".go",".r")
    files=[{"path":item["path"],"size":item.get("size",0)} for item in response.json().get("tree",[]) if item.get("type")=="blob" and item["path"].lower().endswith(supported)]
    return {**target,"files":files}

async def repository_file(url: str, path: str, token: str | None = None) -> dict:
    target=parse_github_url(url)
    if not path or path.startswith("/") or ".." in path.split("/"):
        raise ValueError("Invalid repository file path.")
    headers={"Accept":"application/vnd.github.raw"}
    if token: headers["Authorization"]=f"Bearer {token}"
    api=f"https://api.github.com/repos/{target['owner']}/{target['repo']}/contents/{path}?ref={target['branch']}"
    async with httpx.AsyncClient(timeout=10) as client: response=await client.get(api,headers=headers)
    if response.status_code == 404: raise ValueError("File was not found.")
    response.raise_for_status()
    content=response.text
    if len(content.encode("utf-8")) > 200_000: raise ValueError("File is too large to import (200 KB limit).")
    return {"path":path,"content":content}
