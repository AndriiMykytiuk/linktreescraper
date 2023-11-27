Certainly! Below is the full code with the modifications to include the link mapping:

```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import Optional, List

from dataclasses import dataclass
from typing import Union

import sys
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json

app = FastAPI()

# Your existing dataclasses and logic

@dataclass
class Link:
    url: Optional[str]

@dataclass
class LinktreeUser:
    username: str
    url: Optional[str]
    avartar_image: Optional[str]
    id: int
    tier: str
    isActive: bool
    description: Optional[str]
    createdAt: int
    updatedAt: int
    links: List[Link]

    # Method to generate link mapping
    def get_link_mapping(self):
        link_mapping = {}
        for link in self.links:
            if "twitter.com" in link.url.lower():
                link_mapping["twitter"] = link.url
            elif "instagram.com" in link.url.lower():
                link_mapping["instagram"] = link.url
            elif "onlyfans.com" in link.url.lower():
                link_mapping["onlyfans"] = link.url
            # Add more conditions for other social media platforms as needed
        return link_mapping

class Linktree(object):
    def __init__(self, disable_ssl_verification: bool = False):
        self.disable_ssl_verification = disable_ssl_verification

    async def _fetch(self, url: str, method: str = "GET",
                     headers: dict = {}, data: dict = {}) -> tuple[aiohttp.ClientSession, aiohttp.ClientSession]:
        connector = aiohttp.TCPConnector(ssl=self.disable_ssl_verification)
        session = aiohttp.ClientSession(headers=headers, connector=connector)
        resp = await session.request(method=method, url=url, json=data)
        return session, resp

    async def getSource(self, url: str):
        session, resp = await self._fetch(url)
        content = await resp.text()
        await session.close()
        return content

    async def getUserInfoJSON(self, source=None, url: Optional[str] = None, username: Optional[str] = None):
        if url is None and username:
            url = f"https://linktr.ee/{username}"

        if source is None and url:
            source = await self.getSource(url)

        soup = BeautifulSoup(source, 'html.parser')
        attributes = {"id": "__NEXT_DATA__"}
        user_info = soup.find('script', attrs=attributes)
        user_data = json.loads(user_info.contents[0])["props"]["pageProps"]
        return user_data

    async def uncensorLinks(self, account_id: int, link_ids: Union[List[int], int]):
        if isinstance(link_ids, int):
            link_ids = [link_ids]

        headers = {"origin": "https://linktr.ee",
                   "referer": "https://linktr.ee",
                   "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36"}

        data = {"accountId": account_id,
                "validationInput": {"acceptedSensitiveContent": link_ids},
                "requestSource": {"referrer": None}}

        url = "https://linktr.ee/api/profiles/validation/gates"
        session, resp = await self._fetch(method="POST", url=url, headers=headers, data=data)

        json_resp = await resp.json()
        await session.close()

        _links = json_resp["links"]

        links = []
        for _link in _links:
            if 'fans' in _links:
                _link["of_link"]: _link
            url = _link["url"]
            link = Link(url=url)
            links.append(link)
        return links

    async def getUserLinks(self, username: Optional[str] = None, data: Optional[dict] = None):
        if data is None and username:
            data = await self.getUserInfoJSON(username=username)

        user_id = data["account"]["id"]
        _links = data["links"]

        links = []
        censored_links_ids = []

        for _link in _links:
            id = int(_link["id"])
            url = _link["url"]
            locked = _link["locked"]

            link = Link(url=url)
            if _link["type"] == "COMMERCE_PAY":
                continue

            if url is None and locked is True:
                censored_links_ids.append(id)
                continue
            links.append(link)

        uncensored_links = await self.uncensorLinks(account_id=user_id,
                                                    link_ids=censored_links_ids)
        links.extend(uncensored_links)

        return links

    async def getLinktreeUserInfo(self, url: Optional[str] = None, username: Optional[str] = None) -> LinktreeUser:
        if url is None and username is None:
            print("Please pass linktree username or url.")
            return

        JSON_INFO = await self.getUserInfoJSON(url=url, username=username)
        account = JSON_INFO["account"]
        username = account["username"]
        avatar_image = account["profilePictureUrl"]
        url = f"https://linktr.ee/{username}" if url is None else url
        user_id = account["id"]
        # tier  = account["tier"]
        is_active = account["isActive"]
        created_at = account["createdAt"]
        updated_at = account["updatedAt"]
        description = account["description"]

        links = await self.getUserLinks(data=JSON_INFO)

        return LinktreeUser(username=username,
                            url=url,
                            avartar_image=avatar_image,
                            id=user_id,
                            tier='',
                            isActive=is_active,
                            createdAt=created_at,
                            updatedAt=updated_at,
                            description=description,
                            links=links)

# Define a model for the request
class LinktreeRequest(BaseModel):
    username: Optional[str] = None
    url: Optional[str] = None

# Define the API key
API_KEY = "your_secret_key"  # Replace with your actual secret key
API_KEY_NAME = "X-Secret-Token"
api_key_header = APIKeyHeader(name=API_KEY_NAME)

# Dependency to check the API key
async def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key == API_KEY:
        return api_key
    else:
        raise HTTPException(status_code=401, detail="Invalid API key")

# Endpoint to get LinktreeUser data
@app.post("/get_linktree_user", response_model=LinktreeUser)
async def get_linktree_user(request: LinktreeRequest, api_key: str = Depends(get_api_key)):
    linktree = Linktree()

    try:
        user_info = await linktree.getLinktreeUserInfo(username=request.username, url=request.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return user_info

# Main function to run the FastAPI app
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
