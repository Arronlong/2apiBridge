import asyncio, json, os, re
from fastapi import FastAPI, Request, Response, status
import uvicorn
from camoufox.async_api import AsyncCamoufox
from dotenv import load_dotenv

load_dotenv()

sophnet_token_list = []
promptlayer_token_list = []

# 把 .env 加载到环境变量
load_dotenv()

# 启动时立即校验：没有密钥就报错退出
VALID_API_KEY = os.getenv("API_KEY")

def verify_api_key(req):
    if not VALID_API_KEY: # 没有设置api-key时，不做限制
        return None
        
    """验证 API 密钥"""
    authorization = req.headers.get('Authorization')
    if not authorization or not VALID_API_KEY:
        return Response(json.dumps({'error': 'Missing API key'}), status_code=401, media_type='application/json')

    api_key = authorization.replace('Bearer ', '').strip()
    if api_key != VALID_API_KEY:
        return Response(json.dumps({'error': 'Invalid API key'}), status_code=401, media_type='application/json')

    return None

async def get_sophnet_token():
    async with AsyncCamoufox(os="linux", headless=True) as browser:
        url_with_slash = "https://sophnet.com/#/playground/chat?model=DeepSeek-R1-0528"
        page = await browser.new_page()
        await page.goto(url_with_slash, timeout=60000)
        cookies = await page.context.cookies()
        token = ""
        for cookie in cookies:
            if cookie.get("name") == "anonymous-token":
                token = cookie.get("value", "")
                break

        if token:
            # 清理 token 字符串
            cleaned_token = re.sub(r'{"anonymousToken:([^}]+)}', r"\1", token)
            cleaned_token = re.sub(r"%22", '"', cleaned_token).replace("%2C", ",")
            token = json.loads(cleaned_token).get("anonymousToken", "")
            print(f"Token: {token}")
            await page.get_by_placeholder("请输入内容").fill("i am liu")
            button = page.locator(
                "button.me-1.mb-px.flex.h-8.w-8.items-center.justify-center"
            )
            await button.click()
            await asyncio.sleep(2)
            return token
        else:
            print("Anonymous token not found.")


# 你的账号信息，建议用环境变量保存
PROMPTLAYER_EMAIL = os.getenv("PROMPTLAYER_EMAIL")
PROMPTLAYER_PASSWORD = os.getenv("PROMPTLAYER_PASSWORD")

async def get_promptlayer_token() -> str | None:
    """
    登录 PromptLayer 后，从 localStorage 取出 ACCESS_TOKEN。
    返回 None 表示失败。
    """
    if not PROMPTLAYER_EMAIL or not PROMPTLAYER_PASSWORD:
        raise RuntimeError("请先设置环境变量 PROMPTLAYER_EMAIL 和 PROMPTLAYER_PASSWORD")

    async with AsyncCamoufox(os="linux", headless=True) as browser:
        page = await browser.new_page()
        # 1. 打开登录页
        await page.goto("https://dashboard.promptlayer.com/login", timeout=60000)

        # 2. 填表单
        await page.fill('input[name="email"]', PROMPTLAYER_EMAIL)
        await page.fill('input[name="password"]', PROMPTLAYER_PASSWORD)

        # 3. 点击登录按钮（根据实际页面 selector 微调）
        await page.click('button[type="submit"]')

        # 4. 等待登录成功
        await page.wait_for_url("**/workspace/**/home", timeout=30000)

        # 5. 从 localStorage 拿 ACCESS_TOKEN
        token = await page.evaluate("""() => {
            return localStorage.getItem('ACCESS_TOKEN');
        }""")

        if token:
            print("ACCESS_TOKEN:", token)
            return token
        else:
            print("localStorage 里没有 ACCESS_TOKEN")
            return None


app = FastAPI(title="sophnet2api")

@app.get("/sophnet/get_token")
async def get_sophnet_token_api(request: Request):
    # 手动校验
    auth_error = verify_api_key(request)
    if auth_error:
        return auth_error

    global sophnet_token_list
    if len(sophnet_token_list) == 0:
        sophnet_token_list.append(await get_sophnet_token())
    token = sophnet_token_list[0]
    return {"token": token}

@app.get("/sophnet/get_newtoken")
async def get_sophnet_newtoken_api(response: Response, request: Request):
    # 手动校验
    auth_error = verify_api_key(request)
    if auth_error:
        return auth_error
    global sophnet_token_list
    sophnet_token_list.clear()
    response.status_code = status.HTTP_302_FOUND
    response.headers["Location"] = "/sophnet/get_token"
    return

@app.get("/promptlayer/get_token")
async def get_promptlayer_token_api(request: Request):
    # 手动校验
    auth_error = verify_api_key(request)
    if auth_error:
        return auth_error

    global promptlayer_token_list
    if len(promptlayer_token_list) == 0:
        promptlayer_token_list.append(await get_promptlayer_token())
    token = promptlayer_token_list[0]
    return {"token": token}

@app.get("/promptlayer/get_newtoken")
async def get_promptlayer_newtoken_api(response: Response, request: Request):
    # 手动校验
    auth_error = verify_api_key(request)
    if auth_error:
        return auth_error
    global promptlayer_token_list
    promptlayer_token_list.clear()
    response.status_code = status.HTTP_302_FOUND
    response.headers["Location"] = "/promptlayer/get_token"
    return

def main():
    uvicorn.run("2api_bridge:app", host="0.0.0.0", port=10007, reload=True)


if __name__ == "__main__":
    main()
