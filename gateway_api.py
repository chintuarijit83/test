import os
import json
import logging
import requests
from colorama import init, Fore, Style
from dotenv import load_dotenv
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

load_dotenv()
init(autoreset=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# ─────────────────────────────────────────
# CONFIG — fill these in once
# Works for both local testing and AgentCore deployment
# ─────────────────────────────────────────

REGION                 = "us-east-1"
MODEL_ID               = "us.anthropic.claude-sonnet-4-5-20251001-v1:0"

# AgentCore Gateway → your gateway → Endpoint URL
GATEWAY_URL            = ""   # e.g. "https://xxx.execute-api.us-east-1.amazonaws.com/..."

# Cognito → User Pools → your pool → App integration → Domain + /oauth2/token
COGNITO_TOKEN_ENDPOINT = ""   # e.g. "https://xxx.auth.us-east-1.amazoncognito.com/oauth2/token"

# Cognito → User Pools → App clients → your client
COGNITO_CLIENT_ID      = ""
COGNITO_CLIENT_SECRET  = ""

# Cognito → User Pools → Resource servers → your scope  e.g. "travel/weather"
COGNITO_SCOPE          = ""

# The target name you gave when adding the weather target in Gateway console
WEATHER_TARGET_NAME    = "WeatherSearch"


# ─────────────────────────────────────────
# LAZY CONFIG — reads from constants above
# ─────────────────────────────────────────

_cfg = None

def get_config() -> dict:
    """Build config lazily from hardcoded constants above"""
    global _cfg
    if _cfg is not None:
        return _cfg

    _cfg = {
        "region":                 REGION,
        "model_id":               MODEL_ID,
        "mcp_endpoint":           GATEWAY_URL,
        "cognito_token_endpoint": COGNITO_TOKEN_ENDPOINT,
        "cognito_client_id":      COGNITO_CLIENT_ID,
        "cognito_client_secret":  COGNITO_CLIENT_SECRET,
        "cognito_scope":          COGNITO_SCOPE,
        "weather_target_name":    WEATHER_TARGET_NAME,
    }

    print(Fore.CYAN + "[CONFIG] Region        : " + _cfg["region"])
    print(Fore.CYAN + "[CONFIG] Model         : " + _cfg["model_id"])
    print(Fore.CYAN + "[CONFIG] Gateway URL   : " + (_cfg["mcp_endpoint"][:60] if _cfg["mcp_endpoint"] else "NOT SET"))
    print(Fore.CYAN + "[CONFIG] Cognito EP    : " + (_cfg["cognito_token_endpoint"][:60] if _cfg["cognito_token_endpoint"] else "NOT SET"))
    print(Fore.CYAN + "[CONFIG] Weather Target: " + _cfg["weather_target_name"])

    return _cfg


# ─────────────────────────────────────────
# LAZY OAUTH TOKEN
# Fetched once on first tool call, then cached
# ─────────────────────────────────────────

_access_token = None

def get_access_token() -> str:
    """Fetch OAuth token from Cognito — cached for the process lifetime"""
    global _access_token
    if _access_token:
        print(Fore.GREEN + "[AUTH] Using cached OAuth token")
        return _access_token

    cfg = get_config()
    print(Fore.YELLOW + "[AUTH] Requesting OAuth token from Cognito...")
    print(Fore.YELLOW + f"[AUTH] Token endpoint : {cfg['cognito_token_endpoint']}")
    print(Fore.YELLOW + f"[AUTH] Client ID      : {cfg['cognito_client_id']}")
    print(Fore.YELLOW + f"[AUTH] Scope          : {cfg['cognito_scope']}")

    response = requests.post(
        cfg["cognito_token_endpoint"],
        data={
            "grant_type":    "client_credentials",
            "client_id":     cfg["cognito_client_id"],
            "client_secret": cfg["cognito_client_secret"],
            "scope":         cfg["cognito_scope"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if response.status_code != 200:
        print(Fore.RED + f"[AUTH] ✗ Failed — HTTP {response.status_code}: {response.text}")
        response.raise_for_status()

    _access_token = response.json()["access_token"]
    token_preview = f"{_access_token[:20]}...{_access_token[-10:]}"
    print(Fore.GREEN + f"[AUTH] ✓ Authentication successful")
    print(Fore.GREEN + f"[AUTH] Token           : {token_preview}")
    return _access_token


# ─────────────────────────────────────────
# LAZY AGENT
# BedrockModel + Agent created once on first request
# ─────────────────────────────────────────

_agent = None

def get_agent() -> Agent:
    """Initialise Strands Agent lazily — only on first request"""
    global _agent
    if _agent is not None:
        return _agent

    cfg = get_config()
    print(Fore.YELLOW + f"[AGENT] Initialising BedrockModel → {cfg['model_id']}")
    model = BedrockModel(model_id=cfg["model_id"])
    print(Fore.GREEN + "[AGENT] ✓ BedrockModel ready")

    print(Fore.YELLOW + "[AGENT] Creating Strands Agent with tools: get_current_weather, get_weather_forecast")
    _agent = Agent(
        model=model,
        tools=[get_current_weather, get_weather_forecast],
        system_prompt="""
You are a Travel Weather Assistant specializing in Italy.

You have access to live weather data via AgentCore Gateway.

RULES:
1. For current conditions → call get_current_weather()
2. For planning / future days → call get_weather_forecast()
3. Present results in a friendly travel-relevant way:
   - Suggest what to wear
   - Whether to bring an umbrella
   - Best times to visit outdoor sites
4. If no city is mentioned, ask which Italian city they mean.

Be concise, friendly, and travel-focused.
"""
    )
    print(Fore.GREEN + "[AGENT] ✓ Strands Agent ready")
    return _agent


# ─────────────────────────────────────────
# GATEWAY MCP CALLER
# ─────────────────────────────────────────

def call_gateway_tool(tool_name: str, arguments: dict) -> dict:
    """Send a JSON-RPC tools/call request to the AgentCore Gateway MCP endpoint"""
    cfg   = get_config()
    token = get_access_token()

    print(Fore.YELLOW + f"[GATEWAY] Calling tool  : {tool_name}")
    print(Fore.YELLOW + f"[GATEWAY] Arguments     : {arguments}")

    response = requests.post(
        cfg["mcp_endpoint"],
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id":      f"call-{tool_name}",
            "method":  "tools/call",
            "params":  {
                "name":      tool_name,
                "arguments": arguments
            }
        }
    )

    print(Fore.YELLOW + f"[GATEWAY] HTTP status   : {response.status_code}")

    if response.status_code != 200:
        print(Fore.RED + f"[GATEWAY] ✗ Request failed: {response.text[:200]}")
        response.raise_for_status()

    rpc_result = response.json()

    # MCP wraps the actual API response inside result.content[0].text as a JSON string
    # Structure: { "result": { "content": [ { "type": "text", "text": "{...}" } ] } }
    try:
        content = rpc_result.get("result", {}).get("content", [])
        if content and content[0].get("type") == "text":
            parsed = json.loads(content[0]["text"])
            print(Fore.GREEN + f"[GATEWAY] ✓ Response received and parsed")
            return parsed
    except (KeyError, json.JSONDecodeError):
        pass

    print(Fore.GREEN + f"[GATEWAY] ✓ Response received (raw)")
    return rpc_result


# ─────────────────────────────────────────
# STRANDS TOOLS
# Based on openapi_specs/openweathermap.json
# ─────────────────────────────────────────

@tool
def get_current_weather(city: str, units: str = "metric") -> dict:
    """Get current weather conditions for a city

    Args:
        city:  City name — e.g. 'Rome', 'Florence', 'Venice'
        units: 'metric' = °C  |  'imperial' = °F  |  'standard' = Kelvin

    Returns dict with:
        city        — city name confirmed by API
        temp        — current temperature
        feels_like  — feels like temperature
        humidity    — humidity percentage
        description — e.g. 'clear sky', 'light rain'
        condition   — e.g. 'Clear', 'Rain', 'Clouds'
    """
    cfg = get_config()
    logger.info(Fore.CYAN + f"TOOL → get_current_weather(city='{city}', units='{units}')")
    try:
        raw = call_gateway_tool(
            tool_name=f"{cfg['weather_target_name']}___getCurrentWeather",
            arguments={"q": city, "units": units}
        )
        # OpenAPI spec: raw.weather[0].description/main, raw.main.temp/feels_like/humidity, raw.name
        weather_list = raw.get("weather", [{}])
        main_data    = raw.get("main", {})
        result = {
            "city":        raw.get("name", city),
            "temp":        main_data.get("temp"),
            "feels_like":  main_data.get("feels_like"),
            "humidity":    main_data.get("humidity"),
            "description": weather_list[0].get("description", "") if weather_list else "",
            "condition":   weather_list[0].get("main", "") if weather_list else "",
            "units":       units
        }
        logger.info(Fore.GREEN + f"TOOL RESULT → {result}")
        return result
    except Exception as e:
        logger.error(Fore.RED + f"TOOL ERROR → {e}")
        return {"error": str(e)}


@tool
def get_weather_forecast(city: str, units: str = "metric") -> dict:
    """Get 5-day weather forecast (3-hour intervals) for a city

    Args:
        city:  City name — e.g. 'Rome', 'Florence', 'Venice'
        units: 'metric' = °C  |  'imperial' = °F  |  'standard' = Kelvin

    Returns dict with:
        city     — city name
        forecast — list of entries each with: datetime, temp, description
    """
    cfg = get_config()
    logger.info(Fore.CYAN + f"TOOL → get_weather_forecast(city='{city}', units='{units}')")
    try:
        raw = call_gateway_tool(
            tool_name=f"{cfg['weather_target_name']}___getWeatherForecast",
            arguments={"q": city, "units": units}
        )
        # OpenAPI spec: raw.list[].dt_txt, raw.list[].main.temp, raw.list[].weather[0].description
        entries = []
        for item in raw.get("list", []):
            weather_list = item.get("weather", [{}])
            entries.append({
                "datetime":    item.get("dt_txt", ""),
                "temp":        item.get("main", {}).get("temp"),
                "description": weather_list[0].get("description", "") if weather_list else ""
            })
        result = {"city": city, "units": units, "forecast": entries}
        logger.info(Fore.GREEN + f"TOOL RESULT → {len(entries)} forecast entries for {city}")
        return result
    except Exception as e:
        logger.error(Fore.RED + f"TOOL ERROR → {e}")
        return {"error": str(e)}


# ─────────────────────────────────────────
# AGENTCORE ENTRYPOINT (for deployment)
# ─────────────────────────────────────────

@app.entrypoint
def invoke(payload):
    if isinstance(payload, (bytes, str)):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    user_input = payload.get("prompt") or payload.get("input") or ""
    if not user_input:
        return {"message": "No prompt provided."}

    response = get_agent()(user_input)
    agent_response = response.message["content"][0]["text"]
    return {"message": agent_response}


# ─────────────────────────────────────────
# LOCAL INTERACTIVE LOOP (no curl needed)
# ─────────────────────────────────────────

if __name__ == "__main__":
    cfg = get_config()
    missing = [k for k in ["mcp_endpoint", "cognito_token_endpoint",
                            "cognito_client_id", "cognito_client_secret", "cognito_scope"]
               if not cfg.get(k)]
    if missing:
        print(Fore.RED + f"Missing config values: {', '.join(missing)}")
        print(Fore.YELLOW + "Fill in gateway_info.json or set as env vars and retry.")
        exit(1)

    print(Fore.CYAN + "=" * 55)
    print(Fore.CYAN + "  Travel Weather Agent — AgentCore Gateway")
    print(Fore.CYAN + f"  Gateway  : {cfg['mcp_endpoint'][:50]}...")
    print(Fore.CYAN + f"  Tool     : {cfg['weather_target_name']}___getCurrentWeather")
    print(Fore.CYAN + "  Type 'quit' to exit")
    print(Fore.CYAN + "=" * 55 + "\n")

    agent = get_agent()

    while True:
        user_input = input(Fore.GREEN + "You: " + Style.RESET_ALL).strip()

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print(Fore.YELLOW + "Goodbye!")
            break

        try:
            response = agent(user_input)
            agent_response = response.message["content"][0]["text"]
            print(Fore.BLUE + "\nAgent: " + Style.RESET_ALL + f"{agent_response}\n")
        except Exception as e:
            print(Fore.RED + f"\nError: {e}\n")
