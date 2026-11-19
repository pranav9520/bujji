"""ASCII-framed helper messages, isolated from native-library startup chatter."""
import json

RESULT=b'BUJJI_COMPUTER_RESULT:'
DIAGNOSTIC='BUJJI_COMPUTER_DIAG:'

class WireError(ValueError):pass

def encode(result):
    return b'\n'+RESULT+json.dumps({'version':1,'result':result},ensure_ascii=True,separators=(',',':')).encode('ascii')+b'\n'

def decode(raw):
    if len(raw)>250000:raise WireError('oversized_response')
    records=[line[len(RESULT):] for line in raw.splitlines() if line.startswith(RESULT)]
    try:
        if records:
            body=json.loads(records[-1])
            if not isinstance(body,dict) or body.get('version')!=1:raise WireError('helper_version')
            result=body.get('result')
        else:result=json.loads(raw)  # Transitional compatibility with an older worker.
    except (ValueError,UnicodeError) as exc:
        if isinstance(exc,WireError):raise
        raise WireError('invalid_json') from None
    if not isinstance(result,dict):raise WireError('invalid_result')
    return result

def diagnostic(stream,phase,error_type=None):
    item={'phase':phase}
    if error_type:item['error_type']=error_type
    stream.write(DIAGNOSTIC+json.dumps(item,ensure_ascii=True)+'\n');stream.flush()

def last_diagnostic(raw):
    allowed={'dispatch','request','initializing','windows','catalog','screen_text','action','complete','error'}
    result={}
    for line in raw.decode('ascii',errors='ignore').splitlines():
        if not line.startswith(DIAGNOSTIC):continue
        try:
            value=json.loads(line[len(DIAGNOSTIC):])
            if value.get('phase') in allowed:
                previous=result.get('phase')
                result={'phase':value['phase'],**({'last_phase':previous} if value['phase']=='error' and previous and previous!='error' else {})}
                error=value.get('error_type','')
                if isinstance(error,str) and error.isidentifier() and len(error)<80:result['error_type']=error
        except (ValueError,TypeError,AttributeError):continue
    return result
