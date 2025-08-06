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
        # 导航到登录页面
        page = await browser.new_page()
        await page.goto("https://dashboard.promptlayer.com/login", timeout=30000)

        # 显式等待元素可见（增加超时容错）
        await page.wait_for_selector("input[name='email']", state="visible", timeout=15000)
        await page.wait_for_selector("input[name='password']", state="visible", timeout=15000)

        # 填写登录表单（根据实际页面元素调整选择器）
        await page.fill('input[name="email"]', PROMPTLAYER_EMAIL)  # 邮箱输入框
        await page.fill('input[name="password"]', PROMPTLAYER_PASSWORD)  # 密码输入框
        
        # 提交登录表单
        await page.click('button[type="submit"]')  # 登录按钮
        await page.evaluate(
            """(email) => document.querySelector("#email")?.value=email;""",
            PROMPTLAYER_EMAIL
        )
        await page.evaluate(
            """(pwd) => document.querySelector("#password")?.value=pwd;""",
            PROMPTLAYER_PASSWORD
        )
        await page.evaluate('() => document.querySelector("button[type=submit]")?.click()')
        await asyncio.sleep(3)  # 预留响应时间
        
        # 等待登录完成（检测重定向或关键元素）
        try:
            await page.wait_for_selector("h1:has-text('Welcome to PromptLayer')", state="visible", timeout=3000)
        except:
            # 获取整个页面的HTML源码
            page_content = await page.content()
            # 检查源码中是否包含欢迎文本
            if "Welcome to PromptLayer" in page_content:
                print("✅ 登录成功：在源码中找到欢迎文本")
            elif "Log In" in page_content:
                print("❌ 未触发登录？还在Login页面")
            else:
                print("❌ 登录失败：未找到欢迎元素")

        # 直接从localStorage获取ACCESS_TOKEN
        token = await page.evaluate('() => localStorage.getItem("ACCESS_TOKEN")')
        
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
