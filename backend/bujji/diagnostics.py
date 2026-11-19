"""Run locally with python -m bujji.diagnostics; never prints credentials or raw responses."""
import os
import re
from pathlib import Path
import httpx
from dotenv import dotenv_values, load_dotenv
from .providers import ProviderError, reply


def model_id(value):
    return value if re.fullmatch(r'gemini-[a-zA-Z0-9._-]{1,90}', value) else '(blank or invalid model ID)'


def error_summary(response):
    statuses = {'INVALID_ARGUMENT', 'FAILED_PRECONDITION', 'PERMISSION_DENIED', 'UNAUTHENTICATED', 'NOT_FOUND', 'RESOURCE_EXHAUSTED', 'UNAVAILABLE', 'INTERNAL'}
    reasons = {'API_KEY_INVALID', 'API_KEY_EXPIRED', 'API_KEY_SERVICE_BLOCKED', 'API_KEY_HTTP_REFERRER_BLOCKED', 'API_KEY_IP_ADDRESS_BLOCKED', 'SERVICE_DISABLED', 'BILLING_DISABLED', 'CONSUMER_INVALID', 'ACCESS_TOKEN_EXPIRED'}
    parts = [f'HTTP {response.status_code}']
    try:
        error = response.json().get('error', {})
        if isinstance(error, dict):
            status = error.get('status')
            if isinstance(status, str) and status in statuses:
                parts.append(status)
            for detail in error.get('details', []) if isinstance(error.get('details'), list) else []:
                reason = detail.get('reason') if isinstance(detail, dict) else None
                if isinstance(reason, str) and reason in reasons:
                    parts.append(reason)
    except (ValueError, AttributeError, TypeError):
        pass
    return ' / '.join(parts)


async def diagnose():
    env_path = Path.cwd() / '.env'
    local = dotenv_values(env_path)
    load_dotenv(env_path)
    print('Bujji Gemini diagnostic v1 (no keys or private conversations are printed)')
    print('Local .env found:', env_path.is_file())
    key = os.getenv('GEMINI_API_KEY', '').strip()
    model = os.getenv('GEMINI_MODEL', '').strip()
    print('Gemini key present:', bool(key))
    print('Effective model:', model_id(model))
    print('Daily route:', os.getenv('BUJJI_DAILY_PROVIDER') if os.getenv('BUJJI_DAILY_PROVIDER') in {'gemini','groq','ollama'} else '(unset/invalid)')
    for name in ('GEMINI_API_KEY','GEMINI_MODEL','BUJJI_DAILY_PROVIDER'):
        if name in local and local[name] != os.getenv(name):
            print(f'WARNING: terminal environment overrides {name} from .env. Open a new terminal after saving the file.')
    if not key or not model:
        print('Fill GEMINI_API_KEY and GEMINI_MODEL in .env first.')
        return
    try:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.get('https://generativelanguage.googleapis.com/v1beta/models', headers={'x-goog-api-key':key})
            print('Model-list request:', error_summary(response))
            if response.is_success:
                data = response.json()
                names = [item.get('name','').removeprefix('models/') for item in data.get('models',[]) if isinstance(item,dict) and 'generateContent' in item.get('supportedGenerationMethods',[])]
                print('Configured model listed:', model in names)
                print('Listed Flash text model IDs (availability does not guarantee free quota):')
                for name in names:
                    if 'flash' in name.lower() and 'tts' not in name.lower() and model_id(name) == name:
                        print(' -', name)
                if data.get('nextPageToken'):
                    print('Only the first model-list page is shown; absence here is not conclusive.')
        print('Testing one short greeting through the actual Bujji Gemini adapter...')
        result = await reply([{'role':'user','content':'Reply with only: Hello'}], [], requested='gemini', focus=True)
        print('Generation succeeded:', bool(result['text']))
    except ProviderError as exc:
        print('Generation result:', str(exc))
    except httpx.TimeoutException:
        print('Network request timed out.')
    except httpx.ConnectError:
        print('Secure connection failed. Check firewall, VPN, proxy, and internet access.')
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        print('The diagnostic received a network error or unexpected response. No raw data was printed.')


if __name__ == '__main__':
    import asyncio
    asyncio.run(diagnose())
