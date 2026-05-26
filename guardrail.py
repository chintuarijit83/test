import os
import json
import logging
import boto3
import requests
from colorama import init, Fore, Style
from dotenv import load_dotenv
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

load_dotenv()
init(autoreset=True)

# Suppress SSL warnings caused by corporate network certificate inspection
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# ─────────────────────────────────────────
# CONFIG — fill these in once
# Works for both local testing and AgentCore deployment
# ─────────────────────────────────────────

REGION                 = "us-east-1"
MODEL_ID               = "us.anthropic.claude-sonnet-4-5-20251001-v1:0"
GUARDRAIL_ID           = os.environ.get("GUARDRAIL_ID", "")        # set after create_weather_guardrail()
GUARDRAIL_VERSION      = os.environ.get("GUARDRAIL_VERSION", "DRAFT")

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
# GUARDRAIL SETUP
# Run create_weather_guardrail() once to provision the guardrail.
# Copy the printed IDs into your .env as GUARDRAIL_ID and GUARDRAIL_VERSION.
# ─────────────────────────────────────────

def create_weather_guardrail() -> tuple:
    """Provision a Bedrock Guardrail tailored for the Weather Agent.

    Policies applied:
    - Denied topic : any non-weather request (travel tips, finance, history, etc.)
    - Content filter: all harmful categories at HIGH on both input and output
    - PII redaction : EMAIL, PHONE, NAME anonymised before reaching the model
    - Prompt attack : blocked at HIGH on input (no outputStrength needed)

    Run once, then add the printed IDs to your .env file.
    """
    client = boto3.client("bedrock", region_name=REGION)

    resp = client.create_guardrail(
        name="WeatherAgentGuardrail",
        description="Blocks off-topic requests and harmful content for the Weather Agent",
        topicPolicyConfig={
            "topicsConfig": [
                {
                    "name": "OffTopicRequests",
                    "definition": (
                        "Any request not related to current weather conditions, "
                        "forecasts, temperature, humidity, precipitation, or meteorology. "
                        "This includes travel advice, restaurant recommendations, "
                        "financial or investment advice, historical facts, flight bookings, "
                        "or any other non-weather topic."
                    ),
                    "examples": [
                        "What are the best restaurants in Paris?",
                        "How do I invest in stocks?",
                        "Give me travel tips for Tokyo",
                        "What is the history of London?",
                        "Book me a flight to New York",
                        "Tell me a joke",
                        "Write me a poem",
                    ],
                    "type": "DENY",
                }
            ]
        },
        contentPolicyConfig={
            "filtersConfig": [
                {"type": "SEXUAL",        "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {"type": "VIOLENCE",      "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {"type": "HATE",          "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {"type": "INSULTS",       "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {"type": "MISCONDUCT",    "inputStrength": "HIGH", "outputStrength": "HIGH"},
                # PROMPT_ATTACK only applies to input — outputStrength is not valid for this type
                {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"},
            ]
        },
        sensitiveInformationPolicyConfig={
            "piiEntitiesConfig": [
                {"type": "EMAIL",         "action": "ANONYMIZE"},
                {"type": "PHONE",         "action": "ANONYMIZE"},
                {"type": "NAME",          "action": "ANONYMIZE"},
            ]
        },
        blockedInputMessaging=(
            "I'm a Weather Assistant and can only answer questions about weather, "
            "temperature, and conditions for a specific city. Please ask a weather question!"
        ),
        blockedOutputsMessaging=(
            "I'm unable to provide that response. I'm a Weather Assistant — "
            "ask me about weather conditions for any city."
        ),
    )

    guardrail_id = resp["guardrailId"]
    print(Fore.GREEN + f"[GUARDRAIL] Created guardrail : {guardrail_id}")

    ver_resp = client.create_guardrail_version(
        guardrailIdentifier=guardrail_id,
        description="v1 — weather agent production guardrail",
    )
    version = ver_resp["version"]
    print(Fore.GREEN + f"[GUARDRAIL] Published version : {version}")
    print(Fore.YELLOW + "\nAdd these to your .env file:")
    print(Fore.YELLOW + f"  GUARDRAIL_ID={guardrail_id}")
    print(Fore.YELLOW + f"  GUARDRAIL_VERSION={version}")
    return guardrail_id, version


# ─────────────────────────────────────────
# GUARDRAIL CHECK
# Called on both user input (source="INPUT") and agent response (source="OUTPUT").
# Returns (allowed: bool, text_or_blocked_message: str).
# If GUARDRAIL_ID is not set the check is a no-op — everything passes through.
# ─────────────────────────────────────────

def check_guardrail(text: str, source: str) -> tuple:
    """Apply the configured guardrail to text.

    Args:
        text  : the content to evaluate
        source: "INPUT" (user prompt) or "OUTPUT" (agent response)

    Returns:
        (True,  original_text)     — content is safe, proceed normally
        (False, blocked_message)   — guardrail intervened, return this to the user
    """
    if not GUARDRAIL_ID:
        logger.warning(Fore.YELLOW + "[GUARDRAIL] GUARDRAIL_ID not set — skipping check")
        return True, text

    runtime = boto3.client("bedrock-runtime", region_name=REGION)
    resp = runtime.apply_guardrail(
        guardrailIdentifier=GUARDRAIL_ID,
        guardrailVersion=GUARDRAIL_VERSION,
        source=source,
        content=[{"text": {"text": text}}],
    )

    action = resp.get("action", "NONE")
    logger.info(Fore.CYAN + f"[GUARDRAIL] {source} check → action={action}")

    if action == "GUARDRAIL_INTERVENED":
        outputs = resp.get("outputs", [])
        blocked_msg = (
            outputs[0].get("text", "Request blocked by guardrail.")
            if outputs else "Request blocked by guardrail."
        )
        logger.warning(Fore.RED + f"[GUARDRAIL] {source} BLOCKED | text={text[:80]!r}")
        return False, blocked_msg

    return True, text


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
    print(Fore.CYAN + "[CONFIG] Guardrail ID  : " + (GUARDRAIL_ID or "NOT SET"))

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
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        verify=False  # disable SSL verification for corporate network
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

    print(Fore.YELLOW + "[AGENT] Creating Strands Agent with tools: get_current_weather")
    _agent = Agent(
        model=model,
        tools=[get_current_weather],
        system_prompt="""
You are a Weather Assistant. Your ONLY job is to provide weather information.

RULES:
1. Always call get_current_weather() for any weather question.
2. Report ONLY: temperature, humidity, conditions, and whether to bring an umbrella or jacket.
3. Do NOT give travel tips, attraction suggestions, or destination advice.
4. If no city is mentioned, ask which city they mean.

Keep responses short and weather-focused only.
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
        },
        verify=False  # disable SSL verification for corporate network
    )

    print(Fore.YELLOW + f"[GATEWAY] HTTP status   : {response.status_code}")

    if response.status_code != 200:
        print(Fore.RED + f"[GATEWAY] ✗ Request failed: {response.text[:200]}")
        response.raise_for_status()

    rpc_result = response.json()

    # Print full raw response for debugging
    print(Fore.YELLOW + "[GATEWAY] RAW RESPONSE:")
    print(json.dumps(rpc_result, indent=2))

    # MCP wraps the actual API response inside result.content[0].text as a JSON string
    # Structure: { "result": { "content": [ { "type": "text", "text": "{...}" } ] } }
    try:
        content = rpc_result.get("result", {}).get("content", [])
        if content and content[0].get("type") == "text":
            parsed = json.loads(content[0]["text"])
            print(Fore.GREEN + "[GATEWAY] PARSED RESPONSE:")
            print(json.dumps(parsed, indent=2))
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

    # --- GUARDRAIL: INPUT check ---
    allowed, result = check_guardrail(user_input, "INPUT")
    if not allowed:
        return {"message": result}

    response = get_agent()(user_input)
    agent_response = response.message["content"][0]["text"]

    # --- GUARDRAIL: OUTPUT check ---
    allowed, result = check_guardrail(agent_response, "OUTPUT")
    if not allowed:
        return {"message": result}

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
        print(Fore.YELLOW + "Fill in the constants at the top of this file and retry.")
        exit(1)

    # ── Uncomment once to provision the guardrail, then copy the IDs into .env ──
    # gid, gver = create_weather_guardrail()

    print(Fore.CYAN + "=" * 55)
    print(Fore.CYAN + "  Travel Weather Agent — AgentCore Gateway")
    print(Fore.CYAN + f"  Gateway  : {cfg['mcp_endpoint'][:50]}...")
    print(Fore.CYAN + f"  Tool     : {cfg['weather_target_name']}___getCurrentWeather")
    print(Fore.CYAN + f"  Guardrail: {GUARDRAIL_ID or 'NOT SET — see create_weather_guardrail()'}")
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
            # --- GUARDRAIL: INPUT check ---
            allowed, checked = check_guardrail(user_input, "INPUT")
            if not allowed:
                print(Fore.RED + f"\n[GUARDRAIL BLOCKED INPUT]  {checked}\n")
                continue

            response = agent(user_input)
            agent_response = response.message["content"][0]["text"]

            # --- GUARDRAIL: OUTPUT check ---
            allowed, checked = check_guardrail(agent_response, "OUTPUT")
            if not allowed:
                print(Fore.RED + f"\n[GUARDRAIL BLOCKED OUTPUT] {checked}\n")
                continue

            print(Fore.BLUE + "\nAgent: " + Style.RESET_ALL + f"{agent_response}\n")
        except Exception as e:
            print(Fore.RED + f"\nError: {e}\n")
